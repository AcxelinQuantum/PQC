"""A certificate this computer can't verify is reported as exactly that, with the verification error, never as a guessed proxy (R1).
Interception is named only on its own evidence: several hosts all answering with one certificate issuer this computer does not trust."""
import datetime as dt
import socket
import ssl
import threading
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from acxelin_readiness import cli, endpoints

NOW = dt.datetime.now(dt.timezone.utc)


def name(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def chain(tmp_path):
    """A root that expired yesterday and a server certificate it signed that is valid for another 60 days."""
    root_key, leaf_key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    root = (x509.CertificateBuilder().subject_name(name("Old Root")).issuer_name(name("Old Root")).public_key(root_key.public_key())
            .serial_number(1).not_valid_before(NOW - dt.timedelta(days=400)).not_valid_after(NOW - dt.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()), critical=False).sign(root_key, hashes.SHA256()))
    leaf = (x509.CertificateBuilder().subject_name(name("app.test")).issuer_name(root.subject).public_key(leaf_key.public_key())
            .serial_number(2).not_valid_before(NOW - dt.timedelta(days=30)).not_valid_after(NOW + dt.timedelta(days=60))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("app.test")]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), critical=False).sign(root_key, hashes.SHA256()))
    pem = lambda c: c.public_bytes(serialization.Encoding.PEM)
    (tmp_path / "root.pem").write_bytes(pem(root))
    (tmp_path / "leaf.pem").write_bytes(pem(leaf))
    (tmp_path / "leaf.key").write_bytes(leaf_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return tmp_path / "root.pem"


def serve(tmp_path, request):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(tmp_path / "leaf.pem", tmp_path / "leaf.key")
    sock = socket.create_server(("127.0.0.1", 0))
    request.addfinalizer(sock.close)

    def loop():
        while True:
            try:
                conn, _ = sock.accept()
            except OSError:
                return
            try:
                conn.settimeout(5)
                ctx.wrap_socket(conn, server_side=True).close()
            except (OSError, ssl.SSLError):
                conn.close()
    threading.Thread(target=loop, daemon=True).start()
    return sock.getsockname()[1]


def test_the_verification_error_this_computer_got_is_kept(tmp_path, request):
    root = chain(tmp_path)
    port = serve(tmp_path, request)
    real = ssl.create_default_context
    stale = lambda *a, **k: real(cafile=str(root))  # this computer's trust store holds only an expired root
    out = {}
    with patch("ssl.create_default_context", side_effect=stale):
        endpoints._trusted(out, "127.0.0.1", port, "app.test", 5)
    assert out["trusted"] is False and out["trust_error"] == "certificate has expired"


def row(target, issuer="CN=R11,O=Let's Encrypt", days=60, **more):
    return {"target": target, "grade": "B", "protocol": "tls", "accepts": [], "negotiated": "X25519MLKEM768", "error": None, "cnsa2": False,
            "certificate": {"key": "ECDSA-secp256r1", "issuer": issuer, "expires": (NOW + dt.timedelta(days=days)).date().isoformat(),
                            "days_left": days, "quantum_safe": False}} | more


def texts(o):
    return " ".join(x["text"] for x in o["risks"] + o["actions"])


def test_a_plain_verification_failure_says_this_computer_could_not_verify_it_and_never_guesses_a_proxy():
    site = row("acxelinquantum.com:443", trusted=False, trust_error="certificate has expired", trust_code=10)
    o = endpoints.outlook([site])
    risk = next(r for r in o["risks"] if r["targets"] == ["acxelinquantum.com:443"] and "verify" in r["text"])
    assert "This computer couldn't verify the certificate" in risk["text"] and "certificate has expired" in risk["text"]
    assert "trust store" in risk["text"], "the server's own certificate is valid, so the expired one is in the path this computer built"
    assert "proxy" not in texts(o) and "inspect" not in texts(o)
    html = endpoints.report_html([site])
    assert "certificate has expired" in html and "proxy" not in html


def test_an_expired_server_certificate_is_the_servers_problem_not_this_computers():
    o = endpoints.outlook([row("old.example:443", days=-3, trusted=False, trust_error="certificate has expired", trust_code=10)])
    risk = next(r for r in o["risks"] if "verify" in r["text"])
    assert "trust store" not in risk["text"] and "server's own certificate" in risk["text"]


def test_one_untrusted_issuer_answering_for_several_hosts_is_named_as_possible_interception():
    corp = dict(issuer="CN=Corp Inspection CA", trusted=False, trust_error="unable to get local issuer certificate", trust_code=20)
    o = endpoints.outlook([row("a.example:443", **corp), row("b.example:443", **corp)])
    assert "TLS-inspecting proxy" in texts(o)
    risk = next(r for r in o["risks"] if "proxy" in r["text"])
    assert risk["targets"] == ["a.example:443", "b.example:443"] and "Corp Inspection CA" in risk["text"]


def test_a_shared_public_issuer_or_a_single_unknown_one_is_not_interception():
    trusted = [row("a.example:443", trusted=True), row("b.example:443", trusted=True)]
    assert "proxy" not in texts(endpoints.outlook(trusted)), "two sites on Let's Encrypt share an issuer"
    alone = [row("a.example:443", issuer="CN=Private CA", trusted=False, trust_error="self-signed certificate in certificate chain", trust_code=19)]
    assert "proxy" not in texts(endpoints.outlook(alone))
    mixed = [row("a.example:443", issuer="CN=X", trusted=False, trust_error="unable to get local issuer certificate", trust_code=20), row("b.example:443", issuer="CN=X", trusted=True)]
    assert "proxy" not in texts(endpoints.outlook(mixed))


def test_grade_prints_the_verification_error(capsys):
    site = row("acxelinquantum.com:443", trusted=False, trust_error="certificate has expired", trust_code=10)
    with patch("acxelin_readiness.endpoints.scan", return_value=[site]):
        assert cli.main(["grade", "acxelinquantum.com"]) == 0
    out = capsys.readouterr().out
    assert "couldn't verify the certificate (certificate has expired)" in out and "proxy" not in out
