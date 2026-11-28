"""Film 2: Acxelin QGuard, with QCertificate. The problem on paper, then the real console protecting Acme's services: the
shop protected and QGuard started, watch mode and enforcement beside a real terminal, a partner certificate issued and
revoked (with the real time it took to be refused), and a connection checked. Acme's world is in qguard_world.py."""
import shutil
import time

import films
from capture import VIEW, Recorder
from script import shots
from qguard_world import CERTS, DEMO, INTRANET, PARTNERS, SHOP, World

# A split frame: the console on the left, the terminal on the right, both inside the frame.
CONSOLE_BOX = {"x": 56, "y": 200, "w": 1040}
TERM_BOX, TERM_W, TERM_H = {"x": 1118, "y": 200, "w": 746}, 820, 706
# The stage paints every window layer on its own dark background, so a second window would hide the first. Until the stage
# can leave a boxed window's background out, this rule (carried by the revocation marker) clears it for the right-hand terminal.
SPLIT_FIX = '<style>#frame>.layer.dark:has(>.cam>.win[style*="left: 1118px"]){background:none!important}</style>'


# ---- recording

def mark(scene, rec, name):
    scene.setdefault("marks", {})[name] = round(rec.t, 3)


def spot(scene, name, loc):
    b = loc.bounding_box()
    scene.setdefault("focus", {})[name] = [round(b["x"] + b["width"] / 2), round(b["y"] + b["height"] / 2)]


def bring(rec, loc, top=150, dur=1.2):
    """Scroll smoothly so `loc` sits `top` pixels from the top of the window."""
    y = rec.page.evaluate("() => window.scrollY") + loc.bounding_box()["y"] - top
    most = rec.page.evaluate("() => document.documentElement.scrollHeight - innerHeight")
    y = max(0, min(most, y))
    if abs(y - rec.page.evaluate("() => window.scrollY")) > 4:
        rec.scroll(y, dur)


def press(rec, target, ready, dur=0.7, after=0.35):
    """Move to `target`, click it for real, and take the next frame once `ready` (a locator) shows the result."""
    rec.move(target, dur)
    rec.cursor.append({"t": round(rec.t, 3), "x": round(rec.pos[0]), "y": round(rec.pos[1]), "click": True})
    target.click()
    ready.wait_for(timeout=40000)
    rec.page.wait_for_timeout(300)
    rec.t += 0.15
    rec.shot(after)


def save(rec, extra):
    scene = rec.save(rec.folder.name)
    scene.update(extra)
    return scene


def term(code_out):
    """curl's real output as terminal lines: an error in red, a 200 in green, the rest plain."""
    code, out = code_out
    lines = []
    for line in out.split("\n"):
        kind = "bad" if line.startswith("curl:") else "ok" if line.startswith("HTTP/") and " 200 " in line else "out"
        lines.append({"text": line or " ", "kind": kind})
    return {"code": code, "lines": lines}


