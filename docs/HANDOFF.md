# DRISHTI — Master Context Prompt (paste/attach this at the start of a new chat)

You are joining an in-progress build. Read this whole file, then read project memory, then continue the work — do not restart, redesign, or re-scaffold anything that already exists.

## What this project is

**Drishti** — a web app that turns a CAD floor-plan PDF into a walkable 3D building, for the Indian proptech market. Founders: **Saswat** and **Amit** (contact: awaas.ai.dev@gmail.com).

- GitHub: `github.com/shubhransupadhi/3D-React-Viewer`
- Local folder on Saswat's Windows machine: **`D:\3D React Viewer`** (connect this folder via the device bridge; it is the source of truth)
- Frontend: React + TypeScript + Vite + react-three-fiber, dark glass theme, orange "neon" accent, Playfair italic headlines
- Backend: FastAPI in `server/`, PyMuPDF vector parsing, PyTorch/TF ML models, run locally on Saswat's machine (NVIDIA 12 GB GPU)

## Standing rules (never break these)

1. **Write all code directly into `D:\3D React Viewer`** via the device bridge (stage → edit in workspace → `device_commit_files` back). Never leave deliverables only in the cloud workspace.
2. **Unit-test every unit BEFORE production.** Test each input case individually. Backend: `pytest` in `server/tests/` (~194 passing + 5 skipped). Frontend: `vitest` (16 tests). Run `npm run build` before delivering frontend changes.
3. **Explain every new command/concept in layman's terms.**
4. **DON'T touch the landing page.**
5. **Web app only — no mobile work.** Goals: beautiful output + accurate output, keep the existing theme.
6. Generalization rule: never per-plan hacks — only general rules, validated against the corpus in the plans folder (`batch_eval.py`). If a change regresses any plan, STOP and report back.
7. Claude cannot push to GitHub and never handles tokens/passwords — Saswat pushes himself.

## Architecture (already built — do not rebuild)

Pipeline: **INGEST → READ → ANALYZE → GENERATE → LOG → REVIEW → IMPROVE**

**READ (server/pdf_vector.py — the parsing engine):** vector-first with layered generalization: named wall layers → brick-hatch recovery → schedule-tag openings (`tag_openings.py`: D/D1/W1 etc.) → room-dimension text scale voting → envelope sealing (`DRISHTI_SEAL_FT=4`, seals a dedicated `m_env` mask only; walls stay unsealed to protect stairs) → `force_geometry` retry for unnamed layers → OCR room labels (pytesseract fallback). Health scoring in `plan_health.py` (`score_scene`, `better_scene`) guarantees "never worse".

**ML fallback (server/main.py cascade):** vector parse → geometry retry → ML best-of. Reader registry: `cubicasa` (`perception.py`, PyTorch, **CC BY-NC = demo only**) + `tf2` (`tf2_floorplan.py`, TFLite at `TF2DeepFloorplan\weights\model.tflite`, GPL). `ML_READER=best` runs all, highest health score wins; `meta.reader_scores` records the contest. Boot line to verify: `ML readers active: ['cubicasa', 'tf2'] (mode=best)`. Note: `load_dotenv()` must stay ABOVE the reader registry in main.py.

**GENERATE (server/visualize.py):** SDXL + multi-ControlNet (canny + depth + seg). Seg model `SargeZT/sdxl-controlnet-seg` (5 GB) auto-enables when cached (`_seg_id()`). G-buffer conditioning maps come from the live three.js scene (`src/three/gbuffer.ts` — beauty/depth/seg passes, crash-safe finally-restore). Disk render cache (`render_cache.py`). Device-mismatch auto-retry built in. **SVD** (`stable-video-diffusion-img2vid-xt`, 4.51 GB) powers Animate; canvas MediaRecorder records walkthrough `.webm` with no model.

