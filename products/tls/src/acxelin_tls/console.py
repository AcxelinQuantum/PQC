"""The Acxelin QGuard console: the certificate authority (create, issue, revoke, refresh the CRL), edges (status, connection test) and health.

Runs on acxelin-core's console mechanism; this module is only the product's pages, routes and state. A CA passphrase is held in
memory for the life of the console and is never written anywhere, so a restart locks an encrypted CA again.
"""
import dataclasses
import datetime as dt
import functools
import hashlib
import io
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from acxelin_core import console as core
from acxelin_core import shell, tls
from acxelin_core.files import append, write
from acxelin_core.http import explain, hostport
from acxelin_core.pki import CA, CAError, encrypted, est
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID

from . import __version__, acme, checks, policies, shadow
from .checks import browser_setup, expiry
from .connection import KEYS, PQ_GROUPS, key_name, verdict, why_failed
from .edge import Route, load_config, render_config

NAME = re.compile(r"[A-Za-z0-9*._-]{1,253}")
HOST = re.compile(r"(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*")
MAX_EDGES = 50
METRICS = "127.0.0.1:9100"  # where the QGuard service reports; the console reads it to show what each service sees
NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))
KINDS = {"website": "Public website", "app": "Internal app or API", "partner": "Partner API", "tcp": "Database or other service"}
REASONS = {shadow.slug(t): t for p in ("strict", "cnsa2") for t in shadow.reasons(p, {"groups": [], "sigalgs": [], "suites": []})}


def _kind(r):
    """Which kind of service a route is, from its settings (the settings file has no field for it)."""
    if r.require_client_cert:
        return "partner"
    if r.policy == "transition" or r.fallback_cert:
        return "website"
    return "app" if r.forwarded_headers else "tcp"


def task(fn):
    """Routes raise ValueError for a refused request; CA, TLS and file errors become the same, in words."""
    @functools.wraps(fn)
    def run(self, body):
        try:
            return fn(self, body)
        except (CAError, tls.TLSError, OSError) as e:
            raise ValueError(explain(e)) from None
    return run


def _text(body, key, what, limit=253):
    v = body.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"Enter {what}")
    if len(v.strip()) > limit:
        raise ValueError(f"{what[0].upper() + what[1:]} is too long")
    return v.strip()


