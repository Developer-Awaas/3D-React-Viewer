@echo off
REM ====================================================================
REM  TF2DeepFloorplan — one-time setup for the COMMERCIAL ML plan reader
REM  (the cascade's 2D->3D fallback). Run from the repo root.
REM ====================================================================
setlocal
cd /d "%~dp0server"
call venv\Scripts\activate.bat

echo === 1/4  Install TensorFlow (CPU build is fine for this model) ===
pip install tensorflow gdown

echo === 2/4  Clone the model repo (code + docs) ===
if not exist TF2DeepFloorplan (git clone https://github.com/zcemycl/TF2DeepFloorplan)

echo === 3/4  Download the pretrained TFLite weights ===
echo The weights live on Google Drive (link in TF2DeepFloorplan\README.md,
echo section "Pretrained model"). Download the .tflite file and save it as:
echo    %CD%\TF2DeepFloorplan\model.tflite
echo (tflite is recommended: it loads with no extra code.)
echo.
echo Trying automatic download via gdown (may fail if the link changed)...
python -c "import gdown,os;os.path.exists('TF2DeepFloorplan/model.tflite') or gdown.download(id=os.getenv('TF2FP_GDRIVE_ID',''), output='TF2DeepFloorplan/model.tflite')" 2>nul

echo === 4/4  Verify ===
if exist TF2DeepFloorplan\model.tflite (
  python verify_tf2fp.py TF2DeepFloorplan\model.tflite
) else (
  echo model.tflite not found yet - download it manually (step 3), then run:
  echo    python verify_tf2fp.py TF2DeepFloorplan\model.tflite
)

echo.
echo When verify passes, enable it in server\.env:
echo    ML_READER=tf2
echo    TF2FP_MODEL=%CD%\TF2DeepFloorplan\model.tflite
echo and restart the backend. The cascade will use it automatically on plans
echo the vector parser can't read (and on photos/scans).
pause
