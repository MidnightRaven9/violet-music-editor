@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
set HOST=%1
if "%HOST%"=="" set HOST=0.0.0.0
set PORT=%2
if "%PORT%"=="" set PORT=8002
echo AI Restyle engine: http://%HOST%:%PORT%
python restyle.py --serve --host %HOST% --port %PORT% --dtype float32
pause
