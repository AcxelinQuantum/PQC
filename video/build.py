"""Build a product film, one command per product:

    python video/build.py qreadiness            record the console, speak, render 4K and 1080p, cut, review, deliver
    python video/build.py qguard --reuse        use the last recording instead of recording again
    python video/build.py qvpn --quick          1080p only, for checking timing
    python video/build.py qguard --reuse --voice-dir D:/vo   the narrator's recordings instead of the scratch voice
    python video/build.py qvpn --reuse --eleven    the ElevenLabs narration, score and sounds (made by video/eleven.py)

Recordings go to video/raw/<film>, renders to video/out/<film>; the deliverables are copied to ~/AcxelinVideos/<film>.
A film built from anything but main is marked DRAFT on every frame (the final footage must show what main ships)."""
import argparse
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import films  # noqa: E402
import render  # noqa: E402
import review  # noqa: E402
import voice  # noqa: E402
from script import FILMS, shots  # noqa: E402

DELIVER = Path.home() / "AcxelinVideos"


def branch():
    try:
        return subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    except OSError:
        return "?"


def ff(*args):
    subprocess.run([render.ffmpeg(), "-y", "-loglevel", "error", *map(str, args)], check=True)


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("film", choices=list(FILMS))
    a.add_argument("--reuse", action="store_true", help="use the last recording of the consoles")
    a.add_argument("--quick", action="store_true", help="1080p only, no 4K, no social cut")
    a.add_argument("--captions", action="store_true", help="also make a 1080p copy with the captions burned in")
    a.add_argument("--voice-dir", help="the narrator's recordings (<film>-01.wav onwards, see documents/voice-over-script.md) instead of the scratch voice")
    a.add_argument("--eleven", action="store_true", help="use the ElevenLabs narration, score and interface sounds in ~/AcxelinVideos/audio")
    a.add_argument("--score", help="a music track to lay under the film (ducked under the voice)")
    a.add_argument("--remux", action="store_true", help="keep the rendered picture; only redo the sound, the cuts and the review")
    a.add_argument("--draft", help="mark every frame DRAFT with this note (automatic off main)")
    args = a.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # review text holds characters a Windows console code page lacks

    name, product = args.film, importlib.import_module(args.film)
    raw, out = HERE / "raw" / name, HERE / "out" / name
    out.mkdir(parents=True, exist_ok=True)
    draft = args.draft or (None if branch() == "main" else f"built from {branch()}, not main")

    scenes_file = raw / "scenes.json"
    if args.reuse and scenes_file.exists():
        scenes = json.loads(scenes_file.read_text(encoding="utf-8"))
    else:
        print(f"recording the {FILMS[name]} consoles")
        scenes = product.capture(raw)
        scenes_file.write_text(json.dumps(scenes), encoding="utf-8")

    spec = films.film(name, product, scenes, draft)
    (out / "spec.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
    s = shots(name)

    audio = DELIVER / "audio"
    if args.eleven:
        args.voice_dir = args.voice_dir or str(audio / "voice")
        args.score = args.score or (str(audio / "score.wav") if (audio / "score.wav").exists() else None)
    print("placing the narrator's recordings" if args.voice_dir else "speaking the scratch voice-over")
    placed, overruns = voice.place(s, raw / "voice", name, args.voice_dir)
    for o in overruns:
        print("  overrun:", o)
    effects = voice.effects_of(spec, audio / "sfx") if args.eleven else []
    vo = voice.mix(placed, spec["duration"], out / f"{name}-{'soundtrack' if args.voice_dir else 'scratch-vo'}.wav", args.score, effects)
    lufs, peak = voice.loudness(vo)
    print(f"  soundtrack: {lufs:.1f} LUFS, true peak {peak:.1f} dBTP, {len(effects)} interface sounds, music: {'yes' if args.score else 'none'}")
    cues = voice.srt(placed, out / f"{name}.srt")

    stem = f"acxelin-{name}"
    if args.quick:
        print("rendering 1080p")
        silent = render.video(spec, out / "picture-1080.mp4", scale=1, crf=16)
        ff("-i", silent, "-i", vo, "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out / f"{stem}-1080p.mp4")
    else:
        print("rendering 4K")
        silent = out / "picture-4k.mp4"
        if not (args.remux and silent.exists()):
            silent = render.video(spec, silent, scale=2, crf=14)
        ff("-i", silent, "-i", vo, "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", out / f"{stem}-4k.mp4")
        ff("-i", out / f"{stem}-4k.mp4", "-vf", "scale=1920:1080:flags=lanczos", "-c:v", "libx264", "-profile:v", "high", "-preset", "slow",
           "-crf", "16", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-c:a", "copy", "-movflags", "+faststart", out / f"{stem}-1080p.mp4")
        social(product.SOCIAL, out / f"{stem}-1080p.mp4", out / f"{stem}-social-15s.mp4")
    if args.captions:
        sub = str(out / f"{name}.srt").replace("\\", "/").replace(":", "\\:")
        ff("-i", out / f"{stem}-1080p.mp4", "-vf", f"subtitles='{sub}':force_style='FontName=Host Grotesk,FontSize=22,MarginV=40'",
           "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "copy", out / f"{stem}-1080p-captions.mp4")

    print("making the thumbnail")
    thumb = render.stills(films.thumbnail(FILMS[name], product.thumb_frame(scenes)), [0.5], out / "thumb", scale=1)[0][1]
    ff("-i", thumb, "-vf", "scale=1280:720:flags=lanczos", out / f"{stem}-thumbnail.png")

    print("reviewing")
    report = review.run(name, spec, s, cues, placed, overruns, out)
    print(report.read_text(encoding="utf-8").split("\n## ")[0])

    target = DELIVER / name
    target.mkdir(parents=True, exist_ok=True)
    for f in out.glob(f"{stem}*"):
        shutil.copy2(f, target / f.name)
    for f in (vo, out / f"{name}.srt", report):
        shutil.copy2(f, target / f.name.replace(name, stem, 1) if not f.name.startswith(stem) else target / f.name)
    shutil.copytree(out / "review", target / "review", dirs_exist_ok=True)
    print(f"delivered to {target}")


def social(segments, source, out):
    """A 15-second cut: the given (start, end, keep_voice) pieces joined with short dissolves."""
    parts, graph, n = [], [], len(segments)
    for i, (a, b, voice_on) in enumerate(segments):
        parts += ["-ss", f"{a}", "-to", f"{b}", "-i", str(source)]
        graph.append(f"[{i}:v]fade=in:st=0:d=0.25,fade=out:st={b - a - 0.25}:d=0.25,setpts=PTS-STARTPTS[v{i}]")
        graph.append(f"[{i}:a]afade=in:st=0:d=0.2,afade=out:st={b - a - 0.2}:d=0.2,volume={1 if voice_on else 0},asetpts=PTS-STARTPTS[a{i}]")
    graph.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
    ff(*parts, "-filter_complex", ";".join(graph), "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-profile:v", "high", "-crf", "17",
       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", out)


if __name__ == "__main__":
    main()
