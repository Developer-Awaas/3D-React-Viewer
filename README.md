# Drishti — every plan holds a building within

**CAD floor-plan → walkable 3D building → photoreal renders + India-first
property intelligence (RERA areas, Vastu, cost), in the browser.**

Upload an architect's plan (CAD-exported PDF, DXF/DWG, or photo*). The backend
reads the drawing like an architect — walls, doors, windows, rooms, furniture —
and returns a 3D building you can orbit and walk inside, plus an area
statement, Vastu report and cost estimate. A GPU box can then repaint any view
photoreal with SDXL + ControlNet, geometry-locked to the real plan.

## How it reads a plan (the pipeline)
`INGEST → READ (vector-first cascade, ML fallback) → ANALYZE (scored) →
GENERATE (3D / reports / photoreal) → LOG (corpus) → REVIEW → IMPROVE`

- **Vector engine** (`server/pdf_vector.py`) — exact, no ML: layer parsing,
  brick-hatch wall recovery, geometric door detection, schedule-tag openings
  (D1/W/V), room-dimension + dimension-text scale voting, envelope sealing,
  room typing from labels, furniture staging.
- **ML fallback** — when the vector read fails health checks (or input is a
  photo/scan): CubiCasa (demo) or TF2DeepFloorplan (`ML_READER=tf2`,
  commercial-viable). Same interface, cascade picks the better scene.
- **Analysis** — every parse returns `analysis` (0-100 quality score,
  needs_review), `area_statement` (RERA carpet/built-up/super + Excel export),
  `vastu` (9-zone verdicts, `?north_deg=`), `boq` (₹ estimate).
- **Visualize (beta)** — SDXL + multi-ControlNet (depth + segmentation rendered
  from the scene's own G-buffer) on a local GPU (`RENDER_BACKEND=local`).

## Run it
```bash
# frontend
npm install && npm run dev            # http://localhost:5173

# backend (Windows helper: run_backend_gpu.bat does all of this)
cd server && python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --port 8000
```
Optional extras: `setup_visualize.bat` (SDXL render stack + models),
`setup_tf2fp.bat` (TF2DeepFloorplan reader), `docs/SUPABASE.md` (parse logging
+ ML data corpus), `python server/fetch_models.py` (pre-download weights).

## Tests
```bash
cd server && pytest                   # engine + API (golden corpus pins)
npm test                              # frontend math (vitest)
python server/batch_eval.py plans     # corpus scorecard (generalization)
```

## Key docs
`docs/PIPELINE.md` (architecture) · `docs/GENERATIVE_IDEATION.md` (roadmap) ·
`docs/DEPLOY.md` + `render.yaml`/`vercel.json` (hosting) · `docs/TF2_SETUP.md` ·
`docs/SUPABASE.md`

## Tech
React 18 · TypeScript · Vite · three.js / react-three-fiber · Tailwind ·
FastAPI · PyMuPDF · OpenCV · trimesh · diffusers (SDXL + ControlNet) ·
Supabase (logging/corpus)

*Photo/scan reading uses CubiCasa5k — **CC BY-NC (non-commercial)**: demo only.
Ship TF2DeepFloorplan for paid use. SDXL/ControlNet are OpenRAIL.

— Amit & Saswat · awaas.ai.dev@gmail.com
