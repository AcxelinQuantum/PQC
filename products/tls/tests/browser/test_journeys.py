"""Acxelin QGuard console journeys in a real browser: what a customer does, not what the API returns."""
import io
import socket
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from acxelin_core import console as core
from acxelin_core import openssl

from acxelin_tls import console as tc

sync = pytest.importorskip("playwright.sync_api")
AXE = Path(__file__).resolve().parents[4] / "tools/browser/node_modules/axe-core/axe.min.js"
PASS = "ca-pass-7f3e91"
needs_openssl = pytest.mark.skipif(openssl.available() is not None, reason="needs OpenSSL 3.5+ (set ACXELIN_OPENSSL)")
TABS = ("Overview", "Services", "QCertificate", "Check a connection", "Settings")


@pytest.fixture(scope="module")
def browser():
    with sync.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"no Playwright browser: {e}")
        yield b
        b.close()


@pytest.fixture
def console(tmp_path):
    home = tmp_path / "home"
    app = tc.build(home)
    server = core.start(app, home, port=0)
    yield app, f"http://127.0.0.1:{server.server_address[1]}", home
    state = app.routes[("GET", "/api/status")].__self__
    state._stop()
    server.shutdown()


@pytest.fixture
def page(browser, console):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    yield pg
    ctx.close()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def web_app():
    """An ordinary web app with no post-quantum support: the service a customer puts QGuard in front of."""
    class Hello(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"hello from the shop"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Hello)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def open_console(page, console):
    app, base, _ = console
    page.goto(f"{base}/#{app.sessions.ticket()}")


def create_ca(page, passphrase=""):
    page.get_by_label("Name", exact=True).fill("Example Root CA")
    if passphrase:
        page.get_by_label("Passphrase (recommended)").fill(passphrase)
        page.get_by_label("Repeat passphrase").fill(passphrase)
    page.get_by_role("button", name="Create certificate authority").click()
    page.get_by_role("heading", name="Protect your first service").wait_for()


def tab(page, name):
    page.get_by_role("tab", name=name, exact=True).click()


def issue(page, cn, kind="A service"):
    tab(page, "QCertificate")
    page.get_by_label("Certificate for").select_option(label=kind)
    page.get_by_label("Name", exact=True).fill(cn)
    page.get_by_role("button", name="Issue certificate").click()
    page.get_by_text(f"Issued {cn}.").wait_for()


def protect(page, kind, host, port, target, watch=None):
    page.get_by_label(kind).check()
    page.get_by_label("Address people use").fill(host)
    page.get_by_label("Port", exact=True).fill(str(port))
    page.get_by_label("Where it runs now").fill(target)
    if watch is not None:
        page.get_by_label("Start by watching").set_checked(watch)
    page.get_by_role("button", name="Protect service").click()
    page.get_by_role("heading", name=f"{host}:{port}").wait_for()


def axe(page):
    return page.evaluate("axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))")


def test_first_run_signs_in_without_a_ticket_or_cookie_creates_the_ca_and_asks_for_a_service(page, console):
    app, base, home = console
    ticket = app.sessions.ticket()
    page.goto(f"{base}/#{ticket}")
    page.get_by_role("heading", name="Create your certificate authority").wait_for()
    assert "#" not in page.url and ticket not in page.url and page.context.cookies() == []
    assert page.evaluate("sessionStorage.getItem('acx-token')")
    assert "QCertificate" in page.inner_text("main")
    create_ca(page)
    assert (home / "ca/ca.crt").exists()
    again = page.context.new_page()
    again.goto(f"{base}/#{ticket}")
    again.get_by_role("heading", name="This link has expired").wait_for()
    assert "acxelin-qguard console" in again.content()


