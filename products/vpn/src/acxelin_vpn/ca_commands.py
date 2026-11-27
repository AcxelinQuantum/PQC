"""The certificate authority the VPN needs: gateways, sites and people get ML-DSA certificates from it, invitations enroll
against its EST service, and its revocation list cuts tunnels."""
import json
import os
from pathlib import Path

from acxelin_core.cli import ask, positive, run_until_signal
from acxelin_core.config import env_passphrase
from acxelin_core.pki import ALGORITHMS, CA, CA_ALGORITHMS, REASONS, CAError, encrypted

from . import audit

CA_PASS_ENV = "ACXELIN_VPN_CA_PASSPHRASE"
# One statement of how long a revocation takes, for the CLI and the console (the README and manual say the same).
REVOCATION = ("A gateway that reads this crl.pem cuts the site's tunnel or the person's WireGuard peer within 15 seconds; one that "
              "fetches it with crl_url needs up to crl_every (60 s by default) more, and others need a copy. A revoked person's app "
              "shows it at its next key renewal, within 2 minutes.")


def ca_passphrase(root, new=False):
    """From ACXELIN_VPN_CA_PASSPHRASE or a prompt, only when the key is or will be encrypted."""
    if not new and not encrypted(Path(root) / "ca.key"):
        return None
    given = os.environ.get(CA_PASS_ENV)
    if given:
        return given.encode()
    if not new:
        return ask("CA passphrase: ", f"set {CA_PASS_ENV}")
    instead = f"set {CA_PASS_ENV}, or pass --no-encrypt to leave the CA key unencrypted"
    p1, p2 = ask("New CA passphrase: ", instead), ask("Repeat: ", instead)
    if p1 != p2:
        raise CAError("the passphrases do not match")
    return p1


def console_home():
    return Path(os.environ.get("ACXELIN_VPN_HOME") or Path.home() / ".acxelin-vpn" / "console")


def consoles_ca(a):
    """The console's CA folder when this command uses the default `./pki`, which is not here, and the console has a CA; else None.
    The default stays `pki` (decision 8): this only says where the other one is."""
    there = console_home() / "ca"
    return there if a.dir == "pki" and not Path("pki/ca.crt").exists() and (there / "ca.crt").exists() else None


def require_ca(a):
    there = consoles_ca(a)
    if there:
        raise ValueError(f"there is no certificate authority in ./pki; the console's is in {there}: add --dir \"{there}\" to use it")


def cmd_ca(a):
    if a.ca_cmd == "init":
        there = consoles_ca(a)
        ca = CA.init(a.dir, a.name, a.algorithm, a.days, None if a.no_encrypt else ca_passphrase(a.dir, new=True))
        print(f"created {ca.algorithm} root '{a.name}' in {a.dir}; gateways and people trust {ca.anchor}, gateways check {Path(a.dir) / 'crl.pem'}\n"
              f"next: acxelin-qvpn ca issue site GATEWAY-NAME --san ADDRESS --dir {a.dir}")
        if there:
            print(f"note: this is a second CA; the console's is in {there}. To issue from that one instead, use --dir \"{there}\".")
        return 0
    require_ca(a)
    ca = CA(a.dir, None if a.ca_cmd == "list" else ca_passphrase(a.dir))
    if a.ca_cmd == "issue":
        out, r = ca.issue(a.common_name, a.kind, a.san, a.days, a.algorithm, a.out, env_passphrase(a.key_passphrase_env))
        print(f"issued {r.kind} certificate {r.serial} for {r.common_name} ({r.algorithm}), valid until {r.not_after}")
        print(f"  {out / 'cert.pem'}\n  {out / 'chain.pem'}  (certificate + CA: what a gateway presents)\n  {out / 'key.pem'}")
    elif a.ca_cmd == "revoke":
        ca.revoke(a.serial, a.reason)
        r = ca.find(a.serial)
        audit.record(a.dir, "revoke", name=r.common_name, serial=r.serial, reason=a.reason)
        print(f"revoked {r.serial}; {Path(a.dir) / 'crl.pem'} updated. {REVOCATION}")
    elif a.ca_cmd == "crl":
        ca.crl(a.days)
        print(f"wrote {Path(a.dir) / 'crl.pem'}")
    elif a.ca_cmd == "serve":
        from cryptography.x509 import load_pem_x509_certificate
        from acxelin_core.pki.est import fingerprint, serve
        srv = serve(a.dir, a.listen, a.cert, a.key, ca_passphrase(a.dir), env_passphrase(a.key_passphrase_env))
        print(f"EST enrollment on https://{a.listen}/.well-known/est for `acxelin-qvpn invite --enroll`; CA fingerprint:\n"
              f"{fingerprint(load_pem_x509_certificate(ca.anchor.read_bytes()))}")
        run_until_signal(srv.serve_forever, srv.stop)
    elif a.ca_cmd == "maintain":
        renewed, skipped = ca.maintain(a.renew_within, a.crl_days)
        for r in renewed:
            print(f"renewed {r.common_name} -> {r.serial[:16]} in {r.path}, valid until {r.not_after[:10]}")
        for r in skipped:
            print(f"NOT renewed {r.common_name} ({r.serial[:16]}, expires {r.not_after[:10]}): its key is encrypted; renew it by hand")
        print(f"CRL re-signed, valid {a.crl_days} days")
        return 1 if skipped else 0
    elif a.ca_cmd == "list":
        rows = ca.expiring(a.expiring) if a.expiring is not None else ca.records()
        if a.json:
            print(json.dumps([vars(r) for r in rows], indent=1))
        for r in [] if a.json else rows:
            print(f"{r.serial[:16]:16}  {r.status:7}  {r.kind:6}  {r.not_after[:10]}  {r.algorithm:9}  {r.common_name}  {' '.join(r.names)}")
    return 0


