"""Readiness console journeys in a real browser: what a customer does, not what the API returns.

Run with the Playwright browser installed (`python -m playwright install chromium`); skipped when it is not.
"""
import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from acxelin_core import console as core

from acxelin_readiness import console as rc

sync = pytest.importorskip("playwright.sync_api")
expect = sync.expect
AXE = Path(__file__).resolve().parents[4] / "tools/browser/node_modules/axe-core/axe.min.js"


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
def repos(tmp_path):
    root = tmp_path / "repos"
    (root / "shop").mkdir(parents=True)
    (root / "shop/keys.py").write_text("from cryptography.hazmat.primitives.asymmetric import rsa\n\ndef issue_key():\n    return rsa.generate_private_key(public_exponent=65537, key_size=2048)\n")
    (root / "api").mkdir()
    (root / "api/a.py").write_text("import hashlib\nhashlib.sha1(b'x')\n")
    return root


@pytest.fixture
def console(tmp_path):
    app = rc.build(tmp_path / "home")
    server = core.start(app, tmp_path / "home", port=0)
    yield app, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def page(browser, console):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    yield pg
    ctx.close()


def open_console(page, console):
    app, base = console
    page.goto(f"{base}/#{app.sessions.ticket()}")


def fill_setup(page, repos):
    page.get_by_label("Folder path").fill(str(repos))
    page.get_by_role("button", name="Use this folder").click()
    page.get_by_label("Folder path").wait_for(state="detached")


def scan_shop(page):
    page.get_by_label("Add a repository").select_option("shop")
    page.get_by_role("button", name="Add and scan").click()  # adding starts the first scan
    page.get_by_text("RSA", exact=False).first.wait_for(timeout=30000)


def test_first_run_signs_in_without_leaving_a_ticket_or_cookie(page, console, repos):
    app, base = console
    ticket = app.sessions.ticket()
    page.goto(f"{base}/#{ticket}")
    page.get_by_role("heading", name="What would you like to check?").wait_for()
    assert page.get_by_role("tab", name="Endpoints").is_visible(), "grading servers needs no repository folder"
    assert "#" not in page.url and ticket not in page.url
    assert page.context.cookies() == []
    assert page.evaluate("sessionStorage.getItem('acx-token')")
    fill_setup(page, repos)
    page.go_back() if False else None
    again = page.context.new_page()
    again.goto(f"{base}/#{ticket}")
    again.get_by_role("heading", name="This link has expired").wait_for()
    assert "acxelin-qreadiness console" in again.content()


def test_add_scan_see_priorities_and_assign_an_owner(page, console, repos):
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    assert page.locator("td .tag.critical, td .tag.high").first.is_visible()
    assert "Change code" in page.get_by_role("region", name="Findings, scrolls sideways").inner_text()
    assert page.get_by_role("heading", name="How hard they are to change").is_visible()
    page.locator("details.track summary").first.click()
    page.get_by_label("Owner").first.fill("payments team")
    page.get_by_role("button", name="Save").first.click()
    page.get_by_text("Owner: payments team").wait_for()
    assert "key_size=2048" not in page.content()


def test_an_open_finding_with_long_paths_and_its_example_fix_keeps_the_owner_column_in_view(page, console, tmp_path):
    """Deep source paths and example code wrap inside their cells, so the findings table fits its area on a laptop screen and
    'Assign an owner' never sits past the edge."""
    deep = tmp_path / "repos/vault/src/main/java/com/example/payments"
    deep.mkdir(parents=True)
    (deep / "CardVault.java").write_text('import javax.crypto.Cipher;\nclass CardVault {\n  Cipher c() throws Exception {\n'
                                         '    return Cipher.getInstance("AES/ECB/PKCS5Padding");\n  }\n}\n')
    open_console(page, console)
    fill_setup(page, tmp_path / "repos")
    page.get_by_label("Add a repository").select_option("vault")
    page.get_by_role("button", name="Add and scan").click()
    page.get_by_text("AES-ECB").first.wait_for(timeout=30000)
    page.get_by_text("AES-ECB").first.click()
    page.get_by_text("Example fix in Java").first.click()
    region = page.get_by_role("region", name="Findings, scrolls sideways")
    assert region.evaluate("r => r.querySelector('table').scrollWidth <= r.clientWidth"), "the findings table is wider than its area"
    owner = page.get_by_text("Assign an owner").first.bounding_box()
    box = region.bounding_box()
    assert owner["x"] + owner["width"] <= box["x"] + box["width"]


def test_an_open_list_of_places_and_a_half_typed_owner_survive_a_running_scan(page, console, repos):
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)

    def slow(path, **kw):
        kw["cancel"].wait(20)
        raise rc.workspace.ScanStopped("Scan cancelled; the previous completed assessment is preserved")
    with patch("acxelin_readiness.console.workspace.scan", side_effect=slow):
        page.get_by_role("button", name="Scan repository").click()
        page.get_by_role("button", name="Stop scan").wait_for()
        page.locator("details.where summary", has_text="RSA").click()
        page.locator("details.track summary").first.click()
        page.locator("details.track input[type=text]").first.fill("ali")
        page.wait_for_timeout(2000)
        assert page.locator("details.where", has_text="RSA").evaluate("d => d.open")
        assert page.locator("details.track input[type=text]").first.input_value() == "ali"
        page.get_by_role("button", name="Stop scan").click()
        page.get_by_text("cancelled", exact=False).wait_for()


