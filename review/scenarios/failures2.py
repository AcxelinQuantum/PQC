"""No OpenSSL anywhere on PATH, and an expired certificate signed by the audit CA."""
import datetime as dt
import subprocess
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

sys.path.insert(0, str(Path(__file__).parent))
from harness import ENV, EXE  # noqa: E402

home = Path(__file__).parent / "homes/qguard"
sc = home / "sc"
bare = ENV | {"ACXELIN_OPENSSL": str(home / "empty"), "PATH": str(EXE["qguard"].parent)}


def go(args, env, cwd=sc, seconds=6):
    p = subprocess.Popen([str(EXE["qguard"]), *args], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    try:
        out, _ = p.communicate(timeout=seconds)
        return p.returncode, out.strip()
    except subprocess.TimeoutExpired:
        p.terminate()
        return "still running", p.communicate()[0].strip()


for args in (["doctor"], ["try"], ["edge", "--listen", "127.0.0.1:8462", "--target", "127.0.0.1:18080", "--cert", "apps/chain.pem", "--key", "apps/key.pem"]):
    code, out = go(args, bare)
    print(f"\n### no OpenSSL: acxelin-qguard {args[0]}\n[exit {code}]\n" + "\n".join(out.splitlines()[-5:]))

# expired: sign a leaf with the CA key, valid until yesterday
ca_cert = x509.load_pem_x509_certificate((home / "ca/ca.crt").read_bytes())
ca_key = serialization.load_pem_private_key((home / "ca/ca.key").read_bytes(), b"correct horse battery")
leaf_key = serialization.load_pem_private_key((sc / "apps/key.pem").read_bytes(), None)
now = dt.datetime.now(dt.timezone.utc)
cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "expired.audit.test")])).issuer_name(ca_cert.subject)
        .public_key(leaf_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(days=30))
        .not_valid_after(now - dt.timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName("static.audit.test")]), False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False).sign(ca_key, None))
(sc / "expired").mkdir(exist_ok=True)
(sc / "expired/chain.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM) + (home / "ca/ca.crt").read_bytes())
code, out = go(["edge", "--listen", "127.0.0.1:8463", "--target", "127.0.0.1:18080", "--cert", "expired/chain.pem", "--key", "apps/key.pem"], ENV, seconds=5)
print(f"\n### edge with a certificate that expired yesterday\n[exit {code}]\n" + "\n".join(out.splitlines()[-4:]))
code, out = go(["doctor", "--config", "edges.toml"], ENV)
print(f"\n### doctor --config (unrelated, for comparison)\n[exit {code}] " + out.splitlines()[-1])
code, out = go(["connect", "127.0.0.1:8463", "--ca", "../ca/ca.crt", "--server-name", "static.audit.test"], ENV)
print(f"\n### connect to a running edge whose certificate expired\n[exit {code}]\n{out[-400:]}")
