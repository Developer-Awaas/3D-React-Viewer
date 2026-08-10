# AWAAS (formerly "Drishti") — Complete Project Handoff

**For: Rahul** · Prepared 23 July 2026 · Continuing development on Mac
**Give this whole file to Claude (chat or Claude Code) at the start of every session — it is the full context.**

---

## 1. What this product is (in one paragraph)

Awaas is a web app for Indian real estate. A user uploads **one CAD floor-plan PDF** and, in under a minute, gets back: a **3D building they can walk through in the browser**, the **official RERA areas** (carpet / built-up / super built-up), a **room-by-room Vastu reading**, a **₹ construction cost estimate** (brick count + labour), and — on a GPU machine — **photoreal AI images and short walkthrough videos** of any room. No drawing, no measuring, no expert needed. It is live in production today and costs ₹0/month to run.

- **Live site:** https://3-d-react-viewer.vercel.app
- **GitHub repo:** https://github.com/shubhransupadhi/3D-React-Viewer.git (deployed branch: `main`; recent work landed via branch `fix/all-22`, merged in PR #2)
- **Founders:** Saswat & Amit (awaas.ai.dev@gmail.com)
- **Current source of truth:** `D:\3D React Viewer` on Saswat's Windows GPU PC. ⚠️ Before Rahul clones, Saswat must commit & push any remaining local changes — otherwise the Mac copy will be missing the latest work.

---

## 2. How it works (the pipeline, in plain words)

```
Upload PDF → READ → ANALYZE → BUILD 3D → GRADE → (optional) AI RENDER
```

1. **READ** — The backend opens the PDF and reads its actual vector lines (not a screenshot). It finds walls, doors, windows, room boundaries and the drawing's scale. It self-corrects scale using dimension text printed on the plan and typical door widths. (`server/pdf_vector.py` — the heart of the product.)
2. **ANALYZE** — From those walls it computes carpet/built-up/super built-up area, runs a 9-zone Vastu check per room, and prices the masonry (bricks + labour) in rupees. (`area_statement.py`, `vastu.py`, `boq.py`)
3. **BUILD 3D** — It extrudes the walls into a true-to-scale 3D model (GLB file) with real wall thicknesses, door openings with actual door leaves, and furniture where detected. The browser loads it and you walk through it. (`scene_builder.py`, `scene_to_glb.py`)
4. **GRADE** — A built-in agent called **Plan Doctor** inspects every parse, gives it a report card (A–F + score + plain-English reason), and writes what it learned to a log. More on this in section 5.
5. **AI RENDER (GPU only)** — Any 3D viewpoint can be turned into a furnished, photo-real image (SDXL + ControlNet) or a short video (Stable Video Diffusion). This is the ONLY part that needs an NVIDIA GPU.

**The key architectural insight:** only step 5 needs a GPU. Steps 1–4 (all the everyday value) are pure CPU — which is why the whole thing runs free, and why a Mac can run everything except renders.

---

## 3. The tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite, react-three-fiber (3D), Tailwind. Dark-glass theme, orange neon accents, Playfair italics. |
| Backend | Python FastAPI (`server/`), uvicorn |
| PDF parsing | PyMuPDF (vector line extraction) |
| Geometry / 3D | shapely, trimesh, mapbox-earcut → GLB export |
| ML plan readers (photo/scan path, beta) | CubiCasa5k + TF2DeepFloorplan (PyTorch) |
| AI renders | SDXL + ControlNet (depth/canny) + SVD video, on a 12 GB NVIDIA card |
| Hosting | **Vercel** (frontend, free, auto-deploys from `main`) + **Cloudflare Tunnel** to the GPU PC (backend) |
| Database (optional, currently OFF) | Supabase — logs every parse when configured |
| Tests | pytest (~311 backend), vitest (22 frontend), golden corpus tests |

---

## 4. Everything that has been built (feature by feature, layman terms)

