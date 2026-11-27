"""Deployment checks for `acxelin-qvpn doctor --ca DIR --config FILE`: each check is (level, message) with level ok, warn or fail,
and what to do about it in its `action`."""
import datetime as dt
import importlib.util
import os
import shutil
import sys
from pathlib import Path

from acxelin_core.config import read_toml
from acxelin_core.pki import CA, CAError, encrypted, now, signed_by
from cryptography import x509


class Check(tuple):
    """(level, message), with what to do in `.action`."""

    def __new__(cls, level, message, action=""):
        c = super().__new__(cls, (level, message))
        c.action = action
        return c


def _have(module):
    return importlib.util.find_spec(module) is not None


def _private(path):
    """A key file readable by everyone fails, by its group warns (Kubernetes mounts secrets group-readable for fsGroup). POSIX
    permissions only; Windows ACLs are not checked."""
    if os.name == "nt":
        return []
    mode = os.stat(path).st_mode
    if mode & 0o004:
        return [Check("fail", f"{path} can be read by every user", f"chmod 600 {path}")]
    return [Check("warn", f"{path} can be read by its group", f"chmod 600 {path}, unless the group is this service's")] if mode & 0o040 else []


def ca(root):
    root, out = Path(root), []
    crl_cmd = f"Run `acxelin-qvpn ca crl --dir {root}`"
    try:
        c = CA(root)
    except (CAError, OSError, ValueError) as e:
        return [Check("fail", f"CA at {root}: {e}", "Point at the folder that holds ca.crt and ca.key, or restore it from a backup")]
    left = (c.cert.not_valid_after_utc - now()).days
    valid_now = c.cert.not_valid_before_utc <= now() < c.cert.not_valid_after_utc
    out.append(Check("fail" if not valid_now else "ok" if left > 365 else "warn",
                     f"CA {c.cert.subject.rfc4514_string()} ({c.algorithm}) " + (f"valid for {left} more days" if valid_now else "is expired or not yet valid"),
                     "" if valid_now and left > 365 else "Plan a new CA before this one ends" if valid_now else "Restore a valid CA before serving certificates"))
    if (root / "signer.json").exists():
        out.append(Check("ok", "CA key is held by an external signer (KMS or HSM)"))
    else:
        out += _private(root / "ca.key")
        out.append(Check("ok", "CA key is encrypted") if encrypted(root / "ca.key") else
                   Check("warn", "CA key is not encrypted: anyone who copies ca.key can issue certificates",
                         "Use KMS, an HSM or an encrypted key"))
    try:
        records = c.records()
    except (OSError, ValueError, TypeError) as e:
        return out + [Check("fail", f"{root / 'index.json'} cannot be read ({e})", "Restore it from a backup")]
    crl = root / "crl.pem"
    try:
        listed = x509.load_pem_x509_crl(crl.read_bytes()) if crl.exists() else None
    except ValueError:
        listed = False
    if listed is None:
        out.append(Check("fail", f"no {crl}: mutual-TLS services cannot start", crl_cmd))
    elif listed is False or not signed_by(c.cert, listed.tbs_certlist_bytes, listed.signature):
        out.append(Check("fail", f"{crl} is damaged or not signed by this CA; every client would be refused", crl_cmd))
    else:
        missing = [r.common_name for r in records if r.status == "revoked" and listed.get_revoked_certificate_by_serial_number(int(r.serial, 16)) is None]
        if missing:
            out.append(Check("fail", f"{len(missing)} revoked certificate(s) not in crl.pem ({', '.join(missing[:5])})", crl_cmd))
        days = (listed.next_update_utc - now()) / dt.timedelta(days=1)
        out.append(Check("fail" if days < 0 else "warn" if days < 2 else "ok", f"CRL {'expired' if days < 0 else 'valid for'} {abs(days):.1f} days",
                         "" if days >= 2 else f"Run `acxelin-qvpn ca maintain --dir {root}`, and schedule it daily"))
    newest = {}
    for r in records:
        if r.status == "valid" and r.kind != "ca" and r.path and dt.datetime.fromisoformat(r.not_after) > now():
            newest[r.path] = max(newest.get(r.path, r), r, key=lambda x: x.not_after)
    gone = [r for r in newest.values() if not all((Path(r.path) / f).exists() for f in ("cert.pem", "key.pem", "chain.pem"))]
    if gone:
        out.append(Check("warn", f"{len(gone)} valid certificate(s) recorded without their files ({', '.join(r.common_name for r in gone[:5])}): "
                                 "moved elsewhere, or a crash while issuing", "Revoke any whose files are gone for good"))
    soon = c.expiring(30, current=True)
    out.append(Check("warn", f"{len(soon)} certificate(s) expire within 30 days: {', '.join(r.common_name for r in soon[:5])}",
                     f"`acxelin-qvpn ca maintain --dir {root}` renews gateways and sites; laptops renew their own when the app or join runs")
               if soon else Check("ok", "no certificate expires within 30 days"))
    return out