def capture(raw):
    from playwright.sync_api import sync_playwright
    scenes, terminal = {}, {}
    with World() as w, sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport=VIEW, device_scale_factor=2)
            ticket = w.ticket()
            page.goto(f"{w.base}/#{ticket}")
            page.get_by_role("tab", name="Overview").wait_for()
            ban = [ticket, *w.secrets()]
            tab = lambda name: page.get_by_role("tab", name=name)

            # 01 Protect: the shop, then QGuard started from the console
            tab("Services").click()
            page.get_by_role("button", name="Protect a service").wait_for()
            page.wait_for_timeout(400)
            rec, sc = Recorder(page, raw / "protect", ban), {}
            rec.shot(1.0)
            rec.click(page.get_by_role("button", name="Protect a service"), after=0.6)
            rec.click(page.locator("label:has(input[value=website])"), dur=0.8, after=0.3)
            rec.type(page.locator("#s-host"), SHOP)
            rec.hold(0.3)
            rec.click(page.locator("#s-port"), dur=0.5, after=0.4)
            rec.type(page.locator("#s-target"), "127.0.0.1:8080")
            bring(rec, page.locator("#s-target"), top=120)
            rec.type(page.locator("#s-pub"), str(CERTS / "fullchain.pem").replace("/", "\\"), cps=16)
            rec.type(page.locator("#s-pubkey"), str(CERTS / "privkey.pem").replace("/", "\\"), cps=16)
            rec.hold(0.4)
            mark(sc, rec, "submit")
            press(rec, page.get_by_role("button", name="Protect service", exact=True), page.get_by_role("button", name="Start QGuard on this computer"), after=0.8)
            spot(sc, "added", page.locator(f"section.svc:has(h2:text-is('{SHOP}:443'))"))
            bring(rec, page.locator("#guard-h"), top=330, dur=1.0)
            rec.hold(0.3)
            start = page.get_by_role("button", name="Start QGuard on this computer")
            press(rec, start, page.get_by_text("QGuard is running, started from this console"), after=0.2)
            mark(sc, rec, "running")
            spot(sc, "running", page.get_by_text("QGuard is running, started from this console"))
            rec.hide()
            rec.shot(6.0)
            scenes["protect"] = save(rec, sc)

            # The breather: the first real connections arrive
            rec, sc = Recorder(page, raw / "overview", ban), {}
            rec.shot(0.4)
            rec.click(tab("Overview"), dur=0.8, after=0.2)
            page.get_by_text("Protected services").wait_for()
            rec.shot(2.0)
            spot(sc, "table", page.locator("table"))
            for _ in range(3):
                w.hello(SHOP)
            time.sleep(0.4)
            rec.click(tab("Overview"), dur=0.5, after=2.2)
            for classical in (False, False, True, False):
                w.hello(INTRANET, classical=classical)
            time.sleep(0.4)
            rec.click(tab("Overview"), dur=0.5, after=0.2)
            rec.hide()
            rec.shot(6.0)
            scenes["overview"] = save(rec, sc)

            # 02 Watch, then enforcement beside the terminal
            rec, sc = Recorder(page, raw / "watch", ban), {}
            tab("Services").click()
            item = page.locator(f"section.svc:has(h2:text-is('{INTRANET}:443'))")
            item.wait_for()
            page.wait_for_timeout(400)
            rec.shot(0.6)
            bring(rec, item, top=200, dur=1.4)
            rec.hold(0.4)
            reason = item.get_by_text("Why they would be refused")
            spot(sc, "reason", reason)
            spot(sc, "item", item)
            rec.shot(12.0)
            mark(sc, rec, "enforce")
            rec.click(item.get_by_role("button", name="Turn on enforcement"), dur=0.8, after=0.9)
            press(rec, item.get_by_role("button", name="Confirm: refuse clients that are not quantum-safe"),
                  page.locator(f"section.svc:has(h2:text-is('{INTRANET}:443')) .pill.ok"), dur=0.35, after=0.2)
            mark(sc, rec, "enforced")
            spot(sc, "enforced", page.locator(f"section.svc:has(h2:text-is('{INTRANET}:443'))"))
            rec.hide()
            rec.shot(12.0)
            scenes["watch"] = save(rec, sc)
            w.wait_for(lambda: isinstance(w.hello(INTRANET, classical=True), Exception))  # QGuard has applied the change
            terminal["old"] = term(w.curl("--curves", "X25519", "-i", f"https://{INTRANET}/"))
            terminal["new"] = term(w.curl("-i", f"https://{INTRANET}/"))

            # 03 QCertificate: the authority, a partner's certificate, and its revocation
            rec, sc = Recorder(page, raw / "qcert", ban), {}
            rec.shot(0.4)
            rec.click(tab("QCertificate"), dur=0.8, after=0.2)
            page.locator("#auth-h").wait_for()
            page.wait_for_timeout(300)
            rec.shot(1.0)
            bring(rec, page.locator("#auth-h"), top=260, dur=2.2)
            spot(sc, "authority", page.get_by_text("(post-quantum)"))
            rec.shot(6.0)
            mark(sc, rec, "issue")
            rec.scroll(0, dur=1.4)
            kind = page.locator("#kind")
            rec.move(kind, 0.7)
            rec.cursor.append({"t": round(rec.t, 3), "x": round(rec.pos[0]), "y": round(rec.pos[1]), "click": True})
            kind.select_option("client")
            rec.t += 0.15
            rec.shot(0.5)
            rec.type(page.locator("#cn"), "acme-partner")
            rec.hold(0.3)
            press(rec, page.get_by_role("button", name="Issue certificate"), page.get_by_text("Issued acme-partner."), after=0.2)
            mark(sc, rec, "issued")
            spot(sc, "issued", page.locator("#issued"))
            rec.hide()
            rec.shot(5.0)
            issued = w.call("/api/certificates")["certificates"]
            partner = next(c for c in issued if c["common_name"] == "acme-partner")
            folder = next((w.state.home / "issued").glob("acme-partner-*"))
            shutil.copy(folder / "chain.pem", DEMO / "acme-partner.pem")
            shutil.copy(folder / "key.pem", DEMO / "acme-partner.key")
            with_cert = ("-i", "--cert", "acme-partner.pem", "--key", "acme-partner.key", f"https://{PARTNERS}/")
            terminal["partner"] = term(w.curl(*with_cert))
            terminal["stranger"] = term(w.curl("-i", f"https://{PARTNERS}/"))

            mark(sc, rec, "revoke")
            row = page.locator("tr", has=page.get_by_role("cell", name="acme-partner", exact=True))
            bring(rec, row, top=420, dur=1.6)
            rec.hold(0.3)
            rec.click(row.get_by_role("button", name="Revoke"), dur=0.8, after=0.9)
            confirm = row.get_by_role("button", name="Confirm revoke acme-partner")
            rec.move(confirm, 0.35)
            rec.cursor.append({"t": round(rec.t, 3), "x": round(rec.pos[0]), "y": round(rec.pos[1]), "click": True})
            revoked_at = time.monotonic()
            confirm.click()
            page.locator("tr", has=page.get_by_role("cell", name="acme-partner", exact=True)).locator(".pill.bad").wait_for()
            listed_after = time.monotonic() - revoked_at
            calls, tries = [], []
            while True:  # the partner keeps calling; stop at the first refusal
                tries.append(round(time.monotonic() - revoked_at, 2))
                code, out = w.curl(*with_cert)
                calls.append(term((code, out)))
                if code != 0 or time.monotonic() - revoked_at > 90:
                    break
            refused_after = time.monotonic() - revoked_at
            page.wait_for_timeout(200)
            rec.t += 0.15
            rec.shot(0.2)
            mark(sc, rec, "revoked")
            spot(sc, "revoked", page.locator("tr", has=page.get_by_role("cell", name="acme-partner", exact=True)))
            rec.hide()
            rec.shot(12.0)
            scenes["qcert"] = save(rec, sc)
            terminal["revoked"] = calls
            terminal["refused_after"] = round(refused_after, 1)
            terminal["timing"] = {"revoked_in_console": round(listed_after, 2), "calls_started": tries}
            terminal["partner_serial"] = partner["serial"][:8]

            # 04 Check a connection
            rec, sc = Recorder(page, raw / "check", ban), {}
            rec.scroll(0, dur=0.1)
            rec.shot(0.5)
            rec.click(tab("Check a connection"), dur=0.8, after=0.4)
            rec.type(page.locator("#c-target"), "127.0.0.1:443")
            rec.click(page.locator("label:has(input[value=qcertificate])"), dur=0.8, after=0.4)
            rec.click(page.get_by_text("More options"), dur=0.7, after=0.4)
            rec.type(page.locator("#c-name"), INTRANET)
            rec.hold(0.3)
            press(rec, page.get_by_role("button", name="Check", exact=True), page.locator(".verdict"), after=0.5)
            mark(sc, rec, "verdict")
            bring(rec, page.locator(".verdict"), top=330, dur=1.2)
            spot(sc, "verdict", page.locator(".verdict"))
            spot(sc, "result", page.locator("#c-result"))
            rec.hide()
            rec.shot(10.0)
            scenes["check"] = save(rec, sc)
            page.close()
        finally:
            browser.close()
    scenes["terminal"] = terminal
    return scenes


