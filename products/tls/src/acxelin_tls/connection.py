"""What a TLS connection means for a customer: the key types by name, a one-line verdict, and why a connection failed.
Shared by `acxelin-qguard connect` and the console's connection check."""
from acxelin_core import tls

from . import policies

KEYS = {"1.2.840.10045.2.1": "ECDSA", "1.2.840.113549.1.1.1": "RSA", "1.3.101.112": "Ed25519", "1.3.101.113": "Ed448"}
PQ_GROUPS = set(policies.PQC_GROUPS.split(":")) | {"MLKEM1024"}


def key_name(key):
    return KEYS.get(key, key) if key else key


def post_quantum_certificate(key):
    return bool(key) and str(key).startswith("ML-DSA")


def verdict(info):
    """One line: is the key exchange quantum-safe, and is the certificate."""
    group, key = info.get("group"), key_name(info.get("peer_key"))
    exchange = "quantum-safe key exchange" if group in PQ_GROUPS else f"classical key exchange ({group}): recorded traffic could be decrypted later"
    if not key:
        return exchange
    return f"{exchange}, {'quantum-safe' if post_quantum_certificate(key) else 'classical'} certificate ({key})"


def probe(host, port, name, timeout=3.0):
    """What the server negotiates with a client that accepts anything and checks nothing: tells "classical certificate" and
    "only classical key exchange" apart from "a certificate from another authority". None when even that fails."""
    ctx = tls.client_context(policies.policy("transition"), verify=False)
    try:
        with tls.connect(host, port, ctx, name, timeout) as c:
            info = c.info()
            return info | {"peer_key": key_name(info.get("peer_key"))}
    except (tls.TLSError, OSError):
        return None
    finally:
        ctx.close()


def why_failed(host, port, name, policy, error, public=False):
    """The failure in words, from what the server offers to a client that checks nothing."""
    seen = probe(host, port, name)
    if not seen:
        return str(error)
    group, key = seen.get("group"), seen.get("peer_key")
    offers = f"a post-quantum key exchange ({group})" if group in PQ_GROUPS else f"only a classical key exchange ({group})"
    if policy in ("strict", "cnsa2") and key and not post_quantum_certificate(key):
        return (f"{host} offers {offers} but a classical certificate ({key}); policy {policy} needs an ML-DSA certificate, which "
                f"public websites do not have yet. To see the rest of the connection, use --policy transition")
    if group not in PQ_GROUPS and policy != "transition":
        return f"{host} offers {offers}: a quantum computer could decrypt traffic recorded today. Policy {policy} refuses it"
    if public:
        return (f"{host}'s certificate ({key}) is not from one of the public certificate authorities this computer trusts; for a "
                "service with a certificate from your own certificate authority, pass its CA file with --ca")
    return (f"{host}'s certificate ({key}) is not from the certificate authority you gave (or is for another name: use "
            f"--server-name); it offers {offers}")
