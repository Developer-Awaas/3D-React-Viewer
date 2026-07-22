# CLAUDE.md — Drishti single source of truth
<!-- Read me first. I am the one file that explains the whole project, how
     Claude (the AI pair-engineer) is used, and where everything else lives.
     Claude Code / Cowork auto-loads this file at session start. -->

## What Drishti is

A web app that turns a CAD floor-plan PDF into a walkable 3D building with
photoreal AI renders, RERA area statements, Vastu analysis and ₹ cost
estimates. India-first proptech. Founders: **Saswat & Amit**
(awaas.ai.dev@gmail.com). GitHub: `shubhransupadhi/3D-React-Viewer`, branch
`fix/all-22`. Source of truth: **`D:\3D React Viewer`** on Saswat's Windows
machine (NVIDIA 12 GB GPU runs all ML locally).

Stack: React+TS+Vite+react-three-fiber frontend (dark glass, orange neon,
Playfair italics) · FastAPI backend in `server/` · PyMuPDF vector parsing ·
CubiCasa + TF2DeepFloorplan ML readers · SDXL+ControlNet renders · SVD video.

## The 7 standing rules (never break)

1. Write all code directly into `D:\3D React Viewer` (device bridge), never
   chat-only. 2. Unit-test every unit BEFORE production; full suite + build
   before delivery. 3. Explain every new command/concept in layman's terms.
4. NEVER touch the landing page (LandingHero.tsx, landing.css).
5. Web-app only; goals = beautiful + accurate output, keep the theme.
6. GENERAL rules only — no per-plan hacks; corpus-validate every parser
   change (golden tests + batch_eval); if any plan regresses, STOP and report.
7. Claude never pushes to GitHub and never handles tokens/passwords — Saswat
   does all git pushes and fills all secrets himself.

## How Claude is used (and what each round of use improved)

Claude works as the senior engineer: audits, writes tested code straight to
disk, explains in plain language, and learns between sessions via project
memory + `docs/LEARNINGS.md`. Efficiency/accuracy gains by session:

