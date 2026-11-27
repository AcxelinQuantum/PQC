"""What real browsers show against each QGuard policy. Records the error, a screenshot, and the key exchange the edge saw."""
import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from harness import shot  # noqa: E402

DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))
CASES = [("strict", "https://static.audit.test:8443/", "static"), ("transition+fallback", "https://static.audit.test:8444/", "transition"),
         ("transition-no-fallback", "https://static.audit.test:8447/", "transition-no-fallback"), ("cnsa2", "https://static.audit.test:8445/", "cnsa2"),
         ("mtls-no-client-cert", "https://static.audit.test:8446/", "partner-api")]
ARGS = ["--host-resolver-rules=MAP *.audit.test 127.0.0.1"]
which = sys.argv[1:] or ["chrome", "msedge"]


def status():
    return json.loads(DIRECT.open("http://127.0.0.1:9100/status", timeout=3).read())


def delta(before, after, route):
    b, a = before[route], after[route]
    out = {k: a.get(k, 0) - b.get(k, 0) for k in a if isinstance(a.get(k), int) and a.get(k, 0) != b.get(k, 0) and k != "active"}
    g = {k: v - b.get("groups", {}).get(k, 0) for k, v in a.get("groups", {}).items() if v != b.get("groups", {}).get(k, 0)}
    return out | ({"groups": g} if g else {})


results = []
with sync_playwright() as pw:
    for ch in which:
        browser = pw.chromium.launch(channel=ch, args=ARGS)
        print(ch, browser.version, flush=True)
        for label, url, route in CASES:
            row = {"browser": f"{ch} {browser.version}", "case": label}
            for verify in (True, False):
                ctx = browser.new_context(ignore_https_errors=not verify, viewport={"width": 1100, "height": 700})
                page = ctx.new_page()
                before = status()
                try:
                    resp = page.goto(url, timeout=15000)
                    row["checked" if verify else "unchecked"] = f"loaded {resp.status}: {page.title()!r}"
                except Error as e:
                    row["checked" if verify else "unchecked"] = str(e).split("\n")[0][:160]
                if verify:
                    page.wait_for_timeout(600)
                    shot(page, "browsers", f"{ch}-{label}", full=False)
                    try:
                        row["page_text"] = page.locator("body").inner_text(timeout=2000)[:300].replace("\n", " | ")
                    except Error:
                        pass
                page.wait_for_timeout(300)
                row["edge_saw_" + ("checked" if verify else "unchecked")] = delta(before, status(), route)
                ctx.close()
            results.append(row)
            print(json.dumps(row, indent=1), flush=True)
        browser.close()
Path(__file__).with_name("browsers-" + "-".join(which) + ".json").write_text(json.dumps(results, indent=1))
