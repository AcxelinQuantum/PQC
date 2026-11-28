"""Film 1: Acxelin QReadiness. The problem on paper, then the real console doing real work: a scan of the product's example
project payments-api, three Acme test hosts graded A, B and C by real TLS servers, a finding given an owner and a date, the
services most at risk, a CycloneDX CBOM with the board summary, and what it tracks. Shot times come from the script."""
import json
import re
import time

import films
import qreadiness_world as world
from capture import VIEW, Recorder
from script import shots

W, H = VIEW["width"], VIEW["height"]
FPS = 30
HOSTS = list(world.HOSTS)  # A, B, C in that order
TITLE = "Acxelin QReadiness"


# ---- recording helpers

def until(rec, t):
    if rec.t < t:
        rec.hold(t - rec.t)


def centre(loc):
    b = loc.bounding_box()
    return round(b["x"] + b["width"] / 2), round(b["y"] + b["height"] / 2)


def click_at(rec, x, y, dur=0.8, settle=350, after=0.35):
    """Move to (x, y) and click there for real."""
    rec.move((x, y), dur)
    rec.cursor.append({"t": round(rec.t, 3), "x": round(x), "y": round(y), "click": True})
    rec.page.mouse.click(x, y)
    rec.page.wait_for_timeout(settle)
    rec.t += 0.12
    rec.shot(after)


def click(rec, loc, **kw):
    loc.scroll_into_view_if_needed()
    b = loc.bounding_box()
    click_at(rec, b["x"] + min(b["width"] / 2, 60 if b["width"] > 160 else b["width"] / 2), b["y"] + b["height"] / 2, **kw)


def keys(rec, text, cps=11.0):
    """Type into the focused field a character at a time, at a human pace."""
    for ch in text:
        if ch == "\n":
            rec.page.keyboard.press("Enter")
        else:
            rec.page.keyboard.type(ch)
        rec.shot(rec.rand.uniform(0.75, 1.25) / cps)


def choose(rec, select, value, dur=0.8):
    """Pick an option the way a viewer sees it: a click on the list, then the new value (a native drop-down is not filmed)."""
    x, y = centre(select)
    rec.move((x, y), dur)
    rec.cursor.append({"t": round(rec.t, 3), "x": x, "y": y, "click": True})
    rec.t += 0.5
    select.select_option(value)
    rec.page.wait_for_timeout(150)
    rec.shot(0.45)


def follow(rec, read, done, hold=0.9, limit=180):
    """Film each new state of read() once, until done(): the real wait is not filmed, every state it passes through is."""
    seen, end = object(), time.monotonic() + limit
    while time.monotonic() < end:
        now = read()
        if now != seen:
            rec.shot(hold)
            seen = now
        if done():
            return
        rec.page.wait_for_timeout(80)
    raise RuntimeError("the console did not finish in time")


def scroll_y(page):
    return page.evaluate("() => window.scrollY")


def jump(page, y):
    page.evaluate(f"() => window.scrollTo(0, {y})")
    page.wait_for_timeout(120)


def top_of(page, loc, margin=0):
    """The scroll position that puts `loc` `margin` pixels below the top of the window."""
    return max(0, round(scroll_y(page) + loc.bounding_box()["y"] - margin))


def pan(rec, y, dur, fps=FPS):
    """Scroll to y over dur seconds, a frame per film frame, easing in and out."""
    start = scroll_y(rec.page)
    n = max(1, round(dur * fps))
    for i in range(1, n + 1):
        k = i / n
        k = k * k * (3 - 2 * k)
        rec.page.evaluate(f"() => window.scrollTo(0, {start + (y - start) * k})")
        rec.shot(1 / fps)


def scene(rec, name, **marks):
    out = rec.save(name)
    out["marks"] = marks
    return out


# ---- the recording

def capture(raw):
    from playwright.sync_api import sync_playwright
    s = shots("qreadiness")
    repos, home = world.repositories()
    hosts = world.TestHosts(world.ACME / "hosts")
    scenes = {}
    try:
        app, ids = world.console(repos, home)
        server, base = world.serve(app, home)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                try:
                    ctx = browser.new_context(viewport=VIEW, device_scale_factor=2, accept_downloads=True, reduced_motion="reduce")
                    page = ctx.new_page()
                    page.set_default_timeout(60000)
                    ticket = app.sessions.ticket()
                    page.goto(f"{base}/#{ticket}")
                    page.get_by_text("things to fix now").first.wait_for()
                    page.wait_for_timeout(600)
                    record(page, raw, s, scenes, ticket, app, ids)
                finally:
                    browser.close()
        finally:
            server.shutdown()
    finally:
        hosts.close()
    return scenes