def test_stopping_a_scan_keeps_the_previous_result(page, console, repos):
    app, _ = console
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    first = page.get_by_text("Scanned", exact=False).first.inner_text()

    def slow(path, **kw):
        kw["cancel"].wait(20)
        raise rc.workspace.ScanStopped("Scan cancelled; the previous completed assessment is preserved")
    with patch("acxelin_readiness.console.workspace.scan", side_effect=slow):
        page.get_by_role("button", name="Scan repository").click()
        page.get_by_role("button", name="Stop scan").click()
        page.get_by_text("cancelled", exact=False).wait_for()
    assert page.get_by_text("Scanned", exact=False).first.inner_text() == first
    page.get_by_role("button", name="Scan repository").wait_for()


def test_choosing_another_repository_shows_its_own_state(page, console, repos):
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    page.get_by_label("Add a repository").select_option("api")
    page.get_by_role("button", name="Add and scan").click()
    page.get_by_text("SHA-1", exact=False).first.wait_for(timeout=30000)
    assert not page.get_by_text("RSA", exact=False).count(), "api shows its own findings, not shop's"
    page.get_by_role("button", name="shop", exact=True).click()
    page.get_by_text("RSA", exact=False).first.wait_for()


def grade(target, g):
    return {"target": target, "grade": g, "protocol": "tls", "certificate": None, "negotiated": "TLS 1.3 X25519MLKEM768" if g == "A" else "TLS 1.3 X25519", "group": ""}


def test_endpoints_changes_since_the_last_check_and_cbom_download(page, console, repos):
    open_console(page, console)
    fill_setup(page, repos)
    page.get_by_role("tab", name="Endpoints").click()
    runs = iter([[grade("127.0.0.1:1", "F")], [grade("127.0.0.1:1", "A")]])
    with patch("acxelin_readiness.console.endpoints.scan", side_effect=lambda t: next(runs)):
        for g in ("F", "A"):
            page.get_by_label("Hosts to check").fill("127.0.0.1:1")
            page.get_by_role("button", name="Check endpoints").click()
            page.locator("#ep-result td .pill", has_text=re.compile(f"^{g}:")).wait_for()
            expect(page.locator("#check")).to_be_enabled()
        page.get_by_role("heading", name="Changed since the scan before").wait_for()
        assert "127.0.0.1:1: F → A" in page.content()
    with page.expect_download(timeout=60000) as d:
        page.get_by_role("button", name="Download CBOM").click()
    cbom = json.loads(Path(d.value.path()).read_text())
    assert cbom["bomFormat"] == "CycloneDX" and cbom["specVersion"] == "1.6"
    assert d.value.suggested_filename == "endpoints-cbom.json"


@pytest.mark.parametrize("width,scheme", [(1280, "light"), (1280, "dark"), (390, "light")])
def test_no_accessibility_violations_and_no_sideways_scroll(browser, console, repos, width, scheme):
    ctx = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
    page = ctx.new_page()
    try:
        open_console(page, console)
        page.get_by_role("heading", name="What would you like to check?").wait_for()
        views = []
        views.append(page.evaluate(AXE.read_text() + ";axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))"))
        fill_setup(page, repos)
        scan_shop(page)
        views.append(page.evaluate("axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))"))
        page.get_by_role("tab", name="Endpoints").click()
        views.append(page.evaluate("axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))"))
        assert views == [[], [], []], views
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    finally:
        ctx.close()


def test_keyboard_only_reaches_setup_and_submits(page, console, repos):
    open_console(page, console)
    page.get_by_label("Folder path").wait_for()
    assert page.evaluate("document.activeElement.id") == "dir"
    page.keyboard.type(str(repos))
    page.keyboard.press("Enter")
    page.get_by_label("Folder path").wait_for(state="detached")
    expect(page.locator("#tab-projects")).to_be_focused()
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement !== document.body")


def test_no_browser_errors_through_every_view(browser, console, tmp_path):
    ctx = browser.new_context()
    page = ctx.new_page()
    problems = []
    page.on("console", lambda m: m.type == "error" and problems.append(f"console: {m.text}"))
    page.on("pageerror", lambda e: problems.append(f"exception: {e}"))
    page.on("requestfailed", lambda r: problems.append(f"failed: {r.url} {r.failure}"))
    page.on("response", lambda r: r.status >= 400 and problems.append(f"HTTP {r.status}: {r.url}"))
    try:
        VIEWS(page, console, tmp_path)
        assert problems == []
    finally:
        ctx.close()


def VIEWS(page, console, tmp_path):
    root = tmp_path / "views"
    (root / "shop").mkdir(parents=True)
    (root / "shop/keys.py").write_text("from cryptography.hazmat.primitives.asymmetric import rsa\nrsa.generate_private_key(public_exponent=65537, key_size=2048)\n")
    open_console(page, console)
    fill_setup(page, root)
    scan_shop(page)
    page.get_by_role("tab", name="Endpoints").click()
    page.get_by_label("Hosts to check").wait_for()
    page.get_by_role("tab", name="Projects").click()
    page.get_by_text("RSA", exact=False).first.wait_for()


def test_endpoints_work_before_choosing_a_repository_folder(page, console):
    open_console(page, console)
    page.get_by_role("tab", name="Endpoints").click()
    with patch("acxelin_readiness.console.endpoints.scan", side_effect=lambda t: [grade("example.com:443", "C")]):
        page.get_by_label("Hosts to check").fill("https://example.com/some/page")
        page.get_by_role("button", name="Check endpoints").click()
        page.get_by_text("example.com:443").first.wait_for()
    assert "Only the host and port are checked" in page.content(), "a pasted address says its path was not graded"


