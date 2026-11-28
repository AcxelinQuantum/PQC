"""The review before anyone watches: every cut as frames (the frame before, at and after), and the checks a viewer would
notice: text on screen for less than 1.5 s, text outside the title-safe area, a caption out of step with its line, a line
that overruns its shot, and anything personal in the film's text or captions."""
import json
import subprocess
from pathlib import Path

from capture import forbidden
from render import Stage, ffmpeg

MIN_TEXT = 1.5


def text_spans(spec):
    """(what, seconds on screen) for every piece of text the stage shows."""
    out = []
    for l in spec["layers"]:
        end = l["end"]
        if l["type"] == "title":
            for line in l["lines"]:
                last = line["at"] + (len(line["text"].split()) - 1) * line.get("stagger", 0.14)
                stop = l["start"] + line["out"] if line.get("out") is not None else end
                out.append((line["text"], stop - (l["start"] + max(line["at"], 0)), stop - (l["start"] + last)))
        elif l["type"] in ("lower", "section", "marker"):
            out.append((l.get("text") or l.get("title") or l.get("html"), end - l["start"], end - l["start"]))
        elif l["type"] == "trust":
            for line in l["lines"]:
                out.append((line["text"], end - l["start"] - line["at"], end - l["start"] - line["at"]))
        elif l["type"] == "close":
            out.append((l["url"], end - l["start"] - 2.1 - 1.4, end - l["start"] - 2.1 - 1.4))
        elif l["type"] == "diagram":
            for it in l["items"]:
                if it.get("text"):
                    stop = l["start"] + it["out"] if it.get("out") is not None else end
                    out.append((it["text"], stop - l["start"] - it["at"], stop - l["start"] - it["at"]))
    return out


def cuts(spec, shots):
    times = {s.start for s in shots} | {l["start"] for l in spec["layers"]} | {l["end"] for l in spec["layers"]}
    return sorted(t for t in times if 0 < t < spec["duration"])


def sheets(video, times, folder, fps=30):
    """One image per cut: the frame before, at and after it, side by side, at 640 wide each."""
    from PIL import Image, ImageDraw
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.png"):
        old.unlink()
    made = []
    for t in times:
        frames = []
        for d in (-1, 0, 1):
            ts = max(0, t + d / fps)
            p = folder / f"_f{d}.png"
            subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{ts:.4f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=640:-1", str(p)], check=True)
            frames.append(Image.open(p).copy())
            p.unlink()
        sheet = Image.new("RGB", (640 * 3 + 20, frames[0].height + 34), "#202a33")
        for i, f in enumerate(frames):
            sheet.paste(f, (i * 650, 34))
        ImageDraw.Draw(sheet).text((8, 8), f"cut at {int(t // 60)}:{t % 60:05.2f}  (frame before · at · after)", fill="#ffffff")
        path = folder / f"cut-{t:07.2f}.png"
        sheet.save(path)
        made.append(path)
    return made


def run(name, spec, shots, cues, placed, overruns, out):
    problems, notes = [], []
    for what, first_word, last_word in text_spans(spec):
        if last_word < MIN_TEXT:
            problems.append(f"text on screen {last_word:.1f} s (under {MIN_TEXT}): {what[:60]}")
    for a, b, text in cues:
        if b - a < MIN_TEXT - 0.05:
            problems.append(f"caption shown {b - a:.1f} s: {text[:50]!r}")
    starts = {round(p[0], 2) for p in placed}
    if not all(any(abs(c[0] - s) < 0.01 for c in cues) for s in starts):
        problems.append("a caption does not start with its spoken line")
    problems += [f"voice-over: {o}" for o in overruns]
    text = json.dumps(spec) + (out / f"{name}.srt").read_text(encoding="utf-8")
    for w in forbidden():
        if w.lower() in text.lower().replace(Path(__file__).resolve().parent.as_uri().lower(), ""):
            problems.append(f"personal data in the film's text: {w[:3]}…")
    stage, safe = Stage(spec, 1), []
    try:
        for t in [x / 2 for x in range(0, int(spec["duration"] * 2))]:
            stage.seek(t)
            for b in stage.page.evaluate("t => offscreen(t)", t):
                safe.append(f"{int(t // 60)}:{t % 60:04.1f} {b}")
    finally:
        stage.close()
    problems += sorted(set(f"outside the title-safe area: {s}" for s in safe))[:20]
    video = next(iter(sorted(out.glob("acxelin-*-1080p.mp4"))), None)
    made = sheets(video, cuts(spec, shots), out / "review") if video else []
    notes.append(f"{len(made)} cuts, each as the frame before, at and after, in review/")
    report = out / f"{name}-review.md"
    report.write_text(f"# Review: {name}\n\n" + (f"{len(problems)} problem(s):\n\n" + "\n".join(f"- {p}" for p in problems) if problems else "No problems found by the checks.")
                      + "\n\n## Notes\n\n" + "\n".join(f"- {n}" for n in notes) + "\n", encoding="utf-8")
    return report
