# Drishti 3D - Master Project Context

> Single source of truth for the whole project. Paste/read this at the start of any
> session (or share with Saswat) to instantly know where we are. Updated: 2026-07-02.

---

## 1. Vision - what we're building
A product where a user uploads a 2D floor plan and gets an explorable **3D model**
(+ a walkthrough video). "Drishti" = the visual engine for AWAAS.

Pipeline:  **image -> perception (AI) -> scene.json (geometry) -> 3D build -> viewer + video**,
with a **manual correction** step as the always-available safety net.

---

## 2. Architecture & components
It is a **client-server web app** - two programs that talk over HTTP:

- **Frontend ("the website")** - `3D React Viewer` (React + Three.js/R3F). Runs in the
  browser. What the user sees. *Not yet wired to the backend.*
- **Backend ("the server/brain")** - `server/` (FastAPI, Python). Runs the CubiCasa AI
  model. Currently runs on the local PC at `localhost:8000`; later on a cloud GPU host.
- **AI model** - CubiCasa5k, lives inside the backend (`server/CubiCasa5k/`).
- **Geometry schema** - one canonical `scene.json` (feet, z-up) = the shared language.

```
USER (browser)                         BACKEND (server)
React + Three.js   --- image --->       FastAPI + CubiCasa
(3D React Viewer)  <--- data ----       detect -> scene.json -> 3D
```

---

## 3. Status - DONE
- Validated CubiCasa on real plans (Colab) - good results (walls/doors/windows/fixtures).
- **Step 2 - Perception backend**: `/perceive` loads the model once and returns detected
  rooms/icons + preview images. Fixed all load crashes (backbone cwd + recursive weights).
- **/test page**: `localhost:8000/test` shows the 3 images (plan+rooms+icons) like Colab.
- **Step A - Wall vectorizer** (`server/walls.py`): wall pixels -> clean line-segments.
  Unit-tested (merges parallels, keeps doorways, drops fragments).
- **Phase 0 - Geometry merge**: adopted the drishti reference schema as canonical
  (`docs/SCENE_SCHEMA.md`), migrated example (`server/scenes/bedroom.scene.json`) and the
  builder (`server/scene_to_glb.py`, importable `build_glb`). Opening-cut logic verified.
- **Step B - image -> 3D walls** (done): `/scene` (canonical scene.json), `/scene.glb`
  (downloadable 3D file), `/scene-view` (orbit the walls in the browser). External/internal
  classified, optional building-width param. `scene_builder.py` unit-tested.
- **Step B2 - doors/windows** (done 2026-07-07): CubiCasa Door/Window detections ->
  `openings.py` -> real cuts in walls (doors bridge doorway gaps). Corner snapping +
  looser wall thresholds. Unit + API tested.
- **Step D1 - vector CAD PDFs** (done 2026-07-07): `/scene` routes layered PDFs to
  `pdf_vector.py` (port of drishti reference): wall/plan/window/column layers ->
  exact POLYGON walls (`walls_poly`, angled walls OK) + window openings (sill 3ft/
  head 7ft) + columns + column-box scale (12 in). GLB cuts windows via z-bands
  (`poly_bands`). Raster images still go through CubiCasa. Doors-from-arcs = D2.
- **Quality**: unit + API tests, CI workflow, code review doc, clean `.gitignore`.
- **Frontend groundwork (not wired)**: `src/api/client.ts`, `src/video/useRecorder.ts`.

---

## 4. Status - LEFT (roadmap)
- **Step C - Wire frontend** (NEXT): a button in the React app calls `/scene` and renders
  the walls in 3D inside the real site. Backend + `/scene-view` already prove it works;
  this brings it into the product. (Handle feet->metres in the viewer.)
- **Step 4 - Scale**: real-world size (user-entered width first; OCR later) so you don't
  have to type the width.
- **Doors/windows + rooms** into the 3D (extend scene.json beyond walls).
- **Accuracy test set** (15-20 labelled plans) to measure quality.
- **Deploy** backend to a cloud GPU host.
- **Phase 2 - data flywheel**: save human-corrected plans -> periodic fine-tune.

---

## 5. How to run
**Backend** (PowerShell / VS Code terminal, in `server/`):
```
venv\Scripts\activate
pip install -r requirements.txt      # includes trimesh
uvicorn main:app --port 8000
```
Expect: `Weights loaded. matched_keys=740 missing=0 unexpected=0` then `... ready.`
- Health:     http://localhost:8000/health   -> {"ok":true,"model_loaded":true}
- Detection:  http://localhost:8000/test        (upload a PNG - see detection images)
- 3D walls:   http://localhost:8000/scene-view   (upload a PNG - orbit 3D + download .glb)
- API menu:   http://localhost:8000/docs

**Tests**: from `server/`, `pip install -r requirements-dev.txt` then `pytest`.
**Build reference 3D**: `python scene_to_glb.py scenes/bedroom.scene.json bedroom.glb`.

---

## 6. Key decisions (locked)
- Perception: **local CubiCasa first**; fine-tune only if measured need.
- Product model: **AI draft + human fix** (not fully automatic).
- Runtime: **local FastAPI now**, structured to deploy to cloud later.
- Geometry: **canonical scene.json = feet, z-up**. Convert to metres at the render boundary.
- Codebases: **React Viewer = the one home**; Project viewer = read-only reference.

---

## 7. Known gotchas / risks
- **feet <-> metres boundary**: schema is feet; the in-app renderer uses metres. Convert at
  the boundary or walls come out ~3.28x too big. (GLB builder + scene-view already convert.)
- **No real scale yet** - Step 4. For now type the building width on the scene-view page.
- CubiCasa output is a *draft* (blobby, Finnish room labels, "Undefined") - post-processing
  + manual fix handle it; don't over-invest in retraining early.
- External/internal wall typing is a heuristic (outer-boundary = external) - refine later.
- Env pitfalls seen: OneDrive file locks (moved to D:), CUDA torch build, relative-path cwd.

---

## 8. Vision board
- **Near term (days):** plan -> 3D walls inside the website (Step C, scale).
- **Mid term (weeks):** doors/windows/rooms in 3D; walkthrough video; deploy online;
  accuracy measured on a real test set.
- **Long term (months):** the data flywheel (corrections -> fine-tune), CAD-PDF path via
  the migrated vector parser, multi-unit plans, polished product for AWAAS customers.

---

## 9. Recommendations & parallel tracks
Core track (sequential, with Claude): **Step C -> Scale -> doors/rooms**.
Parallel tracks (don't block the core, can run in other chats):
- **Data track:** collect 15-20 real plans, start a labelled test set (no coding).
- **Infra track:** pick a serverless GPU host + draft a Dockerfile.
- **Experiment track:** try MACU-Net vs CubiCasa on the same test set (after the set exists).

---

## 10. Key file map
- `server/main.py` - API (/health, /perceive, /test, /scene, /scene.glb, /scene-view)
- `server/perception.py` - loads CubiCasa, runs inference (_infer, detect, wall_segments)
- `server/walls.py` - wall pixels -> line segments (Step A)
- `server/scene_builder.py` - segments -> canonical scene.json (Step B)
- `server/scene_to_glb.py` - scene.json -> .glb (migrated)
- `server/scenes/bedroom.scene.json` - example scene
- `docs/SCENE_SCHEMA.md` - canonical geometry schema
- `docs/PROJECT_CONTEXT.md` - THIS file
- `docs/CODE_REVIEW.md`, `docs/AI_PERCEPTION_PLAN.md` - review + strategy
- `src/api/client.ts`, `src/video/useRecorder.ts` - frontend groundwork (not wired)