class TLSConsole:
    def __init__(self, home, ca_dir=None, settings=None):
        self.home = Path(home)
        self.ca_dir = Path(ca_dir) if ca_dir else self.home / "ca"
        self.settings = Path(settings) if settings else self.home / "edge.toml"
        self.guard = None  # QGuard started from this console (until it runs as a system service)
        self.passphrase = None
        self.lock = threading.Lock()
        given = os.environ.pop("ACXELIN_TLS_CA_PASSPHRASE", None)  # read once and removed: the browser this opens inherits the environment
        if given and self._exists() and encrypted(self.ca_dir / "ca.key"):
            try:
                CA(self.ca_dir, given.encode()).signer
                self.passphrase = given.encode()
            except CAError:
                pass

    # --- audit

    def audit(self, action, detail):
        line = json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "action": action, **detail})
        with self.lock:
            self.home.mkdir(parents=True, exist_ok=True)
            append(self.home / "audit.jsonl", line)

    def activity(self, n=12):
        try:
            with open(self.home / "audit.jsonl", encoding="utf-8", errors="replace") as f:
                lines = deque(f, n)
        except FileNotFoundError:
            return []
        out = []
        for line in reversed(lines):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
        return out

    # --- the certificate authority

    def _exists(self):
        return (self.ca_dir / "ca.crt").exists()

    def _ca(self):
        if not self._exists():
            raise ValueError("There is no certificate authority yet: create one first")
        if encrypted(self.ca_dir / "ca.key") and not self.passphrase:
            raise ValueError("The CA key is locked: unlock it with its passphrase")
        return CA(self.ca_dir, self.passphrase)

    def _crl(self):
        f = self.ca_dir / "crl.pem"
        if not f.exists():
            return None
        crl = x509.load_pem_x509_crl(f.read_bytes())
        left = (crl.next_update_utc - dt.datetime.now(dt.timezone.utc)).total_seconds() / 86400
        return {"next_update": crl.next_update_utc.isoformat(), "days_left": round(left, 1)}

    @task
    def status(self, body):
        if not self._exists():
            return 200, {"configured": False}
        ca = CA(self.ca_dir)
        rows = ca.records()
        soon = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30)).isoformat()
        enc = encrypted(self.ca_dir / "ca.key")
        return 200, {"configured": True, "home": str(self.home), "name": next((str(a.value) for a in ca.cert.subject if a.oid == NameOID.COMMON_NAME), ""), "algorithm": ca.algorithm,
                     "encrypted": enc, "unlocked": bool(self.passphrase) or not enc, "crl": self._crl(),
                     "counts": {"valid": sum(r.status == "valid" for r in rows), "revoked": sum(r.status == "revoked" for r in rows),
                                "expiring": sum(r.status == "valid" and r.not_after < soon for r in rows)}, "activity": self.activity()}

    @task
    def create(self, body):
        name = _text(body, "name", "a name for the certificate authority", 120)
        if self._exists():
            raise ValueError("A certificate authority already exists here")
        pw = body.get("passphrase")
        if pw is not None and not isinstance(pw, str):
            raise ValueError("The passphrase must be text")
        key = pw.encode() if pw else None
        CA.init(self.ca_dir, name, passphrase=key)
        ca = CA(self.ca_dir, key)
        ca.crl(7)
        with self.lock:
            self.passphrase = key
        return 200, {"name": name, "algorithm": ca.algorithm}

    @task
    def unlock(self, body):
        pw = body.get("passphrase")
        if not isinstance(pw, str) or not pw:
            raise ValueError("Enter the CA passphrase")
        if not self._exists():
            raise ValueError("There is no certificate authority yet: create one first")
        CA(self.ca_dir, pw.encode()).signer  # raises "wrong passphrase" without echoing it
        with self.lock:
            self.passphrase = pw.encode()
        return 200, {"unlocked": True}

    # --- certificates

    @task
    def certificates(self, body):
        if not self._exists():
            return 200, {"certificates": []}
        records = CA(self.ca_dir).records()
        current = {r.path: r.serial for r in records if r.path}
        rows = []
        for r in sorted(records, key=lambda r: r.not_after):
            row = {k: v for k, v in vars(r).items() if k != "path"}
            rows.append(row | {"has_files": bool(r.path) and current.get(r.path) == r.serial, "renewed": bool(r.path) and current[r.path] != r.serial})
        return 200, {"certificates": rows}

    @task
    def issue(self, body):
        ca = self._ca()
        kind = body.get("kind")
        if kind not in ("server", "client"):
            raise ValueError("Choose server or client")
        cn = _text(body, "common_name", "the name the certificate is for")
        names = body.get("names") or []
        names = [n.strip() for n in (re.split(r"[,\n]", names) if isinstance(names, str) else names) if isinstance(n, str) and n.strip()]
        for n in [cn, *names]:
            if not NAME.fullmatch(n) and not _is_ip(n):
                raise ValueError(f"{n!r} is not a valid name: use letters, digits, dots, dashes and underscores")
        days = body.get("days", 397)
        if type(days) is not int or not 1 <= days <= 3650:
            raise ValueError("Days must be a whole number from 1 to 3650")
        folder = Path("issued") / f"{re.sub(r'[^A-Za-z0-9.-]', '_', cn)}-{secrets.token_hex(3)}"
        _, rec = ca.issue(cn, kind, names, days, out=self.home / folder)
        self.audit("issue", {"serial": rec.serial, "common_name": cn, "kind": kind})
        where = self.home / folder
        return 200, {"serial": rec.serial, "common_name": cn, "kind": kind, "folder": folder.as_posix(), "files": ["chain.pem", "key.pem"],
                     "chain": str(where / "chain.pem"), "key": str(where / "key.pem")}

    @task
    def revoke(self, body):
        ca = self._ca()
        serial = _text(body, "serial", "the serial from the certificate list", 80)
        reason = body.get("reason") or "unspecified"
        if not isinstance(reason, str):
            raise ValueError("The reason must be text")
        try:
            ca.revoke(serial, reason)
            r = ca.find(serial)
        except CAError as e:
            raise ValueError(str(e) if "serial" in str(e).lower() else f"serial {serial}: {e}") from None
        self.audit("revoke", {"serial": r.serial, "common_name": r.common_name, "reason": reason})
        return 200, {"revoked": r.serial, "crl": self._crl()}

    @staticmethod
    def _files(r):
        """The serial of the certificate now in the record's folder, and the folder."""
        folder = Path(r.path)
        try:
            cert = x509.load_pem_x509_certificate((folder / "cert.pem").read_bytes())
        except (OSError, ValueError):
            raise ValueError(f"the files for {r.common_name} are no longer in {folder}") from None
        return format(cert.serial_number, "x"), folder

    def _record(self, ca, body):
        try:
            return ca.find(_text(body, "serial", "the serial from the certificate list", 80))
        except CAError as e:
            raise ValueError(str(e)) from None

    @task
    def renew(self, body):
        ca = self._ca()
        r = self._record(ca, body)
        if not r.path:
            raise ValueError("this certificate was signed from a request (CSR, EST or ACME); its key is with whoever asked for it, so renew it there")
        current = self._files(r)[0]
        if current != r.serial:
            raise ValueError(f"{r.common_name}'s folder already holds a newer certificate ({current}); renew that one")
        if encrypted(Path(r.path) / "key.pem"):
            raise ValueError(f"{r.common_name}'s key is encrypted with a passphrase the console does not hold: renew it with "
                             "`acxelin-qguard ca renew --key-passphrase-env`, so the new key is encrypted too")
        _, new = ca.renew(r.serial, out=r.path)
        self.audit("renew", {"serial": r.serial, "new_serial": new.serial, "common_name": r.common_name})
        return 200, {"renewed": r.serial, "serial": new.serial, "not_after": new.not_after}

    @task
    def maintain(self, body):
        renewed, skipped = self._ca().maintain()
        self.audit("maintain", {"renewed": [r.serial for r in renewed]})
        return 200, {"renewed": [r.common_name for r in renewed], "skipped": [r.common_name for r in skipped], "crl": self._crl()}

    @task
    def download(self, body):
        """A zip with the certificate, its chain and the CA certificate; the private key only when asked for with a JSON true,
        never for a revoked certificate or an encrypted key, and every download is audited."""
        ca = CA(self.ca_dir) if self._exists() else self._ca()
        r = self._record(ca, body)
        with_key = body.get("key") is True
        fmt = body.get("format") or "zip"
        if fmt not in ("zip", "pem"):
            raise ValueError("The format must be zip (certificate, chain and CA in separate files) or pem (one file: the full chain, "
                             "then the key if asked for). PFX is not offered: no tool can write an ML-DSA key into one yet")
        if not r.path:
            raise ValueError("this certificate was signed from a request (CSR, EST or ACME); the console has no files for it")
        current, folder = self._files(r)
        if current != r.serial:
            raise ValueError(f"this certificate was renewed; its folder now holds {current}, download that one")
        if with_key and r.status == "revoked":
            raise ValueError("this certificate is revoked; its key is not handed out")
        if with_key and encrypted(folder / "key.pem"):
            raise ValueError("this key is encrypted with a passphrase; copy it from the CA machine")
        if fmt == "pem":
            data = (folder / "chain.pem").read_bytes() + ((folder / "key.pem").read_bytes() if with_key else b"")
            self.audit("download", {"serial": r.serial, "common_name": r.common_name, "key": with_key, "format": "pem"})
            return 200, core.Download(f"{r.common_name}-{r.serial[:8]}-fullchain{'-and-key' if with_key else ''}.pem", data, "application/x-pem-file")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for name in ("cert.pem", "chain.pem") + (("key.pem",) if with_key else ()):
                z.writestr(name, (folder / name).read_bytes())
            z.writestr("ca.crt", ca.anchor.read_bytes())
        self.audit("download", {"serial": r.serial, "common_name": r.common_name, "key": with_key})
        return 200, core.Download(f"{r.common_name}-{r.serial[:8]}.zip", buf.getvalue(), "application/zip")

    @task
    def refresh(self, body):
        self._ca().crl(7)
        return 200, self._crl()

    # --- edges

    def _edges(self):
        f = self.home / "edges.json"
        return json.loads(f.read_text()) if f.exists() else []

    @task
    def add_edge(self, body):
        url = _text(body, "url", "the edge's metrics address, such as http://127.0.0.1:9100", 300).rstrip("/")
        p = urllib.parse.urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            raise ValueError("Enter an http or https address, such as http://127.0.0.1:9100")
        with self.lock:
            edges = self._edges()
            if url not in edges:
                if len(edges) >= MAX_EDGES:
                    raise ValueError(f"At most {MAX_EDGES} edges")
                write(self.home / "edges.json", json.dumps(edges + [url]).encode())
        return 200, {"url": url}

    @task
    def remove_edge(self, body):
        url = _text(body, "url", "the edge to remove", 300)
        with self.lock:
            write(self.home / "edges.json", json.dumps([u for u in self._edges() if u != url]).encode())
        return 200, {"removed": url}

    @staticmethod
    def _fetch(url):
        """One edge's /status as routes with their quantum-safe handshake counts, or one error in words."""
        try:
            with NO_PROXY.open(url + "/status", timeout=3) as r:
                status = json.loads(r.read(1 << 20))
            if not isinstance(status, dict) or not all(isinstance(v, dict) for v in status.values()):
                raise ValueError("this address does not answer like an edge's /status")
            routes = []
            for name, v in status.items():
                groups = v.get("groups") if isinstance(v.get("groups"), dict) else {}
                routes.append({"name": name, **v, "quantum_safe": sum(c for g, c in groups.items() if g in PQ_GROUPS and isinstance(c, int))})
            return {"url": url, "routes": routes, "error": None}
        except (OSError, ValueError) as e:
            why = explain(e) if isinstance(e, OSError) else str(e)
            return {"url": url, "routes": [], "error": f"cannot read {url}/status: {why}; start the edge with --metrics HOST:PORT"}

    @task
    def edges(self, body):
        urls = self._edges()
        with ThreadPoolExecutor(max_workers=8) as pool:
            return 200, {"edges": list(pool.map(self._fetch, urls))}

    @task
    def test_edge(self, body):
        """Connect to host:port as a client of this CA: what was negotiated, or why it failed and what the server offers instead."""
        target = _text(body, "target", "the edge to test, as host:port", 300)
        host, port = hostport(target, "")
        if not host:
            raise ValueError("Enter host:port, such as localhost:8443")
        chosen = body.get("policy") or "strict"
        if chosen not in policies.POLICIES:
            raise ValueError("Choose strict, transition or cnsa2")
        name = body.get("server_name") or None
        if name is not None and not isinstance(name, str):
            raise ValueError("The certificate name must be text")
        if not self._exists():
            raise ValueError("There is no certificate authority yet: create one first; the test trusts its certificate")
        ca = CA(self.ca_dir)
        cert = key = None
        serial = body.get("client")
        r = None
        if serial:
            r = self._record(ca, {"serial": serial})
            if r.kind == "server":
                raise ValueError(f"{r.common_name} is a server certificate; choose a client certificate")
            if not r.path:
                raise ValueError("the console has no key for that certificate")
            folder = self._files(r)[1]
            if encrypted(folder / "key.pem"):
                raise ValueError("that client's key is encrypted; test it from the command line")
            cert, key = str(folder / "chain.pem"), str(folder / "key.pem")
        started = time.monotonic()
        out = {"target": target, "policy": chosen, "client": r.serial if r else None, "client_status": r.status if r else None}
        ctx = tls.client_context(policies.policy(chosen), ca.anchor, cert, key)
        try:
            with tls.connect(host, port, ctx, name, 5.0) as conn:
                out |= {"ok": True, **self._named(conn.info()), "ms": round((time.monotonic() - started) * 1000)}
                refused = self._accepted(conn)
                if refused:
                    out |= {"ok": False, "refused_after_handshake": True, "error": refused}
        except (tls.TLSError, OSError) as e:
            out |= {"ok": False, "error": explain(e) if isinstance(e, OSError) else str(e), "offers": self._probe(host, port, name),
                    "ms": round((time.monotonic() - started) * 1000)}
        finally:
            ctx.close()
        out["quantum_safe"] = out.get("group") in PQ_GROUPS
        self.audit("test", {"target": target, "ok": out["ok"], "client": out["client"]})
        return 200, out

    @staticmethod
    def _accepted(conn):
        """In TLS 1.3 the server checks a client certificate after the client's side of the handshake is done, so a refusal
        arrives on the first read: an alert, or the connection closing. Silence means the server is waiting for a request.
        An edge only dials its service after the handshake, and Windows takes about two seconds to report a refused connect."""
        try:
            data = conn.recv(timeout=3.0)
        except tls.TLSError as e:
            return None if "timed out" in str(e) else str(e)
        if data == b"":
            return ("the server closed the connection right after the handshake: either it refused the client certificate "
                    "(missing, untrusted or revoked), or the service behind it is down")
        return None

    @staticmethod
    def _named(info):
        return info | {"peer_key": KEYS.get(info.get("peer_key"), info.get("peer_key"))}

    @staticmethod
    def _probe(host, port, name):
        """What the server negotiates with an unverified, anything-goes client: tells 'classical only' from 'wrong CA'."""
        ctx = tls.client_context(policies.policy("transition"), verify=False)
        try:
            with tls.connect(host, port, ctx, name, 3.0) as c:
                return TLSConsole._named(c.info())
        except (tls.TLSError, OSError):
            return None
        finally:
            ctx.close()

    # --- protected services: the settings file the QGuard service reads (the console writes it; the service applies it live)

    def _settings(self):
        return load_config(self.settings) if self.settings.exists() else ([], None)

    def _save_settings(self, routes, metrics):
        if not routes:
            self.settings.unlink(missing_ok=True)
            return
        text = render_config(routes, metrics)
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        trial = self.settings.with_name(self.settings.name + ".check")
        trial.write_text(text, encoding="utf-8")
        try:
            load_config(trial)  # what the service would refuse is never written
        finally:
            trial.unlink(missing_ok=True)
        write(self.settings, text.encode())

    @staticmethod
    def _live(metrics):
        """The running QGuard service's /status, or None when nothing answers at the settings' metrics address."""
        if not metrics:
            return None
        host, port = hostport(metrics, "127.0.0.1")
        host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
        try:
            with NO_PROXY.open(f"http://{'[' + host + ']' if ':' in host else host}:{port}/status", timeout=1) as r:  # Windows takes ~2 s to report a refused loopback port
                data = json.loads(r.read(1 << 20))
            return data if isinstance(data, dict) else None
        except (OSError, ValueError):
            return None

    def _row(self, r, live):
        problems = []
        if r.mode == "terminate":
            for what, path in (("certificate", r.cert), ("public certificate (fallback_cert)", r.fallback_cert)):
                if path and not Path(path).exists():
                    problems.append(f"the {what} file {path} is missing: the service cannot start")
                elif path and (found := expiry(path, what)):
                    problems.append(found[1])
            if (found := browser_setup(r.policy, r.fallback_cert, r.shadow)) and found[0] == "warn":
                problems.append("Visitors' browsers will show \"Your connection is not private\": browsers cannot check quantum-safe "
                                "certificates yet. Add the site's ordinary public certificate (such as Let's Encrypt) with Edit; "
                                "the connection stays quantum-safe.")
        s, status = live.get(r.name), None
        if isinstance(s, dict):
            n = lambda k: s[k] if isinstance(s.get(k), int) else 0
            groups = s.get("groups") if isinstance(s.get("groups"), dict) else {}
            status = {"active": n("active"), "handshakes": n("handshakes"), "refused": n("handshake_failed"),
                      "quantum_safe": sum(c for g, c in groups.items() if g in PQ_GROUPS and isinstance(c, int)),
                      "distrusts": n("client_distrusts_certificate"), "would_refuse": n("shadow_would_refuse"),
                      "bad_requests": n("forwarded_refused"), "upstream_failed": n("upstream_failed"),
                      "reasons": {REASONS.get(k[20:], k[20:].replace("_", " ")): v for k, v in s.items()
                                  if k.startswith("shadow_would_refuse_") and isinstance(v, int)}}
        listen = hostport(r.listen, "127.0.0.1" if r.mode == "originate" else "0.0.0.0")
        return {"name": r.name, "kind": _kind(r), "label": KINDS[_kind(r)], "managed": r.mode == "terminate" and len(r.sni) == 1,
                "host": r.sni[0] if r.sni else "", "port": listen[1], "listen": r.listen, "target": r.target, "mode": r.mode,
                "policy": r.policy, "shadow": r.shadow, "forwarded": r.forwarded_headers, "public_cert": r.fallback_cert,
                "public_key": r.fallback_key, "cert": r.cert, "problems": problems, "status": status}

    @task
    def services(self, body):
        routes, metrics = self._settings()
        live = self._live(metrics)
        return 200, {"settings": str(self.settings), "metrics": metrics, "running": live is not None, "started_here": self._guard_alive(),
                     "log": str(self.home / "qguard-service.log"), "services": [self._row(r, live or {}) for r in routes]}

    @task
    def save_service(self, body):
        kind = body.get("kind")
        if kind not in KINDS:
            raise ValueError("Choose what kind of service this is: a public website, an internal app or API, a partner API, or a database or other service")
        host = _text(body, "host", "the name people use to reach the service, such as shop.example.com").lower()
        if not HOST.fullmatch(host):
            raise ValueError(f"{host!r} is not a valid host name: use letters, digits, dots and dashes, such as shop.example.com")
        port = body.get("port", 443)
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("The port must be a whole number from 1 to 65535 (443 for a website)")
        target = _text(body, "target", "where the service runs now, as host:port, such as 127.0.0.1:8080", 300)
        try:
            th, tp = hostport(target, "")
        except ValueError:
            th = tp = None
        if not th or not tp:
            raise ValueError("Where the service runs now must be host:port, such as 127.0.0.1:8080")
        watch = body.get("watch", False)
        if not isinstance(watch, bool):
            raise ValueError("watch must be true or false")
        if watch and kind == "website":
            raise ValueError("A public website cannot start by watching: browsers need \"Quantum-safe, browsers welcome\" and a public certificate")
        pub, pubkey = (body.get("public_cert") or "", body.get("public_key") or "")
        if not (isinstance(pub, str) and isinstance(pubkey, str)) or bool(pub) != bool(pubkey):
            raise ValueError("Give both the public certificate (full chain) and its key, or neither")
        if pub and kind != "website":
            raise ValueError("A public certificate is only for a public website: other services use your own certificate authority")
        for p in (pub, pubkey):
            if p and not Path(p).is_file():
                raise ValueError(f"{p} does not exist on this computer: give the path of the file, such as /etc/letsencrypt/live/{host}/fullchain.pem")
        original = body.get("original")
        if original is not None and not isinstance(original, str):
            raise ValueError("original must be the name of the service being edited")
        routes, metrics = self._settings()
        old = next((r for r in routes if r.name == original), None)
        if original and not old:
            raise ValueError(f"There is no service named {original}")
        for r in routes:
            if r is not old and r.mode == "terminate" and hostport(r.listen)[1] == port and host in (n.lower() for n in r.sni):
                raise ValueError(f"{r.name} already protects {host} on port {port}: edit that one instead")
            if r is not old and r.name == host:
                raise ValueError(f"A service named {host} already exists: edit that one instead")
        if old and old.sni == [host] and old.cert and Path(old.cert).exists():
            cert, key = old.cert, old.key
        else:
            ca = self._ca()
            folder = self.home / "issued" / f"{re.sub(r'[^a-z0-9.-]', '_', host)}-{secrets.token_hex(3)}"
            _, rec = ca.issue(host, "server", [host], 397, out=folder)
            self.audit("issue", {"serial": rec.serial, "common_name": host, "kind": "server"})
            cert, key = str(folder / "chain.pem"), str(folder / "key.pem")
        policy = "transition" if kind == "website" else old.policy if old and old.policy == "cnsa2" else "strict"
        partner = kind == "partner"
        changes = dict(name=host, mode="terminate", listen=f"0.0.0.0:{port}", target=target, policy=policy, cert=cert, key=key, sni=[host],
                       forwarded_headers=kind != "tcp", shadow=watch and policy != "transition", fallback_cert=pub, fallback_key=pubkey,
                       require_client_cert=partner, ca=str(self.ca_dir / "ca.crt") if partner else "",
                       crl=str(self.ca_dir / "crl.pem") if partner else "", crl_url=old.crl_url if old and partner else "")
        new = dataclasses.replace(old, **changes) if old else Route(**changes)
        new.validate()
        self._save_settings([new if r is old else r for r in routes] if old else routes + [new], metrics or METRICS)
        self.audit("service", {"name": new.name, "kind": kind, "change": "edited" if old else "added"})
        return self.services({})

    def _service(self, body):
        routes, metrics = self._settings()
        name = _text(body, "name", "the service", 253)
        r = next((r for r in routes if r.name == name), None)
        if not r:
            raise ValueError(f"There is no service named {name}")
        return routes, metrics, r

    def _replace(self, routes, metrics, old, new, action):
        self._save_settings([new if r is old else r for r in routes], metrics)
        self.audit("service", {"name": old.name, "change": action})
        return self.services({})

    @task
    def enforce(self, body):
        routes, metrics, r = self._service(body)
        if not r.shadow:
            raise ValueError(f"{r.name} is not in watch mode: it already refuses what its policy does not allow")
        keep = r.policy == "transition"  # a public certificate only works under transition; under strict the service would not start
        return self._replace(routes, metrics, r, dataclasses.replace(r, shadow=False, fallback_cert=r.fallback_cert if keep else "",
                                                                     fallback_key=r.fallback_key if keep else ""), "enforced")

    @task
    def watch(self, body):
        routes, metrics, r = self._service(body)
        if r.policy == "transition" or r.mode != "terminate":
            raise ValueError(f"{r.name} is a public website (or a tunnel): watch mode is for services that refuse classical clients")
        return self._replace(routes, metrics, r, dataclasses.replace(r, shadow=True), "watching")

    @task
    def remove_service(self, body):
        routes, metrics, r = self._service(body)
        self._save_settings([x for x in routes if x is not r], metrics)
        self.audit("service", {"name": r.name, "change": "removed"})
        return self.services({})

    # --- running QGuard on this computer (until it is set up as a system service)

    def _guard_alive(self):
        return self.guard is not None and self.guard.poll() is None

    @task
    def start_guard(self, body):
        routes, metrics = self._settings()
        if not routes:
            raise ValueError("Protect a service first: QGuard has nothing to run yet")
        if self._live(metrics) is not None:
            raise ValueError("QGuard is already running (as a service, or from another console or terminal)")
        log_file = self.home / "qguard-service.log"
        with open(log_file, "ab") as log:
            flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
            self.guard = subprocess.Popen([sys.executable, "-m", "acxelin_tls", "edge", "--config", str(self.settings)], cwd=self.home,
                                          stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
                                          start_new_session=os.name != "nt")
        deadline = time.monotonic() + 20
        while self._live(metrics) is None:
            if self.guard.poll() is not None or time.monotonic() > deadline:
                why = next((line for line in reversed(log_file.read_text(encoding="utf-8", errors="replace").splitlines())
                            if line.startswith("error:") or " ERROR " in line), "")
                self._stop()
                raise ValueError(f"QGuard did not start{': ' + why if why else ''} (its log: {log_file})")
            time.sleep(0.25)
        self.audit("guard", {"change": "started here"})
        return self.services({})

    def _stop(self):
        if self.guard is not None and self.guard.poll() is None:
            self.guard.terminate()
            try:
                self.guard.wait(10)
            except subprocess.TimeoutExpired:
                self.guard.kill()
        self.guard = None

    @task
    def stop_guard(self, body):
        if not self._guard_alive():
            raise ValueError("QGuard was not started from this console: stop it where it runs (its system service, or the terminal it runs in)")
        self._stop()
        self.audit("guard", {"change": "stopped here"})
        return self.services({})

    # --- check any connection: trusting the public authorities this computer trusts, or QCertificate

    @task
    def check(self, body):
        target = _text(body, "target", "the address to check, such as www.example.com:443", 300)
        if not re.search(r":\d+$", target):
            target += ":443"
        host, port = hostport(target, "")
        if not host:
            raise ValueError("Enter an address such as www.example.com or shop.example.com:8443")
        trust = body.get("trust") or "public"
        if trust not in ("public", "qcertificate"):
            raise ValueError("Choose whom to trust: public authorities (like a browser) or your QCertificate authority")
        name = body.get("server_name") or None
        if name is not None and not isinstance(name, str):
            raise ValueError("The certificate name must be text")
        cert = key = r = None
        if body.get("client"):
            if not self._exists():
                raise ValueError("There is no certificate authority yet: create one first")
            r = self._record(CA(self.ca_dir), {"serial": body["client"]})
            if r.kind == "server":
                raise ValueError(f"{r.common_name} is a certificate for a service; choose one for a person, device or partner")
            if not r.path:
                raise ValueError("the console has no key for that certificate")
            folder = self._files(r)[1]
            if encrypted(folder / "key.pem"):
                raise ValueError("that certificate's key is encrypted; check it from the command line with acxelin-qguard connect")
            cert, key = str(folder / "chain.pem"), str(folder / "key.pem")
        with tempfile.TemporaryDirectory() as tmp:
            if trust == "public":
                anchor = tls.public_roots(Path(tmp) / "public-roots.pem")
            elif self._exists():
                anchor = CA(self.ca_dir).anchor
            else:
                raise ValueError("There is no certificate authority yet: create one first, or check against public authorities")
            ctx = tls.client_context(policies.policy("transition"), anchor, cert, key)
        out = {"target": target, "trust": trust, "client": r.serial if r else None, "client_status": r.status if r else None}
        started = time.monotonic()
        try:
            with tls.connect(host, port, ctx, name, 5.0) as conn:
                info = conn.info()
                out |= {"ok": True, **info, "peer_key": key_name(info.get("peer_key")), "verdict": verdict(info)}
                if refused := self._accepted(conn):
                    out |= {"ok": False, "refused_after_handshake": True, "error": refused}
        except (tls.TLSError, OSError) as e:
            out |= {"ok": False, "error": explain(e) if isinstance(e, OSError) else why_failed(host, port, name, "transition", e, trust == "public")}
        finally:
            ctx.close()
        out["ms"] = round((time.monotonic() - started) * 1000)
        out["quantum_safe"] = out.get("group") in PQ_GROUPS
        self.audit("test", {"target": target, "ok": out["ok"], "client": out["client"]})
        return 200, out

    # --- enrollment: one-time EST tokens and ACME account keys, each shown once

    @task
    def enrollment(self, body):
        if not self._exists():
            return 200, {"tokens": [], "eab": []}
        t = dt.datetime.now(dt.timezone.utc).isoformat()
        tokens = [x | {"state": "used" if x.get("used") else "expired" if x["expires"] < t else "unused"} for x in est.list_tokens(self.ca_dir)]
        eab = [{"kid": k, "note": v.get("note", ""), "created": v.get("created"), "used": bool(v.get("used"))} for k, v in acme.eab_keys(self.ca_dir).items()]
        return 200, {"tokens": tokens[::-1], "eab": eab[::-1]}

    @task
    def create_token(self, body):
        if not self._exists():
            raise ValueError("There is no certificate authority yet: create one first")
        kind = body.get("kind")
        if kind not in ("server", "client"):
            raise ValueError("Choose a service (server) or a person, device or partner (client)")
        cn = _text(body, "common_name", "the name the certificate will be for", 64)
        names = body.get("names") or []
        names = [n.strip() for n in (re.split(r"[,\n]", names) if isinstance(names, str) else names) if isinstance(n, str) and n.strip()]
        hours = body.get("hours", 24)
        if type(hours) is not int or not 1 <= hours <= 720:
            raise ValueError("A token lasts 1 to 720 hours")
        token = est.create_token(CA(self.ca_dir), cn, kind, names, hours)
        self.audit("token", {"common_name": cn, "kind": kind, "id": token.split(".")[0]})
        return 200, {"token": token, "expires_hours": hours, "common_name": cn,
                     "command": f"set ACXELIN_TLS_ENROLL_TOKEN to the token, then: acxelin-qguard ca enroll https://CA-ADDRESS:9443 --cn {cn} --out {cn} --ca ca.crt"}

    @task
    def create_eab(self, body):
        if not self._exists():
            raise ValueError("There is no certificate authority yet: create one first")
        note = body.get("note") or ""
        if not isinstance(note, str) or len(note) > 120:
            raise ValueError("The note must be text of at most 120 characters")
        kid, key = acme.create_eab(self.ca_dir, note)
        self.audit("eab", {"kid": kid, "note": note})
        return 200, {"kid": kid, "hmac": key, "command": f"certbot certonly --server https://ACME-ADDRESS/directory --eab-kid {kid} --eab-hmac-key {key} --csr request.der"}

    # --- the authority itself

    @task
    def authority(self, body):
        if not self._exists():
            return 200, {"configured": False}
        ca = CA(self.ca_dir)
        enc = encrypted(self.ca_dir / "ca.key")
        return 200, {"configured": True, "name": next((str(a.value) for a in ca.cert.subject if a.oid == NameOID.COMMON_NAME), ""),
                     "algorithm": ca.algorithm, "fingerprint": hashlib.sha256(ca.cert.public_bytes(serialization.Encoding.DER)).hexdigest(),
                     "not_before": ca.cert.not_valid_before_utc.isoformat(), "not_after": ca.cert.not_valid_after_utc.isoformat(),
                     "folder": str(self.ca_dir), "encrypted": enc, "unlocked": bool(self.passphrase) or not enc, "crl": self._crl()}

    @task
    def download_ca(self, body):
        if not self._exists():
            raise ValueError("There is no certificate authority yet: create one first")
        return 200, core.Download("ca.crt", CA(self.ca_dir).anchor.read_bytes(), "application/x-pem-file")

    @task
    def lock_ca(self, body):
        with self.lock:
            self.passphrase = None
        return 200, {"locked": True}

    # --- health

    @task
    def health(self, body):
        rows = [{k: r[k] for k in ("level", "message", "action")} for r in checks.prerequisites()]
        if self._exists():
            rows += [{"level": level, "message": message, "action": ""} for level, message in checks.ca(self.ca_dir)]
        return 200, {"checks": rows, "version": __version__}


