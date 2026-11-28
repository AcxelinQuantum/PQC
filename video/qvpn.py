"""Film 3, Acxelin QVPN: the problem diagram, the redrawn network, and the real console and app at work.

Everything runs for real in WSL (video/qvpn_lab.py): two sites over IPsec with ML-KEM and a PPK, a WireGuard gateway with its
enrollment service, and Alice's laptop running the product's app, each in its own network namespace. Windows only drives the
browser. The revocation shots carry the measured wall-clock time between the click on Confirm revoke and the frame shown."""
import json
import queue
import secrets
import subprocess
import threading
import time
from pathlib import Path

import films
from capture import VIEW, Recorder, free_port
from script import shots as read_shots

HERE = Path(__file__).resolve().parent
HOME = Path(r"C:\acme\qvpn")  # Windows side: only the downloaded invitation
WSL = ["wsl", "-d", "Ubuntu", "-u", "root", "--"]
PY = "/srv/acme/venv/bin/python"
LAB = "/mnt/" + HERE.drive[0].lower() + (HERE / "qvpn_lab.py").as_posix()[2:]
CONSOLE, APP = "Acxelin QVPN console", "Acxelin QVPN"


def find(s, words):
    return next(x for x in s if words in x.screen)


def social(s):
    """15 s that stand alone: Connect, Protected (7 s), then the name and the signature line (8 s)."""
    connect, close = find(s, "**Connect**"), s[-1]
    return [(float(connect.start), connect.start + 7.0, True), (float(close.start), close.start + 8.0, True)]


SOCIAL = social(read_shots("qvpn"))


# ---------------------------------------------------------------- recording

class Rec(Recorder):
    """The shared recorder, with two changes: a password field's value (shown as dots) is not "on screen", so the passphrase may
    be typed, while it is still refused anywhere else; and each click notes its wall-clock time, for the revocation markers."""

    def check(self):
        seen = self.page.evaluate("() => document.body.innerText + '\\n' + [...document.querySelectorAll('input:not([type=password]),textarea,select')]"
                                  ".map(e => e.value).join('\\n')")
        for w in self.banned:
            if w.lower() in seen.lower():
                raise RuntimeError(f"refusing to record a frame that shows {w[:3]}…: change the demo data")

    def click(self, target, dur=0.7, settle=400, after=0.35):
        self.move(target, dur)
        self.cursor.append({"t": round(self.t, 3), "x": round(self.pos[0]), "y": round(self.pos[1]), "click": True})
        target.click()
        self.wall = time.time()
        self.page.wait_for_timeout(settle)
        self.t += 0.12
        self.shot(after)

    def pad(self, until):
        self.hold(max(0.0, until - self.t))


def centre(*locators, pad=0):
    boxes = [loc.bounding_box() for loc in locators]
    x0, y0 = min(b["x"] for b in boxes), min(b["y"] for b in boxes)
    x1, y1 = max(b["x"] + b["width"] for b in boxes), max(b["y"] + b["height"] for b in boxes)
    return [round((x0 + x1) / 2), round((y0 + y1) / 2 + pad)]


def until_text(page, needle, seconds, every=500):
    end = time.time() + seconds
    while time.time() < end:
        if needle in page.evaluate("() => document.body.innerText"):
            return True
        page.wait_for_timeout(every)
    raise RuntimeError(f"waited {seconds} s for {needle!r} on {page.url.split('#')[0]}")


