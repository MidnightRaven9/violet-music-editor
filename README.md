# Violet Music Editor

An installable web app (PWA) + Android app that turns any uploaded MP3 into an
EDM-style remix: **Nightcore**, **Slowed + Reverb**, **Bass Boost**, **Echo**,
**Reverb**, or a fully **Custom** remix with your own speed / pitch / reverb.

![platform](https://img.shields.io/badge/platform-Web%20%2B%20Android-8b5cf6)

---

## How it works

```
upload MP3 → FFmpeg decode → librosa time-stretch / pitch-shift
           → pedalboard reverb / EQ / delay → FFmpeg encode MP3 → download
```

The heavy audio processing runs on a small FastAPI backend, so the output is
high quality (no browser-quality compromises). The frontend is a PWA that can be
installed on your phone's home screen.

---

## Remix styles

| Style | Speed | Pitch | Reverb |
|-------|-------|-------|--------|
| Nightcore | ×1.3 | +7 semitones | — |
| Slowed + Reverb | ×0.8 | — | 40% |
| Bass Boost | ×1.0 | — | — |
| Echo / Delay | ×1.0 | — | — |
| Reverb | ×1.0 | — | 35% |
| Custom | your sliders | your sliders | your sliders |

---

## Run the web app

```bash
cd edm-remix-pwa
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt   # needs ffmpeg installed
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000> in a browser. On Android Chrome, use
**Add to Home screen** to install the PWA.

### Requirements
- Python 3.10+
- FFmpeg (`apt install ffmpeg`)
- **RubberBand** (`apt install rubberband-cli`) — studio-grade time-stretch / pitch-shift engine
- Python packages in `backend/requirements.txt`

### Audio engine
Remixes use a professional-grade pipeline:
1. **RubberBand** (R2 phase-locked engine) for time-stretch / pitch-shift — avoids the warbling artifacts of basic phase vocoders, preserves stereo
2. **Pedalboard** effects (reverb, bass, delay, chorus, phaser, distortion, bitcrush)
3. **Mastering chain** on every remix: high-pass filter, gentle glue compression, presence/air EQ, limiter, and peak normalization to -1 dBFS
4. High-quality VBR MP3 encoding (~245 kbps)

---

## Android APK

`android-project/` contains a lightweight WebView shell that loads the app.
It is named **Violet Music Editor** (package `com.violet.musiceditor`).

### Build

```bash
cd android-project
./build.sh
# → VioletMusicEditor.apk
```

`build.sh` uses the Android SDK build-tools (`aapt2`, `d8`, `zipalign`,
`apksigner`) directly — no Gradle or Android Studio required. It generates a
debug keystore and signs the APK automatically.

### Server URL

The APK loads a server URL (default `http://127.0.0.1:8000`). Open the app's
overflow menu → **Server URL** to point it at wherever your backend is running
(e.g. a hosted URL, or your phone's local server).

> The APK is a native shell around the web app; the audio processing still
> happens on the FastAPI backend. Keep the backend running on the same network.

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload MP3 + effect params → `{job_id}` |
| `GET` | `/api/jobs/{job_id}` | Poll status/progress |
| `GET` | `/api/download/{job_id}` | Download processed MP3 |
| `GET` | `/api/effects` | List effect presets |

Upload form fields: `file`, `effect`, `rate`, `pitch`, `reverb`.

---

## Project structure

```
edm-remix-pwa/
├── backend/
│   ├── main.py            # FastAPI app + job queue
│   ├── audio.py           # FFmpeg / librosa / pedalboard processing
│   └── requirements.txt
├── public/                # PWA frontend (HTML/CSS/JS + manifest + service worker)
├── android-project/       # Android WebView shell (Violet Music Editor)
│   ├── AndroidManifest.xml
│   ├── res/               # resources + generated icons
│   ├── java/              # MainActivity
│   └── build.sh
├── uploads/               # temporary uploads (gitignored)
└── processed/             # temporary remixes (gitignored)
```

## Tech stack

- **Backend:** FastAPI, FFmpeg, librosa, pedalboard (Spotify), soundfile
- **Frontend:** vanilla JS PWA (service worker + web manifest)
- **Android:** WebView shell, built with the Android SDK build-tools