def _is_ip(s):
    import ipaddress
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


def page():
    return shell.render((Path(__file__).parent / "console.html").read_text(encoding="utf-8"))


def build(home, ca_dir=None, settings=None):
    t = TLSConsole(home, ca_dir, settings)
    routes = {("GET", "/api/status"): t.status, ("POST", "/api/ca/create"): t.create, ("POST", "/api/ca/unlock"): t.unlock,
              ("GET", "/api/certificates"): t.certificates, ("POST", "/api/certificates/issue"): t.issue, ("POST", "/api/certificates/revoke"): t.revoke,
              ("POST", "/api/crl/refresh"): t.refresh, ("POST", "/api/certificates/renew"): t.renew,
              ("POST", "/api/certificates/maintain"): t.maintain, ("POST", "/api/certificates/download"): t.download, ("GET", "/api/edges"): t.edges, ("POST", "/api/edges/add"): t.add_edge,
              ("POST", "/api/edges/remove"): t.remove_edge, ("POST", "/api/edges/test"): t.test_edge, ("GET", "/api/health"): t.health,
              ("GET", "/api/services"): t.services, ("POST", "/api/services/save"): t.save_service, ("POST", "/api/services/remove"): t.remove_service,
              ("POST", "/api/services/enforce"): t.enforce, ("POST", "/api/services/watch"): t.watch,
              ("POST", "/api/guard/start"): t.start_guard, ("POST", "/api/guard/stop"): t.stop_guard, ("POST", "/api/check"): t.check,
              ("GET", "/api/enrollment"): t.enrollment, ("POST", "/api/enrollment/token"): t.create_token, ("POST", "/api/enrollment/eab"): t.create_eab,
              ("GET", "/api/authority"): t.authority, ("POST", "/api/ca/download"): t.download_ca, ("POST", "/api/ca/lock"): t.lock_ca}
    return core.App(page(), routes)


