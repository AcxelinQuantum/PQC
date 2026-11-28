"""Read the approved film script (documents/video-script.md): each film's shots, with their times, voice-over and on-screen text.
The films are built from this file, so what is spoken and shown is what the owner approved."""
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "documents" / "video-script.md"
FILMS = {"qreadiness": "Acxelin QReadiness", "qguard": "Acxelin QGuard", "qvpn": "Acxelin QVPN"}


@dataclass
class Shot:
    start: float
    end: float
    screen: str
    motion: str
    voice: str
    text: str
    music: str


def seconds(stamp):
    m, s = stamp.split(":")
    return int(m) * 60 + int(s)


def shots(film):
    """The shots of `film` ("qreadiness", "qguard" or "qvpn"), in order, checked to follow on from each other."""
    text = SCRIPT.read_text(encoding="utf-8")
    part = next(p for p in re.split(r"^## Film \d: ", text, flags=re.M)[1:] if p.startswith(FILMS[film]))
    out = []
    for a, b, rest in re.findall(r"^\| (\d:\d\d)–(\d:\d\d) \|(.*)\|\s*$", part, re.M):
        cells = [c.strip() for c in rest.split("|")]
        voice = "" if cells[2] == "*(music only)*" else cells[2]
        out.append(Shot(seconds(a), seconds(b), cells[0], cells[1], voice, cells[3], cells[4]))
    for prev, nxt in zip(out, out[1:]):
        assert prev.end == nxt.start, f"{film}: a gap or overlap at {nxt.start}"
    return out


def at(film_shots, start):
    """The shot that starts at `start` (a "m:ss" stamp)."""
    return next(s for s in film_shots if s.start == seconds(start))
