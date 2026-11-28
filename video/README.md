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

The script times each film at 4:00. `python video/cut.py <film>` then makes the 3:00 edit from the finished film, taking time
out of quiet holds only, without rendering again; the 4:00 versions move to `4-minute/`.

`python video/web.py` makes the website's 720p copies, posters and captions.

A film built from anything but `main` is marked DRAFT on every frame.

Needs: Python with this repository installed, Playwright with Chromium, ffmpeg (`winget install Gyan.FFmpeg`), OpenSSL 3.5+
(`ACXELIN_OPENSSL`), and, for QVPN's tunnel, WSL Ubuntu. Renders, recordings and audio are not committed.

| File | Role |
|---|---|
| `script.py` | Reads each film's shots from the script |
| `films.py` | What every film shares: hook, meet card, section cards, lower thirds, trust, close |
| `qreadiness.py`, `qguard.py`, `qvpn.py` | Each film's diagram and console scenes |
| `qreadiness_world.py`, `qguard_world.py` | Acme's demo world on Windows: example repositories, owners spreadsheet and graded test servers; three small apps behind QGuard, with curl in WSL |
| `qvpn_lab.py` | QVPN's network in WSL network namespaces: two sites over real IPsec, the WireGuard gateway, enrolment and Alice's laptop |
| `capture.py` | Records a console: a frame per visible change, the cursor's path, and a check for personal data before every frame |
| `stage/` | The compositor: every frame is a pure function of time |
| `render.py` | Frames into ffmpeg (H.264 High, BT.709), stills |
| `voice.py` | Scratch voice-over, -14 LUFS mix, `.srt` captions |
| `eleven.py` | The ElevenLabs narration, score and interface sounds (`voices`, `sample`, `narrate`, `score`, `sfx`) |
| `review.py` | The checks and the contact sheets at every cut |
| `cut.py` | The 3:00 edit of a finished film |
| `web.py` | The website's 720p copies, posters and captions |
| `build.py` | The one command per film |

**Music and voice.** Without `--eleven` the builds use the scratch Windows voice and leave silence at the script's music cues.
With `--eleven` the narration and the score come from ElevenLabs. Before a film is published, check that the ElevenLabs plan
that made them allows commercial use of generated voice and music; a licensed track can replace the score at the same cues.