def run(home, port=8900, open_browser=True, ca_dir=None, host="127.0.0.1", settings=None):
    """Start the console and sign this browser in: the launch address carries a single-use ticket in its fragment."""
    app = build(home, ca_dir, settings)
    server = core.start(app, home, port, host)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/#{app.sessions.ticket()}"
    if open_browser and core.open_in_browser(url, home):
        print(f"Acxelin QGuard console is open in your browser (http://127.0.0.1:{port}). Press Ctrl+C to stop.")
    else:
        core.link_running(port, home)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()
    return 0


def cmd_console(a):
    import os
    import sys
    home = Path(a.home or os.environ.get("ACXELIN_TLS_HOME") or Path.home() / ".acxelin-tls")
    if a.action == "link":
        try:
            if core.link_running(a.port, home) is None:
                print("acxelin-qguard: console link prints only to a terminal; run it in an interactive session", file=sys.stderr)
        except (OSError, ValueError) as e:
            sys.exit(f"acxelin-qguard: no console is running on port {a.port} ({e}); start one with `acxelin-qguard console`")
        return 0
    return run(home, a.port, open_browser=not a.no_browser and not a.container, ca_dir=a.ca, host="0.0.0.0" if a.container else "127.0.0.1",
               settings=a.settings)


def add(sub):
    p = sub.add_parser("console", help="open the console in your browser; `console link` prints a fresh launch address for a console already running")
    p.set_defaults(func=cmd_console)
    p.add_argument("action", nargs="?", choices=["link"])
    p.add_argument("--port", type=int, default=8900)
    p.add_argument("--home", metavar="DIR", help="where the console keeps the CA, issued certificates and its token (default: ~/.acxelin-tls)")
    p.add_argument("--ca", metavar="DIR", help="manage this CA folder (default: HOME/ca)")
    p.add_argument("--settings", metavar="FILE", help="the settings file the QGuard service reads, which the console edits "
                                                      "(default: HOME/edge.toml; on a Linux server, /etc/acxelin-tls/edge.toml)")
    p.add_argument("--container", action="store_true", help="inside a container: listen on every interface so a published port reaches it (publish it to 127.0.0.1 only)")
    p.add_argument("--no-browser", action="store_true", help="do not open a browser; print the launch address instead")