def _files(where, d, names):
    out = []
    for k in [n for n in names if not (n == "crl" and d.get("crl_url"))]:  # with crl_url the copy appears at the first fetch
        p = d.get(k)
        if not p:
            continue
        if not Path(p).exists() and k == "private_key":
            ok = Path(p).parent.is_dir() and os.access(Path(p).parent, os.W_OK)
            out.append(Check("ok", f"{where}: {k} = {p} is created on first start") if ok else
                       Check("fail", f"{where}: {k} = {p} cannot be created there", "Create its folder and let the service write to it"))
        elif not Path(p).exists():
            out.append(Check("fail", f"{where}: {k} = {p} does not exist", "Copy the file there, or correct the path"))
        elif k in ("key", "private_key"):
            out += _private(p)
    return out


def config(path):
    """Load a site or gateway configuration, then look for settings that work but weaken the deployment."""
    from . import load_config
    from .wireguard import load_gateway
    fix = "Correct the configuration (config/ in the release has every setting explained), then run doctor again"
    try:
        doc = read_toml(path)
    except OSError as e:
        return [Check("fail", f"{path}: {e.strerror or e}", "Check the path")]
    except ValueError as e:
        return [Check("fail", str(e), fix)]
    kind = next((k for k in ("site", "wireguard") if k in doc), None)
    if not kind:
        return [Check("fail", f"{path}: no [site] or [wireguard] section", fix)]
    try:
        {"site": load_config, "wireguard": load_gateway}[kind](path)
    except (OSError, ValueError, CAError) as e:
        return [Check("fail", f"{path}: {e}", fix)]
    s = doc[kind]
    out = [Check("ok", f"{path}: {kind} configuration loads")] + _files(f"{path} [{kind}]", s, ("cert", "key", "ca", "crl", "private_key"))
    if not s.get("crl"):
        out.append(Check("fail", f"{path} [{kind}]: no crl, so revoked peers keep getting keys", "Set crl to the CA's crl.pem (and crl_url to fetch it)"))
    elif not s.get("crl_url"):
        out.append(Check("warn", f"{path} [{kind}]: the CRL is a local file", "Set crl_url, unless this machine is the CA"))
    return out


def prerequisites(role=None):
    """What this machine needs to run Acxelin QVPN, as rows with product, level (ok, warn or fail), message and action. `role`
    fits the advice to the machine: "admin" (the CA and the console: only key agreement matters), "gateway", or None (any)."""
    from acxelin_core import openssl
    frozen = getattr(sys, "frozen", False)  # the desktop installer: everything it needs is inside, so never advise pip
    rows = []

    def add(part, level, message, action=""):
        rows.append({"product": part, "level": level, "message": message, "action": action})
    reason = openssl.available()
    if reason:
        add("key agreement", "fail", reason, "Once that is done, run `acxelin-qvpn doctor` again")
    else:
        add("key agreement", "ok", f"{openssl.lib().version} can agree keys over post-quantum mutual TLS")
    if role == "admin":
        return rows
    if sys.platform.startswith("linux") and _have("vici") and shutil.which("swanctl") and shutil.which("ip"):
        add("ipsec", "ok", "IPsec control tools found; kernel support and tunnel traffic still need a deployment test")
    else:
        add("ipsec", "warn", "This machine is not set up as an IPsec gateway (fine for a laptop)",
            "Gateways run on Linux: the gateway image, or the manual's section 3" if frozen else
            'Gateways need Linux with strongSwan 6.0.2+, iproute2 and pip install "acxelin-qvpn[vpn]"; laptops use `acxelin-qvpn join` or the app')
    if not shutil.which("wg"):
        add("wireguard", "warn", "The WireGuard command was not found on PATH", "Install the official WireGuard tools for this platform before joining")
    if role != "gateway" and not frozen and not all(_have(m) for m in ("pystray", "PIL")):
        add("desktop", "warn", "The desktop app (tray icon) is not installed; `acxelin-qvpn app` opens the VPN window in a browser instead",
            'pip install "acxelin-qvpn[desktop]", or use the desktop installer')
    return rows
