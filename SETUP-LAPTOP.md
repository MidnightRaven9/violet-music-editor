# Setting up Violet Audio Studio on your laptop

Everything runs on the laptop: the web app, the 24 remix effects, and (optionally)
the AI restyle engine. Your phone connects to it over Wi-Fi.

---

## Step 0 — Install the system tools

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg rubberband-cli
```

**macOS (Homebrew):**
```bash
brew install python@3.10 ffmpeg rubberband
```

**Windows:** install Python 3.10 and FFmpeg from their official sites, add FFmpeg
to PATH. RubberBand Windows builds are on the RubberBand website.

Check they work:
```bash
python3 --version      # 3.10 or newer recommended
ffmpeg -version
rubberband --version
```

---

## Step 1 — Get the code

```bash
git clone https://github.com/MidnightRaven9/violet-music-editor.git
cd violet-music-editor
```

---

## Step 2 — Set up the main app (the 24 remix effects + web UI)

**Linux / Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

**Windows:**
```bat
py -3.10 -m venv venv
venv\Scripts\activate
pip install -r backend/requirements.txt
```

Run it:
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
- `--host 0.0.0.0` lets your phone reach it on the same Wi-Fi.
- Open <http://localhost:8000> on the laptop to use the app there.

Find the laptop's LAN IP:
- Linux/Mac: `ip addr` or `ifconfig` (look for `192.168.x.x` or `10.x.x.x`)
- Windows: `ipconfig` (IPv4 Address)

On your phone, open `http://<LAPTOP_IP>:8000` — for example `http://192.168.1.20:8000`.
If your phone is on mobile data instead of Wi-Fi, it won't connect; use Wi-Fi.

---

## Step 3 (optional) — Set up the AI Restyle engine

This is the real AI remix that keeps your song's melody. It needs a decent GPU
(8 GB+ VRAM) or 12 GB+ RAM, and Python 3.10.

**Linux / Mac:**
```bash
cd laptop
chmod +x setup.sh
./setup.sh
```

**Windows:**
```bat
cd laptop
setup.bat
```

First run downloads ~3 GB of model files from Hugging Face.

Start the engine:
```bash
cd laptop
./start_server.sh 0.0.0.0 8002
```
(Windows: `start_server.bat 0.0.0.0 8002`)

Now connect the app to the engine. **Restart the app from Step 2** with the
engine URL set:

**Linux / Mac:**
```bash
export AI_ENGINE_URL=http://<LAPTOP_IP>:8002
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
**Windows (PowerShell):**
```powershell
$env:AI_ENGINE_URL="http://<LAPTOP_IP>:8002"
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open the app and the **AI Restyle** section will say "Engine connected."
Since both run on the same laptop, `<LAPTOP_IP>` can also be `127.0.0.1`.

---

## Step 4 — Use the app

1. Open `http://localhost:8000` (laptop) or `http://<LAPTOP_IP>:8000` (phone).
2. Upload a song.
3. Pick an effect, trim if you like, then **Render & download**.
4. Or use **AI Restyle** with a style prompt for a melody-preserving AI remix.

---

## Troubleshooting

- **`ModuleNotFoundError`** → make sure the venv is active (`source venv/bin/activate`).
- **`rubberband: command not found`** when rendering → install it (Step 0) and
  restart the app. Nightcore/speed effects need it.
- **Phone can't connect** → same Wi-Fi; check firewall allows port 8000;
  use the laptop's LAN IP, not `localhost`, on the phone.
- **AI model `MemoryError`** → use `--dtype float16` in `start_server.sh`, or
  use a GPU. See `laptop/README.md`.
- **Port already in use** → change `--port` to e.g. 8010.

---

## Files

- `backend/` — FastAPI server + audio engine (24 effects, trim, mastering)
- `public/` — the web UI
- `laptop/` — the optional AI restyle engine (MusicGen)
- `android-project/` — optional Android APK shell
