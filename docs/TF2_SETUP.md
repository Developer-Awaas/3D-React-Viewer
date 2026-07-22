# TF2DeepFloorplan — commercial ML reader setup (GPU box)

This is the **shippable** ML fallback for the cascade (GPL-3.0; server-side SaaS
use is generally fine — verify with a lawyer before charging). It reads a
rasterized plan into walls/openings, reusing Drishti's own vectorizer.

## Install (once)
1. Install TensorFlow (CUDA build) into the server venv:
   ```
   pip install tensorflow
   ```
2. Get the model + pretrained weights:
   ```
   git clone https://github.com/zcemycl/TF2DeepFloorplan
   ```
   Download its pretrained weights (Google Drive link in that repo's README) and
   note the SavedModel / weights folder path.
3. Point the backend at it and select the reader (in `server/.env` or the shell):
   ```
   ML_READER=tf2
   TF2FP_MODEL=D:\path\to\TF2DeepFloorplan\weights   # SavedModel dir
   ```
4. Restart the backend.

## Verify
- `GET /health` → the ML path is active.
- Upload a plan that the vector parser flags (e.g. a photo or a messy CAD); the
  returned scene's `meta.reader` should read `ml_fallback`.

## Class order (important)
The adapter assumes the room-boundary head is `0=background, 1=opening (door/
window), 2=wall`. If the model card differs, set:
```
TF2FP_WALL_CLASS=2
TF2FP_OPENING_CLASS=1
```
Confirm by rendering the wall mask on one known plan.

## Notes
- Only ONE ML reader runs at a time (`ML_READER=cubicasa` or `tf2`) — they do the
  same job; you don't run both. Use CubiCasa for demos, TF2 for the paid product.
- The cascade is unchanged: vector-first, and this model only runs when the
  vector result is unhealthy, so it can only improve output.
- Inference quality depends on the model; tune `TF2FP_INPUT` (default 512) if the
  masks look coarse.