### Core product
- **Vector plan reading** — reads real CAD linework; multi-wing sheets are split and the correct wing is auto-picked (scored by enclosed rooms first, so a door-schedule table can never win over the actual floor plan).
- **Self-correcting scale** — the parser cross-checks the drawing scale against printed dimension text and median door width; if the plan's scale is wrong it rescales everything (rooms, walls, areas) consistently.
- **Walkable 3D** — true-to-scale model in the browser: walls with thickness, doors with swinging leaves, windows, furniture (beds, sofas, bathtubs…), walk-inside camera.
- **RERA area statement** — carpet, built-up, super built-up (+ Excel download). The built-up maths was rebuilt (see "big bug" below) so it now measures the gross outer footprint + wall material properly.
- **Vastu** — every typed room is placed in the 9-zone grid and gets a verdict + advice; the compass (north) is user-settable.
- **Cost / BOQ** — brick count and ₹ total (with labour) computed from real wall volumes.
- **4 render styles** — the walkable 3D can be restyled (style-3D feature).
- **AI photoreal renders + video** — furnished, photo-like images of any view and short walkthrough videos (GPU machine only).

### The "G-steps" (accuracy/efficiency roadmap — ALL built)
- **G1 Wall-gap healing** — on messy plans where wall lines don't quite touch, hairline gaps (≤6 in) are sealed on a rooms-only mask so rooms are still found (fires only when 0 rooms were detected; stairs stay safe).
- **G2 OCR room labels** — when CAD text is outlined (unreadable), Tesseract OCR reads the labels off the drawing. (Code done; Tesseract must be installed on the machine to activate.)
- **G3 Scale correction** — auto-rescale using door-width statistics (env-gated `DRISHTI_AUTOSCALE`).
- **G5 Opening fusion** — ML-detected doors/windows are merged into vector scenes, clamped to their host walls so nothing floats in space.
- **G7 User corrections** — a "Correct rooms" panel in the app: fix the true width, rename/delete rooms, change loading factor or north — numbers recompute **instantly** with no re-parse (`/recompute` endpoint).
- Plus: door footprint validation (a "door" wider than 6 ft or fatter than 1.6 ft is demoted — that's merged walls, not a door), overall-dimension envelope snapping (anchor plan now parses to the user-confirmed 38'3" × 64'2" exactly).

### Production hardening (done during the pre-launch audit)
- Rate limiting that sees the real client IP behind the tunnel; CORS locked to the Vercel domain; upload size caps; `/review` page behind a token + XSS-escaped.
- One shared GPU queue so two renders can't crash the card (CUDA out-of-memory → clean "busy" message).
- Timeouts everywhere: a stalled backend can never hang the website forever; a Cancel button on renders.
- The site never white-screens: if the backend URL isn't configured, only the upload action fails with a clear message — the landing page still renders.
- Honest failures: bad input → clear error, never a wrong 3D model or fake number.

### The big bug that was found and fixed (worth knowing the story)
Efficiency % sometimes showed 70–80% and sometimes a flat 0%, and masonry cost sometimes showed ₹0. Root cause: **built-up area** was computed from thin wall strips and could come out *smaller than carpet*, then got clamped equal to carpet — which zeroed wall material (so ₹0 bricks) and froze efficiency. Fixed: built-up = gross outer footprint (or carpet + wall material as a floor). Verified on the corpus: BRICK plan built-up 682→903 sqft, bricks 0→49,978, efficiency now varies honestly (75.6 / 76.0 on different plans). Related rule: efficiency can now **never** silently show 0% — if it can't be trusted it shows "needs review" plus the reason.

---

## 5. Plan Doctor — the self-learning agent (important, please keep it alive)

- `server/plan_doctor.py` runs ~15 rules on **every** parse → grade A–F, 0–100 score, plain-English headline shown in the app's "Plan check" card.
- Every parse appends one line (with failure tags) to **`docs/LEARNINGS.md`** — the product's growing memory.
- `server/doctor_daemon.py` summarises each day's parses into **`docs/DOCTOR-DAILY.md`** (a morning report). On Mac, schedule it with `cron` instead of Windows Task Scheduler.
- **How it "learns":** Claude reads `LEARNINGS.md` at the start of each session and turns repeating failure tags into new rules + new corpus tests. That loop is the learning — keep doing it.
- Optional LLM second opinion exists (`LLM_DOCTOR=1` + `ANTHROPIC_API_KEY`) but **no API key is set today, so it's off by design**. The rules-based agent works fully without it.

---

## 6. Quality: how we know it works

- **~311 backend tests + 22 frontend tests**, all green; clean `npm run build`.
- **Golden corpus tests** (`server/tests/test_corpus_golden.py`): 7 real client plans are pinned to known-correct numbers. **Rule: no change may regress them.** The corpus PDFs live in `plans/` (confidential, gitignored) — tests skip politely if the folder is absent.
- `server/batch_eval.py` re-parses the whole corpus and reports drift.
- The one true accuracy anchor: the FIRST FLOOR plan's real plot is user-confirmed **38'3" × 64'2"** — parsed size must stay within 2.5%.