def test_the_folder_example_is_this_computers_own_kind_of_path(page, console):
    open_console(page, console)
    assert str(Path.home()) in page.get_by_label("Folder path").get_attribute("placeholder")


def test_a_finding_shows_where_it_is_and_the_priority_chips_filter_the_list(page, console, tmp_path):
    root = tmp_path / "many"
    (root / "shop").mkdir(parents=True)
    (root / "shop/keys.py").write_text("from cryptography.hazmat.primitives.asymmetric import rsa\nimport hashlib\n\n"
                                      "rsa.generate_private_key(public_exponent=65537, key_size=2048)\nhashlib.md5(b'x').hexdigest()\n")
    open_console(page, console)
    fill_setup(page, root)
    scan_shop(page)
    table = page.locator("#pj-result table")
    table.get_by_text("MD5", exact=True).wait_for()
    page.get_by_role("button", name="Show only critical").click()
    expect(page.locator("#pj-result table")).not_to_contain_text("RSA-2048")  # not wait_for_function: its polling is an eval, which the console's CSP refuses
    assert table.get_by_text("MD5", exact=True).is_visible()
    page.get_by_role("button", name="Show every priority").click()
    table.get_by_text("RSA-2048").wait_for()
    table.get_by_text("RSA-2048").click()
    page.get_by_text("keys.py:4").wait_for()


def test_a_finding_can_be_accepted_as_a_risk_until_a_date(page, console, repos):
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    page.locator("details.track summary").first.click()
    page.get_by_label("Status").first.select_option("exception")
    page.get_by_label("Why it is accepted").first.fill("Vendor appliance, replaced in 2027")
    assert page.get_by_label("Due date").first.get_attribute("type") == "date"
    page.get_by_label("Accepted until").first.fill("2099-01-01")
    page.get_by_role("button", name="Save").first.click()
    page.get_by_text("Accepted risk until 2099-01-01").wait_for()


def test_endpoints_say_what_can_happen_and_what_to_do_next(page, console):
    rows = [grade("a.example:443", "C") | {"certificate": {"key": "RSA-2048", "issuer": "CN=Old CA", "expires": "2026-01-01", "days_left": -5, "quantum_safe": False}},
            grade("ssh.example:22", "C") | {"target": "ssh://ssh.example:22", "protocol": "ssh",
                                            "certificate": {"key": "ssh-ed25519", "expires": "", "days_left": 9999, "quantum_safe": False}}]
    open_console(page, console)
    page.get_by_role("tab", name="Endpoints").click()
    with patch("acxelin_readiness.console.endpoints.scan", side_effect=lambda t: rows):
        page.get_by_label("Hosts to check").fill("a.example\nssh://ssh.example")
        page.get_by_role("button", name="Check endpoints").click()
        page.get_by_role("heading", name="What could happen").wait_for()
    recommend = page.locator("section.analysis", has=page.get_by_role("heading", name="What to do"))
    assert recommend.locator("ol > li").first.inner_text().startswith("Renew the certificate")
    assert "X25519MLKEM768" in recommend.inner_text() and "mlkem768x25519-sha256" in recommend.inner_text()
    table = page.locator("#ep-result table").inner_text()
    assert "expired 2026-01-01" in table and "9999" not in table, "SSH host keys have no expiry; an expired certificate says so"
    assert page.evaluate(AXE.read_text() + ";axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))") == []


def test_counts_match_the_listed_findings_when_some_are_only_in_tests(page, console, tmp_path):
    root = tmp_path / "tested"
    (root / "shop/tests").mkdir(parents=True)
    (root / "shop/keys.py").write_text("from cryptography.hazmat.primitives.asymmetric import rsa\nrsa.generate_private_key(public_exponent=65537, key_size=2048)\n")
    (root / "shop/tests/test_keys.py").write_text("import hashlib\nhashlib.md5(b'x')\nhashlib.sha1(b'y')\n")
    open_console(page, console)
    fill_setup(page, root)
    scan_shop(page)
    page.get_by_text("only in tests").first.wait_for()
    listed = page.get_by_role("region", name="Findings, scrolls sideways").locator("tbody tr")
    assert page.locator(".counts button").inner_text().split()[-1] == str(listed.count())
    page.get_by_text("Only in tests: 2 findings, not counted above").click()
    tested = page.get_by_role("region", name="Findings only in tests, scrolls sideways")
    assert "MD5" in tested.inner_text() and "SHA-1" in tested.inner_text() and "MD5" not in page.get_by_role("region", name="Findings, scrolls sideways").inner_text()
    glance = page.locator("#pj-result .glance").inner_text()
    assert "1 thing to fix now" in glance.replace("\n", " ") and "of 1 finding outside test code; 2 more only in tests" in glance, glance


def test_after_a_restart_the_selected_repository_is_the_one_whose_results_show(browser, tmp_path, repos):
    first = rc.build(tmp_path / "home")
    first.routes[("POST", "/api/setup")]({"directory": str(repos)})
    for i, name in enumerate(("api", "shop")):
        first.routes[("POST", "/api/projects/register")]({"name": name})
        first.routes[("POST", "/api/projects/select")]({"project": i})
        first.routes[("POST", "/api/projects/scan")]({"project": i})
        while first.routes[("GET", "/api/projects/status")]({})[1]["running"]:
            pass
    app = rc.build(tmp_path / "home")
    server = core.start(app, tmp_path / "home", port=0)
    ctx = browser.new_context()
    try:
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{server.server_address[1]}/#{app.sessions.ticket()}")
        page.get_by_text("RSA", exact=False).first.wait_for()
        assert page.locator(".list button[aria-current=true]").inner_text() == "shop"
    finally:
        ctx.close()
        server.shutdown()


