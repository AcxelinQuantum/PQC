"""Stage 3: the Stage 1 QGuard scenarios again, done the way a customer now does them, in the console. Run from the checkout:
ACXELIN_AUDIT_CHECKOUT=1 python review/scenarios/stage3_qguard.py   (needs the echo and WordPress containers on 18081 and 18083)

Prints one line per check, PASS or FAIL with what was seen, and saves screenshots to review/screenshots/stage3/qguard."""
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from harness import CHECKOUT, Console, run, shot  # noqa: E402
from capture_screens import public_certificate  # noqa: E402

assert CHECKOUT, "set ACXELIN_AUDIT_CHECKOUT=1: Stage 3 checks this checkout"
results = []
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def check(name, ok, seen=""):
    results.append((name, bool(ok), seen))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {seen}"[:400], flush=True)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def curl(*args):
    """curl with OpenSSL 3.5 in a container (an independent post-quantum client), reaching this machine as host.docker.internal."""
    p = subprocess.run(["docker", "run", "--rm", "-v", f"{ca_dir}:/ca:ro", "curlimages/curl", "-sS", "--cacert", "/ca/ca.crt", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return p.stdout + p.stderr


tmp = Path(tempfile.mkdtemp())
home = tmp / "home"
c = Console("qguard", home, 8930)
ca_dir = home / "ca"
port = free_port()
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--host-resolver-rules=MAP *.audit.test 127.0.0.1"])
    page = b.new_page(viewport={"width": 1280, "height": 900})
    page.goto(c.url())
    page.get_by_role("heading", name="Create your certificate authority").wait_for()
    shot(page, "qguard", "01-first-run")
    page.get_by_label("Name", exact=True).fill("Acme Corp Root CA")
    page.get_by_role("button", name="Create certificate authority").click()
    page.get_by_role("heading", name="Protect your first service").wait_for()
    shot(page, "qguard", "02-protect-first-service")
    check("first run goes from the CA straight to protecting a service", True)

    public = public_certificate(tmp / "public", "static.audit.test")
    for kind, host, target, watch, extra in (
            ("Public website", "static.audit.test", "127.0.0.1:18081", None, {"pub": str(public / "fullchain.pem"), "key": str(public / "privkey.pem")}),
            ("Public website", "wp.audit.test", "127.0.0.1:18083", None, {}),
            ("Internal app or API", "echo.audit.test", "127.0.0.1:18081", True, {})):
        if page.get_by_role("button", name="Protect a service").count():
            page.get_by_role("button", name="Protect a service").click()
        page.get_by_label(kind).check()
        page.get_by_label("Address people use").fill(host)
        page.get_by_label("Port", exact=True).fill(str(port))
        page.get_by_label("Where it runs now").fill(target)
        if extra:
            page.get_by_label("Full chain file").fill(extra["pub"])
            page.get_by_label("Its key file").fill(extra["key"])
        if watch is not None:
            page.get_by_label("Start by watching").set_checked(watch)
        page.get_by_role("button", name="Protect service").click()
        page.get_by_role("heading", name=f"{host}:{port}").wait_for()
    shot(page, "qguard", "03-three-services")
    text = page.inner_text("main")
    check("a website without a public certificate says what browsers will show", "not private" in text and "wp.audit.test" in text)

    settings = home / "edge.toml"
    settings.write_text(settings.read_text().replace("127.0.0.1:9100", f"127.0.0.1:{free_port()}"))
    page.get_by_role("button", name="Start QGuard on this computer").click()
    page.get_by_text("QGuard is running").first.wait_for(timeout=30000)
    check("QGuard starts from the console", True)
    shot(page, "qguard", "04-running")

    # forwarded headers, redirects and WordPress: the Stage 1 breakages
    echo = curl("--connect-to", f"echo.audit.test:{port}:host.docker.internal:{port}", f"https://echo.audit.test:{port}/hello", "-H", "X-Forwarded-For: 10.6.6.6")
    check("the app receives X-Forwarded-For/Proto/Host and never the client's own", "X-Forwarded-Proto: https" in echo and "X-Forwarded-Host: echo.audit.test" in echo
          and "10.6.6.6" not in echo, " | ".join(line for line in echo.splitlines() if "Forwarded" in line))
    wp = curl("--connect-to", f"wp.audit.test:{port}:host.docker.internal:{port}", "-o", "/dev/null", "-w", "%{http_code} %{redirect_url}", f"https://wp.audit.test:{port}/")
    check("WordPress redirects to https, not http (Stage 1: http and ERR_CONNECTION_RESET)", wp.strip().startswith("302 https://wp.audit.test"), wp.strip())
    ctx = b.new_context(ignore_https_errors=True)
    p2 = ctx.new_page()
    try:
        p2.goto(f"https://wp.audit.test:{port}/", timeout=30000)
        check("WordPress opens in Chrome through QGuard", "install" in p2.url and "WordPress" in p2.title(), f"{p2.url} {p2.title()!r}")
        shot(p2, "qguard", "05-wordpress-through-qguard", full=False)
    except Exception as e:  # noqa: BLE001
        check("WordPress opens in Chrome through QGuard", False, str(e).splitlines()[0])
    ctx.close()
    smuggle = curl("--connect-to", f"echo.audit.test:{port}:host.docker.internal:{port}", f"https://echo.audit.test:{port}/", "-H", "Content-Length: 4",
                   "-H", "Transfer-Encoding: chunked", "--data-binary", "0\r\n\r\n", "-o", "/dev/null", "-w", "%{http_code}")
    check("a request-smuggling shape gets 400", smuggle.strip().endswith("400"), smuggle.strip()[-40:])

    # watch mode in the console, then enforcement without taking the service down
    from acxelin_core import tls
    classical = tls.Context(False, "X25519", None, "TLS_AES_256_GCM_SHA384", ca=str(ca_dir / "ca.crt"))
    with tls.connect("127.0.0.1", port, classical, "echo.audit.test", 5):
        time.sleep(0.5)
    page.get_by_role("button", name="Refresh").click()
    page.get_by_text("would be refused once enforcing").first.wait_for(timeout=10000)
    svc = page.inner_text("main")
    check("watch mode shows who would be refused and why (Stage 1: counted as refused)", "no post-quantum key exchange offered" in svc and "1 refused" not in svc)
    shot(page, "qguard", "06-watching-reports")
    page.get_by_role("button", name="Turn on enforcement for echo.audit.test").click()
    page.get_by_role("button", name="Confirm: refuse clients that are not quantum-safe").click()
    page.get_by_text("Enforcing").first.wait_for()
    time.sleep(4)
    try:
        with tls.connect("127.0.0.1", port, classical, "echo.audit.test", 5):
            refused = False
    except (tls.TLSError, OSError):
        refused = True
    still = curl("--connect-to", f"echo.audit.test:{port}:host.docker.internal:{port}", "-o", "/dev/null", "-w", "%{http_code}", f"https://echo.audit.test:{port}/")
    check("enforcement turns on from the console: classical refused, the service stays up", refused and still.strip() == "200", f"classical refused={refused}, pq={still.strip()}")

    # check a public site and a QGuard service from the console
    page.get_by_role("tab", name="Check a connection").click()
    page.get_by_label("Address", exact=True).fill("www.google.com")
    page.get_by_role("button", name="Check", exact=True).click()
    page.get_by_text("Connected").first.wait_for(timeout=20000)
    seen = page.inner_text("#c-result")
    check("a public site is checked like a browser (Stage 1: could not)", "quantum-safe key exchange, classical certificate (ECDSA)" in seen, seen.splitlines()[0])
    shot(page, "qguard", "07-check-public-site")
    for name in ("Overview", "QCertificate", "Settings"):
        page.get_by_role("tab", name=name, exact=True).click()
        page.wait_for_timeout(1500)
        shot(page, "qguard", f"08-{name.lower()}")
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("tab", name="Services", exact=True).click()
    page.wait_for_timeout(1500)
    shot(page, "qguard", "09-services-390")
    page.get_by_role("tab", name="Services", exact=True).click()
    page.set_viewport_size({"width": 1280, "height": 900})
    page.get_by_role("tab", name="Services", exact=True).click()
    page.get_by_role("button", name="Stop QGuard").click()
    page.get_by_text("QGuard is not running").first.wait_for(timeout=20000)
    b.close()
c.stop()

# the command line, as Stage 1 tried it
code, out = run("qguard", "connect", "www.google.com:443", "--policy", "transition")
check("connect checks a public site without --ca and names the key", code == 0 and "ECDSA" in out and "verdict" in out, next((line for line in out.splitlines() if "verdict" in line), out[-120:]))
code, out = run("qguard", "connect", "www.google.com:443")
check("strict on a public site explains why", code == 1 and "classical certificate" in out, out.splitlines()[-1][:200] if out else "")
code, out = run("qguard", "try")
check("try ends at the console and prints no log lines", code == 0 and "acxelin-qguard console" in out.strip().splitlines()[-1] and " INFO " not in out)
(Path(__file__).parent / "stage3-qguard.json").write_text(json.dumps([{"check": n, "ok": ok, "seen": s} for n, ok, s in results], indent=1))
print(f"\n{sum(ok for _, ok, _ in results)} of {len(results)} passed")