def record(page, raw, s, scenes, ticket, app, ids):
    rec = lambda name: Recorder(page, raw / name, banned=[ticket])

    # Meet: the console's home screen, customer-portal's last result open
    r = rec("home")
    r.hide()
    card = page.locator(".glance .cards li").first
    r.shot(s[5].end - s[5].start)
    scenes["home"] = scene(r, "home", card=centre(card))

    # 01 Scan, the result, and the breather: one continuous take
    s6, s7, s8 = s[6], s[7], s[8]
    t0 = films.body(s6)
    r = rec("project")
    r.shot(0.9)
    click(r, page.locator(".side .list button", has_text="payments-api"))
    page.get_by_text("Not scanned yet").wait_for()
    r.shot(2.0)
    click(r, page.locator("#scan"), settle=50, after=0.0)
    follow(r, lambda: page.locator("#pj-state").inner_text(), lambda: page.locator(".glance .cards li").count() > 0, hold=1.6)
    page.wait_for_timeout(500)
    r.shot(0.0)
    results_at = r.t
    count = centre(page.locator(".glance .cards li").first)
    r.move((count[0] + 160, count[1] + 120), 1.2)
    r.shot(0)
    until(r, s7.start - t0 + 5.2)  # the push in and its 2 s hold happen on this frame
    row = page.locator("#pj-result tr", has=page.locator("details.where summary", has_text=re.compile(r"^AES-ECB$")))
    r.hide()
    pan(r, top_of(page, page.locator("#pj-result table").first, 150), 1.4)
    summary = row.locator("details.where summary")
    click(r, summary)
    r.hold(1.3)
    click(r, row.locator("details.fix summary"))
    page.wait_for_timeout(200)
    r.shot(0)
    fix_box = row.bounding_box()
    found_at = r.t
    until(r, s8.start - t0)
    # the breather: from "What we found" down to "What to do"
    r.hide()
    breather_at = r.t
    jump(page, top_of(page, page.locator("#pj-descriptive"), 70))
    r.shot(0.6)
    pan(r, top_of(page, page.locator("#pj-prescriptive"), 90), s8.end - s8.start - 1.0, fps=24)
    r.hold(0.6)
    scenes["project"] = scene(r, "project", results=results_at, count=count, found=found_at,
                              row={"x": fix_box["x"], "y": fix_box["y"], "w": fix_box["width"], "h": fix_box["height"]}, breather=breather_at)

    # 02 Grade: three Acme test hosts typed in and checked
    s9, s10 = s[9], s[10]
    jump(page, 0)
    r = rec("grade")
    r.shot(0.6)
    click(r, page.locator("#tab-endpoints"))
    page.locator("#targets").wait_for()
    r.shot(0.5)
    click(r, page.locator("#targets"), after=0.2)
    keys(r, "\n".join(HOSTS), cps=13)
    click(r, page.locator("#check"), settle=100, after=0.0)
    follow(r, lambda: page.locator("#ep-state").inner_text(), lambda: page.locator("#ep-result tbody tr").count() == 3, hold=1.0)
    page.wait_for_timeout(400)
    r.shot(0)
    until(r, s10.start - films.body(s9))
    r.hide()
    table = page.locator("#ep-result table").first
    pan(r, top_of(page, table, 120), 1.5)
    grades = {g: centre(page.locator("#ep-result tbody tr").nth(i).locator(".pill")) for i, g in enumerate("ABC")}
    reasons = page.locator("#ep-diagnostic").locator("xpath=..").locator("dl.key dd")
    graded_at = r.t
    r.shot(0)
    until(r, s10.end - films.body(s9) + 0.4)
    c_row = page.locator("#ep-result tbody tr").nth(2).bounding_box()
    scenes["grade"] = scene(r, "grade", graded=graded_at, grades=grades, c_row=[c_row["x"], c_row["y"], c_row["width"], c_row["height"]],
                            reasons=[centre(reasons.nth(i)) for i in range(reasons.count())] if reasons.count() else [])

    # 03 Track: AES-ECB gets an owner and a due date, then moves from Planned to In progress
    s11 = s[11]
    page.locator("#tab-projects").click()
    page.locator(".glance .cards li").first.wait_for()
    page.wait_for_timeout(300)
    row = lambda: page.locator("#pj-result tr", has=page.locator("details.where summary", has_text=re.compile(r"^AES-ECB$")))
    jump(page, top_of(page, page.locator("#pj-progress"), 40) if page.locator("#pj-progress").count() else top_of(page, page.locator("#pj-result table"), 160))
    r = rec("track")
    r.shot(0.8)
    click(r, row().locator("details.track > summary"))
    form = row().locator("details.track form")
    owner, due, status = form.locator("input[type=text]").first, form.locator("input[type=date]").first, form.locator("select")
    click(r, owner, after=0.2)
    keys(r, "Payments team")
    b = due.bounding_box()
    click_at(r, b["x"] + 16, b["y"] + b["height"] / 2, after=0.2)
    keys(r, "03312027", cps=9)
    choose(r, status, "planned")
    click(r, form.locator("button[type=submit]"), settle=600, after=1.4)
    click(r, row().locator("details.track > summary"))
    choose(r, row().locator("details.track form select"), "in_progress")
    click(r, row().locator("details.track form button[type=submit]"), settle=600, after=0.3)
    r.hide()
    r.shot(0)
    done_at = r.t
    label = centre(row().locator("details.track > summary"))
    progress = centre(page.locator("#pj-progress")) if page.locator("#pj-progress").count() else label
    until(r, s11.end - films.body(s11) + 0.4)
    scenes["track"] = scene(r, "track", done=done_at, label=label, progress=progress)

    # Acme's owners spreadsheet for payments-api (Projects, Owners from a CMDB export), so the overview can rank its services
    world.owners(app, ids["payments-api"], "payments-api")

    # Overview: services most at risk
    s12 = s[12]
    jump(page, 0)
    page.locator("#tab-overview").click()
    page.get_by_role("heading", name="Services most at risk").wait_for()
    page.wait_for_timeout(500)
    heading = page.get_by_role("heading", name="Services most at risk")
    jump(page, top_of(page, heading, 210))
    r = rec("overview")
    r.hide()
    table = page.locator("#ov table").nth(1)
    tb = table.bounding_box()
    r.shot(s12.end - s12.start + 0.6)
    scenes["overview"] = scene(r, "overview", table=[tb["x"], tb["y"], tb["width"], tb["height"]], heading=centre(heading))

    # 04 Share: the CBOM from Endpoints, then the board summary
    page.locator("#tab-endpoints").click()
    page.locator("#export").wait_for()
    page.wait_for_timeout(400)
    jump(page, 10**6)
    r = rec("cbom")
    r.shot(0.6)
    with page.expect_download(timeout=180000) as got:
        click(r, page.locator("#export"), settle=50, after=0.0)
    path = world.ACME / "endpoints-cbom.json"
    got.value.save_as(path)
    page.get_by_text("Downloaded endpoints-cbom.json").wait_for()
    page.wait_for_timeout(200)
    r.shot(0)
    downloaded_at = r.t
    note = centre(page.locator("#ep-export"))
    r.hold(3.0)
    scenes["cbom"] = scene(r, "cbom", downloaded=downloaded_at, note=note, head=path.read_text(encoding="utf-8").splitlines()[:16])

    jump(page, 0)
    page.locator("#tab-overview").click()
    page.locator("#board-btn").wait_for()
    page.wait_for_timeout(400)
    r = rec("board")
    r.shot(0.5)
    click(r, page.locator("#board-btn"), settle=900, after=0.0)
    page.locator("#board").wait_for()
    jump(page, top_of(page, page.locator("#board"), 24))
    r.hide()
    r.shot(0)
    board_at = r.t
    cards = centre(page.locator("#board .cards"))
    r.hold(9.0)
    scenes["board"] = scene(r, "board", board=board_at, cards=cards)

    # Coverage: every algorithm it knows
    s14 = s[14]
    jump(page, 0)
    page.locator("#tab-coverage").click()
    page.get_by_role("heading", name="Every algorithm it knows").wait_for()
    page.wait_for_timeout(400)
    known = page.get_by_role("heading", name="Every algorithm it knows")
    jump(page, top_of(page, known, 110))
    r = rec("coverage")
    r.hide()
    r.shot(1.0)
    groups = page.locator(".cov-group")
    pan(r, top_of(page, groups.nth(min(3, groups.count() - 1)), 120), s14.end - s14.start - 1.4, fps=24)
    r.hold(1.0)
    scenes["coverage"] = scene(r, "coverage")