def fake_fetch(url, dest, token=None):
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "sign.py").write_text("from cryptography.hazmat.primitives.asymmetric import rsa\nrsa.generate_private_key(public_exponent=65537, key_size=2048)\n")
    return dest


def test_a_github_repository_is_scanned_from_the_first_screen_without_a_folder(page, console):
    open_console(page, console)
    with patch("acxelin_readiness.console.remote.fetch", side_effect=fake_fetch):
        page.get_by_label("Repository link").fill("https://github.com/acme/payments")
        page.get_by_role("button", name="Download and scan").click()
        page.locator("#pj-result table").get_by_text("RSA-2048").wait_for(timeout=30000)
    assert page.get_by_role("heading", name="github.com/acme/payments").is_visible()


def test_a_private_repository_token_is_saved_without_ever_showing_it(page, console):
    secret = "github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz"
    open_console(page, console)
    page.get_by_text("Private repositories").click()
    assert page.get_by_label("Access token").get_attribute("type") == "password"
    page.get_by_label("Access token").fill(secret)
    page.get_by_role("button", name="Save token").click()
    page.get_by_text("Private repositories: token saved").wait_for()
    assert secret not in page.content() and secret not in page.url
    page.get_by_text("Token saved.").wait_for()
    page.get_by_text("Private repositories: token saved").click()
    page.once("dialog", lambda d: d.dismiss())
    page.get_by_role("button", name="Remove token").click()
    assert page.get_by_text("Private repositories: token saved").is_visible()
    page.once("dialog", lambda d: d.accept())
    page.get_by_role("button", name="Remove token").click()
    page.get_by_text("Private repositories", exact=True).wait_for()


def test_the_things_to_fix_now_lead_with_their_trend_and_each_host_keeps_its_history(page, console, repos):
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    page.locator(".trendline strong").wait_for()
    assert page.locator(".trendline").inner_text().startswith("Things to fix now: 1")
    assert "of 100" not in page.locator("#panel").inner_text() and "score" not in page.locator("#panel").inner_text().lower(), "decision 7"
    page.get_by_role("button", name="Scan repository").click()
    page.locator("figure.trend svg").wait_for(timeout=30000)
    assert "Things to fix now over the last 2 scans, from 1 to 1" == page.locator("figure.trend svg").get_attribute("aria-label")
    assert page.locator("figure.trend .axis span").last.inner_text().endswith(": 1")
    page.get_by_role("tab", name="Endpoints").click()
    runs = iter([[grade("127.0.0.1:1", "C")], [grade("127.0.0.1:1", "A")]])
    with patch("acxelin_readiness.console.endpoints.scan", side_effect=lambda t: next(runs)):
        for g in ("C", "A"):
            page.get_by_label("Hosts to check").fill("127.0.0.1:1")
            page.get_by_role("button", name="Check endpoints").click()
            page.locator("#ep-result td .pill", has_text=re.compile(f"^{g}:")).wait_for()
            expect(page.locator("#check")).to_be_enabled()
    page.get_by_text("Earlier checks").first.click()
    assert re.search(r"C\s+on\s+\d{4}-\d\d-\d\d", page.locator("#ep-result table").inner_text())
    assert "of 100" not in page.locator("#panel").inner_text()
    assert page.evaluate(AXE.read_text() + ";axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))") == []


def test_findings_and_grades_download_as_csv_and_print_without_the_controls(page, console, repos):
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    with page.expect_download() as d:
        page.get_by_role("button", name="Download CSV").click()
    assert d.value.suggested_filename == "shop-findings.csv" and Path(d.value.path()).read_text().startswith("Asset,Algorithm,Priority")
    page.emulate_media(media="print")
    assert not page.get_by_role("button", name="Scan repository").is_visible() and page.locator("#pj-result table").get_by_text("RSA-2048").is_visible()
    page.emulate_media(media="screen")
    page.get_by_role("tab", name="Endpoints").click()
    with patch("acxelin_readiness.console.endpoints.scan", side_effect=lambda t: [grade("127.0.0.1:1", "C")]):
        page.get_by_label("Hosts to check").fill("127.0.0.1:1")
        page.get_by_role("button", name="Check endpoints").click()
        page.locator("#ep-result td .pill", has_text=re.compile("^C:")).wait_for()
    with page.expect_download() as d:
        page.get_by_role("button", name="Download CSV").click()
    assert Path(d.value.path()).read_text().splitlines()[1].startswith("127.0.0.1:1,C,")


