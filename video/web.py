"""The films for the website: python video/web.py [FILM ...]

From each delivered film in ~/AcxelinVideos/<film>, writes website/assets/films/<film>.mp4 (720p, H.264, sized for the web),
<film>.jpg (the poster: the film's thumbnail, shown before it plays) and <film>.vtt (the captions)."""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from render import ffmpeg  # noqa: E402
from script import FILMS  # noqa: E402

SRC = Path.home() / "AcxelinVideos"
OUT = HERE.parent / "website" / "assets" / "films"


def web(film):
    OUT.mkdir(parents=True, exist_ok=True)
    src = SRC / film / f"acxelin-{film}-1080p.mp4"
    run = lambda *a: subprocess.run([ffmpeg(), "-y", "-loglevel", "error", *map(str, a)], check=True)
    run("-i", src, "-vf", "scale=1280:720:flags=lanczos", "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "24",
        "-maxrate", "1400k", "-bufsize", "2800k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        OUT / f"{film}.mp4")
    run("-i", SRC / film / f"acxelin-{film}-thumbnail.png", "-q:v", "3", OUT / f"{film}.jpg")  # the poster is the film's thumbnail
    srt = (SRC / film / f"acxelin-{film}.srt").read_text(encoding="utf-8")
    (OUT / f"{film}.vtt").write_text("WEBVTT\n\n" + re.sub(r"(\d\d:\d\d:\d\d),(\d\d\d)", r"\1.\2", srt), encoding="utf-8")
    print(film, *(f"{p.name} {p.stat().st_size / 1e6:.1f} MB" for p in sorted(OUT.glob(f"{film}.*"))))


if __name__ == "__main__":
    for f in sys.argv[1:] or FILMS:
        web(f)
