"""QGuard + QCertificate: website pages, then the console as a new customer, screenshotting every screen."""
import json
import shutil
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from harness import REPO, Console, run, shot  # noqa: E402

HOMES = Path(__file__).parent / "homes"
home = HOMES / "qguard"
shutil.rmtree(home, ignore_errors=True)
notes = []


def note(*a):
    line = " ".join(str(x) for x in a)
    notes.append(line)
    print(line, flush=True)


def msg(page):
    return page.locator("#msg").inner_text().strip()


with sync_playwright() as pw:
    b = pw.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 900})

    # --- website
    site = REPO / "build/site"
    for i, name in enumerate(["index", "set-up", "demo", "how-it-works", "security"]):
        page.goto((site / "qguard" / f"{name}.html").as_uri())
        shot(page, "website", f"qguard-{i:02d}-{name}")
    page.goto((site / "index.html").as_uri())
    shot(page, "website", "home")
    note("website: qguard h1 =", page.goto((site / "qguard/index.html").as_uri()) and page.locator("h1").first.inner_text())

    # --- console, first run
    c = Console("qguard", home, 8900)
    page.goto(c.url())
    page.wait_for_selector("#ca-name")
    shot(page, "qguard", "01-first-run-create-ca")
    # create with mismatched passphrases first
    page.fill("#ca-name", "Acme Audit Root CA")
    page.fill("#ca-pass", "correct horse battery")
    page.fill("#ca-pass2", "correct horse batteryX")
    page.get_by_role("button", name="Create certificate authority").click()
    note("mismatch:", msg(page))
    shot(page, "qguard", "02-create-ca-mismatch")
    page.fill("#ca-pass2", "correct horse battery")
    t = time.time()
    page.get_by_role("button", name="Create certificate authority").click()
    page.wait_for_selector("#tab-certs")
    note(f"create CA took {time.time() - t:.1f}s")
    shot(page, "qguard", "03-certificates-empty")

    # issue: invalid name, then server, then client
    page.fill("#cn", "web site.test")
    page.get_by_role("button", name="Issue certificate").click()
    page.wait_for_timeout(500)
    note("bad name:", msg(page))
    page.fill("#cn", "app.audit.test")
    page.fill("#names", "app.audit.test\nlocalhost\n127.0.0.1")
    page.get_by_role("button", name="Issue certificate").click()
    page.wait_for_selector(".ok-msg")
    shot(page, "qguard", "04-issued-server")
    note("issued server result:", page.locator("#issued").inner_text())
    page.select_option("#kind", "client")
    page.fill("#cn", "partner-api-client")
    page.fill("#names", "")
    page.get_by_role("button", name="Issue certificate").click()
    page.locator('#issued', has_text='partner-api-client').wait_for()
    shot(page, "qguard", "05-issued-client")

    # download (no key and with key)
    with page.expect_download() as d:
        page.get_by_role("button", name="Download app.audit.test").click()
    dl = d.value
    note("download filename:", dl.suggested_filename)
    p = HOMES / dl.suggested_filename
    dl.save_as(p)
    import zipfile
    note("zip contents:", zipfile.ZipFile(p).namelist())

    # renew server, revoke client
    page.get_by_role("button", name="Renew app.audit.test").click()
    page.wait_for_timeout(1500)
    shot(page, "qguard", "06-after-renew")
    page.get_by_role("button", name="Revoke partner-api-client").click()
    shot(page, "qguard", "07-revoke-armed", full=False)
    page.get_by_role("button", name="Confirm revoke partner-api-client").click()
    page.wait_for_timeout(1500)
    shot(page, "qguard", "08-after-revoke")
    page.get_by_role("button", name="Run maintenance").click()
    page.wait_for_timeout(1500)
    note("maintenance line:", page.locator("#crl-line").inner_text())

    # edges + test (nothing running yet)
    page.get_by_role("tab", name="Edges").click()
    page.wait_for_selector("#edge-url")
    shot(page, "qguard", "09-edges-empty")
    page.fill("#edge-url", "http://127.0.0.1:9199")
    page.get_by_role("button", name="Add edge").click()
    page.wait_for_timeout(4500)
    note("edge unreachable:", page.locator("#edge-list").inner_text())
    page.fill("#t-target", "127.0.0.1:8443")
    page.get_by_role("button", name="Test connection").click()
    page.wait_for_selector("#t-result .result", timeout=20000)
    note("test nothing listening:", page.locator("#t-result").inner_text())
    shot(page, "qguard", "10-edges-unreachable-and-test-fail")
    page.fill("#t-target", "www.google.com:443")
    page.get_by_role("button", name="Test connection").click()
    page.locator('#t-result .result').wait_for(timeout=20000)
    page.wait_for_timeout(500)
    note("test google strict:", page.locator("#t-result").inner_text())
    shot(page, "qguard", "11-test-public-site")

    page.get_by_role("tab", name="Health").click()
    page.wait_for_selector("#health-list table")
    shot(page, "qguard", "12-health")
    note("health:", page.locator("#health-list").inner_text())

    # mobile width
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("tab", name="Certificates").click()
    page.wait_for_selector("#cert-list")
    page.wait_for_timeout(800)
    shot(page, "qguard", "13-certificates-390")
    page.set_viewport_size({"width": 1280, "height": 900})

    # reuse of the launch link, then restart -> unlock, wrong passphrase
    used = page.url
    p2 = b.new_page()
    p2.goto(used)
    p2.wait_for_timeout(1500)
    note("reused link:", p2.locator("#app").inner_text()[:200])
    shot(p2, "qguard", "14-reused-link")
    p2.close()
    c.stop()
    c = Console("qguard", home, 8900)
    page.goto(c.url())
    page.wait_for_selector("#unlock-pass")
    shot(page, "qguard", "15-unlock-after-restart")
    page.fill("#unlock-pass", "wrong")
    page.get_by_role("button", name="Unlock").click()
    page.wait_for_timeout(1500)
    note("wrong passphrase:", msg(page))
    shot(page, "qguard", "16-wrong-passphrase")
    page.fill("#unlock-pass", "correct horse battery")
    page.get_by_role("button", name="Unlock").click()
    page.wait_for_selector("#tab-certs")
    c.stop()
    b.close()

(HOMES / "qguard-console-notes.txt").write_text("\n".join(notes), encoding="utf-8")
print("files in home:", sorted(str(p.relative_to(home)) for p in home.rglob("*") if p.is_file()))