def test_services_from_a_cmdb_export_filter_and_rank_the_findings(page, console, repos, tmp_path):
    (repos / "shop/legacy.py").write_text("import hashlib\nhashlib.md5(b'x')\n")
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    (tmp_path / "owners.csv").write_text("path,owner,service\nkeys.py,Payments team,Card payments\nlegacy.py,Core team,Ledger\n")
    page.get_by_text("Owners from a CMDB export").click()
    page.get_by_label("CSV file").set_input_files(str(tmp_path / "owners.csv"))
    page.get_by_role("button", name="Use these owners").click()
    page.get_by_text("Owner: Payments team · Card payments", exact=True).first.wait_for()
    assert page.get_by_text("Owner: Payments team · Card payments", exact=True).first.get_attribute("title") == "Suggested owner, from CMDB export"
    page.get_by_role("button", name="Show only Ledger").click()
    table = page.get_by_role("region", name="Findings, scrolls sideways")
    assert "MD5" in table.inner_text() and "RSA-2048" not in table.inner_text()
    services = page.get_by_role("region", name="Services, scrolls sideways").inner_text()
    assert services.index("Ledger") < services.index("Card payments")
    assert not page.get_by_role("button", name="Tickets for Jira").count()
    assert page.evaluate(AXE.read_text() + ";axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))") == []


def test_the_tabs_follow_the_arrow_key_pattern_and_grades_are_read_out_in_words(page, console):
    open_console(page, console)
    page.get_by_role("tab", name="Projects").focus()
    page.keyboard.press("ArrowRight")
    assert page.evaluate("document.activeElement.id") == "tab-overview"
    page.keyboard.press("ArrowRight")
    assert page.evaluate("document.activeElement.id") == "tab-endpoints" and page.get_by_role("tab", name="Endpoints").get_attribute("aria-selected") == "true"
    assert page.get_by_role("tab", name="Projects").get_attribute("tabindex") == "-1"
    with patch("acxelin_readiness.console.endpoints.scan", side_effect=lambda t: [grade("127.0.0.1:1", "C")]):
        page.get_by_label("Hosts to check").fill("127.0.0.1:1")
        page.get_by_role("button", name="Check endpoints").click()
        page.locator("#ep-result td .pill", has_text=re.compile("^C:")).wait_for()
    assert "classical only" in page.locator("#ep-result td .pill").first.text_content()
    page.reload()
    page.goto(page.url.split("#")[0] + "#" + console[0].sessions.ticket())
    page.get_by_role("tab", name="Endpoints").click()
    page.locator("#ep-result td .pill").first.wait_for()
    assert page.get_by_label("Hosts to check").input_value() == "127.0.0.1:1", "the hosts of the last check come back after a reload"


def test_a_finding_marked_fixed_shows_its_history_and_is_flagged_when_the_rescan_still_finds_it(page, console, repos):
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    for status in ("planned", "fixed"):
        page.locator("details.track summary").first.click()
        page.get_by_label("Status").first.select_option(status)
        page.get_by_role("button", name="Save").first.click()
        page.locator("#pj-progress", has_text="1 " + {"planned": "planned", "fixed": "fixed"}[status]).wait_for()
    page.get_by_role("button", name="Scan repository").click()
    page.get_by_text("Fixed, still found").first.wait_for(timeout=30000)
    assert "still found" in page.locator("#pj-progress").inner_text()
    page.get_by_text("Fixed, still found").first.click()
    page.locator("details.track details.more summary", has_text="History").first.click()
    assert page.locator("ul.history li").count() == 2
    assert page.evaluate(AXE.read_text() + ";axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))") == []


def test_another_tools_cbom_is_imported_and_rated_from_the_first_screen(page, console, tmp_path):
    cbom = {"bomFormat": "CycloneDX", "specVersion": "1.6", "metadata": {"tools": [{"name": "codeql"}]},
            "components": [{"type": "cryptographic-asset", "name": "RSA-2048", "cryptoProperties": {"assetType": "algorithm"},
                            "evidence": {"occurrences": [{"location": "src/Billing.java", "line": 10}]}}]}
    (tmp_path / "billing.cbom.json").write_text(json.dumps(cbom))
    (tmp_path / "notjson.json").write_text("{nope")
    open_console(page, console)
    page.get_by_label("Import a CBOM").set_input_files(str(tmp_path / "notjson.json"))
    page.get_by_role("button", name="Import and rate").click()
    page.get_by_text("That file is not JSON").wait_for()
    page.get_by_label("Import a CBOM").set_input_files(str(tmp_path / "billing.cbom.json"))
    page.get_by_role("button", name="Import and rate").click()
    page.locator("#pj-result table").get_by_text("RSA-2048").wait_for(timeout=30000)
    assert page.get_by_role("heading", name="Imported: billing.cbom.json").is_visible()
    assert page.evaluate(AXE.read_text() + ";axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))") == []


def test_each_finding_says_how_it_was_seen_and_how_sure_the_scan_is(page, console, repos):
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    basis = page.locator("#pj-result td small.basis").first.inner_text()
    assert "In code" in basis and "confidence" in basis


def test_coverage_shows_and_a_fall_in_coverage_is_called_out(page, console):
    open_console(page, console)
    page.get_by_role("tab", name="Endpoints").click()
    runs = iter([[grade("127.0.0.1:1", "C"), grade("127.0.0.1:2", "C")], [grade("127.0.0.1:1", "A"), grade("127.0.0.1:2", "F")]])
    with patch("acxelin_readiness.console.endpoints.scan", side_effect=lambda t: next(runs)):
        for g in ("C", "A"):
            page.get_by_label("Hosts to check").fill("127.0.0.1:1\n127.0.0.1:2")
            page.get_by_role("button", name="Check endpoints").click()
            page.locator("#ep-result td .pill", has_text=re.compile(f"^{g}:")).first.wait_for()
            expect(page.locator("#check")).to_be_enabled()
    page.get_by_text("Coverage 50%: 1 of 2 endpoints could be graded.").wait_for()
    assert "Coverage fell from 100% to 50%" in page.locator("#ep-result").inner_text(), "fewer problems only because one endpoint went dark"


