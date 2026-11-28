"""The scratch voice-over, for timing only: each shot's line spoken by the Windows built-in voice (Microsoft Hazel, en-GB),
placed in its shot, mixed to -14 LUFS, and the captions (.srt) timed from the same placement."""
import json
import re
import subprocess
import wave
from pathlib import Path

from render import ffmpeg

VOICE = "Microsoft Hazel Desktop"
LEAD = 0.35  # a line starts this long after its shot begins
PS = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try { $s.SelectVoice('%s') } catch { }
$s.Rate = %d
foreach ($job in (Get-Content -Raw -Encoding UTF8 '%s' | ConvertFrom-Json)) {
  $s.SetOutputToWaveFile($job.wav)
  $s.Speak($job.text)
}
$s.SetOutputToNull()
"""


def spoken(text):
    """What the voice reads: the script's line without markdown."""
    return re.sub(r"[*`]", "", text).replace("…", "...")


def synth(lines, folder, rate=0):
    """lines: [(key, text)] -> {key: (wav path, seconds)}."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    jobs = [{"wav": str(folder / f"{k}.wav"), "text": spoken(t)} for k, t in lines]
    (folder / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    script = folder / "speak.ps1"
    script.write_text(PS % (VOICE, rate, folder / "jobs.json"), encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], check=True)
    out = {}
    for k, _ in lines:
        p = folder / f"{k}.wav"
        with wave.open(str(p)) as w:
            out[k] = (p, w.getnframes() / w.getframerate())
    return out


def recorded(film, shots, source, folder):
    """The narrator's own files, `<film>-01.wav` onwards (one per spoken line, in script order), trimmed of the silence at both
    ends -> {key: (wav, seconds)}, keyed like synth()."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out, missing = {}, []
    trim = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,areverse," \
           "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.12,areverse"
    for n, i in enumerate((i for i, s in enumerate(shots) if s.voice), 1):
        src = Path(source) / f"{film}-{n:02d}.wav"
        if not src.exists():
            missing.append(src.name)
            continue
        dst = folder / f"{i:02d}.wav"
        subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(src), "-af", trim, "-ac", "1", "-ar", "48000", "-c:a", "pcm_s24le", str(dst)], check=True)
        with wave.open(str(dst)) as w:
            out[f"{i:02d}"] = (dst, w.getnframes() / w.getframerate())
    if missing:
        raise SystemExit(f"missing from {source}: {', '.join(missing)}")
    return out


def place(shots, folder, film=None, source=None):
    """Speak (or, with `source`, take the narrator's recording of) every shot's line and place it. Returns
    [(start, seconds, wav, text)] and a list of lines that overrun their shot."""
    lines = [(f"{i:02d}", s.voice) for i, s in enumerate(shots) if s.voice]
    made = recorded(film, shots, source, Path(folder) / "recorded") if source else synth(lines, folder)
    placed, owners = [], []
    for i, s in enumerate(shots):
        if not s.voice:
            continue
        wav, dur = made[f"{i:02d}"]
        start = s.start + LEAD
        if start + dur > s.end - 0.1:  # a long line starts earlier in its shot, but never before it
            start = max(s.start + 0.05, s.end - 0.1 - dur)
        placed.append((start, dur, wav, s.voice))
        owners.append(s)
    # A line that still runs past its shot finishes naturally; the next line waits a beat instead of talking over it.
    # It is a problem only if that pushes the next line out of its own shot.
    overruns = []
    for i in range(1, len(placed)):
        prev_end = placed[i - 1][0] + placed[i - 1][1]
        start, dur, wav, text = placed[i]
        if start < prev_end + 0.3:
            placed[i] = (prev_end + 0.3, dur, wav, text)
    for (start, dur, _, text), s in zip(placed, owners):
        if start + dur > s.end + 0.6 or start + dur > shots[-1].end - 0.3:
            overruns.append(f"{s.start // 60}:{s.start % 60:02.0f} runs {start + dur - s.end:.1f} s past its shot: {text[:50]}")
    return placed, overruns


MUSIC_DB = -15  # the score under the voice before ducking; it ducks a further ~8 dB while someone speaks
SFX_DB = {"click": -24, "swell": -27}


