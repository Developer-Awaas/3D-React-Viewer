# DRISHTI 3D — HANDOFF & CONTEXT (read me first)

> Paste this whole file into a new chat/LLM to continue the project with full context.
> It covers: what this is, the goal, what's built, what's broken, the plan, and the next steps.

---

## 1. What this project is
**Drishti 3D** is an in-browser tool that turns **2D floor plans into 3D models**, built for
AWAAS (real-estate). It started as a 1-week intern sandbox (a standalone React-Three-Fiber
room viewer) and grew into a prototype of the real product: *upload a floor plan → get a 3D model.*

Repo: https://github.com/shubhransupadhi/3D-React-Viewer
Local path: `OneDrive/Desktop/3D React Viewer`

## 2. The goal & constraints
- **Goal:** an **in-house, free** 2D→3D converter. If the prototype works, it becomes AWAAS's product.
- **Timeline:** ~1–2 weeks for a working prototype.
- **Constraint:** in-house only (no paid API as the core), no ML training from scratch (too long).
- **Real plans** are complex Indian residential CAD plans (e.g. "THE ZENITH": 2 flats, bedrooms,
  toilets, balconies, furniture, rotated, thin single-line walls).

## 3. Current status
**Works:**
- React + Vite + TypeScript app with three modes (Demo · Convert · Viewer).
- **Demo** — a furnished 3D room (walls, windows, glass, queen bed, cupboard, dual toilets with
  WC/basin/shower/glass partitions/doors), built parametrically, accurate to a real bedroom plan.
- **Convert** — upload a plan image/PDF → **auto-detect walls in-browser (OpenCV.js in a web worker,
  no UI freeze)** → **click to trace/fix** missing walls → live 3D. Export `plan.json`.
- **Viewer** — load any `.glb`/`.gltf` (URL or upload), HDR-lit.
- Premium UI: Tailwind + shadcn-style glass sidebar, GSAP camera tweens, Framer Motion pills, Inter font.
- A **parametric pipeline** (`pipeline/builder.py`) that turns a plan JSON schema into a 3D GLB.
- An **offline Python detector** (`tools/auto_plan.py`) that is stronger than the in-browser one.

**Does NOT work well (known, expected):**
- **Auto-detection on complex/real plans is rough.** On a clean line plan it's good; on a dense,
  rotated, furnished CAD plan it returns fragmented walls + furniture/text noise. This is the
  ceiling of pixel-based detection — not a bug. The mitigation is the **trace-fix** step.

## 4. Architecture & stack
- **Vite + React 18 + TypeScript 5**
- **react-three-fiber + @react-three/drei + three** (3D)
- **Tailwind CSS** (shadcn-style dark theme), **GSAP** (camera), **Framer Motion** (UI)
- **OpenCV.js** (CDN, in a Web Worker) for wall detection; **pdf.js** for PDF→image
- **Python** side (offline, not in the app): `tools/auto_plan.py`, `pipeline/`

3D output format everywhere is **glTF/GLB** (web standard, portable to Blender/Unity/Unreal).

## 5. File map (the important ones)
```
src/
  App.tsx                       Main app: glass sidebar, 3 modes, GSAP camera, Framer Motion
  index.css                     Inter font + Tailwind + dark theme variables
  cameraPresets.ts              CameraPreset interface + PRESETS map (per material + default)
  materials.ts                  Floor finishes (marble/wood/tile)
  scene.ts                      Demo camera markers + OVERVIEW view
  constants.ts                  Demo room dimensions
  components/
    Room.tsx, Lights.tsx, Furniture.tsx, WindowWall.tsx   Demo room geometry
    Model.tsx                   GLTF loader + auto-fit
    ErrorBoundary.tsx           Catches model-load failures
    CameraMarker.tsx            Glowing clickable camera markers (demo)
    CameraRig.tsx               *** GSAP camera tween (0.8s power3.out) ***
    TraceScene.tsx              Convert/trace 3D: underlay + walls + click-to-add
    ui/Button.tsx               Reusable shadcn-style button
  cv/
    loadOpenCV.ts               Lazy-load OpenCV.js (main-thread fallback)
    detectWalls.ts              Main-thread detector (Seg type lives here)
    detectWorker.ts             *** Worker wrapper — detection off the main thread ***
    rasterizePdf.ts             PDF/image -> canvas
  trace/useTrace.ts             (legacy standalone trace hook — Convert now inlines this logic)
public/
  detect.worker.js              *** Classic web worker: OpenCV.js wall detection ***
  plan.png                      Clean SAMPLE plan (works well with auto-detect)
  *.glb                         Pre-built models (bedroom_toilet.glb is the hand-built bedroom+toilets)
pipeline/                       *** DURABLE: data -> 3D ***
  builder.py                    Parametric GLB builder (rooms/toilets from JSON)
  sample_plan.json              The bedroom+toilets expressed as DATA
  SCHEMA.md                     The plan JSON contract (what a model would output)
  ml/                           ML training scaffold (run on Colab GPU, NOT here)
tools/auto_plan.py              Offline OpenCV detector (cleaner than in-browser)
docs/                           CONTEXT, GUIDE, CONVERTER, REQUIREMENTS, DESIGN_RULES, GITHUB, this file
```