| Date (2026) | What Claude did | Measured improvement |
|---|---|---|
| ~Jul 10–14 | v1 engine: vector parser, 3D pipeline, golden corpus tests | 0 → working product, 110+ tests |
| Jul 21 | Tag reader, Vastu, BOQ, rate limit, /review, sealing, TF2 adapter, ML data pipeline | Corpus 3/7 → 5/7 plans clean; doors 3→7 on tag plans; 188 tests |
| Jul 22 (day) | Style-3D, RERA carpet fallback, SVD Animate, seg moat docs | 4 render styles restyle the walkable 3D; ~197+22 tests |
| Jul 22 (audit) | 3-agent full-product audit → `docs/AUDIT-2026-07-22.md` | Found 9 launch blockers + ML value leaks (~40% of model value unused) |
| Jul 22 (fixes r1) | Review auth+XSS, tunnel real-IP rate limit, upload caps, one GPU gate, RERA super=carpet×loading, tf2 door bug, license gates, **build fix** (deb56aa didn't compile), render timeout+Cancel | Efficiency % corrected +5–9 pts (was understated); tf2 reader revived from dead weight; suite 197→218 |
| Jul 22 (E1) | DPM++ 2M Karras scheduler, 28→22 steps | ~25–30% faster renders, same quality |
| Jul 22 (r2) | Envelope-from-overall-dimension rule in pdf_vector | Anchor plan 39.98×66.9 → **exactly 38.25×64.167** (user-confirmed); RERA areas were ~9% inflated on chhajja plans; suite 225 |
| Jul 22 (night) | **Plan Doctor** self-checking agent + this file; E2 offload rule | Every parse self-grades A–F with layman reason; efficiency can never show a silent 0%; suite 236 |

## The self-learning loop (Plan Doctor)

`server/plan_doctor.py` runs ~15 rules on EVERY parse → grade A–F + plain-
English headline, shown in the app's insights card, embedded in the /scene
response, and appended one-line-per-parse to **`docs/LEARNINGS.md`**.
Claude reads LEARNINGS.md each session, turns repeating failure tags into new
rules + corpus tests — that is how the system auto-learns. Optional LLM
second opinion (`LLM_DOCTOR=1` + `ANTHROPIC_API_KEY`) runs in parallel, never
blocks, never overrides rules. Phase 2 (planned): "looks right/wrong" user
feedback button. Non-negotiable: efficiency 0% is always shown as
"needs review" with the cause (usually: wall lines don't close → no rooms →
carpet unknown).

## How to run & test (Saswat's machine)

Backend: `cd "D:\3D React Viewer\server"` → `.\venv\Scripts\activate` →
`uvicorn main:app --port 8000`. Frontend: `cd "D:\3D React Viewer"` →
`npm run dev` (port 5173). Tests: `python -m pytest` in server/ (expect ~236
passed; corpus tests need `plans/`), `npm run test` (22), `npm run build`.

## Key env vars (`server/.env`, template in `.env.example`)

`REVIEW_TOKEN` /review password · `TRUST_PROXY=1` ONLY behind Cloudflare
Tunnel (else rate limiting is off!) · `ALLOWED_ORIGINS` must include the
Vercel domain in prod · `MAX_CONCURRENT_GPU=1` one shared GPU queue ·
`FAST_SCHEDULER` / `RENDER_STEPS` (E1) · `GPU_OFFLOAD=auto|always|never` (E2)
· `DISABLE_CUBICASA/TF2/SVD` license gates (CubiCasa is CC BY-NC = NO paid
use; TF2 is GPL; SVD community license) · `LLM_DOCTOR` + `ANTHROPIC_API_KEY`
· `ML_READER=best` · `TF2FP_MODEL` weights path · `STORE_UPLOADS=1` corpus
archival · Supabase: `SUPABASE_URL/KEY/TABLE`.

## Where everything lives (doc index)

- `docs/HANDOFF.md` — session hand-off master prompt (architecture deep-dive)
- `docs/AUDIT-2026-07-22.md` — full product audit: blockers, value leaks, test plan
- `docs/FIXES-2026-07-22.md` — every fix applied 22 Jul (rounds 1+2), env keys
- `docs/LEARNINGS.md` — Plan Doctor's growing memory (one line per parse)
- `docs/DEPLOY-GPU.md` — go-live runbook (Vercel + Cloudflare Tunnel)
- `docs/ACTIVATIONS.md` — user-side switch-ons checklist · `docs/RENDER-QA.md` — render tuning
- `docs/SCENE_SCHEMA.md` — scene.json contract · `docs/SUPABASE.md` — logging setup
- `plans/` — confidential corpus + `ground_truth.json` (gitignored; tests skip without it)
- Engine: `server/pdf_vector.py` · API: `server/main.py` · renders:
  `server/visualize.py` · doctor: `server/plan_doctor.py` · health:
  `server/plan_health.py` · eval: `server/batch_eval.py`

## Current state (22 Jul 2026 night) & roadmap

DONE, on disk, uncommitted on deb56aa: all launch blockers, E1, corpus
envelope fix, Plan Doctor. Suite 236 passed / 1 skipped; build clean.
LAUNCH (23 Jul): Saswat runs docs/DEPLOY-GPU.md + sets the 3 prod env values
+ git push. WAITING: render-log baseline from Saswat (seg auto-enable check).
NEXT (E-steps): E2 offload rule (done 22 Jul night, verify on GPU) · E3 seg
fp16 (runtime already fp16 via torch_dtype cast — only download size remains)
· E4 parse-once cache for /scene+/scene.glb (~2× faster uploads) · E5 ML
fusion (merge readers' doors/windows; feed CubiCasa room types + icons into
scenes) · E6 plausibility-aware plan_health scoring. Phase-2 doctor: feedback
button. Parked v2: LoRA fine-tune, render baking, per-frame diffusion video.
Licensing before ANY paid tier: replace/disable CubiCasa (BY-NC), lawyer-check
TF2 (GPL) + SVD.
