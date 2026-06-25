# CONTEXT — Drishti 3D Sandbox

> **What this file is:** a living snapshot of the project. Paste it back to Claude at
> the start of any new session so it instantly knows where we are, and show it to Saswat
> so he can see scope, decisions, and progress at a glance. Update the "Progress log"
> at the bottom whenever a step finishes.

## 1. What we're building
A standalone, browser-only 3D room viewer — a learning prototype for AWAAS's "Drishti"
visual engine. One room you can orbit/zoom/pan, with switchable floor materials, nice
lighting, and a clickable camera marker that snaps to a photo angle.
**No backend, no database, no auth, no real AWAAS data.** Made-up dimensions only.

## 2. Tech stack (fixed — matches Drishti so it slots in later)
| Piece | What it is | Why |
|-------|-----------|-----|
| Vite | Dev server + build tool | Fast startup, instant hot-reload |
| React + TypeScript | UI framework + typed JS | The app skeleton; TS catches mistakes early |
| three | The 3D engine (WebGL) | Does the actual rendering |
| @react-three/fiber (R3F) | Lets you write Three.js *as React components* | Core of the viewer |
| @react-three/drei | R3F helper library | Where OrbitControls, useTexture, etc. come from |

## 3. Scope — IN vs OUT
**In:** single room (floor/walls/ceiling), orbit controls, floor material switcher,
soft-shadow lighting, clickable camera marker with animated snap, short README + demo video.
**Out:** floor-plan import, VR, first-person walkthrough, editing tools, multiple rooms,
any server/API/real data.

## 4. Key decisions
- Room size kept in **named constants** (5 x 5 m floor, 3 m tall) so they're easy to change.
- Materials: MeshStandardMaterial (PBR). Start with flat colors; upgrade to textures if time.
- Camera animation: simple **lerp in the frame loop** (good enough, easy to explain).

## 5. File map
| File | Role |
|------|------|
| index.html | Page shell; loads main.tsx |
| src/main.tsx | React entry point; mounts <App/> |
| src/App.tsx | Top-level scene: Canvas, camera, lights, <Room/>, OrbitControls |
| src/constants.ts | ROOM dimensions + INCLUDE_CEILING flag (single source of truth) |
| src/components/Room.tsx | Builds floor + 4 walls + optional ceiling from constants |
| src/components/Lights.tsx | Hemisphere + ambient fill + shadow-casting directional sun |
| src/materials.ts | Floor finish options (marble/wood/tile) as PBR colours |
| src/components/CameraMarker.tsx | Glowing clickable sphere (pulse + hover) |
| src/components/CameraRig.tsx | Lerps camera + orbit target to a chosen view |
| src/scene.ts | Camera-marker presets + OVERVIEW view |
| src/components/WindowWall.tsx | Back wall built around a window opening + daylight |
| src/components/Furniture.tsx | Primitive rug, coffee table, plant |
| src/components/Model.tsx | Loads + auto-fits an external GLTF model |
| src/components/ErrorBoundary.tsx | Catches model-load failure so app keeps working |
| src/floorplan.ts | Sample plan: wall SEGMENTS in metres + plan image dims |
| src/components/FloorPlanUnderlay.tsx | Lays public/plan.png flat on the floor |
| src/components/WallsFromPlan.tsx | Generates 3D wall boxes from the 2D segments |
| public/plan.png | Generated sample floor-plan image |
| tools/auto_plan.py | OpenCV auto wall-detector -> public/auto_plan.json + preview |
| src/components/AutoPlan.tsx | Renders auto-detected walls in 3D |
| docs/CONVERTER.md | Hands-on guide: local (no-API) 2D->3D converter + how to improve it |
| src/trace/useTrace.ts | Hook: trace state (image, scale, segments) + export |
| src/components/TraceScene.tsx | 3D underlay + live walls + click-to-pick |
| src/components/TracePanel.tsx | HTML upload + trace controls |
| src/components/ViewerPanel.tsx | HTML controls to load a .glb by URL or file |
| src/cv/loadOpenCV.ts | Lazy-loads OpenCV.js (wasm) from CDN |
| src/cv/rasterizePdf.ts | PDF->canvas (pdf.js) + image->canvas helpers |
| src/cv/detectWalls.ts | In-browser wall detection -> wall segments in metres |
| src/components/ImportScene.tsx | Renders detected walls + underlay in 3D |
| src/components/ImportPanel.tsx | Upload JPG/PNG/PDF/GLB + width + status |
| public/manifest.webmanifest | PWA manifest (installable/branding) |
| src/index.css | Resets so the canvas fills the window |
| vite/tsconfig files | Build + TypeScript config (rarely touched) |