def test_owners_come_from_codeowners_and_a_cmdb_export_and_unowned_findings_ask_for_review(page, console, repos, tmp_path):
    (repos / "shop/.github").mkdir()
    (repos / "shop/.github/CODEOWNERS").write_text("keys.py @payments-team\n")
    (repos / "shop/legacy.py").write_text("import hashlib\nhashlib.md5(b'x')\n")
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    page.get_by_text("Owner: @payments-team", exact=True).first.wait_for()
    assert page.get_by_text("Owner: @payments-team", exact=True).first.get_attribute("title") == "Suggested owner, from CODEOWNERS"
    assert page.get_by_text("Assign an owner").count() >= 1
    (tmp_path / "owners.csv").write_text("path,owner\n*.py,Platform Security\n")
    page.get_by_text("Owners from a CMDB export").click()
    page.get_by_label("CSV file").set_input_files(str(tmp_path / "owners.csv"))
    page.get_by_role("button", name="Use these owners").click()
    page.get_by_text("Owner: Platform Security", exact=True).first.wait_for()
    assert page.get_by_text("Owner: Platform Security", exact=True).first.get_attribute("title") == "Suggested owner, from CMDB export"
    assert page.get_by_text("Assign an owner").count() == 0


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_both_pages_show_the_four_analyses_with_their_charts_and_the_nav_reaches_each(browser, console, repos, scheme):
    page = browser.new_page(color_scheme=scheme)
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    kinds = {"descriptive": "What we found", "diagnostic": "Why it matters", "predictive": "What could happen", "prescriptive": "What to do"}

    def check(prefix):
        result = page.locator(f"#{prefix}-result")
        assert [result.locator(f"#{prefix}-{k}").inner_text().startswith(v) for k, v in kinds.items()] == [True] * 4
        assert "[object" not in result.inner_text()
        assert result.locator(".glance li").count() >= 2 and result.locator(".dist[role=img]").first.get_attribute("aria-label")
        page.get_by_role("navigation", name="Sections on this page").get_by_role("button", name=re.compile("^What to do")).click()
        assert page.evaluate("document.activeElement.id") == f"{prefix}-prescriptive"
        assert page.evaluate(AXE.read_text() + ";axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))") == []

    result = page.locator("#pj-result")
    assert "1 thing to fix now" in result.locator(".glance").inner_text().replace("\n", " ") and "high" in result.locator("dl.key").inner_text()
    assert result.locator(".bars .bar-row").filter(has_text="Breakable by a quantum computer").inner_text().endswith("1")
    assert "Replace with" in result.locator("#pj-prescriptive + ol").inner_text()
    check("pj")
    page.get_by_role("tab", name="Endpoints").click()
    with patch("acxelin_readiness.console.endpoints.scan", side_effect=lambda t: [grade("a.example:443", "C"), grade("b.example:443", "A")]):
        page.get_by_label("Hosts to check").fill("a.example\nb.example")
        page.get_by_role("button", name="Check endpoints").click()
        page.locator("#ep-prescriptive").wait_for()
    assert "1 of 2" in page.locator("#ep-result .glance").inner_text()
    assert page.locator("#ep-result .dist").get_attribute("aria-label") == "Endpoints by grade: 1 grade A, 1 grade C"
    check("ep")
    page.close()


def test_findings_with_nothing_to_change_fold_away_and_progress_fills_as_fixes_land(page, console, tmp_path):
    root = tmp_path / "mixed"
    (root / "shop").mkdir(parents=True)
    (root / "shop/a.py").write_text("import hashlib\nhashlib.md5(b'x')\nhashlib.sha256(b'y')\nfrom cryptography.hazmat.primitives.ciphers import algorithms, Cipher\nc = Cipher(algorithms.AES(key), mode)\n")
    open_console(page, console)
    fill_setup(page, root)
    page.get_by_label("Add a repository").select_option("shop")
    page.get_by_role("button", name="Add and scan").click()
    table = page.locator("#pj-result table")
    table.get_by_text("MD5", exact=True).wait_for()
    assert not table.get_by_text("SHA-256", exact=True).count()
    page.get_by_role("button", name="Show the 1 finding with nothing to change").click()
    table.get_by_text("SHA-256", exact=True).wait_for()
    page.get_by_role("button", name="Hide the findings with nothing to change").click()
    assert "0 of 2" in page.locator("#pj-progress").inner_text()
    table.get_by_text("AES", exact=True).click()
    assert "Not seen: key size" in table.inner_text()
    page.locator("details.track summary").first.click()
    page.locator("details.track select").first.select_option("fixed")
    page.locator("details.track").first.get_by_role("button", name="Save").click()
    page.locator("#pj-progress", has_text="1 of 2").wait_for()
    assert page.locator("#pj-progress .seg.s-ok").count() == 1
    assert page.evaluate(AXE.read_text() + ";axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))") == []


