"""What every film shares: the hook, the meet card, section cards and lower thirds taken from the script, the trust section and
the close. A product module adds its problem diagram and its console scenes; the family look comes from here."""
import re

from script import shots as read_shots

SECTION = re.compile(r'Section card "(\d+) · ([^"]+)"')
SECTION_TIME = 1.6  # a section card shows this long before its scene


def section_of(shot):
    m = SECTION.search(shot.screen)
    return m.groups() if m else None


def lower_of(shot):
    m = re.match(r"Lower third: (.+)$", shot.text)
    return m.group(1).strip() if m else None


def body(shot):
    """When a shot's own picture starts: after its section card, if it has one."""
    return shot.start + (SECTION_TIME if section_of(shot) else 0)


def hook(s):
    first, second = s[0].text, s[1].text
    return [
        {"type": "title", "start": 0, "end": s[1].end, "fadeIn": 0, "fadeOut": 0.5, "lines": [
            {"text": first, "at": 2.4, "size": 112},
            {"text": second, "at": 7.6, "size": 112, "rule": len(second.split()) - 1, "ruleAt": 10.2, "stagger": 0.32},
        ]},
        {"type": "black", "start": 0, "end": 1.2, "from": 1, "to": 0},
    ]


def meet(s, until):
    """The product's name and its one line, from 0:45 until `until` (the product's own picture follows)."""
    shot = s[5]
    name, line = (shot.text.split(" · ") + [""])[:2]
    return [{"type": "title", "start": shot.start, "end": until, "fadeIn": 0, "lines": [
        {"text": name, "at": 0.3, "size": 128, "rule": len(name.split()) - 1, "ruleAt": 1.6},
        {"text": line, "at": 1.4, "size": 50, "cls": "small", "stagger": 0.06},
    ]}]


def chrome(s):
    """Section cards and lower thirds wherever the script asks for them."""
    out = []
    for shot in s:
        sec = section_of(shot)
        if sec:
            out.append({"type": "section", "start": shot.start, "end": shot.start + SECTION_TIME, "index": sec[0], "title": sec[1]})
        low = lower_of(shot)
        if low:
            a = body(shot) + 0.7
            out.append({"type": "lower", "start": a, "end": min(shot.end - 0.2, a + 3.6), "text": low})
    return out


def trust(s):
    first, limit = s[-3], s[-2]
    parts = first.text.split(" · ")
    plain = [p for p in parts if "FIPS" not in p]
    tech = " · ".join(p for p in parts if "FIPS" in p)
    lines = [{"text": p, "at": 0.5 + 1.7 * i, "cls": "t"} for i, p in enumerate(plain)]
    if tech:
        lines.append({"text": tech, "at": 0.5 + 1.7 * len(plain), "cls": "m"})
    lines.append({"text": limit.text, "at": limit.start - first.start + 0.4, "cls": "last"})
    return [{"type": "trust", "start": first.start, "end": limit.end, "fadeIn": 0.5, "fadeOut": 0.3, "lines": lines}]


def close(s):
    shot = s[-1]
    name, sig, url = shot.text.split(" · ")
    return [{"type": "close", "start": shot.start, "end": shot.end, "name": name, "sig": sig, "url": url}]


def window(shot, scene, start=None, end=None, camera=None, offset=0.0, title="", enter=None, box=None):
    """A console scene in its window for (part of) a shot. `offset` is the scene time shown at `start`."""
    start = body(shot) if start is None else start
    return {"type": "window", "start": start, "end": shot.end if end is None else end, "scene": scene, "offset": offset,
            "camera": camera or [{"t": 0, "s": 1, "fx": scene["w"] / 2, "fy": scene["h"] / 2}], "title": title, "enter": enter,
            "box": box, "bgFade": 0 if not section_of(shot) else 0.3}


def terminal(start, end, lines, title="Terminal", box=None, w=1100, h=560, camera=None):
    return {"type": "window", "start": start, "end": end, "term": True, "lines": lines, "w": w, "h": h, "title": title, "box": box,
            "camera": camera or [{"t": 0, "s": 1, "fx": w / 2, "fy": h / 2}], "noMark": True}


def film(name, product, scenes, draft=None):
    """The whole film: shared parts, the product's diagram and scenes, then the chrome on top."""
    s = read_shots(name)
    layers = hook(s) + product.problem(s) + product.scenes(s, scenes) + trust(s) + close(s) + chrome(s)
    if draft:
        layers.append({"type": "draft", "start": 0, "end": s[-1].end, "note": draft})
    return {"duration": s[-1].end, "fps": 30, "layers": layers}


def thumbnail(name, scene_frame, w=1440, h=900):
    """A still: the product's name on the left, its console on the right."""
    scene = {"w": w, "h": h, "frames": [{"t": 0, "src": scene_frame}], "cursor": []}
    return {"duration": 1, "layers": [
        {"type": "window", "start": 0, "end": 1, "scene": scene, "box": {"x": 1010, "y": 250, "w": 1050}, "noMark": True, "layerFade": False,
         "camera": [{"t": 0, "s": 1, "fx": w / 2, "fy": h / 2}]},
        {"type": "title", "start": 0, "end": 1, "bg": "ondark", "fadeIn": 0, "fadeOut": 0, "lines": [
            {"text": "Acxelin", "at": -9, "size": 120}, {"text": name.replace("Acxelin ", ""), "at": -9, "size": 132, "rule": 0, "ruleAt": -9}]},
    ]}
