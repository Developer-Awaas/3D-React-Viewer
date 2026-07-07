# Drishti Perception Service (Step 2)

Wraps the CubiCasa model behind an API. Your website sends a floor-plan image to
`/perceive` and gets back what the model detected (rooms, doors/windows + preview
images). This is the "kitchen" from the plan.

> Step 2 returns the DETECTION only. Turning it into 3D geometry (scene.json) is
> Step 3; real-world scale is Step 4.

## What you need
- Python 3.10+ installed
- Git installed
- A machine with an NVIDIA GPU is best (fast). CPU works too, just slower.

## Setup (Windows - do this once)
Open a terminal in this `server/` folder and run:

```bat
python -m venv venv
venv\Scripts\activate
pip install gdown

:: 1) get the CubiCasa model code + trained weights
git clone https://github.com/CubiCasa/CubiCasa5k.git
gdown 1gRB7ez1e4H7a9Y09lLqRuna0luZO5VRK -O CubiCasa5k/model_best_val_loss_var.pkl

:: 2) install python packages
pip install -r requirements.txt

:: 3) make your config file
copy .env.example .env
```

(On Mac/Linux you can instead just run `bash setup.sh`.)

### GPU note
The plain `pip install torch` gives a CPU build. If you have an NVIDIA GPU,
install the CUDA build for a big speed-up, e.g.:
`pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121`

## Run it
```bat
uvicorn main:app --reload --port 8000
```
Wait for the line: **CubiCasa model loaded and ready.**

## Test it (two easy ways)
1. **Browser:** open http://localhost:8000/docs  -> open `POST /perceive` ->
   "Try it out" -> upload a plan image -> Execute. You'll see the JSON reply with
   `rooms_found`, `icons_found`, and two base64 preview images.
2. **Health check:** open http://localhost:8000/health  -> should show
   `{"ok": true, "model_loaded": true}`.

## What the reply looks like
```json
{
  "device": "cuda",
  "width": 1024, "height": 768,
  "rooms_found": ["Wall", "Bed Room", "Bath", "Living Room"],
  "icons_found": ["Door", "Window", "Toilet", "Sink"],
  "rooms_overlay_png_base64": "iVBORw0KG..._(preview image)_",
  "icons_overlay_png_base64": "iVBORw0KG..._(preview image)_"
}
```

## Files
- `main.py` - the API (endpoints /health and /perceive)
- `perception.py` - loads the model + runs inference (same as the Colab)
- `requirements.txt` - python packages
- `.env.example` - settings (copy to `.env`)
- `setup.sh` - one-command setup for Mac/Linux