# ---- the film

def problem(s):
    a, b, c = s[2], s[3], s[4]
    card = {"kind": "box", "text": "", "x": 360, "y": 290, "w": 1200, "style": {"height": "480px", "borderRadius": "22px"}}
    first = [{**card, "at": 0.2, "dur": 0.9},
             {"kind": "note", "text": "Board meeting · item 4", "x": 470, "y": 380, "at": 0.8},
             {"kind": "quote", "text": a.text.strip('"'), "x": 470, "y": 505, "w": 1000, "at": 1.4, "dur": 0.9}]
    second = [{**card, "at": -1},
              {"kind": "note", "text": "The honest answer", "x": 470, "y": 380, "at": -1},
              {"kind": "quote", "text": b.text.strip('"'), "x": 470, "y": 468, "w": 1000, "at": -1}]
    words = [t.strip("`") for t in c.text.split(" · ")]
    samples = ['Cipher.getInstance( "AES/ECB/PKCS5Padding")', "ssl_protocols TLSv1.1 TLSv1.2;", "api.crt · RSA-2048", "billing.acme.example:443"]
    push_at = 4.6
    tiles = []
    for i, (word, sample) in enumerate(zip(words, samples)):
        tiles.append({"kind": "box", "text": f"`{word}`", "sub": sample, "x": 140 + i * 420, "y": 410, "w": 380, "at": 0.4 + 0.15 * i, "dur": 0.7,
                      "out": push_at if i < 2 else None, "style": {"height": "230px", "fontSize": "40px", "overflowWrap": "anywhere"}})
    tiles.append({"kind": "tag", "text": "last login: years ago", "x": 1430, "y": 572, "at": 2.4, "dur": 0.8})
    drift = lambda shot: [{"t": 0, "s": 1.0, "fx": 960, "fy": 530}, {"t": shot.end - shot.start, "s": 1.04, "fx": 960, "fy": 530, "dur": shot.end - shot.start}]
    return [
        {"type": "diagram", "start": a.start, "end": b.start + 0.3, "fadeIn": 0.6, "fadeOut": 0.3, "items": first, "camera": drift(a)},
        {"type": "diagram", "start": b.start, "end": c.start + 0.3, "fadeIn": 0.3, "fadeOut": 0.3, "items": second, "camera": drift(b)},
        {"type": "diagram", "start": c.start, "end": c.end, "fadeIn": 0.3, "fadeOut": 0.4, "items": tiles,
         "camera": [{"t": 0, "s": 1.0, "fx": 960, "fy": 530}, {"t": push_at, "s": 1.0, "fx": 960, "fy": 530},
                    {"t": c.end - c.start - 0.5, "s": 1.3, "fx": 1590, "fy": 540, "dur": c.end - c.start - 0.5 - push_at}]},
    ]


