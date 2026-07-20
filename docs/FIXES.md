# Drishti — Fixes Applied (20 Jul 2026)
All 22 CODE_REVIEW.md findings fixed + layerless-PDF scale seeding. 2 commits on branch `fix/layerless-pdf-scale-seed`, 21 files, +369/-128.

## Verified
- Backend pytest: 87 passed (was 69; +18 new regression tests incl. 3D band placement). Same 4 pre-existing furniture-test failures as before — untouched.
- Frontend: vitest 13/13, `npm run build` clean.
- End-to-end on 20x45Model.pdf (the plan that 422'd): `/scene?width_ft=20` → 200, envelope 20.0 × 45.0 ft, mode vector_pdf_geometry; `/scene.glb` → valid GLB, 0.8 s; `width_ft=nan` → 422.

## What changed (summary)
Server: GLB band height on correct axis; /scene.glb streams bytes (temp-file leak class deleted); timeout actually cancels (abandon_on_cancel); phantom-window near_door fix; PDF render off event loop + dpi clamp + doc.close; chunked upload cap (early 413); width_ft validated (finite, 0<w≤2000); requirements pinned; degenerate CAD entity guard; thread-safe lazy model load; width-override scale seed for layerless PDFs.
Viewer: upload race sequencing (req counter); GPU disposal (useGLTF.clear + geometry/material/texture dispose); worker request IDs; /scene + /scene.glb in parallel with 3-min abort; loud error when VITE_API_BASE unset in prod; NaN width guard; blob URL revocation; tween killed on drag; keyboard-reachable upload input; pinch-zoom restored; dead .pdf accept removed.

## How to apply on your PC (one time)
```bat
cd /d "D:\3D React Viewer"
git checkout -b fix/all-22
git am path\to\drishti-fixes.patch
git push -u origin fix/all-22
```
(or unzip drishti-fixed-files.zip over the repo instead of git am)
Then: restart uvicorn, and `npm run dev` fresh. For flattened PDFs (like 20x45Model.pdf) type the real width (e.g. 20) in "Width override (ft)" — it has no scale info of its own.

## Still open (not bugs — v1.1 work)
- Doors/windows/rooms on flattened PDFs (door-swing arcs ARE in the PDF; geometric arc detection is the next feature)
- Endpoint-first door snapping on dense sheets; envelope sealing for Neelachala; wing pick via title text; README rewrite; dead-file cleanup (~14 unused frontend files)
