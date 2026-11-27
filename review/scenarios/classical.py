"""A classical ECDSA test root and a leaf for the scenario names: stands in for a public (Let's Encrypt) certificate."""
import datetime as dt
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
names = sys.argv[2:]
now = dt.datetime.now(dt.timezone.utc)


def name(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


rk = ec.generate_private_key(ec.SECP256R1())
root = (x509.CertificateBuilder().subject_name(name("Audit Classical Test Root")).issuer_name(name("Audit Classical Test Root"))
        .public_key(rk.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=30)).add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(rk.public_key()), False).sign(rk, hashes.SHA256()))
lk = ec.generate_private_key(ec.SECP256R1())
sans = []
for n in names:
    try:
        import ipaddress
        sans.append(x509.IPAddress(ipaddress.ip_address(n)))
    except ValueError:
        sans.append(x509.DNSName(n))
leaf = (x509.CertificateBuilder().subject_name(name(names[0])).issuer_name(root.subject).public_key(lk.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName(sans), False).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(rk.public_key()), False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(lk.public_key()), False).sign(rk, hashes.SHA256()))
pem = lambda c: c.public_bytes(serialization.Encoding.PEM)
(out / "root.crt").write_bytes(pem(root))
(out / "fullchain.pem").write_bytes(pem(leaf) + pem(root))
(out / "privkey.pem").write_bytes(lk.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
print("classical root + leaf in", out)