## 6. Build steps & status
- [x] **Step 1 — Scaffold:** Canvas + OrbitControls + placeholder cube ("hello world")
- [x] **Step 2 — Room:** floor, 4 walls, ceiling from named constants
- [x] **Step 3 — Lighting:** ambient + directional sun, soft shadows
- [x] **Step 4 — Material panel:** HTML buttons switch floor material via React state
- [x] **Step 5 — Camera marker:** clickable sphere, camera lerps to preset angle
- [ ] **Step 6 — README + demo video**
- [x] **Step 7 — Demo room:** furniture, windowed wall + light, 3 markers, loaded GLTF sofa
- [x] **Step 8 — Floor-plan mode:** plan image underlay + walls generated from segment data
- [x] **Step 9 — Trace mode:** upload any plan, click along walls to generate them, export plan.json
- [x] **Step 10 — GLB Viewer mode:** load any .glb by URL or upload (slot for a 3rd-party 2D->3D service)
- [x] **Step 11 — Import (auto) mode:** upload JPG/PNG/PDF/GLB; in-browser OpenCV.js wall detection -> live 3D

## 7. How to run
```bash
npm install      # first time only — downloads the libraries
npm run dev      # starts dev server, open the printed localhost URL
```

## 8. Progress log (newest first)
- 2026-06-22 — Made the room work DURABLE. Added pipeline/: builder.py (parametric data->3D
  GLB builder), sample_plan.json (bedroom+2 toilets as DATA), SCHEMA.md (the JSON contract),
  and ml/ training scaffold (prepare_data, train_segmentation U-Net, infer_to_schema). The
  hand-built geometry now lives as reusable functions; a trained model would emit the same JSON.
- 2026-06-22 — Step 11: 'Import (auto)' mode. Accepts JPG/PNG/PDF/GLB. PDF rasterised via
  pdf.js; images run OpenCV.js (loaded from CDN) wall detection IN-BROWSER -> walls rendered
  live in 3D over the plan underlay; GLB routes to the viewer. Added pdfjs-dist dependency
  (run npm install). NOTE: written but not browser-tested in the sandbox.
- 2026-06-22 — Added web manifest + icons. Fixed Auto-mode wall height (now 2.5m from JSON).
  Added Step 10 'GLB Viewer' mode: paste a .glb URL or upload a file -> renders via GLTFLoader
  (auto-fit) with load status + ErrorBoundary. This is the display slot for a paid 2D->3D API
  (e.g. GetFloorPlan ~$20/plan GLB export); viewer stays free (our R3F / model-viewer).
- 2026-06-22 — Upgraded auto_plan.py: connected-component cleaning, parallel-edge
  clustering, gap-aware merge (preserves doorways), length filter, grid snap. Sample now
  auto-detects exactly 7 walls (was 21 noisy). Auto (CV) mode renders the clean result.
- 2026-06-22 — Generated wall height set to 2.5m (easy room viewing). Wrote docs/CONVERTER.md
  documenting the fully-local (no-API) 2D->3D pipeline and the modifications to improve it.
- 2026-06-22 — Set generated wall height to 10m. Added tools/auto_plan.py (OpenCV: threshold
  black walls -> Hough lines -> merge -> metres) that writes public/auto_plan.json + a preview.
  New 'Auto (CV)' mode renders the auto-detected walls in 3D. Note: CV grabs text/furniture as
  false walls on stylized plans -> reliable hands-off needs an ML floor-plan model.
- 2026-06-22 — Step 9: Trace mode. Upload any plan image -> shows as floor underlay; click
  along walls (point by point) to generate them live; New wall/Undo/Clear; Export plan.json
  (image, real width, ceiling height, wall segments). This is the 'how a user gives input' answer.
- 2026-06-22 — Fixed floor shadow shimmer (shadow-normalBias + tighter shadow frustum).
  Added Step 8: Demo Room / Floor Plan mode toggle. Floor Plan mode shows a generated
  sample plan as a floor underlay and builds walls from a SEGMENTS data list (the 2D->3D
  bridge). Plan image generated to match the segment coordinates exactly.
- 2026-06-22 — Step 7 (demo room) complete. Added primitive furniture, a windowed back
  wall with daylight, 3 clickable camera markers, and a loaded GLTF sofa (jsDelivr CORS
  URL) wrapped in Suspense + ErrorBoundary. Fixed an 8-digit hex colour + window pane depth.
- 2026-06-22 — Step 5 complete. Clickable glowing CameraMarker + CameraRig that lerps the
  camera/controls to a preset photo view each frame; 'Reset view' button returns to overview.
- 2026-06-22 — Step 4 complete. Dollhouse cutaway walls (THREE.BackSide) so interior is
  visible from any angle. Added materials.ts + HTML button panel; floor material is React
  state in App, passed down to Room.
- 2026-06-22 — Step 3 complete. Lights component: hemisphere+ambient fill, directional
  sun with PCFSoft shadows, shadow map 2048(mobile)/4096(desktop), frustum sized to room.
- 2026-06-22 — Step 2 complete. Added constants.ts + Room component (floor, 4 walls,
  open-top by default via INCLUDE_CEILING=false). Camera pulled back, OrbitControls
  target raised to room centre.
- 2026-06-22 — Step 1 complete. Scaffold created, orange cube orbits. Verified code is
  standard R3F (couldn't npm-install in the sandbox, will run locally).