# ---- the film

def problem(s):
    """0:15-0:45: a tidy plan on a slide; reality's tags; the system nobody touches."""
    a, b, c = s[2], s[3], s[4]
    t0 = a.start
    at = lambda shot, dt: shot.start - t0 + dt
    boxes = [("website", 470, "built 2014"), ("API", 830, "vendor's code"), ("database", 1190, "can't restart")]
    items = [{"kind": "box", "text": "", "x": 380, "y": 170, "w": 1160, "style": {"height": "560px"}, "at": 0.2, "dur": 0.9},
             {"kind": "note", "text": "Quantum-safe migration plan", "x": 450, "y": 220, "at": 0.8}]
    for i, (name, x, tag) in enumerate(boxes):
        items.append({"kind": "box", "text": name, "sub": "→ quantum-safe", "x": x, "y": 360, "w": 260, "at": 1.4 + 0.35 * i,
                      **({"dim": at(c, 0.4)} if name == "database" else {})})
        items.append({"kind": "tag", "text": tag, "x": x + 14, "y": 520, "at": at(b, 0.6 + 0.15 * i)})
    items.append({"kind": "tag", "text": "please don't touch", "x": 1204, "y": 312, "at": at(c, 1.0), "style": {"color": "#ad3218", "borderColor": "#e6a090", "background": "#fde9e4"}})
    items.append({"kind": "quote", "text": "Our services can't be rewritten in time.", "x": 420, "y": 820, "at": at(b, 1.4), "out": at(c, 0.0)})
    camera = [{"t": 0, "s": 1, "fx": 960, "fy": 540}, {"t": at(b, 0), "s": 1.04, "fx": 960, "fy": 520, "dur": 10},
              {"t": at(c, 5.5), "s": 1.15, "fx": 1080, "fy": 460, "dur": 5.0}]
    return [{"type": "diagram", "start": a.start, "end": c.end, "items": items, "camera": camera, "fadeIn": 0.6, "fadeOut": 0}]


