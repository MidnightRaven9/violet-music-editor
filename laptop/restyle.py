#!/usr/bin/env python3
"""
Violet Music Editor — AI Restyle engine (for a laptop/desktop with enough RAM or a GPU).

Uses Meta's MusicGen *melody* model: it listens to your uploaded song's melody and
re-generates it in a new style (genre, instruments, tempo feel) from a text prompt.
This is a true AI remix that keeps your song's melody — unlike DSP effects.

Two ways to run:
  CLI:    python restyle.py input.mp3 "house remix, 120 BPM" output.mp3 --duration 30
  Server: python restyle.py --serve --port 8002      (the app talks to this over LAN)

Requirements: Python 3.10, 12 GB+ RAM (or an 8 GB+ NVIDIA GPU). See README.md.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Keep CPU threads / BLAS sane so memory stays predictable.
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import numpy as np
import soundfile as sf
import torch
import torchaudio
from audiocraft.data.audio import audio_write
from audiocraft.models import MusicGen

MODEL_NAME = "melody"          # melody-conditioned MusicGen (1.5B)
MODEL_SR = 32_000              # melody model expects 32 kHz input
MAX_DURATION = 60              # cap generation length (seconds)
_model = None                  # cached in server mode


def _install_xformers_stub_if_needed() -> None:
    """AudioCraft imports xformers at load time but defaults to the torch
    attention backend on CPU. If xformers is missing, create a tiny stub so
    the import succeeds without installing the heavy CUDA-only package.
    """
    try:
        import xformers  # noqa: F401
        return
    except ImportError:
        pass
    import site
    site_dir = site.getsitepackages()[0]
    stub = Path(site_dir) / "xformers"
    stub.mkdir(exist_ok=True)
    (stub / "__init__.py").write_text(
        "from . import ops\n__version__ = '0.0.0-stub'\n", encoding="utf-8"
    )
    (stub / "ops.py").write_text(
        "def memory_efficient_attention(*a, **k):\n"
        "    raise NotImplementedError('torch backend in use')\n"
        "class LowerTriangularMask:\n"
        "    def __init__(self, *a, **k):\n        pass\n",
        encoding="utf-8",
    )
    print("[setup] created xformers stub (torch attention backend will be used)")


def load_model(device: str | None = None, dtype: torch.dtype = torch.float32):
    """Load (and cache) the melody model."""
    global _model
    if _model is not None:
        return _model
    _install_xformers_stub_if_needed()
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
    print(f"[model] loading '{MODEL_NAME}' on {device} ({dtype})...", flush=True)
    model = MusicGen.get_pretrained(MODEL_NAME, device=device)
    # Cast to requested dtype to cut memory on CPU.
    model.lm.to(dtype)
    if getattr(model, "compression_model", None) is not None:
        model.compression_model.to(dtype)
    model.device = device
    _model = model
    print("[model] ready.", flush=True)
    return model


def restyle(
    input_path: str,
    style: str,
    output_path: str,
    duration: float | None = None,
    device: str | None = None,
    dtype_name: str = "float32",
    strength: float = 1.0,
) -> str:
    """Restyle an uploaded song while keeping its melody."""
    dtype = torch.float16 if dtype_name == "float16" else torch.float32
    model = load_model(device=device, dtype=dtype)

    # Determine length from the source (capped) unless explicitly given.
    if duration is None:
        info = torchaudio.info(input_path)
        src_duration = info.num_frames / info.sample_rate
        duration = min(max(5.0, src_duration), MAX_DURATION)

    # Load melody audio -> 32 kHz mono -> [1, 1, T]
    melody, sr = torchaudio.load(input_path)
    if melody.shape[0] > 1:
        melody = melody.mean(dim=0, keepdim=True)
    if sr != MODEL_SR:
        melody = torchaudio.functional.resample(melody, sr, MODEL_SR)
    melody = melody.unsqueeze(0)  # [batch, channels, samples]

    model.set_generation_params(duration=duration, use_sampling=True, top_k=250)
    print(f"[generate] style={style!r} duration={duration:.1f}s strength={strength}", flush=True)
    t0 = time.time()

    try:
        wav = model.generate(
            [style],
            melody=melody,
            melody_strength=strength,
            progress=True,
        )
    except TypeError:
        # Older AudioCraft versions don't expose melody_strength.
        wav = model.generate([style], melody=melody, progress=True)

    print(f"[generate] done in {time.time() - t0:.1f}s", flush=True)

    # Write WAV then encode MP3 with FFmpeg (loudness-normalized).
    with tempfile.TemporaryDirectory() as td:
        wav_path = str(Path(td) / "restyle.wav")
        audio_write(
            wav_path,
            wav[0].detach().cpu().float(),
            model.sample_rate,
            strategy="loudness",
            loudness_headroom_db=14,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path, "-c:a", "libmp3lame", "-q:a", "0", output_path],
            check=True,
            capture_output=True,
        )
    return output_path


def serve(host: str, port: int, dtype_name: str) -> None:
    """Expose a small HTTP API so the PWA backend can call this engine."""
    from fastapi import FastAPI, File, Form, UploadFile
    from fastapi.responses import FileResponse, JSONResponse
    import uvicorn

    app = FastAPI(title="Violet AI Restyle Engine")

    @app.get("/health")
    def health():
        return {"status": "ok", "model": MODEL_NAME, "loaded": _model is not None}

    @app.post("/restyle")
    async def api_restyle(
        file: UploadFile = File(...),
        style: str = Form("house remix, 120 BPM, four on the floor"),
        duration: float = Form(30),
        strength: float = Form(1.0),
    ):
        with tempfile.TemporaryDirectory() as td:
            inp = str(Path(td) / "input.mp3")
            out = str(Path(td) / "output.mp3")
            with open(inp, "wb") as f:
                f.write(await file.read())
            try:
                restyle(inp, style, out, duration=duration, dtype_name=dtype_name, strength=strength)
            except Exception as exc:  # noqa: BLE001
                return JSONResponse(status_code=500, content={"error": str(exc)})
            data = Path(out).read_bytes()
        from fastapi.responses import Response
        return Response(content=data, media_type="audio/mpeg")

    print(f"[server] listening on http://{host}:{port}", flush=True)
    uvicorn.run(app, host=host, port=port)


def main() -> None:
    p = argparse.ArgumentParser(description="Violet AI Restyle engine")
    p.add_argument("input", nargs="?", help="input audio file")
    p.add_argument("style", nargs="?", help="style prompt")
    p.add_argument("output", nargs="?", help="output mp3 file")
    p.add_argument("--duration", type=float, default=None, help="generation length in seconds")
    p.add_argument("--dtype", choices=["float32", "float16"], default="float32")
    p.add_argument("--device", default=None, help="cpu or cuda (auto-detected)")
    p.add_argument("--strength", type=float, default=1.0)
    p.add_argument("--serve", action="store_true", help="run as HTTP server")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8002)
    args = p.parse_args()

    if args.serve:
        # Preload so the first request isn't slow.
        load_model(device=args.device, dtype=torch.float16 if args.dtype == "float16" else torch.float32)
        serve(args.host, args.port, args.dtype)
        return

    if not (args.input and args.style and args.output):
        p.error("provide input, style, and output (or use --serve)")

    restyle(
        args.input, args.style, args.output,
        duration=args.duration, device=args.device,
        dtype_name=args.dtype, strength=args.strength,
    )
    print(f"[done] wrote {args.output}")


if __name__ == "__main__":
    main()
