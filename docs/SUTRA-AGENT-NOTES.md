# Sutra agent notes — 3D-React-Viewer (Drishti)

Written for Sutra's automatic build/test/review pipeline. This file is new and
additive — it does not replace or override `CLAUDE.md` / `PLAN-READING-RULES.md`
/ `DRISHTI-WORKING-AGREEMENT.md` at the repo root, which are the team's own
working rules and carry their own, much more detailed, standing instructions.
Read those first if you are about to touch the parser (`server/pdf_vector.py`
and friends) — they record months of measured, ruled-on decisions and a long
list of mistakes already made and not to repeat.

## What this app does

Drishti turns a CAD floor-plan PDF into a walkable 3D building: it reads walls,
doors, windows, rooms and furniture from the PDF's vector geometry (no ML
required for the main path), then builds a 3D scene, an RERA-style area
statement, a Vastu report and a rough ₹ cost estimate. India-first proptech,
founders Saswat & Amit.

## Stack

- Frontend: React 18 + TypeScript + Vite + react-three-fiber (three.js) +
  Tailwind. Single-page app, no router.
- Backend: FastAPI (`server/main.py`), pure-Python/OpenCV/Shapely vector
  parser (`server/pdf_vector.py`), PyMuPDF for PDF ingestion, trimesh for GLB
  export, optional tesseract OCR, optional CubiCasa/TF2DeepFloorplan ML
  fallback for photo/scan input, optional SDXL+ControlNet for photoreal
  renders (GPU only).

## Install / run / check

```bash
# frontend
npm install && npm run dev          # http://localhost:5173

# backend
cd server && python -m venv venv && source venv/bin/activate  # (venv\Scripts\activate on Windows)
pip install -r requirements.txt
cp .env.example .env                # fill in only what you need; see below
uvicorn main:app --port 8000        # health check: GET /health
```

Checks:

```bash
cd server && pytest                 # engine + API tests, server/tests/ (~520 tests)
npm run test                        # frontend math tests (vitest, 32 tests)
npm run build                       # tsc typecheck + vite build
python server/batch_eval.py plans   # corpus scorecard (generalization across sample plans)
```

None of the above need a GPU, the internet, or a live database for the core
path. Tesseract (OCR) is installed via `brew install tesseract` on the dev
Mac and some room-labeling tests depend on it being present; if it is
missing, `DRISHTI_OCR=0` reproduces the pre-OCR baseline.

## Folder map

- `src/` — frontend (React + r3f viewer, upload flow, API client in `src/api/`).
- `server/` — FastAPI app + the parser. `main.py` is the API surface;
  `pdf_vector.py` is the core engine; `area_statement.py`/`area_compare.py`
  (R-8), `room_dims.py` (R-2), `opening_schedule.py`, `plan_doctor.py`,
  `scene_to_glb.py`, `visualize.py` round out the pipeline.
- `server/tests/` — pytest suite (one file per feature/fix).
- `plans/` — sample plan PDFs + `ground_truth.json` (the measured, ruled-on
  truth for the "golden" corpus — never hand-edit without an authorised
  re-baseline; see `CLAUDE.md` §0.1).
- `docs/` — design docs, handoffs, deploy notes. `docs/HANDOFF-TO-SCORECARD.md`
  is the running log between the parser work and an independent scorecard
  check; `docs/SUPABASE.md` covers the optional parse-logging DB.
- `overlays/` — PNG exports used to visually verify geometry changes.

## Golden-sheet / scorecard check

`python server/batch_eval.py plans` runs the parser over every PDF in `plans/`
and reports the standard instrument set (footprint, R-2/R-8, doors, M-1, etc.)
against `plans/ground_truth.json`. `cd server && pytest` additionally pins a
"golden corpus" of exact numbers in `test_corpus_golden.py` and
`test_area_compare.py` — these are deliberately strict ratchets; per the
working agreement, a moved golden number must be explained in feet or rupees
before it is accepted, never silently re-baselined.

## Rules

- **Domain: AWAAS only.** This is the Drishti/AWAAS product; do not repurpose
  it or mix in unrelated work.
- **Test data only.** `plans/` already contains sample/test PDFs — use those.
  Never point the app at a live/production Supabase project, and never upload
  real customer floor plans through this pipeline.
- **Never commit secrets.** `SUPABASE_KEY` (service-role), `ANTHROPIC_API_KEY`
  and `REVIEW_TOKEN` are the sensitive env vars this app knows about — they
  belong in a local `.env` (or the Sutra test env file), never in code or a
  commit. Supabase logging is OFF by default and stays off unless both
  `SUPABASE_URL` and `SUPABASE_KEY` are explicitly set.
- **Never touch production.** There is no database migration in this repo
  (Supabase logging is append-only telemetry, not app state); if it is ever
  enabled for a test run, point it at a disposable Supabase project, never the
  real one.
- **Do not edit `CLAUDE.md`, `PLAN-READING-RULES.md`, or
  `DRISHTI-WORKING-AGREEMENT.md`.** They are the team's own working record;
  this file is the Sutra-specific supplement.