def add(sub, common):
    ca = sub.add_parser("ca", help="the certificate authority for gateways, sites and people (ML-DSA), and its enrollment service").add_subparsers(dest="ca_cmd", required=True)
    p = ca.add_parser("init", parents=[common], help="create the VPN's certificate authority",
                      epilog='example: acxelin-qvpn ca init --name "Example VPN Root" --dir pki')
    p.add_argument("--name", required=True, help="the CA's name, shown in every certificate it issues")
    p.add_argument("--algorithm", choices=CA_ALGORITHMS, default="ML-DSA-87", help="SLH-DSA keys need OpenSSL 3.5+")
    p.add_argument("--days", type=int, default=3650, help="the CA certificate's lifetime (default: 3650, ten years)")
    p.add_argument("--no-encrypt", action="store_true",
                   help=f"leave the CA key unencrypted (by default it is encrypted, passphrase from {CA_PASS_ENV} or a prompt)")
    p = ca.add_parser("issue", parents=[common], help="issue a key and certificate for a gateway, a site or a person",
                      epilog="example: acxelin-qvpn ca issue site hq.example --san 198.51.100.1 --dir pki --out hq")
    p.add_argument("kind", choices=["site", "server", "client"],
                   help="site: an IPsec gateway (both ends); server: a service people's computers connect to, the WireGuard gateway or "
                        "the enrollment service (ca serve); client: a person")
    p.add_argument("common_name", help="the gateway, site or person it certifies")
    p.add_argument("--san", action="append", default=[], help="DNS name or IP (repeatable)")
    p.add_argument("--algorithm", choices=list(ALGORITHMS), default="ML-DSA-65")
    p.add_argument("--days", type=int, default=397)
    p.add_argument("--out", help="folder for cert.pem, chain.pem and key.pem")
    p.add_argument("--key-passphrase-env", help="encrypt the new key with the passphrase in this environment variable")
    p = ca.add_parser("revoke", parents=[common], help="revoke a certificate: its tunnels are cut and it gets no new keys")
    p.add_argument("serial")
    p.add_argument("--reason", default="unspecified", choices=["unspecified", *REASONS],
                   help="recorded in the CRL; keyCompromise when the key was stolen or exposed")
    p = ca.add_parser("crl", parents=[common], help="re-sign the revocation list (do this before it expires)")
    p.add_argument("--days", type=positive(int), default=7, help="how long the CRL is valid (default: 7)")
    p = ca.add_parser("maintain", parents=[common], help="renew what expires soon and re-sign the revocation list (run daily)")
    p.add_argument("--renew-within", type=int, default=30, metavar="DAYS", help="renew certificates expiring within DAYS (default: 30)")
    p.add_argument("--crl-days", type=positive(int), default=7, help="how long the re-signed CRL is valid (default: 7 days)")
    p = ca.add_parser("list", parents=[common], help="list issued certificates")
    p.add_argument("--expiring", type=int, metavar="DAYS", help="only those expiring within DAYS")
    p.add_argument("--json", action="store_true")
    p = ca.add_parser("serve", parents=[common], help="the enrollment service invitations use (EST, RFC 7030, over post-quantum TLS)")
    p.add_argument("--listen", default="0.0.0.0:9443", help="host:port (default: every interface, port 9443)")
    p.add_argument("--cert", required=True, help="the service's own server chain.pem")
    p.add_argument("--key", required=True)
    p.add_argument("--key-passphrase-env")
    for c in ca.choices.values():
        c.set_defaults(func=cmd_ca)