---

## 7. The 7 standing rules (do not break — Claude follows these)

1. Write all code directly into the project folder, never chat-only.
2. Unit-test every unit before production; run the full suite + build before delivery.
3. Explain every new command/concept in layman's terms.
4. **NEVER touch the landing page** (`LandingHero.tsx`, `landing.css`).
5. Web-app only; goals = beautiful + accurate output; keep the theme.
6. **GENERAL rules only — no per-plan hacks.** Corpus-validate every parser change; if any plan regresses, STOP and report.
7. Claude never pushes to GitHub and never handles tokens/passwords — the human does all git pushes and fills all secrets.

---

## 8. How it is deployed today (₹0/month)

```
User's browser ──▶ Vercel (static site, free, auto-deploys main branch)
                        │
                        └──▶ Cloudflare Tunnel ──▶ Saswat's GPU PC (FastAPI :8000)
                                                       ├─ CPU: parse · area · vastu · cost · 3D
                                                       └─ GPU: AI renders
```

- The site bakes the backend URL in at build time via the Vercel env var **`VITE_API_BASE`**.
- ⚠️ The free "quick" Cloudflare tunnel gives a **new random URL on every restart**. When it changes: update `VITE_API_BASE` in Vercel → Redeploy → hard-refresh (Ctrl+Shift+R). For an always-on launch, switch to a **named tunnel + custom domain** (top roadmap item).
- Backend start (on the GPU PC): `uvicorn main:app --host 0.0.0.0 --port 8000`, then `cloudflared tunnel --url http://localhost:8000`. Sanity check: `<tunnel-url>/health` → `{"ok": true}`.

---

## 9. Setting up on Rahul's Mac (exact steps)

