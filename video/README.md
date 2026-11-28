# Product films

The three launch films (QReadiness, QGuard with QCertificate, QVPN) are built from the approved script in
`documents/video-script.md`: one command per product.

```
python video/build.py qreadiness
python video/build.py qguard
python video/build.py qvpn
```

Each command does the following:
1. Records the real console doing real work (`<product>.py`, `capture.py`).
2. Speaks the scratch voice-over with the Windows voice (`voice.py`).
3. Renders 4K and 1080p (`stage/`, `render.py`), the 15-second social cut and the thumbnail.
4. Reviews the result (`review.py`): text under 1.5 s, text outside the title-safe area, caption timing, personal data, and
   the frames either side of every cut.

The deliverables land in `~/AcxelinVideos/<film>`. Useful options:
- `--reuse` keeps the last recording, to re-render after an edit.
- `--quick` renders 1080p only.
- `--captions` adds a copy with the captions burned in.
- `--eleven` uses the ElevenLabs narration (George), score and interface sounds that `video/eleven.py` makes in
  `~/AcxelinVideos/audio` (needs `pip install elevenlabs` and the key from `npx @elevenlabs/cli onboard init`).
- `--remux` keeps the rendered picture and redoes only the sound, cuts and review.

`python video/web.py` makes the website's 720p copies, posters and captions.

A film built from anything but `main` is marked DRAFT on every frame.

Needs: Python with this repository installed, Playwright with Chromium, ffmpeg (`winget install Gyan.FFmpeg`), OpenSSL 3.5+
(`ACXELIN_OPENSSL`), and, for QVPN's tunnel, WSL Ubuntu. Renders, recordings and audio are not committed.

| File | Role |
|---|---|
| `script.py` | Reads each film's shots from the script |
| `films.py` | What every film shares: hook, meet card, section cards, lower thirds, trust, close |
| `qreadiness.py`, `qguard.py`, `qvpn.py` | Each film's diagram and console scenes |
| `capture.py` | Records a console: a frame per visible change, the cursor's path, and a check for personal data before every frame |
| `stage/` | The compositor: every frame is a pure function of time |
| `render.py` | Frames into ffmpeg (H.264 High, BT.709), stills |
| `voice.py` | Scratch voice-over, -14 LUFS mix, `.srt` captions |
| `review.py` | The checks and the contact sheets at every cut |
| `build.py` | The one command per film |

The music is the owner's licensed track, added in the edit at the cues the script marks. These builds leave silence there.