def test_an_encrypted_ca_asks_for_its_passphrase_after_a_restart(page, console, browser):
    app, base, home = console
    open_console(page, console)
    create_ca(page, PASS)
    assert b"ENCRYPTED" in (home / "ca/ca.key").read_bytes()
    restarted = tc.build(home)
    server = core.start(restarted, home, port=0)
    try:
        ctx = browser.new_context()
        p2 = ctx.new_page()
        p2.goto(f"http://127.0.0.1:{server.server_address[1]}/#{restarted.sessions.ticket()}")
        p2.get_by_role("heading", name="Unlock the certificate authority").wait_for()
        p2.get_by_label("Passphrase").fill("wrong")
        p2.get_by_role("button", name="Unlock").click()
        p2.get_by_text("wrong passphrase").wait_for()
        p2.get_by_label("Passphrase").fill(PASS)
        p2.get_by_role("button", name="Unlock").click()
        p2.get_by_role("heading", name="Protect your first service").wait_for()
        assert PASS not in p2.content()
        ctx.close()
    finally:
        server.shutdown()


@needs_openssl
def test_protect_a_website_start_qguard_and_check_it_end_to_end(page, console, web_app):
    app, base, home = console
    open_console(page, console)
    create_ca(page)
    port = free_port()
    protect(page, "Public website", "shop.example", port, web_app)
    assert "not private" in page.inner_text("main")  # no public certificate yet: what browsers will show is said up front
    (home / "edge.toml").write_text((home / "edge.toml").read_text().replace("127.0.0.1:9100", f"127.0.0.1:{free_port()}"))
    page.get_by_role("button", name="Start QGuard on this computer").click()
    page.get_by_text("QGuard is running").first.wait_for(timeout=30000)
    page.get_by_role("button", name="Check shop.example").click()
    page.get_by_role("heading", name="Check a connection").wait_for()
    page.get_by_role("button", name="Check", exact=True).click()
    page.get_by_text("quantum-safe key exchange, quantum-safe certificate").wait_for(timeout=20000)
    tab(page, "Overview")
    page.get_by_role("cell", name=f"shop.example:{port}").wait_for()
    assert "Needs attention" in page.inner_text("main") and "not private" in page.inner_text("main")
    tab(page, "Services")
    page.get_by_role("button", name="Stop QGuard").click()
    page.get_by_text("QGuard is not running").first.wait_for(timeout=20000)


def test_watch_first_then_turn_on_enforcement_in_two_steps(page, console):
    app, base, home = console
    open_console(page, console)
    create_ca(page)
    protect(page, "Internal app or API", "intranet.example", 8443, "127.0.0.1:8080", watch=True)
    assert page.get_by_text("Watching").first.is_visible()
    page.get_by_role("button", name="Turn on enforcement for intranet.example").click()
    page.get_by_role("button", name="Confirm: refuse clients that are not quantum-safe").click()
    page.get_by_text("Enforcing").first.wait_for()
    assert "shadow" not in (home / "edge.toml").read_text()


def test_a_bad_address_is_explained_next_to_the_form_and_nothing_is_saved(page, console):
    app, base, home = console
    open_console(page, console)
    create_ca(page)
    page.get_by_label("Internal app or API").check()
    page.get_by_label("Address people use").fill("bad host!")
    page.get_by_label("Where it runs now").fill("127.0.0.1:8080")
    page.get_by_role("button", name="Protect service").click()
    form_msg = page.locator("#service-form [role=alert]")
    form_msg.get_by_text("not a valid host name").wait_for()
    assert not (home / "edge.toml").exists()


def test_issue_then_revoke_in_two_steps_and_the_list_shows_it(page, console):
    open_console(page, console)
    create_ca(page)
    issue(page, "web.example.invalid")
    page.get_by_role("cell", name="web.example.invalid", exact=True).wait_for()
    assert page.get_by_text("Valid").first.is_visible()
    assert "PRIVATE KEY" not in page.content()
    page.get_by_role("button", name="Revoke web.example.invalid").click()
    page.get_by_role("button", name="Confirm revoke web.example.invalid").click()
    page.get_by_role("cell", name="Revoked", exact=True).wait_for()
    page.get_by_role("button", name="Refresh the revocation list").click()
    page.get_by_text("Revocation list valid for").first.wait_for()


