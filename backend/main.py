"""FastAPI backend for the EDM Remix Maker PWA."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Callable

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = BASE_DIR / "public"
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(BASE_DIR / "backend"))
from audio import process_file  # noqa: E402

app = FastAPI(title="EDM Remix Maker")

# In-memory job store: job_id -> {status, progress, message, effect, download_url, error}
JOBS: dict[str, dict] = {}


def _make_cb(job_id: str) -> Callable[[int, str], None]:
    def cb(pct: int, msg: str) -> None:
        if job_id in JOBS:
            JOBS[job_id]["progress"] = pct
            JOBS[job_id]["message"] = msg
    return cb


def _process_job(
    job_id: str,
    input_path: str,
    output_path: str,
    effect: str,
    rate: float,
    pitch: float,
    reverb: float,
) -> None:
    try:
        JOBS[job_id]["status"] = "processing"
        process_file(
            input_path, output_path, effect, rate, pitch, reverb,
            _make_cb(job_id),
        )
        JOBS[job_id]["status"] = "done"
        JOBS[job_id]["progress"] = 100
        JOBS[job_id]["message"] = "Remix ready!"
        JOBS[job_id]["download_url"] = f"/api/download/{job_id}"
    except Exception as exc:  # noqa: BLE001
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["message"] = str(exc)
        JOBS[job_id]["error"] = str(exc)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")


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
    upload_path = UPLOAD_DIR / f"{job_id}.mp3"
    content = await file.read()
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
        "custom": {"label": "Custom Remix", "rate": 1.0, "pitch": 0, "reverb": 0},
    }


# Serve static assets (JS/CSS/manifest/sw) under /static
app.mount("/static", StaticFiles(directory=str(PUBLIC_DIR)), name="static")