## 6. The three app modes
- **Demo:** scripted furnished room; material buttons swap the floor AND glide the camera (GSAP+PRESETS).
- **Convert:** the product. `handleConvert` → `detectWallsWorker` (worker) → segments + underlay →
  `TraceScene` renders them and lets the user click to add walls. Undo / New wall / Clear / Export.
- **Viewer:** `Model.tsx` loads any GLB with HDR env + contact shadows.

## 7. The conversion pipeline (product core)
Two halves:
1. **Image → wall segments** (DETECT). In-browser: `public/detect.worker.js` (threshold dark pixels →
   HoughLinesP → cluster parallel edges + gap-aware merge → metres). Offline & better:
   `tools/auto_plan.py` (adds connected-component cleanup to drop text/furniture).
2. **Segments/JSON → 3D** (BUILD). In-app: `TraceScene` extrudes walls live. Offline/full:
   `pipeline/builder.py` from `SCHEMA.md` JSON (rooms, walls, openings, furniture).
A trained ML model would replace half #1 by OUTPUTTING the SCHEMA.md JSON, feeding straight into half #2.

## 8. Design rules learned (apply when interpreting plans) — see docs/DESIGN_RULES.md
- A **curved arc = a door**; put a door (default closed) in the arc's opening.
- **Bed = queen** (1.53 × 2.03 m), standard across bedrooms.
- **Toilet:** WC + basin both on the **shared centre wall** (WC back, basin beside it toward the
  glass), WC faces the door; exactly **ONE glass partition** between WC and shower; WASH area is
  empty floor (no invented washing machine); attached-room walls **align with the bedroom walls**;
  the whole bedroom+toilet footprint should be a clean **rectangle**.

## 9. Known limitations & WHY
- **Auto-detect fails on complex/rotated/furnished plans** — pixel detection can't tell a wall from
  furniture/text; rotation breaks the H/V assumption. Fix = ML model OR clean input OR human tracing.
- The user's **DWG is a PDF-converted file** (CADSoftTools), so it has NO semantic layers/blocks —
  it's not better than the image. A *native* DXF would be (walls/furniture as named objects).
- OpenCV.js first load is ~8MB (~10–20s once, then cached).
- The hand-built bedroom/toilet GLBs are **parametric scripts** (Python in tools/outputs), not yet
  wired into the app's Convert flow — they're reference outputs + the basis for `pipeline/builder.py`.

## 10. THE PLAN — what to do next (prioritized)
Build the **auto-draft + human-trace** product (this is how Coohom works too):
1. **Click-to-delete a wall** in Convert (currently only Undo) — completes the fix workflow. *High value, low effort.*
2. **Snapping while tracing** — snap to grid + Shift for ortho (straight H/V) walls. *High value.*
3. **Auto-deskew before detection** — rotate tilted plans straight first → better detection on real plans.
4. **Port `tools/auto_plan.py` cleanups into `public/detect.worker.js`** (connected-component blob
   removal, parallel-edge merge) so the in-browser draft is less noisy.
5. **Per-room floors + colors** (flood-fill rooms) and **OCR room labels** (Tesseract.js) to color by type.
6. **Doors & windows** detection/placement.
7. Wall **thickness/height controls** + better materials/lighting on converted models.
Longer term (separate, months): a **trained segmentation model** (U-Net on CubiCasa5K) emitting the
SCHEMA.md JSON — the only path to reliable fully-automatic conversion. Scaffold is in `pipeline/ml/`.

## 11. Run / build / deploy
```
npm install        # needs: three, r3f, drei, tailwind, gsap, framer-motion, pdfjs-dist
npm run dev        # http://localhost:5173
npm run build      # production build (tsc + vite)
```
OpenCV.js loads from https://docs.opencv.org/4.x/opencv.js at runtime (needs internet first time).
Git/GitHub: see docs/GITHUB.md. Push with: `git add . && git commit -m "..." && git push`.

## 12. Strategic decisions on record
- **Build vs buy:** in-house chosen (product ambition). A paid API (GetFloorPlan/CubiCasa ~$20–35/plan)
  is the fast/robust alternative if in-house stalls — view its GLB in the Viewer mode.
- **CV vs ML:** rule-based CV is the 1–2 week deliverable (clean plans + human trace-fix). ML is the
  only path to hands-off conversion of messy plans but is a multi-week project (data + GPU).
- **Honest scope:** clean plans convert automatically; complex plans need the trace-fix step. That's
  shippable and matches how the big tools actually operate.
