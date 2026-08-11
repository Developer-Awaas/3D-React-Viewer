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

## Current state (11 Aug 2026)

Branch `fix/z-fighting` · baseline commit `2c16f6c` · Mac (no CUDA).

| Check | Value |
|---|---|
| `cd server && python -m pytest` | **389 passed, 1 skipped** |
| `npm run test` | **29 passed** |
| `npm run build` | clean |
| `python server/batch_eval.py` | **4/4 clean** — row detail in MAC-BASELINE |

## The three instruments

The drawing's own printed data is ground truth (§0.1). These three measure us
against it. **Never trade one for another without a written ruling.**

| Instrument | What it checks | FLOOR PLAN.pdf now |
|---|---|---|
| **R-8** built-up printed vs parsed | coverage — do we find the whole floor? | **98.8%** (1685 vs 1705); **ratchet 98.8** (raised 11 Aug), floor 68.0 pinned in `test_area_compare` |
| **R-2** room dims printed vs measured | sizes — is each room what the sheet says? | **96.0%** median over 7 rooms; below 80% is a Doctor FAIL |
| **footprint ≤ plot** | physics — a building cannot exceed its land | 1414 / 3371 sqft ✅ (printed plate is 1951) |
| **common area** | R-5/L-5/S-5 — lift+stair+lobby out of carpet | **213.4** vs printed 246 (86.7%) |
| **balcony area** | B-5 — open sides closed as spaces, own line | **310.6** — ONE region, and WRONG: the sheet's balconies are ~60 sqft of 4'0"/3'6" strips. No per-bucket instrument exists for it yet |

**Two of four plans FAIL R-2** and are parked, both recorded in
`ground_truth.json` with a "no improvements accepted below 80%" guard:
**GHATIKIA 58.6%** across 14 rooms (systematic under-segmentation) and
**FIRST FLOOR 31.1%** from a single matched label (a different disease —
R-2 cannot match that sheet's printed dimensions to rooms; not investigated).
BRICK WORK prints no room dimensions, so R-2 is silent there.

## Proven vs open

**Proven.** FLOOR PLAN's scale, from printed room dimensions across 6
independent rooms (golden re-baselined 113.9×35.6 → 95.2×29.8) · the sheet's
own opening schedule overrides our defaults (TG-5) · the printed area statement
read by OCR (R-8) · footprint from the outer wall ring, bridged jamb-to-jamb,
never dilated.

**Also proven.** R-5/L-5/S-5 — lift, staircase and lobby out of carpet into a
common-area line (Stage 2). B-1/B-4/B-5 — the space behind a rejected open face
is closed as a balcony SPACE, reported on its own line, and its open face is
never built as a wall (Stage 3). Both validated on FLOOR PLAN only.

**Open — the split, not the total.** Built-up is 98.8% right while its PARTS
are wrong in opposite directions: balcony 310.6 vs ~60 printed, carpet 842.9 vs
1370 printed. A per-face split was attempted 11 Aug and reverted (it swept
outside ground along the spurious 42/96 ft spans and cost 2.8 points of R-8) —
see §12. Next attempt must bound depth on the RESULTING region's short side and
eliminate the spurious spans first; `room_dims.printed_widths` is ready.
**We have no per-bucket instrument for balcony or common** — that is the real
gap, since the total guard cannot see a cancellation. GHATIKIA + FIRST FLOOR
R-2 failures. C-6 short-side column fix still pending.

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
