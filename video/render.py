"""Render a film spec on the stage, frame by frame, straight into ffmpeg; and single stills for thumbnails and the review."""
import base64
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = (HERE / "stage" / "stage.html").as_uri()
LOGO = (HERE.parent / "website" / "assets" / "acxelin-quantum.svg").read_text(encoding="utf-8")


def ffmpeg():
    found = shutil.which("ffmpeg")
    if found:
        return found
    for p in sorted((Path.home() / "AppData/Local/Microsoft/WinGet/Packages").glob("Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe")):
        return str(p)
    raise SystemExit("ffmpeg is needed: winget install Gyan.FFmpeg")


class Stage:
    def __init__(self, spec, scale=2):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch()
        self.page = self.browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=scale)
        self.page.goto(STAGE)
        self.page.evaluate("s => load(s)", {**spec, "logo": LOGO})
        self.cdp = self.page.context.new_cdp_session(self.page)
        self.scale = scale

    def seek(self, t):
        return self.page.evaluate("t => seek(t)", t)

    def jpeg(self, quality=94):
        clip = {"x": 0, "y": 0, "width": 1920, "height": 1080, "scale": self.scale}  # without the scale CDP captures CSS pixels
        return base64.b64decode(self.cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": quality, "optimizeForSpeed": True, "clip": clip})["data"])

    def png(self, path, t):
        self.seek(t)
        self.page.screenshot(path=str(path))

    def texts(self, t):
        self.seek(t)
        return self.page.evaluate("t => texts(t)", t)

    def close(self):
        self.browser.close()
        self.pw.stop()


def video(spec, out, fps=30, scale=2, start=0.0, end=None, crf=14):
    """Encode the frames of [start, end) as H.264 High, yuv420p, `scale`×1080 lines. Frames that do not change are not re-captured."""
    end = spec["duration"] if end is None else end
    n = round((end - start) * fps)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen([ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
                            "-vf", "scale=out_range=tv:out_color_matrix=bt709,format=yuv420p", "-c:v", "libx264", "-profile:v", "high", "-preset", "slow",
                            "-crf", str(crf), "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                            "-r", str(fps), "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    stage = Stage(spec, scale)
    last_sig, last, captured = None, None, 0
    try:
        for i in range(n):
            sig = stage.seek(start + i / fps)
            if sig != last_sig:
                last, last_sig, captured = stage.jpeg(), sig, captured + 1
            enc.stdin.write(last)
            if i % 300 == 0:
                print(f"  {out.name}: {i / fps:6.1f} s of {n / fps:.0f} s", flush=True)
    finally:
        stage.close()
        enc.stdin.close()
        enc.wait()
    if enc.returncode:
        raise SystemExit(f"ffmpeg failed on {out}")
    print(f"  {out.name}: {n} frames, {captured} rendered")
    return out


def stills(spec, times, folder, scale=1):
    """PNG stills at `times`, named by time; returns their paths and the texts on screen at each."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stage, out = Stage(spec, scale), []
    try:
        for t in times:
            p = folder / f"{t:07.2f}.png"
            stage.png(p, t)
            out.append((t, p, stage.texts(t)))
    finally:
        stage.close()
    return out


if __name__ == "__main__":
    import sys
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    video(spec, sys.argv[2], scale=int(sys.argv[3]) if len(sys.argv) > 3 else 2)