class Lab:
    """video/qvpn_lab.py in WSL: started here, stopped (and its leftovers removed) whatever happens."""

    def __init__(self, console_port, app_port):
        self.p = subprocess.Popen([*WSL, "timeout", "2400", PY, LAB, "up", str(console_port), str(app_port)], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        self.lines = queue.Queue()
        threading.Thread(target=lambda: [self.lines.put(line) for line in self.p.stdout] + [self.lines.put(None)], daemon=True).start()

    def ready(self, seconds=420):
        end, seen = time.time() + seconds, []
        while time.time() < end:
            try:
                line = self.lines.get(timeout=5)
            except queue.Empty:
                continue
            if line is None:
                break
            if line.startswith("{"):
                return json.loads(line)
            seen.append(line)
        raise RuntimeError("the WSL lab did not come up:\n" + "".join(seen[-40:]))

    def close(self):
        try:
            self.p.stdin.write("quit\n")
            self.p.stdin.close()
            self.p.wait(90)
        except (OSError, subprocess.TimeoutExpired):
            self.p.kill()
        subprocess.run([*WSL, "timeout", "90", PY, LAB, "down"], capture_output=True, timeout=120)


def capture(raw: Path) -> dict:
    s = read_shots("qvpn")
    HOME.mkdir(parents=True, exist_ok=True)
    lab = Lab(free_port(), free_port())
    try:
        info = lab.ready()
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                ctx = browser.new_context(viewport=VIEW, device_scale_factor=2, accept_downloads=True)
                ctx.set_default_timeout(60000)
                con, app = ctx.new_page(), ctx.new_page()
                con.goto(info["console"])
                app.goto(info["app"])
                con.get_by_text("branch.acme.example").first.wait_for()
                app.get_by_text("Set up this computer").wait_for()
                tickets = [info["console"].split("#")[1], info["app"].split("#")[1]]
                return record(Path(raw).resolve(), s, con, app, info, tickets)
            finally:
                browser.close()
    finally:
        lab.close()
        for f in HOME.glob("*.acxinvite"):  # a used one-time token, for a CA that no longer exists
            f.unlink()




def record(raw, s, con, app, info, tickets):
    passphrase = "acme-" + secrets.token_urlsafe(9)  # never shown, never kept
    rec = lambda page, name: (r := Rec(page, raw / name, banned=tickets), r.ban(passphrase), r)[2]
    out = {}

    # 01 · Sites: Headquarters is there; the branch office is added by its status address, and both tunnels show protected
    sh = find(s, "01 · Sites")
    con.bring_to_front()
    r = rec(con, "sites")
    r.shot(1.4)
    r.type(con.locator("#site-name"), "Branch office")
    r.type(con.locator("#site-url"), info["branch"])
    r.click(con.get_by_role("button", name="Add a site"), after=0.1)
    con.get_by_text("hq.acme.example", exact=True).wait_for()
    con.wait_for_timeout(300)
    r.hide()
    r.shot(0.0)
    pills = con.locator(".pill.ok", has_text="Protected")
    assert pills.count() == 2, "both sites should report a protected tunnel"
    at = r.t
    r.pad(sh.end - films.body(sh))
    out["sites"] = r.save("sites") | {"focus": {"result": centre(pills.nth(0), pills.nth(1))}, "at": {"result": at}}

    # 02 · People: invite alice; the invitation downloads; it waits under "Invitations not used yet", with Cancel
    sh, pending = find(s, "02 · People"), find(s, "Invitations not used yet")
    con.get_by_role("tab", name="People").click()
    con.locator("#who").wait_for()
    con.wait_for_timeout(600)
    r = rec(con, "people")
    r.shot(1.0)
    r.type(con.locator("#who"), "alice")
    r.hold(0.3)
    with con.expect_download() as dl:
        r.click(con.get_by_role("button", name="Download invitation"), after=0.1)
    dl.value.save_as(HOME / dl.value.suggested_filename)
    invitation = HOME / dl.value.suggested_filename
    con.locator("#pending").wait_for()
    con.wait_for_timeout(300)
    r.shot(0.0)
    at = r.t
    row = con.locator("#pending li").first
    cancel = con.get_by_role("button", name="Cancel the invitation for alice")
    r.pad(pending.start - films.body(sh) + 2.6)
    r.move(cancel, 1.1)
    r.pad(pending.end - films.body(sh))
    out["people"] = r.save("people") | {"focus": {"done": centre(con.locator("#invited"), row), "row": centre(row)},
                                        "at": {"done": at, "row": pending.start - films.body(sh)}}

    # 03 · Join: Alice's app opens the invitation, a passphrase (dots) locks the key, Connect → Protected
    sh, connect = find(s, "03 · Join"), find(s, "**Connect**")
    app.bring_to_front()
    r = rec(app, "join")
    r.shot(2.2)
    with app.expect_file_chooser() as fc:
        r.click(app.locator("#drop"), after=0.1)
    fc.value.set_files(str(invitation))
    app.locator("#form").wait_for(state="visible")
    app.wait_for_timeout(300)
    r.shot(0.9)
    r.type(app.locator("#pass"), passphrase, cps=7)
    r.hold(0.4)
    r.type(app.locator("#repeat"), passphrase, cps=7)
    r.pad(connect.start - films.body(sh) - 0.82)
    r.click(app.locator("#connect"), settle=50, after=0.0)
    words, end = [], time.time() + 90
    while time.time() < end:
        word = app.locator("#word").inner_text()
        text = app.evaluate("() => document.querySelector('main').innerText")
        if not words or text != words[-1]:
            r.shot(0.4)
            words.append(text)
        if word == "Protected":
            break
        app.wait_for_timeout(250)
    else:
        raise RuntimeError("the app never said Protected: " + app.locator("#line").inner_text())
    at = r.t
    r.hide()
    while r.t < connect.end - films.body(sh):  # the key-renewal countdown ticks in real time
        app.wait_for_timeout(800)
        r.shot(1.0)
    out["join"] = r.save("join") | {"focus": {"protected": centre(app.locator("#word"), app.locator("#pq"))}, "at": {"protected": at, "connect": connect.start - films.body(sh)},
                                    "states": [w.split("\n")[0] for w in words]}

    # Connected: back in the console, People shows alice connected
    sh = find(s, "Alice's row")
    con.bring_to_front()
    r = rec(con, "connected")
    r.shot(1.0)
    r.click(con.get_by_role("tab", name="People"), after=0.1)
    con.locator("td .pill.ok", has_text="Connected").wait_for()
    con.wait_for_timeout(300)
    r.hide()
    r.shot(0.0)
    at = r.t
    r.pad(sh.end - sh.start)
    alice = con.locator("tbody tr", has_text="alice").first
    out["connected"] = r.save("connected") | {"focus": {"row": centre(alice)}, "at": {"row": at}}

    # 04 · Revoke: Revoke, confirm; the gateway cuts alice off (its own history says so), timed from the confirming click
    sh = find(s, "04 · Revoke")
    r = rec(con, "revoke")
    r.shot(1.0)
    r.click(con.get_by_role("button", name="Revoke alice"), after=0.6)
    r.click(con.get_by_role("button", name="Confirm revoke alice"), after=0.0)
    revoked_at = r.wall
    con.get_by_text("certificate is revoked").wait_for()
    con.wait_for_timeout(300)
    r.hide()
    r.shot(0.0)
    at = r.t
    focus_revoked = centre(con.locator("tbody tr", has_text="alice").first)
    until_text(con, "Cut off (revoked): alice", 120)
    cut = time.time() - revoked_at
    con.wait_for_timeout(200)
    r.pad(at + 5.6)
    r.shot(0.0)
    cut_at = r.t
    r.pad(sh.end - films.body(sh))
    activity = con.locator("li", has_text="Cut off (revoked): alice").first
    out["revoke"] = r.save("revoke") | {"focus": {"revoked": focus_revoked, "cut": centre(activity)}, "at": {"revoked": at, "cut": cut_at},
                                        "elapsed": {"cut": round(cut, 1)}}

    # The app learns at its next key renewal
    sh = find(s, "Your access was revoked")
    app.bring_to_front()
    r = rec(app, "revoked")
    r.shot(1.4)
    until_text(app, "Your access was revoked", 240, every=250)
    r.shot(0.0)
    told = time.time() - revoked_at
    at = r.t
    r.pad(sh.end - sh.start)
    out["revoked"] = r.save("revoked") | {"focus": {"line": centre(app.locator("#word"), app.locator("#line"))}, "at": {"line": at},
                                          "elapsed": {"told": round(told, 1)}}

    # Health: its checks, a warning and what to do
    sh = find(s, "Health:")
    con.bring_to_front()
    r = rec(con, "health")
    r.shot(0.5)
    r.click(con.get_by_role("tab", name="Health"), after=0.1)
    con.locator("#health-list td").first.wait_for()
    con.wait_for_timeout(400)
    r.hide()
    r.shot(0.0)
    at = r.t
    r.pad(sh.end - sh.start)
    warn = con.locator("tr", has=con.locator(".pill.warn")).first
    out["health"] = r.save("health") | {"focus": {"warn": centre(warn.locator("td").last, warn.locator("td").nth(1))}, "at": {"warn": at}}
    return out


# ---------------------------------------------------------------- the film

INK, OK, COPY = "#9eabb6", "#17704a", "#d9a21b"
NODES = {"hq": (180, 300, 380, "Headquarters", "main office"), "branch": (180, 620, 380, "Branch office", "across town"),
         "gw": (800, 450, 320, "Gateway", None), "l1": (1360, 230, 380, "Laptop", "at home"),
         "l2": (1360, 470, 380, "Laptop", "at a café table"), "l3": (1360, 710, 380, "Laptop", "on the road")}
EDGE = {"hq": ((560, 362), (800, 478)), "branch": ((560, 682), (800, 506)), "l1": ((1360, 292), (1120, 472)),
        "l2": ((1360, 532), (1120, 492)), "l3": ((1360, 772), (1120, 512))}  # each line from its box's edge to the gateway's


def node(k, at, **extra):
    x, y, w, text, sub = NODES[k]
    return {"kind": "box", "x": x, "y": y, "w": w, "text": text, "at": at, **({"sub": sub} if sub else {}), **extra}


def line(a, at, color=INK, **extra):
    (x1, y1), (x2, y2) = EDGE[a]
    return {"kind": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "at": at, "color": color, **extra}


def problem(s):
    first, copied, leaving = s[2], s[3], s[4]
    a, b, c = 0.0, copied.start - first.start, leaving.start - first.start
    quote = copied.text.strip('"“”')
    gone = c + 0.2
    items = [line(k, a + 1.2 + 0.25 * i, out=gone if k in ("hq", "branch") else None) for i, k in enumerate(("hq", "branch", "l1", "l2", "l3"))]
    items += [node("gw", a + 0.4), node("hq", a + 0.7, out=gone), node("branch", a + 0.85, out=gone),
              node("l1", a + 1.0, dim=c + 0.6), node("l2", a + 1.15), node("l3", a + 1.3, dim=c + 0.6)]
    mids = [((x1 + x2) / 2, (y1 + y2) / 2) for (x1, y1), (x2, y2) in EDGE.values()]
    items += [{"kind": "line", "x1": round(x), "y1": round(y), "x2": 960, "y2": 880, "at": b + 0.6 + 0.15 * i, "dur": 1.1, "color": COPY, "width": 3, "out": gone}
              for i, (x, y) in enumerate(mids)]
    items += [{"kind": "box", "x": 790, "y": 870, "w": 340, "text": "recorded today", "at": b + 0.3, "out": gone,
               "style": {"borderStyle": "dashed", "textAlign": "center", "color": "#56636f"}},
              {"kind": "quote", "x": 220, "y": 96, "text": quote, "at": b + 1.4, "out": gone},
              {"kind": "tag", "x": 1580, "y": 452, "text": "last day", "at": c + 0.8}]
    cam = [{"t": 0, "s": 1, "fx": 960, "fy": 540}, {"t": gone + 4.6, "s": 1.25, "fx": 1550, "fy": 530, "dur": 4.2}]
    return [{"type": "diagram", "start": first.start, "end": leaving.end, "fadeIn": 0.6, "fadeOut": 0.3, "items": items, "camera": cam}]


def redrawn(start, end):
    """Every line's keys agreed over a quantum-safe connection, with a certificate at each end."""
    items = [node(k, 0.15 + 0.08 * i) for i, k in enumerate(("gw", "hq", "branch", "l1", "l2", "l3"))]
    for i, k in enumerate(("hq", "branch", "l1", "l2", "l3")):
        items.append(line(k, 1.0 + 0.7 * i, OK, width=5))
        x, y, w = NODES[k][:3]
        items.append({"kind": "tag", "x": x + w - 168, "y": y - 16, "text": "certificate", "at": 1.4 + 0.7 * i,
                      "style": {"color": "#17704a", "background": "#e3f3ea", "borderColor": "#9fd2b6"}})
    items.append({"kind": "tag", "x": 800 + 320 - 168, "y": 434, "text": "certificate", "at": 1.2,
                  "style": {"color": "#17704a", "background": "#e3f3ea", "borderColor": "#9fd2b6"}})
    items.append({"kind": "note", "x": 180, "y": 920, "text": "Keys agreed with ML-KEM · certificates signed with ML-DSA, from your own CA", "at": 5.0})
    return [{"type": "diagram", "start": start, "end": end, "fadeIn": 0.5, "fadeOut": 0.3, "items": items,
             "camera": [{"t": 0, "s": 1.04, "fx": 960, "fy": 540}, {"t": end - start, "s": 1, "fx": 960, "fy": 540, "dur": end - start}]}]


def push(scene, t, focus, s=1.35, hold=2.4, into=1.6, back=1.4):
    """Into `focus` over `into` seconds ending at t + into, hold, then back out."""
    w, h = scene["w"] / 2, scene["h"] / 2
    return [{"t": round(t + into, 2), "s": s, "fx": focus[0], "fy": focus[1], "dur": into},
            {"t": round(t + into + hold + back, 2), "s": 1, "fx": w, "fy": h, "dur": back}]


def cam(scene, *moves):
    return [{"t": 0, "s": 1, "fx": scene["w"] / 2, "fy": scene["h"] / 2}] + [k for m in moves for k in m]


def took(seconds):
    return f"{seconds:.1f} s" if seconds < 60 else f"{int(seconds // 60)} min {round(seconds % 60):02d} s"


def scenes(s, scenes):
    meet = s[5]
    title_end = meet.start + 7.0
    out = films.meet(s, title_end + 0.5) + redrawn(title_end, meet.end)
    out[0]["fadeOut"] = 0  # the paper diagram dissolves in over the title

    sh = find(s, "01 · Sites")
    sc = scenes["sites"]
    out.append(films.window(sh, sc, title=CONSOLE, enter="rise", camera=cam(sc, push(sc, sc["at"]["result"] + 0.4, sc["focus"]["result"], 1.3, 3.4))))

    sh, pending = find(s, "02 · People"), find(s, "Invitations not used yet")
    sc = scenes["people"]
    w = films.window(sh, sc, end=pending.end, title=CONSOLE, enter="rise",
                     camera=cam(sc, push(sc, sc["at"]["done"] + 0.3, sc["focus"]["done"], 1.3, 2.6),
                                push(sc, sc["at"]["row"] + 0.2, sc["focus"]["row"], 1.4, 4.6, back=1.6)))
    out.append(w)

    sh, connect = find(s, "03 · Join"), find(s, "**Connect**")
    sc = scenes["join"]
    out.append(films.window(sh, sc, end=connect.end, title=APP, enter="rise",
                            camera=cam(sc, push(sc, sc["at"]["protected"] + 0.1, sc["focus"]["protected"], 1.4, 4.4, into=1.5, back=1.8))))
    out[-1]["fadeOut"] = 0

    sh = find(s, "Alice's row")
    sc = scenes["connected"]
    out.append(films.window(sh, sc, title=CONSOLE, camera=cam(sc, push(sc, sc["at"]["row"] + 0.3, sc["focus"]["row"], 1.3, 6.0, into=2.4, back=2.0))))

    sh = find(s, "04 · Revoke")
    sc = scenes["revoke"]
    start = films.body(sh)
    out.append(films.window(sh, sc, title=CONSOLE, enter="rise",
                            camera=cam(sc, push(sc, sc["at"]["revoked"] + 0.2, sc["focus"]["revoked"], 1.3, 1.6, back=1.2),
                                       [{"t": round(sc["at"]["cut"] + 0.2, 2), "s": 1.3, "fx": sc["focus"]["cut"][0], "fy": sc["focus"]["cut"][1], "dur": 1.0}])))
    out[-1]["fadeOut"] = 0
    out.append({"type": "marker", "start": round(start + sc["at"]["cut"], 2), "end": sh.end,
                "html": f"Revoke → cut off, shown here · <b>{took(sc['elapsed']['cut'])}</b> real time"})

    sh = find(s, "Your access was revoked")
    sc = scenes["revoked"]
    out.append(films.window(sh, sc, end=sh.end + 0.3, title=APP, camera=cam(sc, push(sc, sc["at"]["line"] + 0.3, sc["focus"]["line"], 1.35, 7.0, into=2.0))))
    out[-1]["fadeOut"] = 0
    out.append({"type": "marker", "start": round(sh.start + sc["at"]["line"], 2), "end": sh.end,
                "html": f"Revoke → this message · <b>{took(sc['elapsed']['told'])}</b> real time"})

    sh = find(s, "Health:")
    sc = scenes["health"]
    out.append(films.window(sh, sc, title=CONSOLE, camera=cam(sc, push(sc, sc["at"]["warn"] + 0.6, sc["focus"]["warn"], 1.35, 4.0))))
    out[-1]["fadeIn"] = 0.3
    out[-1]["fadeOut"] = 0
    return out


def thumb_frame(scenes):
    sc = scenes["join"]
    return next(f["src"] for f in reversed(sc["frames"]) if f["t"] <= sc["at"]["protected"] + 0.01)
