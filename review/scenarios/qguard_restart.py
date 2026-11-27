import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from harness import Console, shot  # noqa: E402

home = Path(__file__).parent / "homes" / "qguard"
subprocess.run(["powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'audit\\\\homes\\\\qguard' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"])
c = Console("qguard", home, 8900)
with sync_playwright() as pw:
    b = pw.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 900})
    page.goto(c.url())
    page.wait_for_selector("#unlock-pass")
    shot(page, "qguard", "15-unlock-after-restart")
    page.fill("#unlock-pass", "wrong")
    page.get_by_role("button", name="Unlock").click()
    page.wait_for_timeout(1500)
    print("wrong passphrase:", page.locator("#msg").inner_text())
    shot(page, "qguard", "16-wrong-passphrase")
    # same tab, new link (hash-only navigation)
    page.goto(c.url())
    page.wait_for_timeout(1500)
    print("same tab after pasting a new link still shows:", page.locator("#app").inner_text()[:80].replace("\n", " "))
    page.fill("#unlock-pass", "correct horse battery")
    page.get_by_role("button", name="Unlock").click()
    page.wait_for_selector("#tab-certs")
    print("unlocked ok")
    b.close()
c.stop()
