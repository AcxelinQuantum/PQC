"""Record a real console as a scene: a screenshot after every visible change, each stamped with the time it appears in the
film, and the cursor's path. The console does the real work; only waiting is shortened, never hidden where it matters
(the revocation shots carry a marker with the real time). Before every screenshot the page's text and every field are
checked for anything that must not appear in a film: the user's name or home folder, a launch ticket, a passphrase."""
import json
import os
import random
import re
import socket
from pathlib import Path

VIEW = {"width": 1440, "height": 900}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def forbidden(extra=()):
    """What must never be on screen: this computer's user name and home folder, plus `extra` (tickets, passphrases)."""
    home = Path.home()
    words = {home.name, str(home), str(home).replace("\\", "/"), "AppData", os.environ.get("USERNAME", ""), os.environ.get("COMPUTERNAME", "")}
    return [w for w in {*words, *extra} if w and len(w) >= 3]


class Recorder:
    def __init__(self, page, folder, banned=(), seed=7):
        self.page, self.folder, self.t, self.frames, self.cursor = page, Path(folder), 0.0, [], []
        self.banned = forbidden(banned)
        self.rand = random.Random(seed)
        self.folder.mkdir(parents=True, exist_ok=True)
        for old in self.folder.glob("*.png"):
            old.unlink()
        self.pos = None

    def ban(self, *words):
        self.banned += [w for w in words if w and len(w) >= 3]

    def check(self):
        seen = self.page.evaluate("() => document.body.innerText + '\\n' + [...document.querySelectorAll('input:not([type=password]),textarea,select')].map(e => e.value).join('\\n')")
        for w in self.banned:
            if w.lower() in seen.lower():
                raise RuntimeError(f"refusing to record a frame that shows {w[:3]}…: change the demo data")

    def shot(self, hold=0.0):
        """Take a frame now (a password field shows only dots, so its value is not checked; shown as text, it is); it shows from the current time. Then move time on by `hold`."""
        self.page.wait_for_timeout(60)
        self.check()
        name = f"{len(self.frames):04d}.png"
        self.page.screenshot(path=str(self.folder / name))
        self.frames.append({"t": round(self.t, 3), "src": (self.folder / name).as_uri()})
        self.t += hold

    def hold(self, seconds):
        self.t += seconds

    def point(self, target):
        box = target.bounding_box() if not isinstance(target, tuple) else {"x": target[0], "y": target[1], "width": 0, "height": 0}
        return box["x"] + min(box["width"] / 2, 60 if box["width"] > 160 else box["width"] / 2), box["y"] + box["height"] / 2

    def move(self, target, dur=0.7):
        x, y = self.point(target)
        if self.pos is None:
            self.cursor.append({"t": round(self.t, 3), "x": round(x + 260), "y": round(y + 180)})
        self.t += dur
        self.cursor.append({"t": round(self.t, 3), "x": round(x), "y": round(y), "move": dur})
        self.pos = (x, y)

    def click(self, target, dur=0.7, settle=400, after=0.35):
        """Move to `target`, click it for real, wait for the page, take a frame."""
        self.move(target, dur)
        self.cursor.append({"t": round(self.t, 3), "x": round(self.pos[0]), "y": round(self.pos[1]), "click": True})
        target.click()
        self.page.wait_for_timeout(settle)
        self.t += 0.12
        self.shot(after)

    def type(self, field, text, cps=11.0):
        """Type `text` into `field` a character at a time, at a steady human pace, a frame per character."""
        self.click(field, after=0.25)
        for ch in text:
            field.press_sequentially(ch)
            self.shot(self.rand.uniform(0.75, 1.25) / cps)

    def scroll(self, y, dur=1.2, steps=24):
        """Scroll the page to `y` smoothly, a frame per step."""
        start = self.page.evaluate("() => window.scrollY")
        for i in range(1, steps + 1):
            k = i / steps
            k = 1 - (1 - k) ** 3
            self.page.evaluate(f"() => window.scrollTo(0, {start + (y - start) * k})")
            self.shot(dur / steps)

    def hide(self):
        self.cursor.append({"t": round(self.t, 3), "x": 0, "y": 0, "hide": True})
        self.pos = None

    def save(self, name):
        scene = {"w": VIEW["width"], "h": VIEW["height"], "frames": self.frames, "cursor": self.cursor, "duration": round(self.t, 3)}
        (self.folder / "scene.json").write_text(json.dumps(scene, indent=1), encoding="utf-8")
        return scene


def at(page, selector_or_text, exact=False):
    """A locator by text (or a CSS selector when it starts with one of # . [)."""
    if re.match(r"^[#.\[]", selector_or_text):
        return page.locator(selector_or_text).first
    return page.get_by_text(selector_or_text, exact=exact).first