**What a Mac CAN run:** everything except AI renders — parsing, areas, Vastu, cost, 3D, Plan Doctor, the website, all tests. **What it CANNOT run:** the SDXL/SVD render stack and the CubiCasa/TF2 photo readers (they require NVIDIA CUDA; Apple chips don't have it). The app degrades gracefully — renders just show a "beta unavailable" message. Renders stay on the Windows GPU PC (or a rented cloud GPU later).

### Install (Terminal)
```bash
# 1. Homebrew from brew.sh if not installed, then:
brew install git python@3.12 node
# optional: brew install cloudflared tesseract

# 2. Get the code (AFTER Saswat has pushed everything)
git clone https://github.com/shubhransupadhi/3D-React-Viewer.git
cd 3D-React-Viewer

# 3. Backend
cd server
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt   # if torch version complains: pip install torch torchvision
cp .env.example .env
uvicorn main:app --reload --port 8000   # check localhost:8000/health

# 4. Frontend (second Terminal tab)
cd ~/3D-React-Viewer
npm install
echo 'VITE_API_BASE=http://localhost:8000' > .env
npm run dev                        # open localhost:5173

# 5. Verify
cd server && python -m pytest      # ~230+ pass; corpus tests skip without plans/
cd .. && npm run test && npm run build
```

### Things git will NOT bring (copy separately if needed)
- `plans/` — the confidential corpus PDFs + `ground_truth.json`. Needed only for the golden accuracy tests. Copy from Saswat's PC privately (never commit them).
- `.env` files — recreated from `.env.example` (above).
- ML weights (CubiCasa/TF2) — skip on Mac entirely; GPU-path only.
- `node_modules/`, `venv/`, `dist/` — rebuild themselves; never copy.
- The `.bat` files in the repo root are Windows-only; ignore them on Mac.

---

## 10. Supabase (optional database — currently OFF)

The app runs 100% without it. It exists to log every parse (metrics + full scene JSON) into a table, which doubles as a training corpus and a production error log. To switch on:
1. Create a free project at supabase.com.
2. SQL editor → paste and run `server/schema.sql` (creates the `parses` table, indexes, and locks it down with RLS).
3. In `server/.env`: `SUPABASE_URL=...` and `SUPABASE_KEY=<service_role key>` (server-side only — never put this key in the frontend).
4. Optional: `STORE_UPLOADS=1` to also archive the uploaded PDFs to Supabase Storage.
Design guarantee: logging is fire-and-forget — a Supabase outage can never break or slow a parse. Full notes: `docs/SUPABASE.md`.

---

## 11. Key environment variables (`server/.env`)

| Variable | What it does |
|---|---|
| `REVIEW_TOKEN` | Password for the `/review` page |
| `TRUST_PROXY=1` | ONLY behind the Cloudflare tunnel (otherwise rate limiting breaks) |
| `ALLOWED_ORIGINS` | Must include the Vercel domain in production |
| `MAX_CONCURRENT_GPU=1` | One shared GPU queue |
| `DRISHTI_ROOM_SEAL_FT` / `DRISHTI_AUTOSCALE` / `DRISHTI_OCR` | Toggles for G1 / G3 / G2 |
| `DISABLE_CUBICASA` / `DISABLE_TF2` / `DISABLE_SVD` | **License gates — see section 13** |
| `LLM_DOCTOR` + `ANTHROPIC_API_KEY` | Plan Doctor's optional AI second opinion (off today) |
| `SUPABASE_URL` / `SUPABASE_KEY` / `SUPABASE_TABLE` | Parse logging (off today) |
| `FAST_SCHEDULER` / `RENDER_STEPS` / `GPU_OFFLOAD` | Render speed tuning (GPU box only) |

---

## 12. Where everything lives (read in this order)

| File | What it is |
|---|---|
| `CLAUDE.md` (repo root) | Single source of truth for Claude — auto-loaded by Claude Code. **Note: its "current state" section predates the 23 Jul deploy; this handoff is newer.** |
| `docs/EFFICIENCY-ROADMAP.md` | The G-steps analysis (all now built) |
| `docs/FIXES-2026-07-22.md` · `docs/AUDIT-2026-07-22.md` | Every fix + the full pre-launch audit |
| `docs/LEARNINGS.md` · `docs/DOCTOR-DAILY.md` | Plan Doctor's memory + daily digest |
| `docs/DEPLOY-GPU.md` | Go-live runbook (Vercel + tunnel) |
| `docs/SCENE_SCHEMA.md` | The scene.json contract (walls/rooms/openings format) |
| `docs/SUPABASE.md` | Database setup |
| `server/pdf_vector.py` | THE parsing engine |
| `server/main.py` | All API endpoints |
| `server/plan_doctor.py` | The self-learning agent |
| `server/visualize.py` | GPU render stack |
| `src/App.tsx` | Main frontend app · `src/api/scene.ts` + `visualize.ts` — backend calls |

---

## 13. ⚠️ Licensing — must resolve before ANY paid tier

- **CubiCasa5k weights are CC BY-NC — non-commercial only.** Must be disabled (`DISABLE_CUBICASA=1`) or replaced before charging money.
- **TF2DeepFloorplan is GPL-3.0** (copyleft) — lawyer-check before commercial use.
- **SVD** runs under Stability's community license — check revenue thresholds.
- The env gates for all three already exist and the app degrades gracefully with them off. The core vector-PDF path (the actual product) has **no** licensing problem.

---

## 14. What's next (roadmap, in priority order)

1. **Named Cloudflare tunnel + custom domain** — kills the "new URL every restart → redeploy" dance. Biggest quality-of-life win.
2. **Nightly Plan Doctor digest on a schedule** — `cron` on Mac / Task Scheduler on Windows → `python doctor_daemon.py`.
3. **Install Tesseract** wherever the backend runs → activates G2 OCR room labels.
4. **Supabase logging on** (section 10) → start building the real-world corpus.
5. **E4 parse-once cache** for `/scene` + `/scene.glb` (~2× faster uploads) · **E5 ML fusion** (merge readers' doors/windows, feed CubiCasa room types into scenes) · **E6 plausibility-aware health scoring**.
6. **Plan Doctor phase 2** — a "looks right / looks wrong" feedback button that feeds LEARNINGS.md.
7. Licensing cleanup (section 13) before monetisation. Parked v2 ideas: LoRA fine-tune, render baking, per-frame diffusion video.

---

## 15. The first message Rahul should send Claude

> "Read AWAAS-HANDOFF.md and CLAUDE.md fully. This project (formerly Drishti, now Awaas) is being continued on this Mac. Follow the 7 standing rules. Confirm the backend and frontend run locally, run the test suites, then summarise the current state back to me before we start any new feature."

That's it. Everything above is the complete picture — the product, the code, the story of what was built and fixed, how to run it, and where to take it next.

*Prepared as part of the Drishti → Awaas handoff, 23 July 2026.*
