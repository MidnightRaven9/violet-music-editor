"""FastAPI backend for the EDM Remix Maker PWA."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = BASE_DIR / "public"
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

app = FastAPI(title="EDM Remix Maker")

# In-memory job store: job_id -> {status, progress, message, effect, download_url, error}
JOBS: dict[str, dict] = {}

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
PROCESS_TIMEOUT_SECONDS = 600  # 10 minutes


def _process_job(
    job_id: str,
    input_path: str,
    output_path: str,
    effect: str,
    rate: float,
    pitch: float,
    reverb: float,
) -> None:
    """Run audio processing in an isolated subprocess.

    This keeps the API server alive even if the worker is OOM-killed or crashes.
    """
    JOBS[job_id]["status"] = "processing"
    JOBS[job_id]["message"] = "Starting audio engine..."

    worker_script = str(BASE_DIR / "backend" / "worker.py")
    cmd = [
        sys.executable, worker_script,
        input_path, output_path, effect,
        str(rate), str(pitch), str(reverb),
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(BASE_DIR),
        )

        # Stream progress updates from worker stdout
        if proc.stdout:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    JOBS[job_id]["progress"] = data.get("progress", 0)
                    JOBS[job_id]["message"] = data.get("message", "Processing...")
                except json.JSONDecodeError:
                    pass

        try:
            proc.wait(timeout=PROCESS_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError("Processing timed out (audio too long or server overloaded)")

        if proc.returncode == 0:
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["progress"] = 100
            JOBS[job_id]["message"] = "Remix ready!"
            JOBS[job_id]["download_url"] = f"/api/download/{job_id}"
        else:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(stderr.strip() or "Audio processing failed")
    except Exception as exc:  # noqa: BLE001
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["message"] = str(exc)
        JOBS[job_id]["error"] = str(exc)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    effect: str = Form("nightcore"),
    rate: float = Form(1.3),
    pitch: float = Form(7.0),
    reverb: float = Form(0.3),
):
    job_id = str(uuid.uuid4())
    content = await file.read()

    if len(content) > MAX_UPLOAD_BYTES:
        return {
            "job_id": None,
            "error": f"File too large ({len(content) / 1024 / 1024:.1f} MB). Max is {MAX_UPLOAD_BYTES / 1024 / 1024:.0f} MB.",
        }

    upload_path = UPLOAD_DIR / f"{job_id}.mp3"
    upload_path.write_bytes(content)

    JOBS[job_id] = {
        "status": "uploaded",
        "progress": 0,
        "message": "File uploaded",
        "effect": effect,
        "download_url": None,
        "error": None,
    }

    output_path = PROCESSED_DIR / f"{job_id}.mp3"
    background_tasks.add_task(
        _process_job, job_id, str(upload_path), str(output_path),
        effect, rate, pitch, reverb,
    )
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOBS[job_id]


@app.get("/api/download/{job_id}")
def download(job_id: str):
    job = JOBS.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(status_code=404, detail="Remix not ready")
    path = PROCESSED_DIR / f"{job_id}.mp3"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Remix file not found")
    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=f"remix_{job_id[:8]}.mp3",
    )


@app.get("/api/effects")
def list_effects():
    return {
        "nightcore": {"label": "Nightcore", "rate": 1.3, "pitch": 7, "reverb": 0},
        "slowed_reverb": {"label": "Slowed + Reverb", "rate": 0.8, "pitch": 0, "reverb": 0.4},
        "bass_boost": {"label": "Bass Boost", "rate": 1.0, "pitch": 0, "reverb": 0},
        "echo": {"label": "Echo / Delay", "rate": 1.0, "pitch": 0, "reverb": 0},
        "reverb": {"label": "Reverb", "rate": 1.0, "pitch": 0, "reverb": 0.35},
        "chroma": {"label": "Chorus/Flange", "rate": 1.0, "pitch": 0, "reverb": 0.1},
        "distortion": {"label": "Distortion", "rate": 1.0, "pitch": 0, "reverb": 0.2},
        "phaser": {"label": "Phaser", "rate": 1.0, "pitch": 0, "reverb": 0.1},
        "bitcrush": {"label": "Bitcrush", "rate": 1.0, "pitch": 0, "reverb": 0.0},
        "glitchcore": {"label": "Glitchcore", "rate": 1.4, "pitch": 12, "reverb": 0.3},
        "house": {"label": "House", "rate": 1.0, "pitch": 0, "reverb": 0.12},
        "techno": {"label": "Techno", "rate": 1.05, "pitch": 0, "reverb": 0.08},
        "trance": {"label": "Trance", "rate": 1.05, "pitch": 2, "reverb": 0.3},
        "dubstep": {"label": "Dubstep", "rate": 0.95, "pitch": 0, "reverb": 0.05},
        "trap": {"label": "Trap", "rate": 0.9, "pitch": -1, "reverb": 0.08},
        "drum_and_bass": {"label": "Drum & Bass", "rate": 1.4, "pitch": 0, "reverb": 0.05},
        "future_bass": {"label": "Future Bass", "rate": 1.0, "pitch": 2, "reverb": 0.25},
        "custom": {"label": "Custom Remix", "rate": 1.0, "pitch": 0, "reverb": 0},
    }


# Serve static assets (JS/CSS/manifest/sw) under /static
app.mount("/static", StaticFiles(directory=str(PUBLIC_DIR)), name="static")
