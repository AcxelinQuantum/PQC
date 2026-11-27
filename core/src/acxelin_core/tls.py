"""TLS 1.3 contexts and a client helper on top of the OpenSSL bridge. What a peer may negotiate is a `Policy` the caller passes in."""
import re
import socket
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509

from .http import hostport, http_server, listen, nodelay  # noqa: F401  (the reference keeps these beside the contexts)
from .openssl import Connection, Context, OpenSSLUnavailable, TLSError, lib  # noqa: F401
from .pki import algorithm_of


@dataclass(frozen=True)
class Policy:
    """What a peer may negotiate: key-exchange groups, signature algorithms (None allows any) and cipher suites.
    `cert_algorithm`, when set, is the only certificate key algorithm that can work under the policy; a certificate with another
    one is refused at start-up, with a message that says why, instead of failing every handshake."""
    name: str
    groups: str
    sigalgs: str | None
    ciphersuites: str
    cert_algorithm: str | None = None


def _check_certificate(p, cert):
    if not p.cert_algorithm or not cert:
        return
    try:
        leaf = x509.load_pem_x509_certificates(Path(cert).read_bytes())[0]
    except (OSError, ValueError):
        return
    found = algorithm_of(leaf.public_key())
    if found != p.cert_algorithm:
        raise TLSError(f"the {p.name} policy needs an {p.cert_algorithm} certificate, but {cert} holds {found or 'a non-ML-DSA key'}; "
                       f"issue one with --algorithm {p.cert_algorithm}")


def server_context(policy, cert, key, ca=None, require_client_cert=False, key_passphrase=None, request_client_cert=False,
                   any_purpose=False, fallback=None):
    """`request_client_cert` asks for a client certificate and verifies it if one is sent, but lets clients without one in.
    `any_purpose` accepts a client certificate whose extended key usage is not clientAuth (the chain is still verified).
    `fallback` (cert, key) is a trusted classical certificate, preferred for clients offering both signature families. It needs
    a policy that allows classical signatures; clients offering only ML-DSA still get the primary certificate."""
    if (require_client_cert or request_client_cert) and not ca:
        raise TLSError("checking client certificates needs the CA that issued them")
    if fallback and policy.sigalgs:
        raise TLSError(f"a fallback certificate needs a policy that allows classical signatures; {policy.name} only allows {policy.sigalgs}")
    _check_certificate(policy, cert)
    return Context(True, policy.groups, policy.sigalgs, policy.ciphersuites, cert, key, key_passphrase, ca, True, require_client_cert,
                   request_client_cert, any_purpose, fallback)


def client_context(policy, ca=None, cert=None, key=None, key_passphrase=None, verify=True):
    if verify and not ca:
        raise TLSError("verifying the server needs a CA certificate (or pass verify=False for a probe)")
    _check_certificate(policy, cert)
    return Context(False, policy.groups, policy.sigalgs, policy.ciphersuites, cert, key, key_passphrase, ca, verify)


def public_roots(path):
    """Write the public certificate authorities this computer trusts (the Windows store on Windows, the system bundle elsewhere)
    to `path` as PEM, for a client that should trust what a browser on this machine trusts. Returns the path."""
    import ssl
    ctx = ssl.create_default_context()
    ders = ctx.get_ca_certs(binary_form=True)
    if not ders:  # roots kept as one file per authority (Ubuntu's /etc/ssl/certs) are not listed by Python's ssl: read them
        paths = ssl.get_default_verify_paths()
        files = [Path(f) for f in (paths.cafile, paths.openssl_cafile) if f and Path(f).is_file()]
        for d in (paths.capath, paths.openssl_capath):
            if d and Path(d).is_dir():
                files += sorted(p for p in Path(d).iterdir() if p.is_file())
        for f in files:
            try:
                text = f.read_bytes()
            except OSError:
                continue
            ders += [ssl.PEM_cert_to_DER_cert(m.decode()) for m in
                     re.findall(rb"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", text, re.S)]
        ders = list(dict.fromkeys(ders))
    if not ders:
        try:  # where the system store cannot be listed, the usual Python bundle, if it is installed
            import certifi
            ctx.load_verify_locations(certifi.where())
            ders = ctx.get_ca_certs(binary_form=True)
        except (ImportError, OSError):
            pass
    if not ders:
        raise TLSError("could not read the certificate authorities this computer trusts; pass the CA file with --ca")
    Path(path).write_text("".join(ssl.DER_cert_to_PEM_cert(d) for d in ders), encoding="ascii")
    return path


def connect(host, port, ctx, server_name=None, timeout=10.0):
    """Open a verified TLS 1.3 connection; the certificate must match `server_name` (defaults to `host`)."""
    sock = nodelay(_dial(host, port, timeout))
    return ctx.wrap(sock, server_name or host, timeout)


def _dial(host, port, timeout):
    """For "localhost", IPv4 first: Windows tries ::1 first and, when the server listens on 127.0.0.1 only, waits two
    seconds after the refusal before trying IPv4."""
    if host.lower() != "localhost":
        return socket.create_connection((host, port), timeout=timeout)
    try:
        return socket.create_connection(("127.0.0.1", port), timeout=timeout)
    except ConnectionRefusedError as refused:
        try:
            return socket.create_connection(("::1", port), timeout=timeout)
        except OSError:
            raise refused from None  # no IPv6 here, or nothing there either: the refusal is the answer