def mix(placed, duration, out, score=None, effects=()):
    """One track: every line at its time; the score (if any) under it, ducking while the voice speaks and coming forward in
    the breathers; quiet interface sounds at `effects` [(time, wav, dB)]. Loudness -14 LUFS integrated, -1.5 dBTP, measured
    in a first pass and applied evenly in the second."""
    args, chains, n = [ffmpeg(), "-y", "-loglevel", "error"], [], 0
    for start, _, wav, _ in placed:
        args += ["-i", str(wav)]
        ms = round(start * 1000)
        chains.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=mono,pan=stereo|c0=c0|c1=c0,adelay={ms}|{ms}[a{n}]")
        n += 1
    chains.append("".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,apad,atrim=0:{duration}[vo]")
    final = ["[vo]"]
    if score:
        args += ["-i", str(score)]
        chains.append("[vo]asplit=2[vo1][key]")
        chains.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{duration},volume={MUSIC_DB}dB,"
                      f"afade=t=in:d=1,afade=t=out:st={duration - 2}:d=2[mus]")
        chains.append("[mus][key]sidechaincompress=threshold=0.015:ratio=5:attack=80:release=900:knee=4[duck]")
        final = ["[vo1]", "[duck]"]
        n += 1
    fx = []
    for t, wav, db in effects:
        args += ["-i", str(wav)]
        ms = round(t * 1000)
        chains.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,volume={db}dB,adelay={ms}|{ms}[f{n}]")
        fx.append(f"[f{n}]")
        n += 1
    if fx:
        chains.append("".join(fx) + f"amix=inputs={len(fx)}:normalize=0[fx]")
        final.append("[fx]")
    chains.append("".join(final) + f"amix=inputs={len(final)}:normalize=0,apad,atrim=0:{duration}[pre]")
    graph = ";".join(chains)
    target = "I=-14:TP=-1.5:LRA=11"
    probe = subprocess.run([args[0], "-hide_banner", "-loglevel", "info"] + args[4:] + ["-filter_complex", graph + f";[pre]loudnorm={target}:print_format=json[o]", "-map", "[o]", "-f", "null", "-"],
                           capture_output=True, text=True, check=True).stderr
    import json as _json
    m = _json.loads(probe[probe.rindex("{"):probe.rindex("}") + 1])
    measured = f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}"
    subprocess.run(args + ["-filter_complex", graph + f";[pre]loudnorm={target}:{measured}:linear=true[out]", "-map", "[out]",
                           "-ar", "48000", "-c:a", "pcm_s24le", str(out)], check=True)
    return out


def loudness(path):
    """Integrated loudness (LUFS) and true peak (dBTP) of a file, as the review reports them."""
    import json as _json
    err = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = _json.loads(err[err.rindex("{"):err.rindex("}") + 1])
    return float(m["input_i"]), float(m["input_tp"])


def effects_of(spec, folder):
    """Where the interface sounds go: a click at every real click the cursor makes on screen, a swell under each section card."""
    folder, out = Path(folder), []
    click, swell = folder / "click.wav", folder / "swell.wav"
    for l in spec["layers"]:
        if l["type"] == "section" and swell.exists():
            out.append((l["start"], swell, SFX_DB["swell"]))
        if l["type"] == "window" and l.get("scene") and click.exists():
            for k in l["scene"].get("cursor", []):
                if k.get("click"):
                    t = l["start"] + k["t"] - (l.get("offset") or 0)
                    if l["start"] <= t < l["end"]:
                        out.append((t, click, SFX_DB["click"]))
    return sorted(out, key=lambda e: e[0])


def srt(placed, out, width=42):
    """Captions from the placed lines: at most two lines of `width` characters, split at sentence or phrase ends, each shown
    for its share of the line's time and at least 1.5 s."""
    cues = []
    for start, dur, _, text in placed:
        text = spoken(text)
        parts = [p for p in re.split(r"(?<=[.?!:])\s+", text) if p]
        chunks = []
        for p in parts:
            while len(p) > 2 * width:
                cut = max(p.rfind(", ", 0, 2 * width), p.rfind(" ", 0, 2 * width))
                chunks.append(p[:cut + 1].strip())
                p = p[cut + 1:].strip()
            if chunks and len(chunks[-1]) + len(p) + 1 <= 2 * width and len(chunks[-1]) < 30:
                chunks[-1] += " " + p
            else:
                chunks.append(p)
        merged = []
        for c in chunks:  # a piece too short to read in its share of time joins its neighbour, if the pair still fits two lines
            if merged and (len(merged[-1]) < 24 or len(c) < 24) and len(merged[-1]) + len(c) + 1 <= 2 * width:
                merged[-1] += " " + c
            else:
                merged.append(c)
        chunks = merged
        total = sum(len(c) for c in chunks)
        shares = [max(dur, 1.5 * len(chunks)) * len(c) / total for c in chunks]
        short = [i for i, s in enumerate(shares) if s < 1.5]
        if short and len(short) < len(shares):  # a short piece is held 1.5 s; the longer ones give up that time
            need = sum(1.5 - shares[i] for i in short)
            long_total = sum(s for i, s in enumerate(shares) if i not in short)
            shares = [1.5 if i in short else s - need * s / long_total for i, s in enumerate(shares)]
        t = start
        for c, d in zip(chunks, shares):
            cues.append((t, t + d, wrap(c, width)))
            t += d
    for i in range(len(cues) - 1):  # a cue never overlaps the next
        a, b, text = cues[i]
        cues[i] = (a, min(b, cues[i + 1][0] - 0.04), text)
    stamp = lambda s: f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{int(s % 60):02d},{int(round(s % 1 * 1000)) % 1000:03d}"
    Path(out).write_text("".join(f"{n}\n{stamp(a)} --> {stamp(b)}\n{text}\n\n" for n, (a, b, text) in enumerate(cues, 1)), encoding="utf-8")
    return cues


def wrap(text, width):
    if len(text) <= width:
        return text
    spaces = [i for i, c in enumerate(text) if c == " "]
    cut = min(spaces, key=lambda i: max(i, len(text) - i - 1))  # the most even pair of lines
    return text[:cut] + "\n" + text[cut + 1:]
