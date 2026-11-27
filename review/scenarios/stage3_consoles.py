"""Stage 3: every screen of the reworked QReadiness and QVPN consoles, with real work done, for the second slop review.
Run from the checkout: python review/scenarios/stage3_consoles.py  (saves to review/screenshots/stage3/)"""
import sys
import tempfile
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "review/screenshots/stage3"
sys.path.insert(0, str(ROOT / "tools"))
from capture_screens import serve  # noqa: E402


def snap(page, product, name, width=1280):
    (OUT / product).mkdir(parents=True, exist_ok=True)
    page.set_viewport_size({"width": width, "height": 900})
    page.wait_for_timeout(900)
    page.screenshot(path=str(OUT / product / f"{name}.png"), full_page=True)


with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
    tmp, b = Path(tmp), p.chromium.launch()
    from acxelin_readiness import console as rc
    app = rc.build(tmp / "r")
    app.routes[("POST", "/api/setup")]({"directory": str(ROOT / "products/readiness/examples")})
    for i, name in enumerate(("payments-api", "customer-portal")):
        app.routes[("POST", "/api/projects/register")]({"name": name})
        app.routes[("POST", "/api/projects/select")]({"project": i})
        app.routes[("POST", "/api/projects/scan")]({"project": i})
        while app.routes[("GET", "/api/projects/status")]({})[1]["running"]:
            time.sleep(0.2)
    server, base = serve(app, tmp / "r")
    page = b.new_page()
    page.goto(f"{base}/#{app.sessions.ticket()}")
    page.get_by_text("to fix now").first.wait_for(timeout=60000)
    snap(page, "qreadiness", "01-project-result")
    for i, tab in enumerate(("Overview", "Endpoints", "What it tracks"), 2):
        page.get_by_role("tab", name=tab).click()
        snap(page, "qreadiness", f"{i:02d}-{tab.lower().replace(' ', '-')}")
    page.get_by_role("tab", name="Projects").click()
    snap(page, "qreadiness", "05-project-result-390", 390)
    page.close()
    server.shutdown()

    from acxelin_vpn import app as va
    from acxelin_vpn import console as vc
    app = vc.build(tmp / "v")
    call = lambda path, body=None: app.routes[("POST" if body is not None else "GET", path)](body or {})
    call("/api/ca/create", {"name": "Acme Corp VPN CA"})
    call("/api/people/settings", {"enroll": "https://vpn.example.com:9443", "gateway": "vpn.example.com:7444"})
    for person in ("alice", "bob"):
        call("/api/people/invite", {"name": person, "hours": 72})
    server, base = serve(app, tmp / "v")
    page = b.new_page()
    page.goto(f"{base}/#{app.sessions.ticket()}")
    page.get_by_role("tab", name="Sites").wait_for()
    for i, tab in enumerate(("Sites", "People", "Health"), 1):
        page.get_by_role("tab", name=tab).click()
        snap(page, "qvpn", f"{i:02d}-{tab.lower()}")
    page.get_by_role("tab", name="People").click()
    snap(page, "qvpn", "04-people-390", 390)
    page.close()
    server.shutdown()
    window = va.App(folder=tmp / "person", apply=False)
    server = va.serve(window)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    page = b.new_page()
    page.goto(f"http://127.0.0.1:{server.server_address[1]}/#{window.ticket()}")
    snap(page, "qvpn", "05-app")
    page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
    snap(page, "qvpn", "06-app-without-link")
    server.shutdown()
    b.close()
print("saved to", OUT)
