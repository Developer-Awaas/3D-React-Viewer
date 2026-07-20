# Drishti — Code Review (actual code, GitHub main @ 8243e69)
20 Jul 2026 • Backend + frontend line-by-line pass. Severity-ranked. ✔ = verified by hand.

## A. Backend bugs (server/)

| # | Sev | Where | Bug | Failure | Fix |
|---|-----|-------|-----|---------|-----|
| 1 | 🔴 ✔ | scene_to_glb.py:90 `_add_poly_prism` | Height offset `FT*z0` is on the wrong matrix row (plan-Z instead of Y) | Every wall band above sill/header level (any wall with a window, band above a door) renders at floor level and shifted in plan — corrupted GLB geometry on vector-path plans. Tests only pin 2D bands, so this ships green | `M = [[FT,0,0,0],[0,0,FT,FT*z0],[0,FT,0,0],[0,0,0,1]]` |
| 2 | 🔴 | main.py:310-316 | Temp .glb leaks when `build_glb` throws | Repeated failing /scene.glb requests fill /tmp → disk-full kills API | Delete `out` in the except path, or export GLB to bytes (`scene.export(file_type="glb")`) and skip temp files entirely |
| 3 | 🟠 | main.py:156-168 | Timeout can't actually cancel work: `run_in_threadpool` shields cancellation, so `wait_for` fires only after the thread ends | One pathological PDF holds the infer slot for hours; every later request queues forever; 120 s limit is illusory | `anyio.to_thread.run_sync(fn, abandon_on_cancel=True)` |
| 4 | 🟠 | pdf_vector.py:945-949 | `near_door` window filter checks `openings` before any doors are added → always False (dead code) | Door-leaf rects sized like windows get emitted as phantom windows punched through doorway walls | Test against `door_centers` computed earlier |
| 5 | 🟠 | main.py:274 | `_pdf_first_page_png` runs on the event loop, unbounded dpi, doc never closed | Max-size page at 200 dpi ≈ 4.8 GB alloc → freezes/OOMs the container | Route through `_run_heavy`, clamp dpi by page size, `doc.close()` |
| 6 | 🟡 | main.py:195-198 | Whole upload read into RAM before the 25 MB check | Multi-GB multipart body buffered before 413 → memory DoS | Reject on Content-Length header first; read chunked |
| 7 | 🟡 | main.py:289,303 | `width_ft` unvalidated: 0 / negative / NaN accepted | NaN serialises as invalid JSON, breaks every JS client; 0 → degenerate geometry | `Query(gt=0, le=2000, allow_inf_nan=False)` |
| 8 | 🟡 | requirements-deploy.txt | Zero version pins | Next docker build silently pulls breaking numpy/PyMuPDF → prod stops parsing | Pin exact versions |
| 9 | 🟡 | cad_vector.py:114-119 | Degenerate ARC/SPLINE → empty seg list → TypeError → 500 instead of 422 | Malformed DXF-derived PDF crashes with generic 500 | Only yield when `len(pts) >= 2` |
| 10 | 🟡 | perception.py:75-80 | `os.chdir` in lazy `load_model` races across threads | Intermittent wrong-path errors under concurrency | `threading.Lock` around load+chdir |

## B. Frontend bugs (src/)

| # | Sev | Where | Bug | Failure | Fix |
|---|-----|-------|-----|---------|-----|
| 1 | 🔴 | App.tsx:193-213 | No request sequencing in `handlePlan` | Upload A then B fast (or quick wing clicks): A's slower response overwrites B — wrong building shown, blob URL leaked | `useRef` request counter; ignore stale responses; AbortController |
| 2 | 🔴 | Model.tsx + api/scene.ts:46 | `useGLTF` caches every blob URL forever; nothing disposes geometry/materials | 5-10 uploads or wing switches → GPU memory climbs until WebGL context loss (tab crash on mobile) | `useGLTF.clear(url)` on unmount + traverse-dispose |
| 3 | 🟠 | three/planMaterials.ts:176 | Old indexed geometry + original GLB materials never disposed after boxUV swap | Compounds B2 — full extra set of GPU buffers leaked per rebuild | `dispose()` old geometry/material after swap |
| 4 | 🟠 | cv/detectWorker.ts:16-28 | Singleton worker, no request IDs: concurrent calls both resolve with the first result | Re-upload during detection → new plan shows old plan's walls | Per-request id in postMessage, match in handler |
| 5 | 🟠 | api/scene.ts:41-42 | PDF uploaded & parsed TWICE sequentially (/scene then /scene.glb), no abort/timeout | Doubles the 30 s cold-start wait; hung backend = eternal loading screen | `Promise.all` + `AbortSignal.timeout`; ideally one endpoint |
| 6 | 🟠 | api/scene.ts:4 | Prod silently falls back to `http://localhost:8000` when VITE_API_BASE unset | Deployed site's uploads fail mysteriously (also mixed-content) | Fail loudly at startup if `PROD && !VITE_API_BASE` |
| 7 | 🟡 | App.tsx:375 | Clearing width field → `+"" = NaN` → NaN propagates through detection | Silent blank scene | `+e.target.value \|\| 18`, clamp > 0 |
| 8 | 🟡 | App.tsx:152,244,440 | Viewer blob URLs never revoked | Each GLB upload leaks the full file in memory | Revoke prior blob URL in `loadUrl` |
| 9 | 🟡 | TraceScene.tsx:49-55, ImportScene.tsx | Textures not disposed; out-of-order loads overwrite newer underlay | Stale underlay + texture leak | Cancelled flag + dispose in effect cleanup |
| 10 | 🟡 | CameraRig.tsx:20-39 | User drag fights in-flight GSAP tween | Jitter/snap-back when dragging during walk-inside glide | Kill tween on OrbitControls `start` event |
| 11 | 🟡 | index.html:6 + App.tsx:71 | Pinch-zoom disabled app-wide; file input unfocusable (`hidden`) | Accessibility: keyboard users can't upload; mobile users can't zoom text | `sr-only` clipping for input; drop `user-scalable=no` |
| 12 | 🟡 | App.tsx:377 vs 247 | Convert accepts `.pdf` but handler rejects PDFs — `rasterizePdf` path is dead | Users pick a PDF, get an error | Remove .pdf from accept, or route to Plan mode |

## C. Highest-value improvements

1. **Fix A1 + add a 3D-placement test** — assert each band mesh's Y-range = [z0·FT, z1·FT]; this is the exact hole the bug slipped through.
2. **GLB from memory** (kills A2's whole leak class) + single request returning meta+GLB together (kills B5, halves perceived wait).
3. **Delete ~14 dead frontend files** (AppSections, VisualizeButton, ViewerPanel, TracePanel, ImportPanel, ImportScene, AutoPlan, WallsFromPlan, FloorPlanUnderlay, useTrace, useRecorder, client.ts, visualize.ts, floorplan.ts) — none are imported anywhere.
4. **Texture scale is wrong at world scale**: UVs are in local metres but the model is rescaled to fit a 14 m stage — a 30 m building shows ~28 cm "600 mm" tiles. Pass the group scale into `applyPlanMaterials` and divide repeat.
5. **Logging over print()** on the server; per-request scale-source/wing/warnings — makes prod parse failures triageable.

Previously reported (from your PDFs, still valid): door snapping on dense sheets (endpoint-first fix), open-envelope sealing, wing pick via title text, README rewrite, Render cold-start wake ping.