def test_a_bad_certificate_name_is_explained_and_nothing_is_issued(page, console):
    open_console(page, console)
    create_ca(page)
    tab(page, "QCertificate")
    page.get_by_label("Name", exact=True).fill("bad name!")
    page.get_by_role("button", name="Issue certificate").click()
    page.locator("#issue-form [role=alert]").get_by_text("is not a valid name").wait_for()
    assert page.get_by_text("Nothing issued yet").first.is_visible()


def test_download_each_format_renew_and_see_it_in_recent_activity(page, console):
    open_console(page, console)
    create_ca(page)
    issue(page, "api.example.invalid")
    page.get_by_role("button", name="Download api.example.invalid").click()
    with page.expect_download() as d:
        page.get_by_role("button", name="Certificate and chain (zip)").click()
    assert sorted(zipfile.ZipFile(io.BytesIO(Path(d.value.path()).read_bytes())).namelist()) == ["ca.crt", "cert.pem", "chain.pem"]
    with page.expect_download() as d:
        page.get_by_role("button", name="With the private key (zip)").click()
    assert "key.pem" in zipfile.ZipFile(io.BytesIO(Path(d.value.path()).read_bytes())).namelist()
    with page.expect_download() as d:
        page.get_by_role("button", name="One PEM file: full chain and key").click()
    pem = Path(d.value.path()).read_bytes()
    assert pem.count(b"BEGIN CERTIFICATE") >= 2 and b"PRIVATE KEY" in pem
    page.get_by_role("button", name="Renew api.example.invalid").click()
    page.get_by_text("Renewed api.example.invalid").first.wait_for()
    activity = page.inner_text("#activity")
    assert "Issued api.example.invalid" in activity and "Downloaded api.example.invalid (with key)" in activity


def test_a_device_enrolment_token_is_shown_once_and_listed_without_it(page, console):
    open_console(page, console)
    create_ca(page)
    tab(page, "QCertificate")
    page.get_by_label("Device or service name").fill("device1.example")
    page.get_by_role("button", name="Create a one-time token").click()
    token = page.locator("#token-result code").first.inner_text()
    assert "." in token
    tab(page, "Overview")
    tab(page, "QCertificate")
    page.get_by_role("cell", name="device1.example").wait_for()
    assert token not in page.content() and page.get_by_role("cell", name="Unused").is_visible()


def test_check_a_connection_explains_a_refusal(page, console):
    open_console(page, console)
    create_ca(page)
    tab(page, "Check a connection")
    page.get_by_label("Address", exact=True).fill(f"127.0.0.1:{free_port()}")
    page.get_by_role("button", name="Check", exact=True).click()
    page.get_by_text("connection refused").wait_for(timeout=20000)


@needs_openssl
def test_settings_show_where_things_are_and_what_this_computer_can_do(page, console):
    app, base, home = console
    open_console(page, console)
    create_ca(page)
    tab(page, "Settings")
    page.get_by_text("can do post-quantum TLS 1.3").wait_for()
    assert str(home / "edge.toml") in page.inner_text("main")
    assert page.get_by_role("button", name="Check again").is_visible()


@needs_openssl
def test_other_qguard_services_can_be_watched_by_their_status_address(page, console):
    from acxelin_tls.edge import Edge, Route, serve_metrics
    app, base, home = console
    open_console(page, console)
    create_ca(page)
    state = app.routes[("GET", "/api/status")].__self__
    cert = tc.TLSConsole.issue(state, {"kind": "server", "common_name": "localhost", "names": ["127.0.0.1"], "days": 30})[1]
    edge = Edge(Route("remote-shop", "terminate", "127.0.0.1:0", "127.0.0.1:9", cert=str(home / cert["folder"] / "chain.pem"),
                      key=str(home / cert["folder"] / "key.pem"))).start()
    metrics = serve_metrics("127.0.0.1:0", [edge], None)
    try:
        tab(page, "Settings")
        page.get_by_label("Status address of another QGuard").fill(f"http://127.0.0.1:{metrics.server_address[1]}")
        page.get_by_role("button", name="Watch it").click()
        page.get_by_text("remote-shop").wait_for()
        page.get_by_role("button", name="Stop watching http://127.0.0.1", exact=False).click()
        page.get_by_text("No other QGuard services watched").wait_for()
    finally:
        edge.stop(0)
        metrics.shutdown()


