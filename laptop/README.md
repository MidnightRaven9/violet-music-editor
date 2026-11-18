# Violet Music Editor — AI Restyle Engine (laptop)

This runs **Meta's MusicGen melody model** on your laptop to do a true AI remix:
it listens to your uploaded song's melody and regenerates it in a new style
(genre, instruments, tempo feel) from a text prompt. Unlike the phone app's DSP
effects, this actually creates new music around your melody.

It needs real hardware: **Python 3.10 + 12 GB+ RAM, or an 8 GB+ NVIDIA GPU.**
(That's why it can't run on the phone — verified: the model needs 2–4 GB just to load.)

---

## 1. Prerequisites

- **Python 3.10** (not 3.11/3.12 — AudioCraft pins older deps)
- **FFmpeg** on PATH (`ffmpeg -version` should work)
- Optional: NVIDIA GPU with 8 GB+ VRAM for fast generation

Check: `python3.10 --version` and `ffmpeg -version`.

## 2. Install (one time)

**Linux / Mac:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows:**
```bat
setup.bat
```

If you have an NVIDIA GPU, replace the CPU torch install in `setup.sh`/`.bat`
with the CUDA build from https://pytorch.org (select torch 2.1.0, CUDA 11.8/12.1).

The first run downloads the model (~3 GB) from Hugging Face into your cache.

## 3. Use it

### Option A — command line
```bash
source venv/bin/activate
python restyle.py my_song.mp3 "house remix, 120 BPM, four on the floor, warm bass" output.mp3 --duration 30
```
`--duration` is seconds (10–60). Use `--dtype float16` if you are low on RAM.

### Option B — server for the phone app (recommended)
```bash
chmod +x start_server.sh
./start_server.sh 0.0.0.0 8002
```
You'll see `AI Restyle engine: http://0.0.0.0:8002`.

Then point the phone app at it. On the **machine running the app backend**, set:
```bash
export AI_ENGINE_URL=http://<LAPTOP_LAN_IP>:8002
```
Example: `http://192.168.1.20:8002`. Find your laptop's LAN IP with `ip addr`
(Linux/Mac) or `ipconfig` (Windows). The phone and laptop must be on the same Wi-Fi.

Restart the app backend after setting it. The app's **AI Restyle** card will show
"🟢 Engine connected."

## 4. Style prompt tips

Describe genre + tempo + instruments + mood:
- `nightcore EDM remix, 150 BPM, pitched up, bright synths`
- `slowed reverb, dreamy trap, 808 bass, hazy`
- `dark techno remix, 130 BPM, rolling bass, minimal drums`
- `future bass, 140 BPM, supersaw chords, festival drop`

The model keeps the *melody* of your song and changes everything around it.

## Files
- `restyle.py` — engine (CLI + HTTP server)
- `setup.sh` / `setup.bat` — one-time install
- `start_server.sh` / `start_server.bat` — launch server
- `requirements.txt` — pinned deps

## Troubleshooting
- **`MemoryError` / killed process** → use `--dtype float16`, shorten `--duration`,
  or close other apps. A GPU is strongly recommended.
- **"xformers not installed"** → the script auto-creates a stub on CPU; ignore it.
- **Model download slow** → set `HF_TOKEN` for higher rate limits, or wait once.
