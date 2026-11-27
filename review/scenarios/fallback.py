"""Does a browser that trusts only the classical fallback certificate get a working page on the transition+fallback port?
And which certificate does each kind of client receive?"""
import base64
import hashlib
import socket
import ssl
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from playwright.sync_api import Error, sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from harness import shot  # noqa: E402

sc = Path(__file__).parent / "homes/qguard/sc"
leaf = x509.load_pem_x509_certificate((sc / "classical/fullchain.pem").read_bytes())
spki = base64.b64encode(hashlib.sha256(leaf.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).digest()).decode()

# 1. a classical-only client (Python's ssl, its own OpenSSL, no ML-KEM groups offered): which certificate does it get?
for port in (8444, 8447, 8443):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    try:
        ctx.set_ecdh_curves("X25519:P-256") if hasattr(ctx, "set_ecdh_curves") else None
    except Exception:
        pass
    try:
        with socket.create_connection(("127.0.0.1", port), 5) as s, ctx.wrap_socket(s, server_hostname="static.audit.test") as t:
            der = t.getpeercert(binary_form=True)
            c = x509.load_der_x509_certificate(der)
            print(f"python ssl ({ssl.OPENSSL_VERSION}) port {port}: {t.version()} {t.cipher()[0]} cert={c.signature_algorithm_oid._name} issuer={c.issuer.rfc4514_string()}")
    except Exception as e:
        print(f"python ssl port {port}: FAILED {type(e).__name__}: {e}")

# 2. Chrome and Edge trusting only the fallback key
with sync_playwright() as pw:
    for ch in ("chrome", "msedge"):
        b = pw.chromium.launch(channel=ch, args=["--host-resolver-rules=MAP *.audit.test 127.0.0.1", f"--ignore-certificate-errors-spki-list={spki}"])
        for port in (8444, 8447):
            page = b.new_page(viewport={"width": 1100, "height": 700})
            try:
                r = page.goto(f"https://static.audit.test:{port}/", timeout=15000)
                sec = page.evaluate("() => window.isSecureContext")
                print(f"{ch} trusting fallback key, port {port}: loaded {r.status}, secure context {sec}")
                shot(page, "browsers", f"{ch}-fallback-trusted-{port}", full=False)
            except Error as e:
                print(f"{ch} trusting fallback key, port {port}: {str(e).splitlines()[0]}")
            page.close()
        b.close()
