"""The 3:00 edit of a finished 4:00 film, without rendering a frame again: python video/cut.py FILM [--length 180]

The time comes out of quiet holds only. After each spoken line at least HOLD seconds stay. Every shot keeps its last TAIL seconds,
so its own transition still plays. Nothing comes out of the hook or the trust section, and the close keeps its fade to black.
Every scene and every line stays, and the section numbers stay in order. Joins are 0.3 s dissolves. The narration, the interface
sounds and the captions are placed again on the new timeline, and the score is cut at the same points with crossfades. Writes
the 4K and 1080p films, the soundtrack and the captions over the 4:00 ones in ~/AcxelinVideos/<film> (the 4:00 versions move to
4-minute/), and the frames either side of every join to video/out/<film>/cut-review."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import films  # noqa: E402
import review  # noqa: E402
import voice  # noqa: E402
from render import ffmpeg  # noqa: E402
from script import FILMS, shots  # noqa: E402

DELIVER, AUDIO = Path.home() / "AcxelinVideos", Path.home() / "AcxelinVideos" / "audio"
HOLD, TAIL, FPS, XV, XA = 2.0, 0.8, 30, 0.3, 1.0
q = lambda t: round(t * FPS) / FPS  # on a frame


def removable(s, placed, protect=()):
    """(start, end) stretches that can go: in each product, problem and meet shot, from HOLD after its line to TAIL before its end,
    never over a `protect` interval (a real-time marker stays on screen as long as it was rendered)."""
    ends = {}
    for a, d, _, text in placed:
        shot = next(x for x in s if x.voice == text)
        ends[shot.start] = max(ends.get(shot.start, 0), a + d)
    out = []
    for i, shot in enumerate(s):
        if i < 2 or i >= len(s) - 3:  # the hook and the trust section stay whole
            continue
        quiet_from = ends.get(shot.start, films.body(shot) + 2.5) + HOLD
        if shot.end - TAIL - quiet_from > 0.5:
            out.append((q(quiet_from), q(shot.end - TAIL)))
    close = s[-1]  # the close: keep its line, its card building (3.6 s) and its last 2 s, the fade to black
    a = max(ends.get(close.start, close.start) + HOLD, close.start + 4.0)
    out.append((q(a), q(close.end - 2.0)))
    clipped = []
    for a, b in out:
        for p, e in protect:
            if p < b and e > a:
                a, b = (a, min(b, p)) if p > a else (max(a, e), b)
        if b - a > 0.5:
            clipped.append((q(a), q(b)))
    return clipped


def plan(s, placed, length, protect=()):
    """Cut the removable stretches, the longest first and each in proportion, until the film is `length` seconds."""
    cuts = removable(s, placed, protect)
    need = s[-1].end - length
    total = sum(b - a for a, b in cuts)
    if total < need:
        raise SystemExit(f"only {total:.1f} s of quiet holds can go; {need:.1f} s is needed")
    out = []
    for a, b in cuts:
        take = q((b - a) * need / total)
        out.append((q(b - take), b))  # take the end of each quiet stretch, so the result stays on screen right after the line
    drift = q(need - sum(b - a for a, b in out))
    a, b = out[0]
    out[0] = (q(a - drift), b)
    keep, t = [], 0.0
    for a, b in sorted(out):
        keep.append((t, a))
        t = b
    keep.append((t, float(s[-1].end)))
    return [(a, b) for a, b in keep if b - a > 0.05]


def remap(t, keep):
    """Where time t of the 4:00 film lands in the edit, or None if it was cut."""
    at = 0.0
    for a, b in keep:
        if a <= t < b:
            return at + t - a
        at += b - a
    return None


def video(src, keep, out, crf):
    """The kept pieces joined with short dissolves. Each piece runs on by XV, so the dissolve eats into cut footage, not kept."""
    parts, chains = [], []
    for i, (a, b) in enumerate(keep):
        end = b + (XV if i < len(keep) - 1 else 0)
        parts += ["-ss", f"{a:.4f}", "-to", f"{end:.4f}", "-i", str(src)]
        chains.append(f"[{i}:v]setpts=PTS-STARTPTS,fps={FPS}[v{i}]")
    last, at = "[v0]", keep[0][1] - keep[0][0]
    for i in range(1, len(keep)):
        chains.append(f"{last}[v{i}]xfade=transition=fade:duration={XV}:offset={at:.4f}[x{i}]")
        last, at = f"[x{i}]", at + keep[i][1] - keep[i][0]
    chains.append(f"{last}format=yuv420p[out]")
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", *parts, "-filter_complex", ";".join(chains), "-map", "[out]",
                    "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", str(crf), "-colorspace", "bt709",
                    "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", "-movflags", "+faststart", str(out)], check=True)


def score(keep, out):
    parts, chains = [], []
    for i, (a, b) in enumerate(keep):
        end = b + (XA if i < len(keep) - 1 else 0)
        parts += ["-ss", f"{a:.4f}", "-to", f"{end:.4f}", "-i", str(AUDIO / "score.wav")]
    last = "[0:a]"
    for i in range(1, len(keep)):
        chains.append(f"{last}[{i}:a]acrossfade=d={XA}:c1=tri:c2=tri[m{i}]")
        last = f"[m{i}]"
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", *parts, "-filter_complex", ";".join(chains) if chains else "anull",
                    "-map", last if chains else "0:a", "-c:a", "pcm_s24le", str(out)], check=True)


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("film", choices=list(FILMS))
    a.add_argument("--length", type=float, default=180.0)
    args = a.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    name, out = args.film, HERE / "out" / args.film
    s = shots(name)
    placed4, _ = voice.place(s, HERE / "raw" / name / "voice", name, AUDIO / "voice")
    spec = json.loads((out / "spec.json").read_text(encoding="utf-8"))
    keep = plan(s, placed4, args.length, [(l["start"], l["end"]) for l in spec["layers"] if l["type"] == "marker"])
    length = sum(b - a for a, b in keep)
    print(f"{name}: keeping {len(keep)} pieces, {length:.2f} s; cut " + ", ".join(f"{b:.1f}-{c:.1f}" for (_, b), (c, _) in zip(keep, keep[1:])))

    placed = []
    for start, dur, wav, text in placed4:
        new = remap(start, keep)
        if new is None or remap(start + dur - 0.01, keep) is None or remap(start + dur - 0.01, keep) - new > dur + 0.05:
            raise SystemExit(f"a cut would run through the line: {text[:50]}")
        placed.append((new, dur, wav, text))
    effects = [(remap(t, keep), w, db) for t, w, db in voice.effects_of(spec, AUDIO / "sfx") if remap(t, keep) is not None]
    short = []
    for l in spec["layers"]:  # every lower third, section card and marker still shows for 1.5 s or more
        if l["type"] in ("lower", "section", "marker"):
            shown = sum(max(0.0, min(b, l["end"]) - max(a, l["start"])) for a, b in keep)
            if shown < review.MIN_TEXT:
                short.append(f"{l.get('text') or l.get('title') or 'marker'} now {shown:.1f} s")
    if short:
        raise SystemExit("text would show too briefly: " + "; ".join(short))

    edit = out / "cut"
    edit.mkdir(parents=True, exist_ok=True)
    score(keep, edit / "score-3min.wav")
    track = voice.mix(placed, length, edit / f"{name}-soundtrack.wav", edit / "score-3min.wav", effects)
    voice.srt(placed, edit / f"{name}.srt")
    print(f"  soundtrack {voice.loudness(track)}; rendering the edit")
    video(out / "picture-4k.mp4", keep, edit / "picture-4k.mp4", 15)
    stem = f"acxelin-{name}"
    run = lambda *x: subprocess.run([ffmpeg(), "-y", "-loglevel", "error", *map(str, x)], check=True)
    run("-i", edit / "picture-4k.mp4", "-i", track, "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", edit / f"{stem}-4k.mp4")
    run("-i", edit / f"{stem}-4k.mp4", "-vf", "scale=1920:1080:flags=lanczos", "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "16",
        "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-c:a", "copy", "-movflags", "+faststart",
        edit / f"{stem}-1080p.mp4")
    joins = [q(sum(b - a for a, b in keep[:i + 1])) for i in range(len(keep) - 1)]
    review.sheets(edit / f"{stem}-1080p.mp4", joins, out / "cut-review")

    target, old = DELIVER / name, DELIVER / name / "4-minute"
    old.mkdir(parents=True, exist_ok=True)
    for f in (f"{stem}-4k.mp4", f"{stem}-1080p.mp4", f"{stem}.srt", f"{stem}-soundtrack.wav"):
        if (target / f).exists() and not (old / f).exists():
            shutil.move(str(target / f), str(old / f))
    for f in (f"{stem}-4k.mp4", f"{stem}-1080p.mp4"):
        shutil.copy2(edit / f, target / f)
    shutil.copy2(edit / f"{name}.srt", target / f"{stem}.srt")
    shutil.copy2(track, target / f"{stem}-soundtrack.wav")
    (target / f"{stem}-edit.txt").write_text("The 3:00 edit keeps these pieces of the 4:00 film (seconds):\n" +
                                            "\n".join(f"{a:7.2f} - {b:7.2f}" for a, b in keep) + "\n", encoding="utf-8")
    print(f"delivered the 3:00 edit to {target} (the 4:00 film is in {old})")


if __name__ == "__main__":
    main()
