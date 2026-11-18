#!/usr/bin/env bash
# One-time setup for the Violet AI Restyle engine on a Linux/Mac laptop.
# Requires Python 3.10 and FFmpeg.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> creating venv (Python 3.10)"
python3.10 -m venv venv
source venv/bin/activate

echo "==> installing PyTorch 2.1 (CPU build)"
pip install --index-url https://download.pytorch.org/whl/cpu torch==2.1.0 torchaudio==2.1.0

echo "==> installing AudioCraft and runtime deps"
pip install audiocraft==1.3.0 av==11.0.0 numpy soundfile fastapi uvicorn python-multipart

echo "==> ready. Run: ./start_server.sh"