def test_the_board_summary_prints_alone_and_says_when_it_is_provisional(page, console, repos):
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    page.get_by_role("tab", name="Overview").click()
    page.get_by_role("button", name="Board summary").click()
    board = page.locator("#board")
    board.get_by_text("First five actions").wait_for()
    assert "to fix now" in board.inner_text() and "of 100" not in board.inner_text() and "Provisional" not in board.inner_text()
    page.evaluate("window.prints = 0; window.print = () => { window.prints += 1; }; 0")  # ends in 0: Playwright calls an expression that ends in a function
    board.get_by_role("button", name="Print or save as PDF").click()
    page.get_by_role("tab", name="Projects").click()
    page.get_by_role("button", name="Print or save as PDF").click()
    assert page.evaluate("window.prints") == 2, "one click prints once (R12)"
    page.get_by_role("tab", name="Overview").click()
    page.get_by_role("button", name="Board summary").click()
    board.get_by_text("First five actions").wait_for()
    page.evaluate("document.body.classList.add('board-print')")
    page.emulate_media(media="print")
    assert board.is_visible() and not page.locator("#ov").is_visible() and not page.get_by_role("tab", name="Projects").is_visible()
    page.emulate_media(media="screen")
    page.evaluate("document.body.classList.remove('board-print')")
    assert page.evaluate(AXE.read_text() + ";axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))") == []


def test_choosing_countries_and_sectors_sets_the_next_deadline_on_the_board(page, console, repos):
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    page.get_by_role("tab", name="Overview").click()
    page.get_by_text("Deadlines that apply to you: next 2030").click()
    page.get_by_label("India").check()
    page.get_by_label("Critical infrastructure").check()
    page.get_by_role("button", name="Save", exact=True).click()
    page.get_by_text("Deadlines that apply to you: next 2029").wait_for()
    page.get_by_role("button", name="Board summary").click()
    card = page.locator("#board .cards li").nth(3)
    card.get_by_text("2029").wait_for()
    assert "India" in card.inner_text()
    assert page.evaluate(AXE.read_text() + ";axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))") == []



@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_what_it_tracks_lists_every_kind_and_algorithm_and_passes_axe(browser, console, scheme):
    from acxelin_readiness.catalog import CATALOG
    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme=scheme)
    page = ctx.new_page()
    try:
        open_console(page, console)
        page.get_by_role("tab", name="What it tracks").click()
        page.get_by_role("heading", name="Every algorithm it knows").wait_for()
        text = page.locator("#panel").inner_text()
        assert not [name for name in CATALOG if name not in text]
        for kind in ("Algorithms", "Protocols", "Certificates", "Keys and key material", "Libraries"):
            assert page.get_by_role("heading", name=kind, exact=True).count() == 1, kind
        assert page.evaluate(AXE.read_text() + ";axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))") == []
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    finally:
        ctx.close()


def axe(page):
    return page.evaluate(AXE.read_text() + ";axe.run().then(r=>r.violations.map(v=>v.id+': '+v.help))")


def test_a_project_is_removed_only_after_confirming(page, console, repos):
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    page.once("dialog", lambda d: d.dismiss())
    page.get_by_role("button", name="Remove from QReadiness").click()
    expect(page.get_by_role("heading", name="shop", exact=True)).to_be_visible()
    asked = []
    page.once("dialog", lambda d: asked.append(d.message) or d.accept())
    page.get_by_role("button", name="Remove from QReadiness").click()
    page.get_by_text("Removed shop.").wait_for()
    assert "not touched" in asked[0] and "shop" in asked[0]
    assert not page.locator(".list button", has_text="shop").count()
    assert "shop" in page.get_by_label("Add a repository").inner_text(), "it can be added again"
    assert (repos / "shop/keys.py").exists()


def test_the_repositories_folder_can_be_changed_and_a_wrong_one_is_flagged_next_to_its_field(page, console, repos, tmp_path):
    (tmp_path / "work/web").mkdir(parents=True)
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    page.get_by_text("Change folder").click()
    field = page.get_by_label("Repositories folder")
    field.fill(str(tmp_path / "nope"))
    page.get_by_role("button", name="Use this folder").click()
    expect(field).to_have_attribute("aria-invalid", "true")
    error = page.locator("#" + field.get_attribute("aria-describedby"))
    assert error.inner_text().startswith("Choose an existing folder") and field.evaluate("e => e.nextElementSibling.id") == error.get_attribute("id")
    assert page.locator("#msg").inner_text() == "", "not in a banner at the top of the page (R6)"
    field.fill(str(tmp_path / "work"))
    page.get_by_role("button", name="Use this folder").click()
    page.get_by_label("Add a repository").locator("option", has_text="web").wait_for(state="attached")
    assert str((tmp_path / "work").resolve()) in page.locator("#panel").inner_text()


def test_a_github_link_that_leads_nowhere_is_not_kept(page, console):
    open_console(page, console)
    gone = rc.remote.Refused("Repository not found on GitHub. For a private repository, save a read-only access token first.")
    with patch("acxelin_readiness.console.remote.fetch", side_effect=gone):
        page.get_by_label("Repository link").fill("https://github.com/acme/no-such-repo")
        page.get_by_role("button", name="Download and scan").click()
        page.locator("#gh-error", has_text="It was not added to your projects.").wait_for()
    assert not page.get_by_text("github.com/acme/no-such-repo").count()
    page.get_by_role("tab", name="Overview").click()
    page.get_by_text("No projects yet").wait_for()


def test_an_accepted_risk_without_a_reason_is_flagged_next_to_that_field(page, console, repos):
    open_console(page, console)
    fill_setup(page, repos)
    scan_shop(page)
    page.locator("details.track summary").first.click()
    page.get_by_label("Status").first.select_option("exception")
    page.get_by_label("Accepted until").first.fill("2099-01-01")
    page.get_by_role("button", name="Save").first.click()
    reason = page.get_by_label("Why it is accepted").first
    expect(reason).to_have_attribute("aria-invalid", "true")
    error = page.locator("#" + reason.get_attribute("aria-describedby"))
    assert error.inner_text().startswith("Why it is accepted:") and reason.evaluate("e => e.nextElementSibling.id") == error.get_attribute("id")
    assert page.locator("#msg").inner_text() == ""
    assert axe(page) == []
    reason.fill("Vendor appliance, replaced in 2027")
    page.get_by_role("button", name="Save").first.click()
    page.get_by_text("Accepted risk until 2099-01-01").wait_for()


