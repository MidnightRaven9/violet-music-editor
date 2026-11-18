@echo off
REM One-time setup for the Violet AI Restyle engine on Windows.
REM Requires Python 3.10 and FFmpeg on PATH.
cd /d "%~dp0"

echo ==^> creating venv (Python 3.10)
py -3.10 -m venv venv
call venv\Scripts\activate.bat

echo ==^> installing PyTorch 2.1 (CPU build)
pip install torch==2.1.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cpu

echo ==^> installing AudioCraft and runtime deps
pip install audiocraft==1.3.0 av==11.0.0 numpy soundfile fastapi uvicorn python-multipart

echo ==^> ready. Run start_server.bat
pause
