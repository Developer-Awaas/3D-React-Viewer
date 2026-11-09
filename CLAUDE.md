# CLAUDE.md — Drishti, single entry point
<!-- Read me first. Then PLAN-READING-RULES.md (how a drawing must be read)
     and MAC-BASELINE-10AUG.md (the numbers that must not move).
     Update this file at the END of every task, in place. Never a v2. -->

## What Drishti is

A web app that turns a CAD floor-plan PDF into a walkable 3D building with
photoreal AI renders, RERA area statements, Vastu analysis and ₹ cost
estimates. India-first proptech. Founders: **Saswat & Amit**
(awaas.ai.dev@gmail.com). Stack: React+TS+Vite+react-three-fiber (dark glass,
orange neon, Playfair italics) · FastAPI in `server/` · PyMuPDF vector parsing ·
tesseract OCR · CubiCasa + TF2DeepFloorplan ML readers · SDXL+ControlNet renders.

## The 7 standing rules (never break)

1. Write code directly to disk, never chat-only. 2. Unit-test every unit before
production; full suite + build before delivery. 3. Explain every new command in
layman's terms. 4. NEVER touch the landing page (`LandingHero.tsx`,
`landing.css`). 5. Web-app only; beautiful + accurate output, keep the theme.
6. GENERAL rules only — no per-plan hacks; corpus-validate every parser change;
if any plan regresses, STOP and report. 7. Claude never pushes to GitHub and
never handles tokens/passwords.

## Working agreement (DRISHTI-WORKING-AGREEMENT.md)

- Claude builds, edits, runs tests. **Rahul** does all git push, merges, deploys.
- Write a short plan first, get it approved, then build. One cause per branch.
- **After any change, all four:** `pytest` · `python server/batch_eval.py` ·
  `npm run test` · `npm run build`.
- Any batch_eval number that moves must be explained **in feet or rupees**
  before it is accepted. Never edit a golden to make code pass. If a number
  moves unexpectedly: **STOP and report**, do not self-approve.
- Browser-check anything visual; source-level proof is not enough.
- **Dry run after building, before reporting** — collisions (incl. later
  phases), contradictions with PLAN-READING-RULES, silent movement, and
  assumptions. One line each, each with a data point (number / file:line /
  measured value). A serious collision means STOP, not work around.
- **Update this file at the END of every task, in place, before reporting.**

## Where everything lives

- `PLAN-READING-RULES.md` — the reading spec, single source of truth. §0.1 is
  the verification law (printed data wins · re-baselining · units · gap ≤ wall ·
  footprint ≤ plot · the 444 lock). Every change logged in §12.
- `MAC-BASELINE-10AUG.md` — the four baseline numbers and why each moved.
- `plans/ground_truth.json` — per-plan truth and rejections. **Mode 444 on
  purpose**; unlock only for an authorised re-baseline, restore 444 after.
- Engine `server/pdf_vector.py` · areas `area_statement.py` + `area_compare.py`
  (R-8) · `room_dims.py` (R-2) · `opening_schedule.py` (TG-5) · doctor
  `plan_doctor.py` · API `main.py` · renders `visualize.py`.
- `docs/` — HANDOFF · AUDIT-2026-07-22 · FIXES · DEPLOY-GPU · SCENE_SCHEMA ·
  LEARNINGS (Plan Doctor's growing memory, one line per parse).

## Run & test

Backend: `cd server && source venv/bin/activate && uvicorn main:app --port 8000`.
Frontend: `npm run dev` (5174 here; 5173 is taken). tesseract is installed via
brew and is what makes the OCR-dependent reading work — `DRISHTI_OCR=0` disables
it and reproduces the pre-OCR baseline.


## Current judged numbers (the golden four — do not move these without a ruling)

As of the last implied-faces measurement (30 Oct 2026), unchanged for weeks:

| sheet | footprint sqft |
|---|---|
| FLOOR PLAN | **1796.8** |
| FIRST FLOOR | **4472.1** |
| GHATIKIA | **1738.4** |
| BRICK WORK | **1247.1** |

If any of these four numbers moves after a change, **STOP and report** — do not
self-approve. Full history and every other instrument (R-2, R-8, M-1, anchors,
carpet, common, doors, columns) per sheet, per date, lives in the dated log
files indexed below — most recent first: `docs/DRISHTI-LOG-SEP15-OCT.md`.

## READ THIS FIRST on any result (standing protocol, 2 Sep 2026, Rahul)

**Before any number, read four fields.** They say which algorithm produced the
number, at what scale, and whether anything can contradict it:

| field | question it answers |
|---|---|
| `scale_verified` / `refusals[]` | **is the scale backed by anything printed?** If false, no ft/sqft/₹ below is usable |
| `meta.route` | layers or geometry, and which of the invisible floors were reached |
| `meta.parse_pass` | which of the self-re-entrant passes built this scene |
| `meta.plot_source` | printed · user · unknown — `footprint ≤ plot` is blind when unknown |

## Index — which file to read for which kind of work

This file is the 1-2 page essentials. Everything else that was ever measured,
built, reverted or ruled on is preserved verbatim in the files below — nothing
has been deleted, only moved out of the file that is loaded on every build.

| file | read it when |
|---|---|
| `PLAN-READING-RULES.md` | you are reading or changing how a PDF is interpreted — this is the single source of truth, §0.1 is the verification law |
| `DRISHTI-WORKING-AGREEMENT.md` | you need the full working agreement (who does what, dry-run checklist, environment notes) — the version here is condensed |
| `MAC-BASELINE-10AUG.md` | you need the original four baseline numbers and why each moved |
| `plans/ground_truth.json` | you need per-plan truth data and rejection evidence (mode 444 — do not unlock without an authorised re-baseline) |
| `docs/DRISHTI-PROJECT-STATUS.md` | you want the project's status as of 28 Aug 2026 — work streams, the three instruments, proven-vs-open, the half-done OPEN items from that period |
| `docs/DRISHTI-LOG-AUG31-SEP3.md` | you are touching plan regions, the two-pass/wing-split ambiguity, the 3D defect sheet, staircases, or the cold-sheet plausibility checks — dated entries 31 Aug–3 Sep 2026 |
| `docs/DRISHTI-LOG-SEP4-5.md` | you are touching ducts, free-text area statements, poché (filled walls), or the M-2 model-vs-parse check — dated entries 4–5 Sep 2026 |
| `docs/DRISHTI-LOG-SEP5-7.md` | you are touching the wing/region frame, `meta.glb`, the DHAL stilt-parking sheets, or the envelope/column-reader investigation — dated entries 5–7 Sep 2026 |
| `docs/DRISHTI-LOG-SEP7-8.md` | you are touching columns (seven rejected discriminators), the Vastu north-arrow reader, or chhajja — dated entries 7–8 Sep 2026 |
| `docs/DRISHTI-LOG-SEP15-OCT.md` | you are touching lifts/staircases, the implied-wall-face work, or `wall_modes` — dated entries 15 Sep–30 Oct 2026 |
| `docs/HANDOFF.md`, `docs/AUDIT-2026-07-22.md`, `docs/FIXES.md`, `docs/DEPLOY-GPU.md`, `docs/SCENE_SCHEMA.md`, `docs/LEARNINGS.md` | general handoff, audit, fix history, GPU deploy, scene schema, Plan Doctor's running memory |

Engine `server/pdf_vector.py` · areas `area_statement.py` + `area_compare.py`
(R-8) · `room_dims.py` (R-2) · `opening_schedule.py` (TG-5) · doctor
`plan_doctor.py` · API `main.py` · renders `visualize.py`.