**ANALYZE (proptech):** `area_statement.py` (RERA carpet/built-up/super + `/area-statement.xlsx`), `vastu.py` (9-zone, compass north via UI arrows → `north_deg`), `boq.py` (₹ cost estimate). All shown in the insights card.

**LOG/REVIEW:** parse summary logging, Supabase fire-and-forget (`db.py`, needs keys in `.env`), `/review` dashboard, `corpus_export.py`, `rate_limit.py`.

**Frontend:** `src/App.tsx` (R = roof, M = measure tool, compass), `src/three/planMaterials.ts` (procedural canvas textures + boxUV), `src/components/VisualizeButton.tsx` (style grid, Listing Pack, walkthrough recorder), `RenderLoading.tsx` (cinematic overlay). `public/sample.glb` was regenerated via `tools/make_sample_plan.py` — don't revert it.

## Current status

- Corpus: **7/7 plans readable** (20x45, 342, 343, FLOOR PLAN, BRICK WORK, both Neelachala).
- First photoreal SDXL render SUCCEEDED on Saswat's GPU.
- Licensing: CubiCasa CC BY-NC (demo only, not paid product), TF2DFP GPL-3.0 (SaaS likely OK, verify with lawyer), SVD Stability Community License (revenue cap).

## ✅ Recently shipped (2026-07-22 session — do NOT redo)

- **Style-integrated 3D**: the 4 Visualize styles now restyle the walkable model itself. `STYLE_PALETTES` + per-style material cache in `planMaterials.ts` (uvBoxed guard; `managed` WeakSet so shared materials never get disposed), `styleKey` prop on `Model` (style changes run in a SEPARATE effect — they must not re-fire onFramed/camera), `vizStyle` lifted in App, VisualizeButton style select controlled. Palette tests in `planMaterials.test.ts` (22 vitest total).
- **RERA carpet fallback**: when no rooms are detected, carpet = enclosed area inside the wall rings (walls_poly "holes"); `carpet_source` field + explanatory note. 3 new tests in `test_area_statement.py`.
- **Sidebar "Contact founders" button** in all app modes → shared `ContactModal` (now exported from AppSections.tsx). F2 closed.
- **Maker's mark**: tiny clickable "built by raj padhi" (Playfair italic, 9px, white/35) in the contact popup corner → slim popover with raj85sp@gmail.com + tel:+919437418279. Saswat's personal signature — keep it.
- `docs/RENDER-QA.md` (F3 tuning guide) and `docs/ACTIVATIONS.md` (F6 checklist). SVD 4.51 GB download COMPLETED on Saswat's machine; first Animate generated frames.
- Task board 49/51 complete. Only open: **F7 GO LIVE** (user executes docs/DEPLOY-GPU.md) and **C.1 LoRA fine-tune** (parked for v2).

## Pending (user-side, don't redo)

- **git push** (~50 commits sitting only on Saswat's disk — top priority).
- Supabase project creation → keys in `server/.env` (unlocks /review dashboard + corpus archival); tesseract Windows install (OCR room labels on scans); verify seg ControlNet auto-enabled after its 5 GB download (crisper renders); go-live per `docs/DEPLOY-GPU.md` (Cloudflare Tunnel + Vercel).
- v2 ideas parked: LoRA fine-tune on own corpus; baking AI renders onto 3D geometry; per-frame diffusion walkthrough video.
- Licensing before charging money: CubiCasa reader is CC BY-NC (demo only) — disable/replace it in any paid product.

## How to run (Saswat's machine, two PowerShells)

- Backend: `cd "D:\3D React Viewer\server"` → `.\venv\Scripts\activate` → `uvicorn main:app --port 8000`
- Frontend: `cd "D:\3D React Viewer"` → `npm run dev` (Vite, port 5173)

## First moves in the new chat

1. Read project memory (all files) and this file.
2. Connect/verify the `D:\3D React Viewer` folder via the device bridge.
3. Continue the in-flight style task above. Test → build → deliver to disk. No questions that memory already answers.
