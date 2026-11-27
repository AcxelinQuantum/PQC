"""What a customer sees when things go wrong: each case prints the command's exit code and its last lines."""
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import ENV, EXE, run  # noqa: E402

home = Path(__file__).parent / "homes/qguard"
sc = home / "sc"
E = {"ACXELIN_TLS_CA_PASSPHRASE": "correct horse battery"}


def edge(*args, env=None, seconds=4):
    p = subprocess.Popen([str(EXE["qguard"]), "edge", *args], cwd=sc, env=ENV | (env or {}), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    try:
        out, _ = p.communicate(timeout=seconds)
        return p.returncode, out.strip()
    except subprocess.TimeoutExpired:
        p.terminate()
        out, _ = p.communicate()
        return "still running", out.strip()


def show(title, result):
    code, out = result
    print(f"\n### {title}\n[exit {code}]\n" + "\n".join(out.splitlines()[-6:]))


base = ["--target", "127.0.0.1:18080", "--cert", "apps/chain.pem", "--key", "apps/key.pem"]
show("port already in use (8443 is the running edge)", edge("--listen", "0.0.0.0:8443", *base))
show("target nothing listening (edge starts; first client)", (0, ""))
show("certificate file missing", edge("--listen", "127.0.0.1:8460", "--target", "127.0.0.1:18080", "--cert", "nope/chain.pem", "--key", "apps/key.pem"))
show("key does not match certificate", edge("--listen", "127.0.0.1:8460", "--target", "127.0.0.1:18080", "--cert", "apps/chain.pem", "--key", "partner-c/key.pem"))

# an encrypted key with the wrong passphrase
code, out = run("qguard", "ca", "issue", "server", "enc.audit.test", "--dir", "ca", "--out", "sc/enc", "--key-passphrase-env", "KP", cwd=home,
                env=E | {"KP": "right-key-pass"})
show("encrypted key, passphrase variable missing", edge("--listen", "127.0.0.1:8460", "--target", "127.0.0.1:18080", "--cert", "enc/chain.pem", "--key", "enc/key.pem"))
show("encrypted key, wrong passphrase", edge("--listen", "127.0.0.1:8460", "--target", "127.0.0.1:18080", "--cert", "enc/chain.pem", "--key", "enc/key.pem",
                                             "--key-passphrase-env", "KP", env={"KP": "wrong"}))

# an expired certificate: valid for a fraction of an hour, then wait
code, out = run("qguard", "ca", "issue", "server", "short.audit.test", "--dir", "ca", "--out", "sc/short", "--hours", "0.002", cwd=home, env=E)
print("\n### issue a 7-second certificate\n", code, out[-300:])
time.sleep(9)
show("edge with an expired certificate", edge("--listen", "127.0.0.1:8461", "--target", "127.0.0.1:18080", "--cert", "short/chain.pem", "--key", "short/key.pem"))
code, out = run("qguard", "doctor", "--ca", "ca", cwd=home)
print("\n### doctor after that\n", out[-700:])

# no OpenSSL 3.5: point at an empty folder and drop OpenSSL from PATH
empty = home / "empty"
empty.mkdir(exist_ok=True)
path = os.pathsep.join(p for p in os.environ["PATH"].split(os.pathsep) if "openssl" not in p.lower())
show("no OpenSSL 3.5 (edge)", edge("--listen", "127.0.0.1:8462", *base, env={"ACXELIN_OPENSSL": str(empty), "PATH": path}))
code, out = run("qguard", "doctor", cwd=home, env={"ACXELIN_OPENSSL": str(empty), "PATH": path})
show("no OpenSSL 3.5 (doctor)", (code, out))
code, out = run("qguard", "try", cwd=home, env={"ACXELIN_OPENSSL": str(empty), "PATH": path})
show("no OpenSSL 3.5 (try)", (code, out))