def test_each_host_keeps_its_last_grade_and_a_host_can_be_forgotten(page, console):
    open_console(page, console)
    page.get_by_role("tab", name="Endpoints").click()
    runs = iter([[grade("a.example:443", "C")], [grade("b.example:443", "F")]])
    with patch("acxelin_readiness.console.endpoints.scan", side_effect=lambda t: next(runs)):
        for host, g in (("a.example", "C"), ("b.example", "F")):
            page.get_by_label("Hosts to check").fill(host)
            page.get_by_role("button", name="Check endpoints").click()
            page.locator("#ep-result tr", has_text=host).locator(".pill", has_text=re.compile(f"^{g}:")).wait_for()
            expect(page.locator("#check")).to_be_enabled()
    table = page.locator("#ep-result table")
    assert "a.example:443" in table.inner_text(), "checking b did not wipe a's grade (R7)"
    page.once("dialog", lambda d: d.accept())
    page.get_by_role("button", name="Forget b.example:443").click()
    expect(table).not_to_contain_text("b.example:443")
    assert "a.example:443" in table.inner_text()


def test_a_certificate_this_computer_cannot_verify_is_reported_without_guessing_a_proxy(page, console):
    site = grade("acxelinquantum.com:443", "B") | {"trusted": False, "trust_error": "certificate has expired", "trust_code": 10,
                                                   "certificate": {"key": "ECDSA-secp384r1", "issuer": "CN=E7,O=Let's Encrypt,C=US", "expires": "2027-01-20",
                                                                   "days_left": 54, "quantum_safe": False}}
    open_console(page, console)
    page.get_by_role("tab", name="Endpoints").click()
    with patch("acxelin_readiness.console.endpoints.scan", side_effect=lambda t: [site]):
        page.get_by_label("Hosts to check").fill("acxelinquantum.com")
        page.get_by_role("button", name="Check endpoints").click()
        page.locator("#ep-result td .pill").first.wait_for()
    row = page.locator("#ep-result tr", has_text="acxelinquantum.com").inner_text()
    assert "This computer couldn't verify the certificate (certificate has expired)" in row
    assert "proxy" not in page.locator("#ep-result").inner_text().lower() and "inspect" not in page.locator("#ep-result").inner_text().lower()


def test_projects_results_and_overview_fit_a_phone_and_long_paths_wrap(browser, console, tmp_path):
    root = tmp_path / ("averylongfoldernamewithoutanyplacetobreakit" * 2) / "repositories"
    (root / "shop").mkdir(parents=True)
    (root / "shop/keys.py").write_text("from cryptography.hazmat.primitives.asymmetric import rsa\nimport hashlib\n"
                                       "rsa.generate_private_key(public_exponent=65537, key_size=2048)\nhashlib.md5(b'x')\n")
    fits = "document.documentElement.scrollWidth <= window.innerWidth"
    for width in (390, 1280):
        ctx = browser.new_context(viewport={"width": width, "height": 900})
        page = ctx.new_page()
        try:
            open_console(page, console)
            if width == 390:
                fill_setup(page, root)
                scan_shop(page)
            page.locator("#pj-result table").first.wait_for()
            page.locator("details.track summary").first.click()
            assert page.evaluate(fits), f"Projects scrolls sideways at {width} px (R11)"
            page.get_by_role("tab", name="Overview").click()
            page.locator("#ov table").wait_for()
            assert page.evaluate(fits), f"Overview scrolls sideways at {width} px"
        finally:
            ctx.close()


def test_scan_every_project_shows_progress_straight_away(page, console, repos):
    import time
    open_console(page, console)
    fill_setup(page, repos)
    page.get_by_role("tab", name="Overview").click()

    def slow(path, **kw):
        kw["progress"]("Analyzing source and cryptography")
        time.sleep(1.5)
        raise rc.workspace.ScanStopped("Scan cancelled; the previous completed assessment is preserved")
    with patch("acxelin_readiness.console.workspace.scan", side_effect=slow):
        page.get_by_role("button", name="Scan every project").click()
        page.locator("#ov-state progress").wait_for(timeout=2000)
        assert "Scanning 1 of 2" in page.locator("#ov-state").inner_text()
        expect(page.get_by_role("button", name="Scan every project")).to_be_disabled()
        page.get_by_text("Last run", exact=False).wait_for(timeout=15000)


def test_times_are_the_viewers_own_with_utc_on_hover(browser, console, repos):
    ctx = browser.new_context(timezone_id="Asia/Kolkata")  # UTC+5:30: the local time never reads like UTC
    page = ctx.new_page()
    try:
        open_console(page, console)
        fill_setup(page, repos)
        scan_shop(page)
        stamp = page.locator("#pj-result time").first
        shown, title = stamp.inner_text(), stamp.get_attribute("title")
        assert title.endswith(" UTC") and shown != title.removesuffix(" UTC") and re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d", shown)
        assert "UTC" not in page.locator("#pj-result").inner_text()
    finally:
        ctx.close()
