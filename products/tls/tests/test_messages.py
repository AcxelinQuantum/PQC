"""What a customer reads when something goes wrong, and what `connect` and `try` tell them: plain words and the next step."""
import contextlib
import datetime as dt
import io
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from acxelin_core import openssl, tls
from acxelin_core.pki import CA
from acxelin_core.server import Server
from acxelin_tls import policies
from acxelin_tls.cli import main
from acxelin_tls.common import schedule_hint
from support_tls import REASON


def run(*argv, stdin=""):
    """(exit code, stdout, stderr) of the command line."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), mock.patch("sys.stdin", io.StringIO(stdin)):
        try:
            main([str(a) for a in argv])
            code = 0
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


def classical_site(d):
    """A server certificate like a public website's: ECDSA, from a classical CA. (ca.crt, chain.pem, key.pem)"""
    t, name = dt.datetime.now(dt.timezone.utc), lambda cn: x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    rk, lk = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    root = (x509.CertificateBuilder().subject_name(name("Public-style Root")).issuer_name(name("Public-style Root")).public_key(rk.public_key())
            .serial_number(1).not_valid_before(t - dt.timedelta(1)).not_valid_after(t + dt.timedelta(30))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(rk.public_key()), False).sign(rk, hashes.SHA256()))
    leaf = (x509.CertificateBuilder().subject_name(name("localhost")).issuer_name(root.subject).public_key(lk.public_key()).serial_number(2)
            .not_valid_before(t - dt.timedelta(1)).not_valid_after(t + dt.timedelta(30))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(rk.public_key()), False).sign(rk, hashes.SHA256()))
    pem = lambda c: c.public_bytes(serialization.Encoding.PEM)
    (d / "ca.crt").write_bytes(pem(root))
    (d / "chain.pem").write_bytes(pem(leaf) + pem(root))
    (d / "key.pem").write_bytes(lk.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return d


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.ca = CA.init(self.d / "pki", "Root")
        self.srv, _ = self.ca.issue("localhost", "server", ["localhost", "127.0.0.1"], out=self.d / "srv")


class StartupErrorTest(Base):
    @unittest.skipIf(REASON, REASON)
    def test_a_port_already_in_use_says_so_and_what_to_do(self):
        taken = socket.create_server(("127.0.0.1", 0))
        self.addCleanup(taken.close)
        port = taken.getsockname()[1]
        code, _, err = run("edge", "--listen", f"127.0.0.1:{port}", "--target", "127.0.0.1:1", "--cert", self.srv / "chain.pem", "--key", self.srv / "key.pem")
        self.assertEqual(code, 1)
        self.assertIn(f"port {port} is already in use", err)
        self.assertIn("choose another port", err)

    @unittest.skipIf(REASON, REASON)
    def test_a_missing_certificate_file_is_called_missing(self):
        code, _, err = run("edge", "--listen", "127.0.0.1:0", "--target", "127.0.0.1:1", "--cert", self.d / "nope" / "chain.pem", "--key", self.srv / "key.pem")
        self.assertEqual(code, 1)
        self.assertIn("file not found", err)
        self.assertNotIn("No such process", err)

    @unittest.skipIf(REASON, REASON)
    def test_an_encrypted_key_without_its_passphrase_says_it_is_encrypted_and_how_to_give_it(self):
        self.ca.issue("enc.example", "server", ["127.0.0.1"], out=self.d / "enc", passphrase=b"key-pass")
        code, _, err = run("edge", "--listen", "127.0.0.1:0", "--target", "127.0.0.1:1", "--cert", self.d / "enc" / "chain.pem", "--key", self.d / "enc" / "key.pem")
        self.assertEqual(code, 1)
        self.assertIn("is encrypted", err)
        self.assertIn("--key-passphrase-env", err)
        self.assertNotIn("cipherfinal", err)

    def test_missing_openssl_on_windows_says_how_to_install_it_there(self):
        empty = self.d / "empty"
        empty.mkdir()
        msg = openssl.not_found([], str(empty), "Windows")
        self.assertIn("choco install openssl", msg)
        self.assertIn(str(empty), msg)
        self.assertNotIn("Debian", msg)
        self.assertIn("Debian 13", openssl.not_found([], None, "Linux"))

    def test_scheduling_advice_fits_the_platform(self):
        with mock.patch("os.name", "nt"):
            self.assertIn("scheduled task", schedule_hint())
        with mock.patch("os.name", "posix"):
            self.assertIn("cron", schedule_hint())


@unittest.skipIf(REASON, REASON)
class TourTest(Base):
    def test_the_tour_tells_its_story_without_log_lines_and_ends_at_the_console(self):
        code, out, err = run("try")
        self.assertEqual(code, 0, err)
        self.assertNotIn("INFO", err)
        self.assertNotIn("WARNING", err)
        self.assertIn("acxelin-qguard console", out.strip().splitlines()[-1])


@unittest.skipIf(REASON, REASON)
class ConnectTest(Base):
    def site(self, policy_name, cert, key):
        s = Server(("127.0.0.1", 0), lambda: tls.server_context(policies.policy(policy_name), cert, key), lambda c, a: c.recv(timeout=15))  # longer than any client here waits
        s.start()
        self.addCleanup(s.stop, 1)
        return s.port

    def test_a_site_with_a_classical_certificate_is_explained_under_strict(self):
        site = classical_site(self.d)
        port = self.site("transition", site / "chain.pem", site / "key.pem")
        code, _, err = run("connect", f"127.0.0.1:{port}", "--server-name", "localhost", "--ca", site / "ca.crt")
        self.assertEqual(code, 1)
        self.assertIn("classical certificate (ECDSA)", err)
        self.assertIn("post-quantum key exchange", err)
        self.assertIn("--policy transition", err)

    def test_transition_names_the_key_and_gives_a_verdict(self):
        site = classical_site(self.d)
        port = self.site("transition", site / "chain.pem", site / "key.pem")
        code, out, err = run("connect", f"127.0.0.1:{port}", "--server-name", "localhost", "--ca", site / "ca.crt", "--policy", "transition")
        self.assertEqual(code, 0, err)
        self.assertIn("ECDSA", out)
        self.assertNotIn("1.2.840.10045.2.1", out)
        self.assertIn("quantum-safe key exchange, classical certificate", out)

    def test_without_ca_the_server_is_checked_against_this_computers_public_authorities(self):
        port = self.site("strict", self.srv / "chain.pem", self.srv / "key.pem")
        code, _, err = run("connect", f"127.0.0.1:{port}", "--server-name", "localhost")
        self.assertEqual(code, 1)
        self.assertIn("public certificate authorities this computer trusts", err)
        self.assertIn("--ca", err)

    def test_this_computers_public_authorities_can_be_read(self):
        path = tls.public_roots(self.d / "roots.pem")
        self.assertGreater(Path(path).read_text().count("BEGIN CERTIFICATE"), 10)

    def test_public_authorities_kept_as_a_folder_are_read_too(self):
        """Ubuntu keeps them as one file per authority in /etc/ssl/certs, which Python's ssl does not list."""
        import ssl
        folder = self.d / "certs"
        folder.mkdir()
        for i in range(3):
            (self.d / f"s{i}").mkdir()
            (folder / f"root{i}.pem").write_bytes((classical_site(self.d / f"s{i}") / "ca.crt").read_bytes())
        (folder / "README").write_text("not a certificate")
        paths = ssl.DefaultVerifyPaths(None, str(folder), "", "", "", "")
        with mock.patch("ssl.SSLContext.get_ca_certs", return_value=[]), mock.patch("ssl.get_default_verify_paths", return_value=paths), \
                mock.patch.dict(sys.modules, {"certifi": None}):
            path = tls.public_roots(self.d / "roots.pem")
        self.assertEqual(Path(path).read_text().count("BEGIN CERTIFICATE"), 3)
