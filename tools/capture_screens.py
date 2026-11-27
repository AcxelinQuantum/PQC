"""Make the website's screenshots from the real consoles in this checkout: python tools/capture_screens.py [name ...]

Each console runs in this process with a fresh home and real work done through its own API (a CA, protected services, a
running guard with real connections; invitations; a scan of the product's example project). A headless Chromium takes the
picture, and the PNG records a digest of the files it was made from, which the website tests compare with this checkout.
Needs Playwright with Chromium, and OpenSSL 3.5 (ACXELIN_OPENSSL) for the QGuard picture.
"""
import socket
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site  # noqa: E402

OUT = build_site.ROOT / "website/assets/screens"
SIZE = {"width": 1280, "height": 900}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def save(page, name, clip=None):
    """Save what the page shows (or the `clip` region of it: no local folder path ever goes on the public site)."""
    png = page.screenshot(full_page=False, clip=clip)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_bytes(build_site.with_text(png, build_site.KEY, build_site.digest(name)))
    print(f"wrote {OUT / name}")


def public_certificate(folder, name):
    """An ordinary (ECDSA) certificate and key for `name`, standing in for the site's Let's Encrypt certificate."""
    import datetime as dt
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key, t = ec.generate_private_key(ec.SECP256R1()), dt.datetime.now(dt.timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(t - dt.timedelta(days=1)).not_valid_after(t + dt.timedelta(days=90))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), False).sign(key, hashes.SHA256()))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "fullchain.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (folder / "privkey.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return folder


def serve(app, home):
    from acxelin_core import console as core
    server = core.start(app, home, port=0)
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def qguard(browser, tmp):
    """Three protected services behind a running guard, with real post-quantum connections and one classical client seen in watch mode."""
    from acxelin_core import tls
    from acxelin_tls import console as tc
    from acxelin_tls.edge import Edge, load_config, serve_metrics
    home = tmp / "qguard"
    app = tc.build(home)
    state = app.routes[("GET", "/api/status")].__self__
    call = lambda path, body=None: app.routes[("POST" if body is not None else "GET", path)](body or {})[1]
    call("/api/ca/create", {"name": "Acme Corp Root CA"})
    public = public_certificate(tmp / "public", "shop.example.com")  # a public website is set up with its ordinary public certificate
    for kind, host, target, watch in (("website", "shop.example.com", "127.0.0.1:8080", False), ("app", "intranet.example.com", "127.0.0.1:3000", True),
                                      ("partner", "api.example.com", "127.0.0.1:9000", False)):
        extra = {"public_cert": str(public / "fullchain.pem"), "public_key": str(public / "privkey.pem")} if kind == "website" else {}
        call("/api/services/save", {"kind": kind, "host": host, "port": 443, "target": target, "watch": watch, **extra})  # one port, chosen by name
    metrics_port = free_port()
    settings = home / "edge.toml"
    settings.write_text(settings.read_text().replace("127.0.0.1:9100", f"127.0.0.1:{metrics_port}"))
    routes, _ = load_config(settings)
    edges = [Edge(r).start() for r in routes]
    metrics = serve_metrics(f"127.0.0.1:{metrics_port}", edges, None)
    ca = str(home / "ca" / "ca.crt")
    from acxelin_tls import policies
    for e in edges[:2]:
        for _ in range(3):
            with tls.connect("127.0.0.1", e.port, tls.client_context(policies.policy("strict"), ca), e.route.sni[0], 5):
                time.sleep(0.2)
    with tls.connect("127.0.0.1", edges[1].port, tls.Context(False, "X25519", None, policies.CIPHERSUITES, ca=ca), edges[1].route.sni[0], 5):
        time.sleep(0.3)
    server, base = serve(app, home)
    try:
        page = browser.new_page(viewport=SIZE)
        page.goto(f"{base}/#{app.sessions.ticket()}")
        page.get_by_role("tab", name="Overview").click()
        page.get_by_text("Nothing needs your attention").wait_for()
        page.wait_for_timeout(500)
        bottom = page.get_by_text("Nothing needs your attention").bounding_box()
        save(page, "qguard-console.png", clip={"x": 0, "y": 0, "width": 1280, "height": round(bottom["y"] + bottom["height"] + 40)})
        page.close()
    finally:
        for e in edges:
            e.stop(0)
        metrics.shutdown()
        state._stop()
        server.shutdown()


def qvpn(browser, tmp):
    """The administrator's People view with invitations made, and the person's app before it is set up."""
    from acxelin_vpn import console as vc
    home = tmp / "qvpn"
    app = vc.build(home)
    call = lambda path, body=None: app.routes[("POST" if body is not None else "GET", path)](body or {})
    call("/api/ca/create", {"name": "Acme Corp VPN CA"})
    call("/api/people/settings", {"enroll": "https://vpn.example.com:9443", "gateway": "vpn.example.com:7444"})
    for person in ("alice", "bob"):
        call("/api/people/invite", {"name": person, "hours": 72})
    server, base = serve(app, home)
    try:
        page = browser.new_page(viewport=SIZE)
        page.goto(f"{base}/#{app.sessions.ticket()}")
        page.get_by_role("tab", name="People").click()
        page.get_by_text("alice").first.wait_for()
        page.wait_for_timeout(500)
        save(page, "qvpn-console.png")
        page.close()
    finally:
        server.shutdown()
    import threading
    from acxelin_vpn import app as va
    window = va.App(folder=tmp / "qvpn-person", apply=False)
    server = va.serve(window)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        page = browser.new_page(viewport=SIZE)
        page.goto(f"http://127.0.0.1:{server.server_address[1]}/#{window.ticket()}")
        page.wait_for_timeout(1500)
        save(page, "qvpn-app.png", clip={"x": 150, "y": 0, "width": 980, "height": 460})  # the window, not the empty page under it
        page.close()
    finally:
        server.shutdown()


def qreadiness(browser, tmp):
    """The product's example project, scanned through the console."""
    from acxelin_readiness import console as rc
    home = tmp / "qreadiness"
    app = rc.build(home)
    app.routes[("POST", "/api/setup")]({"directory": str(build_site.ROOT / "products/readiness/examples")})
    app.routes[("POST", "/api/projects/register")]({"name": "payments-api"})
    app.routes[("POST", "/api/projects/select")]({"project": 0})
    app.routes[("POST", "/api/projects/scan")]({"project": 0})
    while app.routes[("GET", "/api/projects/status")]({})[1]["running"]:
        time.sleep(0.2)
    server, base = serve(app, home)
    try:
        page = browser.new_page(viewport=SIZE)
        page.goto(f"{base}/#{app.sessions.ticket()}")
        page.get_by_text("to fix now").first.wait_for(timeout=60000)
        page.wait_for_timeout(800)
        box = page.get_by_role("heading", name="payments-api", level=1).bounding_box()  # the result, not the sidebar with the folder's path
        save(page, "qreadiness-console.png", clip={"x": box["x"] - 16, "y": box["y"] - 16, "width": 1280 - box["x"] - 40, "height": 900 - box["y"]})
        page.close()
    finally:
        server.shutdown()


MAKERS = {"qguard": qguard, "qvpn": qvpn, "qreadiness": qreadiness}


def main(names):
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        browser = p.chromium.launch()
        for name in names or MAKERS:
            MAKERS[name](browser, Path(tmp))
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
