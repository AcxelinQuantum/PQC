"""Acme's world for the QReadiness film: the product's example repositories copied under C:\\acme\\qreadiness, the console's
own home there, Acme's owners spreadsheet (a CMDB export), and three real TLS test servers graded A, B and C.

The three Acme test hosts listen on loopback addresses. Their .example names resolve to those addresses inside this process
only (a hosts-file entry for this process alone): the console's real probe connects to real servers that really negotiate what
their grade says, and no system setting is touched."""
import datetime as dt
import os
import shutil
import socket
import logging
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACME = Path(r"C:\acme\qreadiness")
OPENSSL = Path(r"C:\Program Files\OpenSSL-Win64\bin")
if OPENSSL.is_dir():
    os.environ.setdefault("ACXELIN_OPENSSL", str(OPENSSL))

# name -> (loopback address, how it is set up)
HOSTS = {
    "api.test.acme.example": ("127.77.0.1", "strict"),       # post-quantum key exchange only: grade A
    "shop.test.acme.example": ("127.77.0.2", "transition"),  # hybrid post-quantum, classical still accepted: grade B
    "billing.test.acme.example": ("127.77.0.3", "classical"),  # an older stack, classical only: grade C
}
PORT = 443

# Acme's CMDB export, one per repository: which team owns each part, the business service, and how important it is
OWNERS = {
    "payments-api": "path,owner,service,importance\n"
                    "/src/,Payments team,Card payments,critical\n"
                    "/services/,Payments team,Card payments,critical\n"
                    "/deploy/,Platform team,Payments gateway,high\n"
                    "/cmd/release/,Release team,Releases,medium\n",
    "customer-portal": "path,owner,service,importance\n"
                       "/src/,Web team,Customer portal,high\n"
                       "/deploy/,Platform team,Customer portal,high\n",
    "batch-jobs": "path,owner,service,importance\n"
                  "/jobs/,Data team,Nightly exports,medium\n"
                  "/deploy/,Platform team,Batch servers,low\n",
}

_real_getaddrinfo = socket.getaddrinfo


def _getaddrinfo(host, *args, **kwargs):
    if isinstance(host, str) and host.lower().rstrip(".") in HOSTS:
        host = HOSTS[host.lower().rstrip(".")][0]
    return _real_getaddrinfo(host, *args, **kwargs)


def repositories():
    """The example repositories copied into ACME/repos, and a fresh console home beside them."""
    repos, home = ACME / "repos", ACME / "console"
    for old in (home, ACME / "hosts"):
        for _ in range(40):  # Windows can hold a just-emptied folder for a moment
            shutil.rmtree(old, ignore_errors=True)
            if not old.exists():
                break
            time.sleep(0.5)
        if old.exists():
            raise SystemExit(f"could not clear {old}; close what holds it and try again")
    for name in OWNERS:
        shutil.copytree(ROOT / "products/readiness/examples" / name, repos / name, dirs_exist_ok=True)
    return repos, home


def _classical_cert(folder, name):
    """An ECDSA certificate from a small classical Acme CA, as an older server would have."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    t = dt.datetime.now(dt.timezone.utc)
    ca_key, key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Acme Legacy CA")])
    cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])).issuer_name(ca_name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(t - dt.timedelta(days=1)).not_valid_after(t + dt.timedelta(days=200))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), False).sign(ca_key, hashes.SHA256()))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (folder / "key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return folder


class TestHosts:
    """The three Acme test servers, each on its own loopback address at port 443."""

    def __init__(self, folder):
        from acxelin_core import server as core_server
        from acxelin_core import tls
        from acxelin_core.pki import CA
        from acxelin_tls import policies
        self.folder, self.stops = Path(folder), []
        ca = CA.init(self.folder / "ca", "Acme Test CA", algorithm="ML-DSA-65")
        socket.getaddrinfo = _getaddrinfo
        logging.getLogger(core_server.__name__).setLevel(logging.ERROR)  # the probe's refused handshakes are its job, not news

        def answer(conn, addr):
            try:
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
            finally:
                conn.close()

        classical = tls.Policy("classical", "X25519:secp256r1:secp384r1", None, policies.CIPHERSUITES)  # what an older stack offers
        for name, (address, kind) in HOSTS.items():
            if kind == "classical":
                out = _classical_cert(self.folder / name, name)
            else:
                out, _ = ca.issue(name, "server", algorithm="ML-DSA-65", out=self.folder / name)
            pick = classical if kind == "classical" else policies.policy(kind)
            chain = out / "chain.pem" if (out / "chain.pem").exists() else out / "cert.pem"
            make = lambda chain=chain, out=out, pick=pick: tls.server_context(pick, str(chain), str(out / "key.pem"))
            srv = core_server.Server((address, PORT), make, answer, name=name, max_rate_per_client=100000.0, max_per_client=4096)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            self.stops.append(lambda srv=srv: (srv.stopping.set(), srv.sock.close()))

    def close(self):
        for stop in self.stops:
            try:
                stop()
            except OSError:
                pass
        socket.getaddrinfo = _real_getaddrinfo


def console(repos, home):
    """The real QReadiness console with Acme's three repositories added. customer-portal and batch-jobs are scanned now, with
    their owners spreadsheets loaded; payments-api is added but left for the film to scan."""
    from acxelin_readiness import console as rc
    app = rc.build(home)
    call = lambda path, body=None: app.routes[("POST" if body is not None else "GET", path)](body or {})[1]
    call("/api/setup", {"directory": str(repos)})
    ids = {name: call("/api/projects/register", {"name": name})["project"] for name in ("batch-jobs", "customer-portal", "payments-api")}
    for name in ("batch-jobs", "customer-portal"):
        call("/api/projects/scan", {"project": ids[name]})
        while call("/api/projects/status")["running"]:
            time.sleep(0.1)
        assert call("/api/projects/status")["last"], f"{name} did not scan: {call('/api/projects/status')['error']}"
        owners(app, ids[name], name)
    return app, ids


def owners(app, project, name):
    """Load Acme's owners spreadsheet for one scanned repository, as Projects, Owners from a CMDB export does."""
    app.routes[("POST", "/api/projects/owners")]({"project": project, "csv": OWNERS[name]})


def serve(app, home):
    from acxelin_core import console as core
    server = core.start(app, home, port=0)
    return server, f"http://127.0.0.1:{server.server_address[1]}"