def meet_diagram(start, end):
    """QGuard slides in front of the three unchanged services; the outside lines become one quantum-safe line."""
    q = 2.4  # QGuard arrives
    services = [("website", 250), ("API", 470), ("database", 690)]
    items = [{"kind": "box", "text": "Outside", "sub": "browsers · apps · partners", "x": 140, "y": 452, "w": 420, "at": 0.2}]
    for i, (name, y) in enumerate(services):
        items.append({"kind": "line", "x1": 560, "y1": 515, "x2": 1380, "y2": y + 50, "at": 0.6 + 0.2 * i, "out": q + 0.6})
        items.append({"kind": "line", "x1": 1120, "y1": 515, "x2": 1380, "y2": y + 50, "at": q + 0.9 + 0.15 * i})
        items.append({"kind": "box", "text": name, "sub": "unchanged", "x": 1380, "y": y, "w": 330, "at": 0.3 + 0.15 * i})
    items += [{"kind": "line", "x1": 560, "y1": 515, "x2": 820, "y2": 515, "color": "#17704a", "width": 9, "at": q + 1.2, "dur": 1.6},
              {"kind": "box", "text": "Acxelin QGuard", "sub": "in front", "x": 820, "y": 448, "w": 300, "cls": "edge", "at": q, "dx": -160, "dur": 1.4},
              {"kind": "tag", "text": "quantum-safe", "x": 610, "y": 452, "at": q + 2.2,
               "style": {"color": "#17704a", "background": "#e3f4ec", "borderColor": "#7cc4a1"}}]
    camera = [{"t": 0, "s": 1, "fx": 960, "fy": 540}, {"t": end - start, "s": 1.05, "fx": 960, "fy": 520, "dur": end - start}]
    return {"type": "diagram", "start": start, "end": end, "items": items, "camera": camera, "fadeIn": 0.4, "fadeOut": 0}


