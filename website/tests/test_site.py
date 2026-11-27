"""The website in a real browser: a short showcase. From the home page to each product and to a conversation; each product page
names only its product and shows real, current screenshots of it; no install or manual content; working links; every earlier
address lands on the product; accessibility on every page in light, dark and mobile."""
import functools
import http.server
import re
import sys
import threading
from pathlib import Path

import pytest

sync = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[2]
AXE = ROOT / "tools/browser/node_modules/axe-core/axe.min.js"
sys.path.insert(0, str(ROOT / "tools"))
import build_site  # noqa: E402

PAGES = ["index.html"] + [f"{s}/index.html" for s in build_site.SECTIONS]
OLD = re.compile(r"Wolf ?Pack|wolfpack", re.I)
CONTACT = "https://acxelinquantum.com/"


@pytest.fixture(scope="module")
def site():
    build_site.main()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(build_site.OUT))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", build_site.OUT
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"no Playwright browser: {e}")
        yield b
        b.close()


@pytest.mark.parametrize("section", build_site.SECTIONS)
def test_home_to_the_product_and_to_a_conversation(browser, site, section):
    base, _ = site
    name = build_site.SECTIONS[section]
    page = browser.new_page()
    page.goto(base + "/index.html")
    page.get_by_role("link", name=f"See {name}").click()
    page.get_by_role("heading", level=1).wait_for()
    assert page.url.endswith(f"/{section}/")
    assert page.locator("figure.shot img").count() >= 1
    assert "Nothing is sent to Acxelin Quantum" in page.inner_text("main")
    assert page.get_by_role("link", name="Talk to Acxelin Quantum").first.get_attribute("href") == CONTACT
    page.close()


def test_each_product_page_names_only_its_own_product_and_the_home_page_names_all(browser, site):
    base, _ = site
    page = browser.new_page()
    for section, name in build_site.SECTIONS.items():
        page.goto(f"{base}/{section}/")
        text = page.inner_text("body")
        others = [n for s, n in build_site.SECTIONS.items() if s != section]
        assert not [o for o in others if o in text], section
        assert not OLD.search(text), section
        assert [a.inner_text() for a in page.get_by_role("navigation", name=name).get_by_role("link").all()] == [name]
    page.goto(base + "/index.html")
    assert all(n in page.inner_text("body") for n in build_site.SECTIONS.values())
    page.close()


def test_the_site_shows_products_not_installation_or_manuals(site):
    _, out = site
    for path in PAGES:
        text = (out / path).read_text(encoding="utf-8")
        for word in ("install.sh", "install.ps1", "pip install", "docker", "wheelhouse", "<pre", "Set up", "Manual"):
            assert word not in text, (path, word)
        assert not re.search(r"\s--[a-z]", text), (path, "a command-line option")


def test_screenshots_are_current_output_of_the_products_in_this_checkout():
    """Each screenshot records a digest of the console files it was made from (tools/capture_screens.py); a change to those files
    without a new screenshot fails here, so the site never shows a console that no longer exists."""
    stale = []
    for screen in build_site.SCREENS:
        path = ROOT / "website/assets/screens" / screen
        if not path.exists():
            stale.append(f"{screen}: missing")
        elif build_site.png_text(path).get(build_site.KEY) != build_site.digest(screen):
            stale.append(f"{screen}: made from other files than this checkout's")
    assert not stale, "run python tools/capture_screens.py:\n" + "\n".join(stale)


def test_images_load_and_every_internal_link_resolves(browser, site):
    base, out = site
    page = browser.new_page()
    broken = []
    for path in PAGES:
        page.goto(f"{base}/{path}")
        assert page.evaluate("[...document.images].every(i => i.complete && i.naturalWidth > 0)"), path
        for href in page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))"):
            if href.startswith(("http", "#", "mailto:")):
                continue
            if href.split("#")[0].endswith("index.html"):
                broken.append((path, href, "link the folder, so the address does not show index.html"))
            if not ((out / path).parent / href.split("#")[0]).exists():
                broken.append((path, href))
    assert not broken, broken
    page.close()


@pytest.mark.parametrize("scheme,width", [("light", 1280), ("dark", 1280), ("light", 390)])
def test_every_page_passes_axe_and_does_not_scroll_sideways(browser, site, scheme, width):
    base, _ = site
    ctx = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
    page = ctx.new_page()
    axe = AXE.read_text()
    found = {}
    for path in PAGES:
        page.goto(f"{base}/{path}")
        page.wait_for_load_state("networkidle")
        v = page.evaluate(axe + ";axe.run().then(r=>r.violations.map(v=>v.id+': '+v.nodes.slice(0,2).map(n=>n.html.slice(0,60)).join(' | ')))")
        if v:
            found[path] = v
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (path, "scrolls sideways")
    assert not found, found
    ctx.close()


def test_skip_link_reaches_the_main_content(browser, site):
    base, _ = site
    page = browser.new_page()
    page.goto(base + "/qguard/")
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.className") == "skip"
    page.keyboard.press("Enter")
    assert page.evaluate("location.hash") == "#main"
    page.close()


def test_no_page_has_a_browser_error(browser, site):
    base, _ = site
    page = browser.new_page()
    problems = []
    page.on("console", lambda m: m.type == "error" and problems.append(f"console: {m.text}"))
    page.on("pageerror", lambda e: problems.append(f"exception: {e}"))
    page.on("requestfailed", lambda r: problems.append(f"failed: {r.url} {r.failure}"))
    page.on("response", lambda r: r.status >= 400 and problems.append(f"HTTP {r.status}: {r.url}"))
    for path in PAGES:
        page.goto(f"{base}/{path}")
        page.wait_for_load_state("networkidle")
    assert problems == []
    page.close()


def test_every_earlier_address_lands_on_the_product(browser, site):
    base, _ = site
    page = browser.new_page()
    for section in build_site.SECTIONS:
        for old in ("set-up.html", "manual.html", "how-it-works.html"):
            page.goto(f"{base}/{section}/{old}")
            page.wait_for_url(f"{base}/{section}/")
    for old, new in build_site.MOVED.items():
        for path in ("", "set-up.html", "manual.html"):
            page.goto(f"{base}/{old}/{path}")
            page.wait_for_url(f"{base}/{new}/")
    page.close()
