"""QCertificate beyond the console: EST enrollment, OCSP stapling, CRL publishing with crl_url, exports. Prints each command and result."""
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import ENV, EXE, run, wait_port  # noqa: E402

home = Path(__file__).parent / "homes/qguard"
E = {"ACXELIN_TLS_CA_PASSPHRASE": "correct horse battery"}
procs = []


def step(title, *args, env=None):
    code, out = run("qguard", *args, cwd=home, env=(E | (env or {})))
    print(f"\n$ acxelin-qguard {' '.join(args)}\n[{code}] {out[-900:]}")
    return code, out


def bg(name, *args, port):
    log = open(home / f"{name}.log", "w")
    p = subprocess.Popen([str(EXE["qguard"]), *args], cwd=home, env=ENV | E, stdout=log, stderr=subprocess.STDOUT)
    procs.append(p)
    try:
        wait_port(port, 20)
    except TimeoutError:
        log.flush()
        print(f"{name} did not start:", (home / f"{name}.log").read_text()[-500:])
    return p


try:
    # EST: the service, a one-time token, enrollment from "another machine"
    bg("est", "ca", "serve", "--dir", "ca", "--listen", "127.0.0.1:9443", "--cert", "sc/apps/chain.pem", "--key", "sc/apps/key.pem", port=9443)
    code, out = step("token", "ca", "token", "server", "device1.audit.test", "--dir", "ca")
    token = out.strip().splitlines()[-1].strip().split()[-1]
    step("enroll", "ca", "enroll", "https://127.0.0.1:9443", "--cn", "device1.audit.test", "--out", "est/device1", "--ca", "ca/ca.crt",
         "--server-name", "apps.audit.test", env={"ACXELIN_TLS_ENROLL_TOKEN": token})
    step("enroll again with the same token", "ca", "enroll", "https://127.0.0.1:9443", "--cn", "device1.audit.test", "--out", "est/device1b",
         "--ca", "ca/ca.crt", "--server-name", "apps.audit.test", env={"ACXELIN_TLS_ENROLL_TOKEN": token})
    step("renew over EST", "ca", "enroll", "https://127.0.0.1:9443", "--renew", "est/device1", "--ca", "ca/ca.crt", "--server-name", "apps.audit.test")

    # OCSP staple for the apps certificate
    step("ocsp", "ca", "ocsp", "--dir", "ca", "--cert", "sc/apps/chain.pem", "--out", "sc/ocsp")

    # publish the CRL and CA certificate over HTTP, read them like an edge would
    bg("publish", "ca", "publish", "--dir", "ca", "--listen", "127.0.0.1:18090", port=18090)
    for path in ("/crl.pem", "/ca.crt", "/"):
        try:
            r = urllib.request.build_opener(urllib.request.ProxyHandler({})).open("http://127.0.0.1:18090" + path, timeout=5)
            print(f"GET {path}: {r.status} {r.headers.get('Content-Type')} {len(r.read())} bytes")
        except Exception as e:
            print(f"GET {path}: {e}")

    # a CSR made elsewhere, signed by the CA
    step("csr", "ca", "csr", "csr1.audit.test", "--out", "csr1")
    step("sign-csr", "ca", "sign-csr", "--help")
    step("list", "ca", "list", "--dir", "ca")
finally:
    for p in procs:
        p.terminate()
print("\nexports available: files in an issued folder ->", sorted(p.name for p in (home / "sc/apps").iterdir()))
print("est folder ->", sorted(str(p.relative_to(home)) for p in (home / "est").rglob("*") if p.is_file()) if (home / "est").exists() else "none")
