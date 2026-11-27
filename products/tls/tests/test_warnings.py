"""The edge and `doctor` say so when a certificate is expired or about to be, and when a public website is set up in a way
browsers will refuse (transition without a public certificate)."""
import datetime as dt
import logging
import tempfile
import unittest
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from acxelin_core.pki import CA
from acxelin_tls import checks
from acxelin_tls.edge import Edge, Route
from support_tls import REASON


def leaf(ca_dir, out, days_from_now):
    """A server certificate for localhost from the CA in `ca_dir`, ending `days_from_now` days from now (negative: expired)."""
    ca_cert = x509.load_pem_x509_certificate((ca_dir / "ca.crt").read_bytes())
    ca_key = serialization.load_pem_private_key((ca_dir / "ca.key").read_bytes(), None)
    key = serialization.load_pem_private_key((out.parent / "srv" / "key.pem").read_bytes(), None)
    t = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])).issuer_name(ca_cert.subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(t - dt.timedelta(days=60))
            .not_valid_after(t + dt.timedelta(days=days_from_now)).add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False).sign(ca_key, None))
    out.mkdir(parents=True, exist_ok=True)
    (out / "chain.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM) + (ca_dir / "ca.crt").read_bytes())
    (out / "key.pem").write_bytes((out.parent / "srv" / "key.pem").read_bytes())
    return out


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.d = Path(cls.tmp.name)
        CA.init(cls.d / "pki", "Warnings Root", passphrase=None).issue("localhost", "server", ["127.0.0.1"], out=cls.d / "srv")
        cls.expired = leaf(cls.d / "pki", cls.d / "expired", -1)
        cls.soon = leaf(cls.d / "pki", cls.d / "soon", 5)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def config(self, body):
        p = self.d / f"edge-{self._testMethodName}.toml"
        p.write_text(body)
        return checks.config(p)


class DoctorTest(Base):
    def edge_toml(self, folder, extra=""):
        return f'[[edge]]\nname = "web"\nmode = "terminate"\nlisten = "127.0.0.1:0"\ntarget = "127.0.0.1:9"\ncert = "{folder}/chain.pem"\nkey = "{folder}/key.pem"\n{extra}'

    def test_an_expired_certificate_fails_and_says_to_renew(self):
        out = self.config(self.edge_toml("expired"))
        fails = [m for level, m in out if level == "fail"]
        self.assertTrue(any("expired" in m and "renew" in m for m in fails), out)

    def test_a_certificate_ending_within_two_weeks_warns(self):
        out = self.config(self.edge_toml("soon"))
        self.assertTrue(any(level == "warn" and "ends in 5 days" in m for level, m in out), out)

    def test_transition_without_a_public_certificate_says_browsers_will_refuse(self):
        out = self.config(self.edge_toml("srv", 'policy = "transition"\n'))
        warns = [m for level, m in out if level == "warn"]
        self.assertTrue(any("browsers" in m and "fallback_cert" in m and "not private" in m for m in warns), out)
        self.assertFalse(any("fine for browsers" in m for _, m in out))

    def test_transition_with_a_public_certificate_is_not_called_a_browser_problem(self):
        extra = 'policy = "transition"\nfallback_cert = "srv/chain.pem"\nfallback_key = "srv/key.pem"\n'
        out = self.config(self.edge_toml("srv", extra))
        self.assertFalse(any("not private" in m for _, m in out), out)


@unittest.skipIf(REASON, REASON)
class EdgeStartTest(Base):
    def start(self, folder, **kw):
        e = Edge(Route("web", "terminate", "127.0.0.1:0", "127.0.0.1:9", cert=str(self.d / folder / "chain.pem"),
                       key=str(self.d / folder / "key.pem"), **kw))
        with self.assertLogs("acxelin_tls", logging.WARNING) as logs:
            e.start()
        self.addCleanup(e.stop, 1)
        return logs.output

    def test_an_edge_started_with_an_expired_certificate_says_so(self):
        out = self.start("expired")
        self.assertTrue(any("expired" in line and "every client" in line for line in out), out)

    def test_an_edge_started_as_transition_without_a_public_certificate_says_what_browsers_will_show(self):
        out = self.start("srv", policy="transition")
        self.assertTrue(any("fallback_cert" in line and "not private" in line for line in out), out)
