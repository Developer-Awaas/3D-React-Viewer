@echo off
REM ====================================================================
REM  Drishti "Visualize" (Beta) — one-time local GPU setup (RTX 3060)
REM  Run this by DOUBLE-CLICKING it, or from a terminal in the repo root.
REM ====================================================================
setlocal
cd /d "%~dp0server"

echo.
echo === 1/5  Create / activate the Python venv ===
if not exist venv (python -m venv venv)
call venv\Scripts\activate.bat

echo.
echo === 2/5  Install CUDA-enabled PyTorch (cu121 build) ===
python -m pip install --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

echo.
echo === 3/5  Install the diffusers render stack ===
pip install -r requirements.txt
pip install -r requirements-visualize.txt

echo.
echo === 4/5  Verify the GPU is visible to PyTorch ===
python -c "import torch;print('CUDA available:',torch.cuda.is_available());print('GPU:',torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE - fix the driver / torch build')"

echo.
echo === 5/5  Done. ===
echo Models download automatically on the FIRST render:
echo   * SDXL base + canny ControlNet  (~7 GB, public)
echo   * Stable Video Diffusion XT     (~5 GB, GATED - see note below)
echo.
echo SVD is license-gated on Hugging Face. Once, run:
echo   huggingface-cli login
echo and accept the license at:
echo   https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt
echo.
echo Then start the backend with:  run_backend_gpu.bat
echo.
pause
