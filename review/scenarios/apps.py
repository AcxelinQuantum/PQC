"""Real apps behind the edge in Chrome (certificate checks off: browsers cannot verify ML-DSA, see browsers.py), and an idle socket."""
import socket
import ssl
import sys
import time
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from harness import shot  # noqa: E402

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome", args=["--host-resolver-rules=MAP *.audit.test 127.0.0.1"])
    ctx = b.new_context(ignore_https_errors=True, viewport={"width": 1200, "height": 800})
    page = ctx.new_page()

    # WordPress: the first redirect
    hops = []
    page.on("response", lambda r: hops.append(f"{r.status} {r.url} -> {r.headers.get('location', '')}") if 300 <= r.status < 400 else None)
    try:
        page.goto("https://wp.audit.test:8443/", timeout=20000)
        print("wordpress landed on:", page.url, "title:", page.title())
    except Error as e:
        print("wordpress:", str(e).splitlines()[0])
    print("wordpress redirects:", hops)
    shot(page, "apps", "wordpress-first-visit", full=False)
    hops.clear()

    # Grafana: login, then the live websocket
    sockets = []
    page.on("websocket", lambda ws: sockets.append(ws))
    page.goto("https://grafana.audit.test:8443/login", timeout=30000)
    page.fill("input[name=user]", "admin")
    page.fill("input[name=password]", "audit-admin-pass")
    page.click("button[type=submit]")
    page.wait_for_timeout(5000)
    if "skip" in page.content().lower():
        try:
            page.get_by_role("button", name="Skip").click(timeout=3000)
        except Error:
            pass
    page.goto("https://grafana.audit.test:8443/explore", timeout=30000)
    page.wait_for_timeout(6000)
    print("grafana url:", page.url, "title:", page.title())
    print("grafana websockets:", [(w.url, w.is_closed()) for w in sockets])
    shot(page, "apps", "grafana-after-login", full=False)

    # echo server websocket: send and receive
    frames = []
    page2 = ctx.new_page()
    page2.on("websocket", lambda ws: (ws.on("framereceived", lambda f: frames.append(("in", str(f)[:60]))), ws.on("framesent", lambda f: frames.append(("out", str(f)[:60])))))
    page2.goto("https://echo.audit.test:8443/.ws", timeout=20000)
    page2.wait_for_timeout(4000)
    print("echo websocket frames:", frames[:6])
    shot(page2, "apps", "echo-websocket", full=False)
    b.close()

# An idle connection: a browser opens sockets ahead of time and uses them later
ca = Path(__file__).parent / "homes/qguard/ca/ca.crt"
for wait in (25, 40):
    c = ssl.create_default_context(cafile=str(ca))
    c.check_hostname = False
    s = c.wrap_socket(socket.create_connection(("127.0.0.1", 8443), 5), server_hostname="static.audit.test")
    time.sleep(wait)
    try:
        s.sendall(b"GET / HTTP/1.1\r\nHost: static.audit.test\r\nConnection: close\r\n\r\n")
        data = s.recv(200)
        print(f"idle {wait}s then request:", data[:40] or b"<closed by edge>")
    except OSError as e:
        print(f"idle {wait}s then request: {type(e).__name__} {e}")
    s.close()
