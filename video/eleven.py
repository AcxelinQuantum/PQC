"""The films' sound from ElevenLabs: the narration, the score and two quiet interface sounds.

    python video/eleven.py voices                       the voices this account can use
    python video/eleven.py sample VOICE_ID              one line, to judge the voice before spending credits on all of them
    python video/eleven.py narrate VOICE_ID [FILM ...]  every line, as <film>-01.wav onwards (lines already made are kept)
    python video/eleven.py score                        one score for all three films, in the script's M1–M5 shape
    python video/eleven.py sfx                          a soft click and a soft section swell

Everything is written to ~/AcxelinVideos/audio; build.py uses it from there. The key is read from the project's .env (made by
`npx @elevenlabs/cli onboard init`) into this process only, and is never printed."""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from render import ffmpeg  # noqa: E402
from script import FILMS, shots  # noqa: E402
from voice import spoken  # noqa: E402

AUDIO = Path.home() / "AcxelinVideos" / "audio"
MODEL = "eleven_v4"
NARRATION = {"stability": 0.7, "similarity_boost": 0.5}  # the guide's narration preset: a steady tone, natural variation


def client():
    if not os.environ.get("ELEVENLABS_API_KEY"):
        env = HERE.parent / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                name, _, value = line.partition("=")
                if name.strip() == "ELEVENLABS_API_KEY" and value.strip():
                    os.environ["ELEVENLABS_API_KEY"] = value.strip().strip('"').strip("'")
    if not os.environ.get("ELEVENLABS_API_KEY"):
        raise SystemExit("no ElevenLabs key: run `npx -y @elevenlabs/cli@latest onboard init` in the project folder")
    from elevenlabs import ElevenLabs
    return ElevenLabs()


def to_wav(data, out):
    """Any audio ElevenLabs returns, as 48 kHz 24-bit WAV."""
    raw = out.with_suffix(".download")
    raw.write_bytes(data)
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(raw), "-ar", "48000", "-c:a", "pcm_s24le", str(out)], check=True)
    raw.unlink()
    return out


def voices():
    for v in sorted(client().voices.get_all().voices, key=lambda v: (v.category != "premade", v.name)):
        labels = ", ".join(f"{v2}" for v2 in (v.labels or {}).values())
        print(f"{v.voice_id}  {v.name:<22} {v.category:<10} {labels}")


def speak(c, voice_id, text, previous=None, following=None):
    from elevenlabs import VoiceSettings
    audio = c.text_to_speech.convert(text=spoken(text), voice_id=voice_id, model_id=MODEL, output_format="mp3_44100_128",
                                     voice_settings=VoiceSettings(**NARRATION), previous_text=previous, next_text=following,
                                     apply_text_normalization="auto")
    return b"".join(audio)


def sample(voice_id):
    out = AUDIO / "samples"
    out.mkdir(parents=True, exist_ok=True)
    line = shots("qreadiness")[5].voice  # "Meet Acxelin QReadiness. It finds…": the product name and a long sentence
    path = to_wav(speak(client(), voice_id, line), out / f"sample-{voice_id}.wav")
    print(f"sample: {path} ({len(spoken(line))} characters)")


def narrate(voice_id, films=None):
    c, used = client(), 0
    for film in films or FILMS:
        lines = [s.voice for s in shots(film) if s.voice]
        folder = AUDIO / "voice"
        folder.mkdir(parents=True, exist_ok=True)
        for n, text in enumerate(lines, 1):
            path = folder / f"{film}-{n:02d}.wav"
            if path.exists():
                continue
            previous = spoken(lines[n - 2]) if n > 1 else None
            following = spoken(lines[n]) if n < len(lines) else None
            to_wav(speak(c, voice_id, text, previous, following), path)
            used += len(spoken(text))
            print(f"  {path.name}")
    (AUDIO / "voice" / "voice.txt").write_text(f"ElevenLabs voice {voice_id}, model {MODEL}, settings {NARRATION}\n", encoding="utf-8")
    print(f"narration in {AUDIO / 'voice'} ({used} characters this run)")


# The score follows the script's cues, which fall at the same times in all three films.
STYLES = ["warm minimal electronic", "instrumental", "soft pulse", "light piano", "gentle plucks", "100 BPM", "modern product film"]
AVOID = ["vocals", "heavy drums", "EDM drop", "epic orchestral", "aggressive", "dark", "dubstep", "lo-fi crackle"]
SCORE = [
    (15000, "[Intro] One low, sustained, warm synth note. Spacious and calm. Almost nothing else.", ["sparse", "ambient"]),
    (30000, "[Build] A soft, steady pulse enters under the low note. Curious, quietly purposeful.", ["soft pulse", "subtle"]),
    (80000, "[Main] The full bed arrives: light piano and gentle plucks over the soft pulse. Optimistic, confident, unhurried. "
            "Leaves room for a narrator's voice.", ["light piano", "gentle plucks", "steady"]),
    (75000, "[Main continues] The same bed, evolving slowly with small variations, still leaving room for a voice.", ["light piano", "steady"]),
    (25000, "[Reflection] Thins out: piano and a soft pad only, quieter, reflective, trustworthy.", ["sparse", "piano", "quiet"]),
    (15000, "[Resolve] A warm final chord that resolves and rings out to silence.", ["resolving", "warm ending"]),
]


def score():
    plan = {"chunks": [{"text": text, "duration_ms": ms, "positive_styles": (STYLES if i == 0 else []) + extra,
                        "negative_styles": AVOID, "context_adherence": "high"} for i, (ms, text, extra) in enumerate(SCORE)]}
    assert sum(ms for ms, *_ in SCORE) == 240000
    audio = client().music.compose(composition_plan=plan, model_id="music_v2_5")
    AUDIO.mkdir(parents=True, exist_ok=True)
    path = to_wav(b"".join(audio), AUDIO / "score.wav")
    print(f"score: {path}")


SFX = {
    "click": ("A single soft, clean computer mouse click, close and dry, subtle, no room sound", 0.5),
    "swell": ("A very soft, short airy swell, a gentle breath of air rising and fading, subtle, clean, for a title card", 1.2),
}


def sfx():
    c = client()
    folder = AUDIO / "sfx"
    folder.mkdir(parents=True, exist_ok=True)
    for name, (text, seconds) in SFX.items():
        audio = c.text_to_sound_effects.convert(text=text, model_id="eleven_text_to_sound_v3", duration_seconds=seconds, prompt_influence=0.8)
        print(f"sfx: {to_wav(b''.join(audio), folder / f'{name}.wav')}")


if __name__ == "__main__":
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    if cmd == "voices":
        voices()
    elif cmd == "sample" and args:
        sample(args[0])
    elif cmd == "narrate" and args:
        narrate(args[0], args[1:] or None)
    elif cmd == "score":
        score()
    elif cmd == "sfx":
        sfx()
    else:
        raise SystemExit(__doc__)