@needs_openssl
@pytest.mark.parametrize("width,scheme", [(1280, "light"), (1280, "dark"), (390, "light")])
def test_no_accessibility_violations_and_no_sideways_scroll(browser, console, width, scheme):
    ctx = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
    page = ctx.new_page()
    try:
        open_console(page, console)
        page.get_by_role("heading", name="Create your certificate authority").wait_for()
        page.evaluate(AXE.read_text())
        found = {"setup": axe(page)}
        create_ca(page)
        found["first service"] = axe(page)
        protect(page, "Internal app or API", "intranet.example", 8443, "127.0.0.1:8080", watch=True)
        issue(page, "web.example.invalid")
        for name in TABS:
            tab(page, name)
            page.wait_for_timeout(400)
            found[name] = axe(page)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), name
        assert {k: v for k, v in found.items() if v} == {}, found
    finally:
        ctx.close()


def test_keyboard_only_creates_the_ca(page, console):
    open_console(page, console)
    page.get_by_label("Name", exact=True).wait_for()
    assert page.evaluate("document.activeElement.id") == "ca-name"
    page.keyboard.type("Keyboard CA")
    page.keyboard.press("Enter")
    page.get_by_role("heading", name="Protect your first service").wait_for()


def test_no_browser_errors_through_every_view(browser, console):
    ctx = browser.new_context()
    page = ctx.new_page()
    problems = []
    page.on("console", lambda m: m.type == "error" and problems.append(f"console: {m.text}"))
    page.on("pageerror", lambda e: problems.append(f"exception: {e}"))
    page.on("requestfailed", lambda r: problems.append(f"failed: {r.url} {r.failure}"))
    page.on("response", lambda r: r.status >= 400 and problems.append(f"HTTP {r.status}: {r.url}"))
    try:
        open_console(page, console)
        create_ca(page)
        issue(page, "web.example.invalid")
        for name, ready in zip(TABS, ("Protected services", "QGuard on this computer", "Issued certificates", "Whom to trust", "Where things are")):
            tab(page, name)
            page.get_by_text(ready).first.wait_for()
        assert problems == []
    finally:
        ctx.close()


def test_a_mistyped_passphrase_is_caught_before_the_ca_exists(page, console):
    app, base, home = console
    open_console(page, console)
    page.get_by_label("Name", exact=True).fill("Example Root CA")
    page.get_by_label("Passphrase (recommended)").fill("first-try-1")
    page.get_by_label("Repeat passphrase").fill("first-try-2")
    page.get_by_role("button", name="Create certificate authority").click()
    page.get_by_text("The two passphrases are different").wait_for()
    assert not (home / "ca/ca.crt").exists()


def test_an_issued_certificate_says_where_its_files_are_and_what_to_do_next(page, console):
    app, base, home = console
    open_console(page, console)
    create_ca(page)
    issue(page, "web.example.invalid")
    folder = next((home / "issued").iterdir())
    text = page.locator("#issued").inner_text()
    assert str(folder / "chain.pem") in text and str(folder / "key.pem") in text, text
    assert "Protect a service" in text


def test_the_owner_only_launch_page_opens_the_console_signed_in(page, console):
    app, url, home = console
    launch = core.launch_page(f"{url}/#{app.sessions.ticket()}", home)
    assert "#" not in launch, "the ticket is not in what the browser is given"
    page.goto(launch)
    page.wait_for_url(f"{url}/**", timeout=10000)
    page.wait_for_function("Object.keys(sessionStorage).length > 0", timeout=10000)
    assert "#" not in page.url or not page.url.split("#", 1)[1], "the redeemed ticket is cleared from the address bar"
