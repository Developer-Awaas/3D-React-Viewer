# Drishti 3D

An in-browser **2D floor plan → 3D model** converter, built with React, react-three-fiber and OpenCV.js.
Upload a plan, auto-detect a wall draft, fix it by tracing, and view the result in 3D — all client-side.

> New here or handing off? Read **[`docs/HANDOFF.md`](docs/HANDOFF.md)** for the full context
> (goal, architecture, what works, what's next).

## Features
- **Demo** — a furnished 3D room (materials, glass windows, furniture, dual toilets) with smooth GSAP camera moves.
- **Convert** — upload a plan (JPG/PNG/PDF) → OpenCV.js detects walls in a **web worker** (no UI freeze)
  → **click to trace/fix** missing walls → live 3D → export `plan.json`.
- **Viewer** — load any `.glb` / `.gltf` (URL or file) with HDR lighting.
- Premium UI: Tailwind (shadcn-style glass sidebar), Framer Motion, Inter typography, neon-cyan accent.

## Run
```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # production build
```
First detection downloads OpenCV.js (~8 MB) once; needs internet.

## Tech stack
React 18 · TypeScript 5 · Vite · react-three-fiber · @react-three/drei · three · Tailwind CSS ·
GSAP · Framer Motion · OpenCV.js (web worker) · pdf.js · glTF/GLB output.

## Project layout
```
src/            React app (App.tsx + components, cv/ detection, ui/)
public/         detect.worker.js (OpenCV), sample plan.png, prebuilt .glb models
pipeline/       Parametric data→3D builder (builder.py) + plan SCHEMA + ML scaffold (ml/)
tools/          auto_plan.py — offline OpenCV wall detector
docs/           HANDOFF, CONTEXT, GUIDE, CONVERTER, REQUIREMENTS, DESIGN_RULES, GITHUB
```

## How conversion works
1. **Detect** — plan image → wall segments (OpenCV: threshold → Hough → cluster/merge → metres).
2. **Trace-fix** — click along walls the detector missed (auto-draft + human cleanup, like Coohom).
3. **Build** — segments are extruded to 3D (glTF). Offline, `pipeline/builder.py` builds full rooms from a JSON schema.

## Status & limits
Clean line plans convert well automatically; complex/rotated/furnished CAD plans come out rough and
rely on the trace-fix step. Reliable fully-automatic conversion of messy plans needs a trained ML
model (scaffold in `pipeline/ml/`) — a separate, longer effort. See `docs/HANDOFF.md` §9–10.

## License / data
Prototype for AWAAS. Use sample/synthetic plans only — no real proprietary plans committed.