def push(t, at, s=1.35, dur=1.5):
    return {"t": t, "s": s, "fx": at[0], "fy": at[1], "dur": dur}


def rest(t, dur=1.4):
    return {"t": t, "s": 1.0, "fx": W / 2, "fy": H / 2, "dur": dur}


def scenes(s, sc):
    out = []
    meet_end = s[5].start + 8.0
    out += films.meet(s, meet_end)
    home = sc["home"]
    out.append(films.window(s[5], home, start=meet_end, title=TITLE, enter="rise",
                            camera=[rest(0, 0), rest(4.0, 0), push(s[5].end - meet_end - 0.4, home["marks"]["card"], 1.15, 6.0)]))

    # 01 Scan, the result and the breather
    p, m = sc["project"], sc["project"]["marks"]
    t0 = films.body(s[6])
    r7 = s[7].start - t0
    found = m["found"]
    row = m["row"]
    cam = [rest(0, 0), rest(r7, 0), push(r7 + 1.6, m["count"], 1.4, 1.6), push(r7 + 3.8, m["count"], 1.4, 0.1), rest(r7 + 5.2, 1.4),
           rest(found + 0.2, 0.1), push(found + 1.8, (row["x"] + row["w"] * 0.42, row["y"] + row["h"] / 2), 1.3, 1.6),
           push(s[8].start - t0 - 1.6, (row["x"] + row["w"] * 0.42, row["y"] + row["h"] / 2), 1.3, 0.1), rest(s[8].start - t0 - 0.1, 1.4)]
    out.append(films.window(s[6], p, end=s[8].start + 0.3, title=TITLE, camera=cam))
    br = films.window(s[8], p, title=TITLE, offset=m["breather"], camera=[rest(0, 0)])
    br["fadeIn"] = 0.3
    out.append(br)

    # 02 Grade
    g, gm = sc["grade"], sc["grade"]["marks"]
    b9 = films.body(s[9])
    c = gm["c_row"]
    why = gm["reasons"][2][1] if len(gm["reasons"]) > 2 else c[1] + c[3]
    c_at = (560, (c[1] + 20 + why) / 2)  # the C row and, below it, the C reason under Why it matters
    out.append(films.window(s[9], g, end=s[10].end, title=TITLE,
                            camera=[rest(0, 0), rest(gm["graded"] + 1.0, 0.1), push(gm["graded"] + 3.0, c_at, 1.3, 1.8),
                                    push(s[10].end - b9 - 1.6, c_at, 1.3, 0.1), rest(s[10].end - b9, 1.5)]))

    # 03 Track
    t, tm = sc["track"], sc["track"]["marks"]
    b11 = films.body(s[11])
    lab = tm["label"]
    out.append(films.window(s[11], t, end=s[12].start + 0.3, title=TITLE,
                            camera=[rest(0, 0), rest(tm["done"] + 0.1, 0.1), push(tm["done"] + 1.7, (lab[0] - 260, lab[1] - 60), 1.3, 1.6),
                                    push(s[11].end - b11 - 1.4, (lab[0] - 260, lab[1] - 60), 1.3, 0.1), rest(s[11].end - b11 + 0.3, 1.4)]))

    # Overview: services most at risk
    o, om = sc["overview"], sc["overview"]["marks"]
    tb = om["table"]
    ov = films.window(s[12], o, end=s[13].start, title=TITLE,
                      camera=[rest(0, 0), push(s[12].end - s[12].start - 1.0, (tb[0] + tb[2] * 0.4, tb[1] + tb[3] * 0.45), 1.25, 7.0)])
    ov["fadeIn"] = 0.3
    out.append(ov)

    # 04 Share: Download CBOM, the file's first lines in a terminal, then the board summary
    b13 = films.body(s[13])
    cb, cm = sc["cbom"], sc["cbom"]["marks"]
    term_at = b13 + cm["downloaded"] + 1.8
    out.append(films.window(s[13], cb, end=term_at, title=TITLE,
                            camera=[rest(0, 0), rest(cm["downloaded"] - 0.2, 0.1), push(cm["downloaded"] + 1.6, cm["note"], 1.3, 1.4)]))
    lines = [{"t": 0.4, "kind": "cmd", "text": "head -n 12 endpoints-cbom.json", "cps": 18}]
    lines += [{"t": 2.4 + 0.05 * i, "kind": "dim" if i == 0 else "", "text": line} for i, line in enumerate(cm["head"][:12])]
    board_at = term_at + 6.6
    out.append(films.terminal(term_at, board_at + 0.3, lines, title="Terminal · C:\\acme\\qreadiness", w=1100, h=560))
    bd, bm = sc["board"], sc["board"]["marks"]
    lead = 1.2  # the click on Board summary starts this long before the summary shows
    bw = films.window(s[13], bd, start=board_at, offset=max(0.0, bm["board"] - lead), title=TITLE,
                      camera=[rest(0, 0), rest(lead + 0.4, 0.1), push(lead + 2.4, bm["cards"], 1.25, 2.0)])
    bw["fadeIn"] = 0.3
    out.append(bw)

    # Coverage breather
    out.append(films.window(s[14], sc["coverage"], title=TITLE, camera=[rest(0, 0)]))
    return out


def _social():
    """15 s: the risk in one spoken line, the scan's verdict on screen, then the name and its signature line."""
    s = shots("qreadiness")
    hook, result, close = s[1], s[7], s[-1]
    return [(hook.start + 0.1, hook.start + 7.1, True), (result.start + 1.0, result.start + 4.0, False), (close.start + 0.2, close.start + 5.2, True)]


SOCIAL = _social()


def thumb_frame(scenes):
    p = scenes["project"]
    at = p["marks"]["results"] + 0.5
    return [f for f in p["frames"] if f["t"] <= at][-1]["src"]


if __name__ == "__main__":
    print(json.dumps(SOCIAL))