def cam(*keys):
    return [{"t": 0, "s": 1, "fx": VIEW["width"] / 2, "fy": VIEW["height"] / 2}] + list(keys)


def fill(s, fx, fy, w=1440, h=900):
    """The focus nearest (fx, fy) at which a centred window pushed in to `s` still fills the frame, so no edge shows."""
    x0, y0, k = (1920 - w) / 2, (1080 - h - 40) / 2, min(1, (s - 1) / 0.4)
    d = s + k - 1

    def clamp(v, lo, hi):
        return (lo + hi) / 2 if lo > hi else min(hi, max(lo, v))
    px = clamp(x0 + fx, (960 * k + s * x0) / d, (960 * k + s * (x0 + w) - 1920) / d)
    py = clamp(y0 + 40 + fy, (540 * k + s * y0) / d, (540 * k + s * (y0 + h + 40) - 1080) / d)
    return round(px - x0), round(py - y0 - 40)


def push(t, focus, s=1.35, dur=1.5):
    fx, fy = fill(s, *focus)
    return {"t": t, "s": s, "fx": fx, "fy": fy, "dur": dur}


def back(t, dur=1.2):
    return {"t": t, "s": 1, "fx": VIEW["width"] / 2, "fy": VIEW["height"] / 2, "dur": dur}


def lines_at(t, cmd, result, cps=22, gap=0.45, comment=None):
    """A command typed from `t`, then its real output; returns the lines and when the output appears."""
    out = []
    if comment:
        out.append({"t": t, "text": comment, "kind": "dim"})
        t += 0.5
    out.append({"t": t, "text": cmd, "kind": "cmd", "cps": cps})
    shown = t + len(cmd) / cps + gap
    out += [{"t": shown, **line} for line in result["lines"]]
    return out, shown


