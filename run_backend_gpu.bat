@echo off
REM Start the Drishti backend on your GPU machine with Visualize enabled.
setlocal
cd /d "%~dp0server"
call venv\Scripts\activate.bat

REM local = run diffusers on this machine's GPU. Set to "fal" for hosted prod.
set RENDER_BACKEND=local
REM one heavy job at a time so CubiCasa + SDXL don't fight over 12 GB
set MAX_CONCURRENT_INFER=1
set MAX_CONCURRENT_RENDER=1
REM let the Vite dev server (5173) call this API
set ALLOWED_ORIGINS=http://localhost:5173

echo Backend starting on http://localhost:8000  (Visualize backend: %RENDER_BACKEND%)
uvicorn main:app --host 0.0.0.0 --port 8000
