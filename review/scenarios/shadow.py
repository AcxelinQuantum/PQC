"""Shadow mode, then enforcement: a classical client before and after, the edge's report, and what the console shows."""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from harness import ENV, EXE, Console, shot, wait_port  # noqa: E402

A = Path(__file__).parent
SC = A / "homes/qguard/sc"
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def edge(shadow):
    args = [str(EXE["qguard"]), "edge", "--listen", "127.0.0.1:8450", "--target", "127.0.0.1:18080", "--policy", "strict",
            "--cert", "apps/chain.pem", "--key", "apps/key.pem", "--fallback-cert", "classical/fullchain.pem", "--fallback-key", "classical/privkey.pem",
            "--metrics", "127.0.0.1:9101"] + (["--shadow"] if shadow else [])
    log = open(A / f"shadow-{shadow}.log", "w")
    p = subprocess.Popen(args, cwd=SC, env=ENV, stdout=log, stderr=subprocess.STDOUT)
    wait_port(8450)
    return p, log


def classical():  # Windows' own TLS (Schannel): no post-quantum key exchange
    r = subprocess.run(["curl.exe", "-sS", "-k", "--ssl-no-revoke", "-o", "NUL", "-w", "%{http_code}", "--resolve", "static.audit.test:8450:127.0.0.1",
                        "https://static.audit.test:8450/"], capture_output=True, text=True)
    return (r.stdout + " " + r.stderr.strip()[:120]).strip()


home = A / "homes/qguard"
for shadow in (True,):
    p, log = edge(shadow)
    print(f"--- shadow={shadow}: classical client ->", classical())
    time.sleep(1)
    print("status:", json.dumps(json.loads(DIRECT.open("http://127.0.0.1:9101/status").read())))
    if shadow:
        c = Console("qguard", home, 8901, env={"ACXELIN_TLS_CA_PASSPHRASE": "correct horse battery"})
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_page(viewport={"width": 1280, "height": 900})
            page.goto(c.url())
            page.get_by_role("tab", name="Edges").click()
            page.fill("#edge-url", "http://127.0.0.1:9101")
            page.get_by_role("button", name="Add edge").click()
            page.wait_for_timeout(7000)
            print("console edge view:", page.locator("#edge-list").inner_text().replace("\n", " | "))
            shot(page, "qguard", "17-edges-shadow-mode")
            b.close()
        c.stop()
    p.terminate()
    p.wait(10)
    log.close()
    print("edge log:", (A / f"shadow-{shadow}.log").read_text()[-600:])