def scenes(s, sc):
    meet, protect, start, breather, watch, enforce = s[5], s[6], s[7], s[8], s[9], s[10]
    qcert, issue, revoke, check = s[11], s[12], s[13], s[14]
    t = sc["terminal"]
    out = films.meet(s, meet.start + 7.0) + [meet_diagram(meet.start + 7.0, meet.end)]

    # 01 Protect and start: one take, the Protect service click landing on the cut into the next shot
    p = sc["protect"]
    off = p["marks"]["submit"] - (start.start - films.body(protect))
    local_run = p["marks"]["running"] - off
    out.append(films.window(protect, p, end=start.end, offset=off, enter="rise", title="Acxelin QGuard",
                            camera=cam({"t": local_run - 0.2, "s": 1, "fx": 720, "fy": 450, "dur": 0.1},
                                       push(local_run + 2.0, p["focus"]["running"], 1.35, 1.6))))

    # Breather: the overview fills in
    o = sc["overview"]
    out.append(films.window(breather, o, title="Acxelin QGuard",
                            camera=cam(push(breather.end - breather.start - 0.3, o["focus"]["table"], 1.35, breather.end - breather.start - 1.2))))

    # 02 Watch: who would be refused, and why
    wv = sc["watch"]
    body = films.body(watch)
    wlen = watch.end - body
    w_off = wv["marks"]["enforce"] - wlen
    out.append(films.window(watch, wv, offset=w_off, title="Acxelin QGuard",
                            camera=cam(push(wlen - 9.5, wv["focus"]["reason"], 1.4, 2.0), back(wlen - 0.4, 1.4))))

    # Enforcement: console left, terminal right
    e_off = wv["marks"]["enforce"] - 0.3
    done = wv["marks"]["enforced"] - e_off
    out.append(films.window(enforce, wv, offset=e_off, title="Acxelin QGuard", box=CONSOLE_BOX))
    old, shown = lines_at(done + 0.6, f"curl --curves X25519 -i https://{INTRANET}/", t["old"], cps=26, comment="# an old client: classical key exchange only")
    new, shown = lines_at(shown + 0.9, f"curl -i https://{INTRANET}/", t["new"], cps=26, comment="# a quantum-safe client")
    out.append(films.terminal(enforce.start, enforce.end, old + new, title="Terminal", box=TERM_BOX, w=TERM_W, h=TERM_H))

    # 03 QCertificate: the authority
    q = sc["qcert"]
    body = films.body(qcert)
    q_off = q["marks"]["issue"] - (qcert.end - body)
    out.append(films.window(qcert, q, offset=q_off, title="Acxelin QGuard",
                            camera=cam(push(qcert.end - body - 2.6, q["focus"]["authority"], 1.35, 2.4))))

    # Issue the partner's certificate; cut to the terminal
    cut = issue.start + q["marks"]["issued"] - q["marks"]["issue"] + 1.6
    out.append(films.window(issue, q, end=cut, offset=q["marks"]["issue"], title="Acxelin QGuard",
                            camera=[push(0, q["focus"]["authority"], 1.35, 0.1), back(1.0, 1.0)]))
    a, shown = lines_at(0.5, "curl -i --cert acme-partner.pem --key acme-partner.key https://" + PARTNERS + "/", t["partner"], cps=30)
    b, _ = lines_at(shown + 1.3, f"curl -i https://{PARTNERS}/", t["stranger"], cps=26)
    out.append(films.terminal(cut, issue.end, a + b, title="Terminal · the partner's computer"))

    # Revoke: console left, the partner's next call right, and the real time it took
    r_off = q["marks"]["revoke"] - 0.2
    out.append(films.window(revoke, q, offset=r_off, title="Acxelin QGuard", box=CONSOLE_BOX))
    first = q["marks"]["revoked"] - r_off
    lines, refused = [], first + 0.6
    for i, call in enumerate(t["revoked"]):
        more, refused = lines_at(refused + (0.6 if i else 0), "curl -i --cert acme-partner.pem --key acme-partner.key https://" + PARTNERS + "/",
                                 call, cps=34, comment="# the partner's next call" if i == 0 else None)
        lines += more
    term_cam = [{"t": 0, "s": 1, "fx": TERM_W / 2, "fy": TERM_H / 2}, {"t": refused + 1.6, "s": 1.12, "fx": TERM_W / 2, "fy": TERM_H * 0.42, "dur": 1.4}]
    out.append(films.terminal(revoke.start, revoke.end, lines, title="Terminal · the partner's computer", box=TERM_BOX, w=TERM_W, h=TERM_H, camera=term_cam))
    out.append({"type": "marker", "start": revoke.start + refused + 0.3, "end": revoke.end,
                "html": SPLIT_FIX + f"Revoked → refused <b>{t['refused_after']:.1f} s</b> · real time"})

    # 04 Check a connection
    c = sc["check"]
    c_off = c["marks"]["verdict"] - 10.5
    out.append(films.window(check, c, offset=c_off, title="Acxelin QGuard", camera=cam(push(10.5 + 1.7 + 1.8, c["focus"]["verdict"], 1.4, 1.8))))
    return cuts(out)


def cuts(layers):
    """Clean cuts where one window follows another: no dip through black."""
    windows = [x for x in layers if x["type"] == "window"]
    for x in windows:
        if any(abs(y["end"] - x["start"]) < 1e-6 for y in windows if y is not x):
            x["fadeIn"] = 0
        if any(abs(y["start"] - x["end"]) < 1e-6 for y in windows if y is not x):
            x["fadeOut"] = 0
    return layers


_s = shots("qguard")
SOCIAL = [(_s[1].start, _s[1].end, True), (_s[10].start + 4.5, _s[10].start + 11.5, True)]  # the risk; old clients refused, quantum-safe ones served


def thumb_frame(scenes):
    return scenes["check"]["frames"][-1]["src"]
