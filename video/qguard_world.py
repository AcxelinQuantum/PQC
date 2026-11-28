"""Acme's world for the QGuard film: three small real apps, the real QGuard console with its own CA, real clients.

Everything lives under C:\\acme, so no folder on screen names the user. The console runs in this process (as
tools/capture_screens.py does); QGuard itself is started by the console's own button, as a subprocess. The terminal's commands
are real: curl with OpenSSL 3.5 in WSL Ubuntu, reaching the guard by the Windows host's address. Acme's names reach that address
through a curl config file in the demo folder (`resolve`), never through the hosts file."""
import datetime as dt
import os
import secrets
import shutil
import socket
import socketserver
import subprocess
import threading
import time
from pathlib import Path

os.environ.setdefault("ACXELIN_OPENSSL", r"C:\Program Files\OpenSSL-Win64\bin")

ACME = Path("C:/acme")
HOME = ACME / "qguard"
DEMO = ACME / "demo"
CERTS = ACME / "certs"
SHOP, INTRANET, PARTNERS = "shop.acme.example", "intranet.acme.example", "partners.acme.example"
PAGES = {8080: "Acme shop", 3000: "Acme intranet", 9000: "Acme partner API"}


def free(port):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class App(socketserver.ThreadingTCPServer):
    """A tiny HTTP app that answers every request with one line: the service QGuard stands in front of."""
    daemon_threads = allow_reuse_address = True

    def __init__(self, port, text):
        body = (text + "\n").encode()
        reply = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s" % (len(body), body)

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                data = b""
                self.request.settimeout(10)
                try:
                    while b"\r\n\r\n" not in data and len(data) < 65536:
                        chunk = self.request.recv(4096)
                        if not chunk:
                            return
                        data += chunk
                    self.request.sendall(reply)
                except OSError:
                    pass

        super().__init__(("127.0.0.1", port), Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()


def public_certificate(folder, name):
    """An ordinary ECDSA certificate and key for `name`, standing in for the shop's public (Let's Encrypt) certificate."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key, t = ec.generate_private_key(ec.SECP256R1()), dt.datetime.now(dt.timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(t - dt.timedelta(days=1)).not_valid_after(t + dt.timedelta(days=90))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), False).sign(key, hashes.SHA256()))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "fullchain.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (folder / "privkey.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))


class World:
    def __init__(self):
        self.apps, self.server, self.state = [], None, None
        self.passphrase = secrets.token_urlsafe(18)

    # --- set up and tear down

    def start(self):
        from acxelin_core import console as core
        from acxelin_tls import console as tc
        for port in (443, *PAGES):
            if not free(port):
                raise SystemExit(f"port {port} is in use: the film shows Acme's services on 443, 8080, 3000 and 9000")
        for d in (HOME, DEMO, CERTS):
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True)
        self.apps = [App(p, t) for p, t in PAGES.items()]
        public_certificate(CERTS, SHOP)
        self.app = tc.build(HOME)
        self.state = self.app.routes[("GET", "/api/status")].__self__
        self.call("/api/ca/create", {"name": "Acme Corp Root CA", "passphrase": self.passphrase})
        # Acme already put two services behind QGuard; the film protects the third, the shop.
        self.call("/api/services/save", {"kind": "app", "host": INTRANET, "port": 443, "target": "127.0.0.1:3000", "watch": True})
        self.call("/api/services/save", {"kind": "partner", "host": PARTNERS, "port": 443, "target": "127.0.0.1:9000"})
        settings = HOME / "edge.toml"
        self.metrics = free_port()  # the console's default status address, moved to a free port (other films record at the same time)
        settings.write_text(settings.read_text(encoding="utf-8").replace("127.0.0.1:9100", f"127.0.0.1:{self.metrics}"), encoding="utf-8")
        shutil.copy(HOME / "ca" / "ca.crt", DEMO / "ca.crt")
        self.server = core.start(self.app, HOME, port=0)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.host_ip = self.wsl_host()
        (DEMO / ".curlrc").write_text(f"# Acme's names lead to this QGuard; trust Acme's own CA\nresolve = *:443:{self.host_ip}\n"
                                      "cacert = /mnt/c/acme/demo/ca.crt\nsilent\nshow-error\nmax-time = 8\n",
                                      encoding="utf-8", newline="\n")
        return self

    def stop(self):
        try:
            if self.state:
                self.state._stop()
        finally:
            if self.server:
                self.server.shutdown()
            for a in self.apps:
                a.shutdown()
                a.server_close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    def call(self, path, body=None):
        return self.app.routes[("POST" if body is not None else "GET", path)](body or {})[1]

    def ticket(self):
        return self.app.sessions.ticket()

    def secrets(self):
        token = (HOME / "console.token").read_text().strip()
        return [self.passphrase, token]

    # --- clients

    def hello(self, name, classical=False, cert=None, key=None):
        """One real HTTPS request to `name` on the guard, from this computer: quantum-safe, or classical only."""
        from acxelin_core import tls
        from acxelin_tls import policies
        ca = str(HOME / "ca" / "ca.crt")
        ctx = (tls.Context(False, "X25519", None, policies.CIPHERSUITES, ca=ca) if classical
               else tls.client_context(policies.policy("strict"), ca, cert, key))
        try:
            with tls.connect("127.0.0.1", 443, ctx, name, 5) as c:
                c.sendall(f"GET / HTTP/1.1\r\nHost: {name}\r\n\r\n".encode())
                return c.recv(timeout=5)
        except (tls.TLSError, OSError) as e:
            return e
        finally:
            ctx.close()

    @staticmethod
    def wsl_host():
        out = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "sh", "-c", "ip route show default"], capture_output=True, text=True, timeout=60).stdout.split()
        return out[out.index("via") + 1]

    @staticmethod
    def curl(*args):
        """Run curl in WSL Ubuntu (OpenSSL 3.5) from the demo folder; the output as the terminal shows it, stdout and stderr in order."""
        run = subprocess.run(["wsl", "-d", "Ubuntu", "--cd", "/mnt/c/acme/demo", "-e", "env", "HOME=/mnt/c/acme/demo", "curl", *args],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        return run.returncode, run.stdout.decode("utf-8", "replace").replace("\r\n", "\n").rstrip("\n")

    def wait_for(self, test, seconds=20):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if test():
                return True
            time.sleep(0.25)
        raise RuntimeError("QGuard did not reach the expected state in time")
