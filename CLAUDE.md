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
| `cd server && python -m pytest` | **405 passed, 1 skipped** |
| `npm run test` | **29 passed** |
| `npm run build` | clean |
| `python server/batch_eval.py` | **4/4 clean** — row detail in MAC-BASELINE |

## Work streams

**Numbers** (10-11 Aug) — done to the point where the totals are right and the
splits are not; see open. **Geometry** (12 Aug, phases 0-7) — **Phase 0 done**:
the wall-overlay instrument (`/overlay` + `WallOverlay.tsx`), which draws the
parsed geometry over the original sheet, including the DISCARD pile. It found a
live regression on its first run (columns 26 -> 0, fixed 12 Aug). Registration
verified visually at rotation 270 (FLOOR PLAN) and rotation 0 (BRICK WORK), and
confirmed by Rahul. Single-layer PNG export ("Export one layer" -> click a
chip); four reference exports live in `overlays/`.

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
| **wall overlay** | geometry — is a wall in the right PLACE? | Phase 0 instrument, `POST /overlay`. Registration verified visually + `test_overlay.py` |

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

## OPEN — half-done, read this first (12 Aug, end of day)

| item | state |
|---|---|
| **LOBBY BUG** | **NOT FIXED.** Cause narrowed twice: not the diagonal bridge (that fix was tried and REVERTED — it moved GHATIKIA/FIRST FLOOR and did not restore the lobby). Real cause: the 15.7 ft entrance gap (x 25.6→41.3 at y≈0) is never a CANDIDATE pair in `_free_ring_endpoints` — one of its two jambs fails the "free endpoint" test (an endpoint is free only if no other endpoint sits within `join_tol`). Next action: work out which endpoint is suppressed and why. Common area is 23.6 vs printed 246 until this is fixed. |
| **Queue items 2, 3, 4** | **NOT STARTED**, deliberately. Item 2 (pin common at 246) would be a red test while the lobby bug is live; items 3-4 (page-unit constants) move numbers on sheets whose instruments are blind, and the lobby fix will move them again. |
| `test_corpus_golden::test_floor_plan_golden` | **FAILS** — `snapped >= 11`, now 10. Doors are still 12. Golden NOT touched, by instruction. |
| `test_area_compare` R-8 ratchet | **FAILS** — 97.0 vs pinned 98.8. Not re-baselined, by instruction. |

**ROOT CAUSE FOUND (12 Aug), FIXED for walls.** `BORDER_MAXLEN_PT = 900 pt`
drops any wall-layer line longer than 900 POINTS — a page-unit constant, the
same class of bug as the column tolerance. At FLOOR PLAN's scale that is 31.6
ft, so its **54 ft south external wall (two `ar wall` lines, 0.83 ft = 10 in
apart) is discarded before parsing**; 11 wall-layer lines are dropped on that
sheet. Replaced by `keep_structural_lines` (pairing, not length: a line survives at
any length if it has a parallel partner 3-18 in away; an unpaired line only if
it lies inside the paired extent — BRICK WORK's site boundary is a 39 ft
DIAGONAL on a layer called `wall`). Still live at three other call sites
(`_text_scale`, `_overall_dims`, `wall_gap_pairs`). That single cap explained
the open south side, the 42/96 ft spurious ring
spans, the 300 ft footprint perimeter vs 512 ft wall contour, and the 40 ft
diagonal on the balcony polygon. The cap is 17 ft on BRICK WORK, 102 ft on
GHATIKIA, 158 ft on FIRST FLOOR — i.e. it bites hardest on the sheets drawn at
the largest scale, arbitrarily.

**Open — geometry (Phase 1 next).** The outer wall ring is ONE mask component
but is open in 12 places (8 bridged + 4 rejected spans), and its contour is
512.6 ft against a 300.1 ft footprint perimeter because it weaves in and out of
every gap. Both FLOOR PLAN balconies are drawn almost entirely OFF the wall
layer (4 and 16 `ar wall` lines within 8 ft, out of 503 and 646 lines) — they
are read and discarded, not missing from the PDF.

**Open — the split, not the total.** Built-up is 98.8% right while its PARTS
are wrong in opposite directions: balcony 310.6 vs ~60 printed, carpet 842.9 vs
1370 printed. A per-face split was attempted 11 Aug and reverted (it swept
outside ground along the spurious 42/96 ft spans and cost 2.8 points of R-8) —
see §12. Next attempt must bound depth on the RESULTING region's short side and
eliminate the spurious spans first; `room_dims.printed_widths` is ready.
**We have no per-bucket instrument for balcony or common** — that is the real
gap, since the total guard cannot see a cancellation. GHATIKIA + FIRST FLOOR
R-2 failures. C-6 short-side column fix still pending — the column ACCEPTANCE
band now uses the short side, but `_scale_ppf` still derives ppf from the long
side. **W-2 measured AND located** (gap-class overlay layers): 9-11 in = the outer
envelope (11 of 18 on the boundary), 4-5 in = internal partitions, and
FLOOR PLAN's 12 in cluster is **fixture/tile linework inside the two toilets
and the lift** — 25 of 28 fall inside a room, 0 near a column, visually a dense
grid in the toilet cubicles. It is not a wall class. No spec change made: a
histogram says a cluster exists, not what it is. **P1 (repetition at fixed
pitch) measured**: at a 1.5 ft radius, 96% of the 12 in tile pairs have a
parallel neighbour vs 28% of real external walls — strongly indicative but NOT
a clean separator on its own (it would misflag ~30% of real walls). A §2
amendment is drafted and awaiting Rahul's approval; nothing written to the spec.

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
