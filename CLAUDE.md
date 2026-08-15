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

## Current state (14 Aug 2026)

Branch `fix/z-fighting` · baseline commit `2c16f6c` · Mac (no CUDA).

| Check | Value |
|---|---|
| `cd server && python -m pytest` | **409 passed, 1 skipped, 2 failed** — both the KNOWN red ratchets (golden `snapped>=11` now 10; R-8 98.8 pinned vs 97.0). Untouched by instruction |
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

**TWO OF FOUR PLANS ARE NOW INSTRUMENTED** (15 Aug). **neelachala FIRST
FLOOR is PROMOTED**: R-2 **96.8% over 8 rooms**, ratchet pinned in
`test_room_dims.py::test_first_floor_r2_ratchet`, the 80% guard LIFTED. Its
31.1%/one-room verdict is withdrawn — the cause was a regex that could not read
`11'-5"`, not the sheet. **R-8 stays BLIND there** (it prints no area
statement), so its coverage is still unmeasured; only room SIZES are checked.
**Caveat:** its 2 balconies both sit in the LOWER plan block, and the view
splitter will change that count. Still parked: **GHATIKIA 58.6%** across 14
rooms, guard intact.
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
| **LOBBY BUG** | **NOT FIXED. THREE fixes tried and all REVERTED** — (1) collinear-bridge constraint, (2) end-cap exemption in the free-endpoint test, (3) both. Cause is now fully measured: the east jamb at (41.24, 0.00) is suppressed by its own 0.84 ft END CAP (= that wall's 10 in thickness). Classified all 258 suppressing neighbours on this sheet: **0 exact duplicates, 26 collinear continuations, 232 perpendicular** — of which only ~75 are cap-length (0.4/0.8/1.0 ft) and the rest are REAL perpendicular walls. Exempting caps makes the east jamb free, but FLOOR PLAN gets WORSE not better: R-8 97.0 -> 73.4, balcony line collapses to 0, lobby STILL absent — so freeing that jamb is necessary but far from sufficient, and something downstream of the bridge (the fill, or the balcony subtraction) is the real blocker. **Fill now instrumented** (12 Aug): `footprint` + `footprint_ext` are overlay layers, PNGs in `overlays/5,6,7`. The contour ENTERS the notch at the entrance's east jamb (41.2, -0.2), runs north to y=7.0, west along the lobby's north edge (33.3 -> 27.6, 7.0), and exits south at (27.1, 0.3) — so the lobby is a NOTCH in the outline and RETR_EXTERNAL traces into and out of it. It never crosses the 15.7 ft entrance. Common stays 23.6 vs printed 246. **Rahul rules on the fix on return; no further lobby attempts.** |
| **GHATIKIA — NOTATION IS FINE, THE SCALE IS NOT (15 Aug, measured)** | Metric reads correctly end to end: `2.31x1.37` m → 7.58 × 4.50 ft, tagged `unit=m`, 44 pairs, 14/14 rooms matched. **But the printed room dims imply ppf 7.14 (median, range 6.45–9.52) against the column-box 8.80 — a 19% scale overestimate.** At 7.14 its R-2 median goes **58.1 → 85.5**. So my 14 Aug reading was half wrong: the 0.812 MEDIAN is a scale error, and only the 0.106 SCATTER is the boundary disease — two diseases, not one. Its 6 anchored railing runs are **3 mirrored pairs** (the sheet draws 2 mirrored flats) of straight single strokes; the nearest parallel wall behind the 8.24 ft south-edge run is **21.67 ft** away (its own lines sit at 0.09 and 0.65), so they enclose nothing at any printed width (2.99–3.51 ft). **Not a balcony detection failure — there is no balcony-shaped pocket there.** No fixes made. |
| **1-SIDED BALCONIES + LABELLED DIM PAIRS — BUILT (15 Aug)** | Three fixes, one variable each. (1) `printed_widths` now reads `<label> <W x H>` as well as `<ft-in> WIDE`, taking the SHORT side; **and the pair regex now allows the `11'-5"` hyphen**, which FLOOR PLAN never uses and FIRST FLOOR always does. (2) B-2a no longer requires a turn — §10's own 1-sided case — and a straight run's depth is measured to the **wall behind it** (its bbox short side is 0.00, so every 0-turn run scored depth 0 and could never match). (3) `railings.pocket_ft` extends a 1-sided run's rectangle to that wall, or no area can form. **FLOOR PLAN untouched: R-8 97.3, R-2 97.0, balcony 50.8, carpet 1203.5, footprint 1705.3 ≤ 3371; the 4.91 ft lobby run is still rejected.** Results: **FIRST FLOOR R-2 31.1 → 96.8** (rooms checked 1 → 8) and **balcony 0 → 67.9 sqft in 2 regions** (depths 3.91 and 4.40 against printed 4'-0" and 4'-6"; 33.7 sqft against a printed `9'-7" X 3'-6"` = 33.5); GHATIKIA widths `[]` → `[2.99, 3.35, 3.41, 3.51]` but still **0 of 38** runs classify (6 anchored, all bundles of parallel strokes); BRICK WORK unchanged at 0 (prints no width). Reported, not accepted, on all three. |
| **ROOT BLOCKER — MEASURED, and it is TWO problems not one (15 Aug)** | (1) **FIRST FLOOR is not one building**: the sheet carries **two complete plans stacked**, separated by an **8 ft empty band at y 98–108 ft** (blocks 0–98 and 108–182); `38'-3"` overall is printed twice (y 97.4 and 109.4), room labels + dims appear in both halves, and `FIRST FLOOR PLAN` titles the lower one at y 185.9. Both draw on the SAME layers (`0`, `chhaja`, `a-text`) — only POSITION separates them. **Multi-view problem, different fix from an anchor problem.** (2) **The geometry reader IS a usable anchor**: as the trusted set it takes FIRST FLOOR's `ends_on_wall>=2` from 0 to **37 of 50 runs** (GHATIKIA 6 of 38) — but **still 0 classify**, because the second gate fails: **47 of 50 runs have 0 turns** (42 are a single stroke), and on GHATIKIA **all 38** have 0 turns. Those sheets draw balconies as straight 1-sided runs, not the turning 3-sided run FLOOR PLAN uses. The anchor was only half the blocker. |
| **FIRST FLOOR PRINTS BALCONY DIMS WE DO NOT READ (15 Aug)** | It prints `balcony 9'-7" 3'-6"`, `11'-2" 4'-0"`, `6'-4" 4'-11"` — real balcony widths — but `room_dims.printed_widths` only matches the `<ft-in> WIDE` form, so it returns `[]` and B-5 is blind there. **The width is on the sheet; the reader is looking for the wrong shape.** Measured, not built. |
| **GHATIKIA R-2 58.6 — NOT one disease, and NOT scale (15 Aug)** | Side ratios vs printed, with FLOOR PLAN as the control: **FLOOR PLAN 0.982 ± 0.007**, GHATIKIA **0.812 ± 0.106** — 15× the scatter, range 0.73–1.08. A scale error or a uniform wall-band inset would be TIGHT like the control; this is per-room boundary error. Composition: 1 room is a 3.24× merge (the whole flat interior, holding **48** of the sheet's 256 geometry spans), 2 rooms measure 1.01–1.08 (correct), 11 measure 0.73–0.91 on BOTH sides. Partially attributable to the root cause — **256 geometry-signature spans vs 24 named-layer segs (91% unnamed)**, and the signature admits any parallel pair 3–11 in apart, so 56 spans (22%) land inside printed rooms. **The systematic 0.81 shrink on the other 11 is NOT explained by that** (only 4 rooms hold any interior span) and stays open. |
| **FLAT-2 MISALLOCATION — KNOWN, QUANTIFIED, HELD (15 Aug)** | Balcony reads **50.8, not ~83.9**, because flat-2's 32.4 sqft pocket (x 62.3–72.0, y 14.1–17.5, depth 3.37 vs printed 3'6") sits INSIDE the 233.4 sqft `dining` polygon (x 54.0–76.0, y 0.9–17.3) — so it is currently counted in **CARPET**, not balcony. Separating it needs the railing to become a room BOUNDARY, which moves carpet: that is **one variable on its own** and is held. Rahul's ruling 15 Aug: accepted and held, not a defect to fix opportunistically. |
| **BALCONY BLIND ON 3 OF 4 SHEETS — fallback MEASURED, NOT BUILT (15 Aug)** | Balcony is structurally 0 wherever the sheet prints no balcony width. Measured a fallback band from the sheet's own room dims: **"shallower than any habitable room" ADMITS FLOOR PLAN's 4.91 ft false positive** (band 6.33) and is disqualified; "shallower than any printed room at all" (band **4.50**, a bathroom) rejects 4.91 ✅ and keeps both real balconies ✅ — but **rescues no blind sheet**: BRICK WORK reads **0 of 10** printed room dims so no band exists there, and GHATIKIA/FIRST FLOOR pass **0 candidate runs** anyway. The blind sheets are blind for the same root cause, not for want of a band. NOT WIRED. |
| **BALCONY FROM THE DRAWN EDGE — BUILT AND WIRED (14 Aug)** | `foot_ext − foot` DELETED. Each railing run classified `railing` is closed against its wall, filled, wall pixels subtracted, room pixels subtracted (no double count); scratch mask only, so the open face is still never built as a wall (B-4). **FLOOR PLAN: balcony 42.7 (artefact) → 50.8 measured, built-up 1650.7 → 1658.8, R-8 96.8 → 97.3**; carpet 1203.5, common 23.6, rooms 13, R-2 97.0, footprint 1705.3 ≤ plot 3371 all unchanged. **flat-2 (32.4 sqft) is NOT yet separated** — its pocket lies inside the 233.4 sqft `dining` polygon (x 54.0–76.0 vs balcony x 62.3–72.0), i.e. it is currently counted in CARPET. Splitting it needs the railing to become a room BOUNDARY, which is the deferred step and will move carpet. **GHATIKIA lost its 354.5 sqft artefact balcony** (bu 2571.2 → 2216.7, rooms 16 → 14) — no instruments there, reported not accepted. |
| **B-5 BALCONY FILTER — depth vs PRINTED width (14 Aug)** | `railings.classify`: ends_on_wall≥2 AND turns≥1 AND enclosed depth matches a printed balcony width within 0.25 ft. FLOOR PLAN 3/5 → **2/5** — the 12.33 ft lobby run (depth 4.91, matching neither 4'0" nor 3'6") is REJECTED, killing the 37.3 sqft false positive. BRICK WORK 3/27 → **0/27**: it prints no balcony width, so nothing is claimed (no numbers moved there). GHATIKIA 0/38, FIRST FLOOR 0/50 unchanged. 7 tests in `test_railings.py`. |
| **CANVAS EXTENSION — BUILT, one variable (14 Aug)** | The raster was exactly the wall extent, so flat-1's balcony at **x −3.92..0.00 ft** was off-canvas and unmeasurable. It now extends to cover traced RAILING RUNS (never the page, never the plot — dash-dot is dropped before a run exists). FLOOR PLAN 4865 → **5065 px** (+3.93 ft west); BRICK WORK bound 10.5–29.4 ft is inside its wall extent → unchanged; GHATIKIA + FIRST FLOOR classify 0 runs → no bound, unchanged. Frame (`x0`/`y0`/`d_ft`) untouched. `DRISHTI_CANVAS_EXT=0` reproduces the old canvas. **One number moved and is fully attributed**: footprint 1709.5 → 1705.3, built-up 1654.6 → **1650.7**, R-8 97.0 → **96.8** — the footprint's west edge goes x −0.20 → −0.06 ft, 0.14 ft over the 29.8 ft side = 4.2 sqft, because a 10 px pad had the west face abutting the canvas edge where OpenCV shields it from the erode. **The old number was the artefact.** Not wired to balcony. |
| **BALCONY FEED-IN — ATTEMPTED, REVERTED (14 Aug)** | Railing runs as room boundaries + balcony as the pocket behind them. **FLOOR PLAN degraded**: balcony 42.7 -> 0.0, built-up 1654.6 -> 1251.8, R-8 97.0 -> ~73. Root cause: **flat-1's balcony is at x −4..0 ft, west of the linework origin `x0`** — outside the raster, so no pocket can ever form there. `foot_ext − foot` survives only because its bridges reach outside the extent. **Next: extend the raster to cover geometry outside the wall extent (balconies, projections), then re-run the feed-in.** The tracer itself is correct and stays wired additively. |
| **B-2a RAILING TRACER — BUILT AND WIRED, additive (14 Aug)** | `server/railings.py` (pure) + `scene.railings`. Pipeline: thin pairs -> drop dash-dot families (constant-pitch collinear strokes = plot boundary) -> dedupe same-edge centrelines -> trace runs through turns -> classify. **Acceptance met from tracer output**: flat-1's balcony = **20.65 ft, 3 segs, 2 turns, 2/2 ends on wall, 3-sided**. Classifier `ends_on_wall>=2 AND turns>=1` correctly REJECTS the 27.33 ft stair run (0 turns, 0 ends) and the 15.16 ft lobby line (0 turns) — the drafting error. Runs per sheet: FLOOR PLAN 3/5, BRICK WORK 3/27 (that sheet draws 3 balconies), **GHATIKIA 0/38 and FIRST FLOOR 0/50 — false negatives from the SAME structural constraint as the position gate: no trusted walls, so `ends_on_wall` is always 0**. Failing runs are emitted TAGGED `unclassified`, never discarded. **Feeds nothing** — no area, room or ring number moved. |
| **RAILING = CONTINUITY, and the dash-dot signature (14 Aug)** | B-2a ruling: trace the thin double line as a connected RUN, not per edge. Measured on FLOOR PLAN: flat-1's balcony is **ONE 20.6 ft run (13.0 + 3.8 + 3.8) with 2 turns**, both ends on the building wall at x=0 = railing on 3 sides. **Plot boundary separates cleanly by gap structure**: 11 collinear strokes of 6.3-6.7 ft at a **constant 3.1 ft gap** (dash-dot) vs a railing's **single unbroken stroke** per line. This beats length and third-line, both of which failed at the short end. |
| **CONTRADICTS — new certainty mark** | The drawing states something a building cannot be = a DRAFTING ERROR, not a parsing gap. FLAG and ASK, never auto-correct. Worked example (Rahul-confirmed): FLOOR PLAN's lobby is a 15.7 ft opening in an external wall on a first floor with no street entrance — in reality a wall with a window. **CE-4 narrowed**: the lobby is enclosed in reality, so covered-but-not-enclosed now rests on balconies alone; CE-4 stays open. |
| **RAILING RULE — LENGTH+THIRD-LINE HAS ZERO MARGIN AT THE SHORT END (14 Aug)** | Shortest confirmed railing edge is **3.8 ft** (flat-1's balcony ends). Plot-boundary strokes measure **3.0, 3.8, 6.3 x10, 6.7 x2 ft** — so a 3.8 ft boundary stroke sits exactly on the shortest railing. Length gives NO margin there. Worse, the third-line test kills that same railing: the plot boundary runs 0.5–1.5 in beside flat-1's south end railing, so it reads as "has a third line". **The rule works on long edges and fails on balcony ends.** Both need a further signal before any build. |
| **RAILING SIGNATURE — measured, not built (14 Aug)** | Railing = thin double line, gap **1.9–3.0 in**, **9.5–15.2 ft** long, **no third parallel line** within a wall thickness. Door-leaf mispairs: gap looks the same but length is **~2.5 ft** and **8 of 8** have the third line (the second wall face) — Rahul's mispairing theory CONFIRMED on length and the third-line test; **overlap fraction disproved** (1.00 for every class, because the leaf sits wholly within the wall face's span). Ruling recorded in §10/B-2: both gaps are railings, type is USER ENTRY. **Position gate is NOT the answer for the plot boundary**: it passes 12 of 14 `boundary limit` thin pairs and REJECTS flat-1's genuine railing (it sits at x −4..−2, outside the trusted wall extent). |
| **PHASE 1 (a) `ar stairs` — RUN AND REVERTED (14 Aug)** | One variable, FLOOR PLAN judged. All 11 stair lines passed the gate and were admitted — and **FLOOR PLAN degraded**: R-8 97.0 -> 78.6, built-up 1654.6 -> 1340.3, rooms 13 -> 12, **balcony 42.7 -> 0.0**, wall+circ 384.8 -> 113.2 (carpet, common and R-2 all unchanged). Footprint GREW 1710 -> 1798 and bridges went 8 -> 19 with a single 72 ft span rejected. So the stair walls close the ring so much that `foot_ext` collapses onto `foot` and the balcony line vanishes — **the same failure mode as the end-cap attempt, and the same root cause: balcony is a mask difference (§0.1), so any ring improvement destroys it.** Attribution is now certain: attempt 1's damage was `ar stairs`, not layer `0` and not the band. Reverted. **Nothing can be admitted until balcony stops being `foot_ext - foot`.** |
| **POSITION GATE — FIXED AND PROVEN, NOTHING ADMITTED (14 Aug)** | `paired_extent()` + `inside_extent()`: the building extent is now computed from the TRUSTED walls ALONE, before any candidate is seen (the old gate recomputed it from a set containing the candidates, so FLOOR PLAN's 13 layer-`0` lines paired with each other, extended the "building", and passed). Proven in isolation: FLOOR PLAN rejects those 13 lines at y −13.0..−7.9 ✅ and passes `ar stairs` (11 lines, x 33.2–41.2, y 7.1–14.6 = the lobby's north wall) ✅; BRICK WORK rejects 23 layer-`0` lines at x −7.1..3.8 ✅. **STRUCTURAL LIMIT FOUND:** GHATIKIA's trusted extent is a 0.3 ft sliver (x 1.4–50.5, y 13.1–13.4) so it rejects 744 of 779 real lines, and FIRST FLOOR has **no trusted paired walls at all**, so the gate cannot be computed and everything passes — which is exactly how it inflated to 47.6×185.3 ft. **The sheets that most need admission are the ones with no trusted base to gate against.** 4 unit tests pin this. Next: (a) `ar stairs` alone, (b) layer `0` alone, (c) band 3-11→3-18 alone — but only on sheets where the gate is computable. |
| **PHASE 1 ATTEMPT 1 — REVERTED (14 Aug)** | Conservative admission (layer-name hint + position: `ar stairs`, layer `0`; `hatch` left out; band widened 3-11 -> 3-18 in) **degraded FLOOR PLAN**: R-8 97.0 -> 78.6, built-up 1654.6 -> 1340.3, rooms 13 -> 12. GHATIKIA collapsed to 5.8x0.7 ft / 0 rooms; FIRST FLOOR inflated to 47.6x185.3 ft with footprint 7614 sqft on a 2455 sqft plot (physics violation). Reverted, not tuned. **Cause not yet isolated** — on FLOOR PLAN, layer `0` carries 13 lines at y −13.0..−7.9 (OUTSIDE the building, below it) which the position gate should have caught but the widened 3-18 in band admitted first. Next: admit ONE layer at a time and measure, and check whether the band widening (not the layer admission) is what broke it. |
| **REGISTRATION ANCHOR** | Landed 14 Aug and green: `test_overlay.py::test_registration_anchor_does_not_drift` pins FLOOR PLAN's south-wall east jamb (41.24, 0.00 ft) at (2497.2, 2600.3) px @110dpi ±2. The overlay can no longer drift silently. |
| **ANCHOR FOUND (measured, not wired)** | The geometry reader's own output is a legitimate signature-derived anchor for the sheets with no trusted named layers. GHATIKIA: named extent is a 0.3 ft sliver (y 13.1-13.4) but the **geometry extent is x 0.0-80.0, y 0.0-47.8 ft = the real building**; FIRST FLOOR: named extent NONE, **geometry extent x 0.0-41.6, y -3.2..177.3 ft** — right in x, but 177 ft deep — **CORRECTED 15 Aug: that is TWO COMPLETE PLANS stacked on one sheet**, not wings and not sections, so the extent spans two buildings and is NOT a safe gate there until a view splitter runs. Gating non-named lines against the geometry extent rejects only 0% (GHATIKIA) and 2% (FIRST FLOOR), so on its own it admits almost everything. GHATIKIA's 35 sliver-passing lines are a 5 ft x 1.7 ft cluster at x 12.7-33.8, y 12.4-14.1 — interior partition fragments, not the building. |
| **LAYER NAMES LIE — PHASE 1 REORDERED** | Measured 12 Aug across all 4 sheets: wall-signature pairs (W-1/W-3: parallel, 3-18 in apart, >=2 ft) sitting on EXCLUDED layers total **454 ft (BRICK WORK) / 225 ft (FLOOR PLAN) / 786 ft (GHATIKIA) / 1477 ft (FIRST FLOOR)**. The two neelachala sheets read **22.8 ft and 0.0 ft** of wall from their named layers — they are parsed almost entirely by the geometry fallback, and nearly all their real wall sits on layer `0`. Four symptoms, one cause: balconies on `column`/`furniture`, tile grid on `ar wall`, the lobby's north wall on `ar stairs`, and whole buildings on `0`. **Phase 1 is therefore not "classify walls" — it is "stop trusting layer names".** May dissolve CE-4: read by signature and the lobby may be properly bounded. |
| **§10.1 COVERED BUT NOT ENCLOSED** | New spec category (12 Aug): roofed spaces inside the building line but open on one+ sides — lobby, balcony, porch. Part of the building for area; identified by printed label/dimension, not by wall enclosure. **CE-4 is OPEN and is Rahul's next ruling**: what makes such a space "inside the building line" with no wall on two sides. FLOOR PLAN's lobby (printed 15'8"x6'2" = 96.6 sqft, counted in the sheet's 246 common) is the worked case. |
| **BALCONY = MASK DIFFERENCE — now proven an ARTEFACT** | `foot_ext − foot` never measured a balcony: flat-1's is off-canvas, so 42.7 sqft is the reach of the ring bridging outside the raster. Direct read once the canvas covers it (computed, NOT wired): flat-1 **3.92 × 13.15 = 51.5 sqft** (printed width 4'0" ✅), flat-2 **3.37 × 9.62 = 32.4** (printed 3'6" ✅), **total 83.9** vs the artefact's 42.7. The known false positive at (25.58, 24.06) would add **37.3** if not filtered. Design flaw recorded in PLAN-READING-RULES §0.1 + §12: balcony area is `foot_ext - foot`, so it measures mask disagreement, not balconies (42.7 -> 0.0 from one eligibility change, taking 400 sqft of built-up with it). Must eventually be read from the DRAWN open edge (B-1/B-4). Not fixed. |
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
