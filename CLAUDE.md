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

## Current state (22 Aug 2026)

Branch `fix/z-fighting` · baseline commit `2c16f6c` · Mac (no CUDA).

| Check | Value |
|---|---|
| `cd server && python -m pytest` | **481 passed, 1 skipped, 0 failed** — green. The two FIRST FLOOR goldens were **RE-DERIVED 22 Aug on Rahul's ruling**, not adjusted to pass: they recorded a misunderstanding (one block pinned as the whole building, its 38'-3" × 64'-2" block dimension called "the plot", and the other block called a "door-schedule/legend block" — measured false). Evidence + superseded values in `ground_truth.json` → `envelope_rebaseline_2026_08_22` |
| 3D coherence (**M-1**) | **BUILT + DENOMINATOR CORRECTED 19 Aug; in the judged set, ceiling PROVISIONAL 1.35 awaiting ruling.** Net `walls_poly` material / what `_mask()` actually paints (pair rectangles ∪ unpaired survivors at the sheet's median wall), per wing. **FLOOR PLAN 1.05 · BRICK WORK 1.06 · FIRST FLOOR 1.10 · GHATIKIA 1.15**; the 19 Aug broken build reads **3.00**. `M-1 − 1.0` is the corner closure's contribution in feet — that is how the last fault was located |
| pair-rectangle walls | **SHIPPED 19 Aug at the third attempt** (two reverts: closure to the neighbour's far bound, then closure applied to unpaired survivors that were never clipped). FLOOR PLAN **short steps 195 → 4, outline points 290 → 96, wall meshes 22 → 15, zero plan-wide meshes**, volume 98.6 → 96.2 m3. Every judged number identical on all four sheets |
| `npm run test` | **32 passed** |
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
| **ROOT BLOCKER — MEASURED, and it is TWO problems not one (15 Aug)** | (1) **FIRST FLOOR is ONE BUILDING WITH TWO BLOCKS** (corrected by Rahul 15 Aug; it was read as two stacked plans and it is not). An 8 ft **real** gap at y 98–108 ft separates a top block (39.0 × 96.7 ft, **3 flats**) from a bottom block (41.6 × 70.8 ft, **2 flats**) — five flats on one floor — and the first-floor slab bridges the gap as a private terrace, marked by the diagonal hatch: **20 lines cross the band and 11 span it**. `38'-3"` is printed twice because each block carries its own. **The wing splitter drops one block: 3 of 5 flats missing. No view splitter is to be built.** (2) **The geometry reader IS a usable anchor**: as the trusted set it takes FIRST FLOOR's `ends_on_wall>=2` from 0 to **37 of 50 runs** (GHATIKIA 6 of 38) — but **still 0 classify**, because the second gate fails: **47 of 50 runs have 0 turns** (42 are a single stroke), and on GHATIKIA **all 38** have 0 turns. Those sheets draw balconies as straight 1-sided runs, not the turning 3-sided run FLOOR PLAN uses. The anchor was only half the blocker. |
| **FIRST FLOOR PRINTS BALCONY DIMS WE DO NOT READ (15 Aug)** | It prints `balcony 9'-7" 3'-6"`, `11'-2" 4'-0"`, `6'-4" 4'-11"` — real balcony widths — but `room_dims.printed_widths` only matches the `<ft-in> WIDE` form, so it returns `[]` and B-5 is blind there. **The width is on the sheet; the reader is looking for the wrong shape.** Measured, not built. |
| **GHATIKIA R-2 58.6 — NOT one disease, and NOT scale (15 Aug)** | Side ratios vs printed, with FLOOR PLAN as the control: **FLOOR PLAN 0.982 ± 0.007**, GHATIKIA **0.812 ± 0.106** — 15× the scatter, range 0.73–1.08. A scale error or a uniform wall-band inset would be TIGHT like the control; this is per-room boundary error. Composition: 1 room is a 3.24× merge (the whole flat interior, holding **48** of the sheet's 256 geometry spans), 2 rooms measure 1.01–1.08 (correct), 11 measure 0.73–0.91 on BOTH sides. Partially attributable to the root cause — **256 geometry-signature spans vs 24 named-layer segs (91% unnamed)**, and the signature admits any parallel pair 3–11 in apart, so 56 spans (22%) land inside printed rooms. **The systematic 0.81 shrink on the other 11 is NOT explained by that** (only 4 rooms hold any interior span) and stays open. |
| **FLAT-2 MISALLOCATION — KNOWN, QUANTIFIED, HELD (15 Aug)** | Balcony reads **50.8, not ~83.9**, because flat-2's 32.4 sqft pocket (x 62.3–72.0, y 14.1–17.5, depth 3.37 vs printed 3'6") sits INSIDE the 233.4 sqft `dining` polygon (x 54.0–76.0, y 0.9–17.3) — so it is currently counted in **CARPET**, not balcony. Separating it needs the railing to become a room BOUNDARY, which moves carpet: that is **one variable on its own** and is held. Rahul's ruling 15 Aug: accepted and held, not a defect to fix opportunistically. |
| **THE BAND RULE SEPARATES BOTH CASES (15 Aug, measured)** | *An empty band splits a sheet only if NOTHING crosses it.* **GHATIKIA is the two-views sheet I said the corpus lacked** — FIRST FLOOR left, TYPICAL FLOOR (2nd/3rd/4th) right, differing only in the top-left room: vertical band **x 38–42 ft, ZERO crossings → SPLIT**. neelachala FIRST FLOOR: horizontal band y 98–108, **11 terrace-hatch lines spanning → JOINED**. Same test, opposite answers, nothing tuned. **GHATIKIA is currently parsed as ONE building across both plans**: every room appears twice at Δx ≈43.5 ft, its 80.0 × 47.8 ft extent is two ~40 ft plans side by side, and the **530.5 sqft blob that wrecks its R-2 straddles the band (x 35.1–61.1)**. Its 19% scale error is NOT explained by this — that comes from the column box, independent of extent. |
| **10% PROPORTIONAL TOLERANCE + UTILITY ADMITTED (16 Aug, built)** | Tolerance is now **10% of the printed width**, replacing the fixed ±0.25 ft (§10.2 D-4 basis gap; **provisional** — a consistent gap would mean a basis correction instead, which is the better fix). Admits and rejects **exactly as before** on all four sheets; FLOOR PLAN's 4.91 ft run still rejected. **UTILITY admitted per CE-5**: it was in NO bucket at all — **36.1 sqft absent** — now measured from its drawn edge (depth 4.92 vs printed 4'6") on its own `utility_area` line (not carpet, not balcony, not common). **Built-up 1658.8 → 1694.9, R-8 97.3 → 99.4**; carpet 1203.5, common 23.6, balcony 50.8, R-2 97.0 all unchanged. |
| **RAHUL'S RULINGS 16 AUG — recorded in the spec** | §0.1.9 **geometry first, printed total is the CHECK not the target** (architects' carpet conventions differ; measure walls, derive area, then explain the gap). §4 **ducts = common area** + the FLOOR PLAN worked case. §5 **L-6 lift = its own SHAFT, no floor** (recessed lift door deferred to §11). §6 **S-6 staircase = actual STEPS, not a solid block**. §10.1 **CE-5 utility is BALCONY-TYPE, not a room**. |
| **THE TWO REJECTED DUCT CANDIDATES — measured, NOT the recorded limit (16 Aug)** | GHATIKIA **2.63 × 4.36 ft (11.5 sqft)** at x 10.43–13.06, y 34.49–38.85 (and its mirror at x 53.97, the second view) — rejected by **OVERHANG 2.62 ft** against a 0.50 ft limit. FIRST FLOOR **3.47 × 3.47 ft (12.1 sqft)** at x 2.76–6.23, y 127.35–130.82 — **OVERHANG 1.66 ft**. Both miss by a wide margin, not marginally. **Measured wall thickness 0.52 and 0.42 ft against candidate widths 2.63 and 3.47 ft**, so the thin-wall guard never fired and the recorded limit is not what is happening here. Their sides are shared with longer wall runs = a shaft carved into a corner rather than drawn as its own box. **Not loosened — Rahul rules on whether that shape is a duct.** |
| **WALLS BUILT FROM PAIR RECTANGLES — the blob is gone (19 Aug)** | `walls_poly` was still **traced** out of the raster (`findContours` + `approxPolyDP`) even though `_mask()` has painted pair rectangles since 18 Aug: **one object, two code paths, one fixed**. Tracing kept the morphology's rounding at each punched door hole as a 0.07–0.25 ft staircase, which extruded into a **lumpy mass in the wall run at almost every doorway** — five x-values spanning **1.57 ft** where a 0.42 ft wall has two faces. Now built from the rectangles; openings still cut by `poly_bands`; unpaired reuse the median-wall rule; **`approxPolyDP` untouched**. **Corners closed** (the overlap clip left a 0.8 ft square open at every junction) by extending a rectangle only where another wall sits. **Result: flat-2's entry now ONE x value, spread 0.00 ft.** New metric `wall_face_quality`: **short steps 195 → 1, outline points 290 → 41, polygons 7 → 1.** Judged set all held; BRICK WORK (173/368) and GHATIKIA (23/86) reported, not accepted. |
| **DOOR POSITION + HINGE FIXED FROM THE DRAWN SYMBOL (20 Aug)** | Settled first: **misplaced CUTS, not mis-associated symbols** — 12 symbols, 12 openings, **1:1, none shared**, each hinge's nearest jamb belongs to its own door, and every drawn opening OVERLAPS its cut (0.70–2.87 ft). So the drawn hinge is safe to use. Built: **hinge → the arc end lying ALONG this wall IS the doorway** (the strip keeps only orientation + perpendicular position), and the **cut depth is now the wall's own measured 0.83 ft** instead of the ROI close's 1.06–1.55. Result **hinge on a jamb 6/12 → 12/12** (median move was 0.77 ft, max 3.56), **`doors_placed_sound` 11 → 12/12**, leaf buried in wall material **0.35 sqft total, 10 of 12 exactly zero**. `opens_toward` could NOT set the rotation sign — it is measured against the drawn LEAF, which the drafter draws shut on some doors and open on others, so FLOOR PLAN's two `right` doors needed OPPOSITE signs; **new `opens_ccw`** (cross product of the symbol's shut and open arc ends, in plan) takes **wrong-side 3/12 → 0/12**. **CORRECTION: my 19 Aug pierce figures (52% etc.) were measured on the leaf's AABB, not the rotated leaf — overstated. The hinge-distance and wrong-side numbers are unaffected.** One movement, reported not accepted: **GHATIKIA doors 37 → 39** (it reads no arcs, so only the depth change reaches it; the thinner cut lets 2 more schedule-tag doors in; `sound` unchanged at 13) |
| **FIX 1 — DERIVED PAIRING FLOOR: SHIPPED (20 Aug, Rahul)** | `min_ovl_ft = 2.0` served two purposes; the floor is now **derived — a wall run is at least as long as the wall is thick**, from the pair's own measured gap. FLOOR PLAN pairs **48 → 60**, all 7 fin ends single rectangles at 0.42 ft, outline points 96 → **82**; **BRICK WORK pairs 39 → 126, short steps 361 → 162, M-1 1.06 → 1.13, doors 11 → 12**. Cost: footprint 1799.4 → **1796.8**, **R-8 96.7 → 96.6** — pin re-derived with evidence (`r8_pin_rederived_2026_08_20`), the 2.6 sqft being material claimed at twice its drawn thickness. **The lobby confirms it independently: 94.6 → 96.9 against a printed 96.6** |
| **FIX 2 — DOOR WALL LINE FROM THE HINGE: SHIPPED (20 Aug)** | 6 of 12 off their symbol's wall line → **0 of 12**; flat-1's bedroom entry was 3.32 ft out, on a different wall. Nothing else moved |
| **GAP GROUPING FIXED — order-dependence, not the axis (20 Aug)** | `_runs_by_line` keyed each group on a **rolling mean**, so groups chained without limit (7 faces spanning 2.92 ft under a 1.2 ft tolerance) and the key stopped wherever the walk did: the same faces key **18.70 ft read bottom-up and 16.73 ft read top-down**, and raster px runs y-DOWN while feet run y-UP. Now bounded by the group's own extent and keyed on its centre. **Blast radius checked first: doors only** — walls and rooms come from the mask contours. FLOOR PLAN unchanged (12 doors, 12 sound); **BRICK WORK 12 → 20 doors, reported not accepted** |
| **`doors_placed_sound` LEAFLESS BRANCH (20 Aug)** | A gap opening has no leaf, so it is scored on the cut sitting ON the drawn gap, at the gap's own width, inside the plan. `meta.doors_placed_sound.leafless` counts them |
| **TERRACE HATCH VERIFIED — FIRST FLOOR STAYS JOINED (21 Aug)** | Across the real band **y 67.6–80.7 (13.1 ft)**: 0 wall lines span, 2 stroked paths span, **0 FILLED paths span** — the hatch is not a fill. It is **19 strokes at exactly 45°**, 21.9–24.0 ft long, x **0.4 → 41.7** (full block width), on layer `0`. Only 2 of 29 span end-to-end (a 45° stroke enters and leaves at different y) but **collectively they cover 100% of the band in ONE run**. The band rule must ask what COVERS the band, across strokes/fills/diagonals — not what individually spans it. `_segs` drops anything not horizontal or vertical, so the wall reader is blind to it by construction |
| **PLOT FALLBACK REMOVED — the physics check was self-referential (21 Aug)** | `_plot_sqft` fell back to the **building's own bounding box** when the envelope came from dimension text, so `footprint ≤ plot` compared the building to itself. Now: printed statement, or **user entry (`corrections.plot_area_sqft`)**, or **UNKNOWN and BLIND — said out loud** as `plot_area_unknown`, never a quiet pass. `meta.plot_source` records which. **FIRST FLOOR 2454.4 → unknown → 14% with Rahul's 11,500** (both blocks 39%). FLOOR PLAN keeps 3371 (printed). BRICK WORK + GHATIKIA already unknown, now said to be. 2 new tests |
| **PLOT CORRECTED 2454.4 → 11,500 (21 Aug, Rahul) — NOW LIVE** | The parser fallback is **fixed** (row above) and Rahul's 11,500 reaches the runtime through **`corrections.plot_area_sqft`**, not `ground_truth.json` (which is still not read at runtime). **Measured end to end: FIRST FLOOR footprint 4472.1 on 11,500 = 39%, `plot_source` `user`, `plot_area_unknown` clears, `footprint_exceeds_plot` never fires.** |
| **THE 16-ROOM CAP IS GONE — IT WAS DELETING A VERIFIABLE ROOM (22 Aug)** | `rooms = rooms[:16]`, an **absolute count** applied after sorting by area. FIRST FLOOR — five flats over two blocks — finds **NINETEEN** and the cap threw away the three smallest: **balcony 34.0 · bathroom 33.5 · balcony 29.1**. The bathroom **matched its printed dimension at 96.9%**, and the two balconies are why B-5 read 0.0 on a sheet that prints `balcony 9'-7" X 4'-0"` twice. **This supersedes my previous two explanations of the balcony line.** Rooms are already bounded by a **derived** floor (`_min_room_px`), so the cap was a blunter second filter on the same thing. **FIRST FLOOR rooms 16 → 19, `rooms_checked` 14 → 16, R-2 98.4 → 96.9 (median FELL as the sample rose — pre-authorised), `rooms_off` 6/14 → 7/16, balcony 0.0 → 63.1, carpet 2976.6 → 3010.1, built-up 4472.1 → 4505.9, footprint unchanged. Other three sheets identical to every decimal** (FLOOR PLAN finds exactly 16 and never met it). **Same family as `BORDER_MAXLEN_PT` and `DOOR_MIN_FT`: a constant not derived from the drawing, failing SILENTLY because every survivor still looks reasonable.** Pinned by `test_no_absolute_room_cap` |
| **THE SEAL'S TWO JOBS ARE NOT SEPARABLE AT THIS LAYER — closed (24 Aug)** | Predicted before building: feeding the ring the unsealed `m` would not rescue the fragmented sheets. **Confirmed, and worse — it fails on ALL FOUR sheets with the seal held at 4.0** (ring input the only variable): footprint **BRICK WORK 1247.1 → 528.6 (−57.6%) · FLOOR PLAN 1796.8 → 999.1 (−44.4%) · GHATIKIA 2647.7 → 1993.5 (−24.7%) · FIRST FLOOR 4472.1 → 3720.4 (−16.8%)**. **Judging the footprint FIRST ended it in one run** — no room number was read, because none would mean anything under that. **`_footprint_from_walls` is not an independent envelope-closer; it is a REFINEMENT ON TOP OF THE SEAL**: `_free_ring_endpoints` hunts gap endpoints in a mask whose doorways are already closed, and on the raw mask every doorway is itself a ring gap. **The dependency runs both ways — one operation in two pieces, not two operations sharing a constant.** Only remaining direction, recorded not proposed: bridge between drawn SEGMENT ends only, ignoring raster gaps (`seg_px` is already passed in) |
| **CARPET ↑ WHILE R-2 ↓ IS A REGRESSION — built as a check (24 Aug)** | The seal split moved FLOOR PLAN carpet **1191.1 → 1328.1 (+137)** and R-2 **98.0 → 94.6** in one run. **Carpet alone reads as a win; read with R-2 it says the rooms grew past their printed dimensions.** Coverage and accuracy move **together** when the parse improves; apart means a **boundary** moved. `batch_eval.carpet_r2_verdict(prev, cur)` — pure, unit-tested — and `parse_metrics` now emits `carpet_sqft` + `r2_median` **together** (and `route`), so any diff has the inputs. **No parse number moved.** Sent to the scorecard session for `--compare`. **Mirror case RULED 25 Aug: UNVERIFIED, flagged for a human** — carpet falling while R-2 rises is *both* rooms shrinking inside their printed dims *and* what an honest correction looks like (the 20 Aug footprint fix lost 2.6 sqft of wall claimed at twice its drawn thickness). Not choosable from the numbers, so it is an **ask**, never silently scored. Verdicts prefixed `REGRESSION:` / `UNVERIFIED:` |
| **THE WELD MEASURED — it is ENVELOPE CLOSURE, and the second operation ALREADY EXISTS (24 Aug, nothing built)** | Free space split into OUTSIDE (touching the raster border) and INTERIOR at seal 3.1 vs 4.0. **FIRST FLOOR outside 6511 → 4400 sqft (−2111), interior 182 → 2012 (+1830), free regions ≥18 sqft 6 → 16 · GHATIKIA 2973 → 2146 / 338 → 872 · BRICK WORK 411 → 277 / 539 → 614.** **FLOOR PLAN is the control and it settles it: outside moves TWO sqft (1350 → 1348) because its envelope is already closed at 3.1, and its interior LOSES 111 sqft — the headroom buys nothing there and eats rooms.** So 17 Aug named the second job wrongly: not interior fragment welding, **outer-ring closure**. **The weld gaps DO have their own signature and we already read it** — `_footprint_from_walls` finds ring gaps (`_free_ring_endpoints`), bridges them jamb-to-jamb and bounds each bridge **relatively** (`max_bridge` = its own wall run), not by a constant. **The split is buildable and its second half is already written.** Prediction to test: FLOOR PLAN recovers 111 sqft, fragmented sheets keep enclosure. **NOT BUILT** |
| **BRICK WORK's −2.00 HEADROOM WAS THE WINDOW ROWS (24 Aug)** | Its schedule p90 of 6.0 used all eight OCR'd widths — **[2.0, 2.5, 3.0, 3.25, 3.75, 5.0, 6.0, 7.0]** — including a ventilator and two windows. **A window cannot be a doorway.** Doors only (D 3'9" · D1 3'3" · D2 3'0" · D3 2'6" · SD 7'0") gives **p90 3.75**, and headroom **−2.00 → +0.25**. The outlier joins the other three and its doorway lands in the same **2.2–3.8 ft** band. **The anomaly was our filter, not the sheet.** Not applied — the tag filter needs the schedule TAGS the derivation does not yet request |
| **DERIVED SEAL — BUILT, DISPROVED, REVERTED (24 Aug)** | **My proposal rested on a CIRCULAR measurement.** The p90s that made it look right (3.11 · 4.70 · 4.77 · 5.12) came from **our own CUT widths** — produced by the mask the seal makes, so they were reporting the seal back to me. **Honest p90 of the DRAWN leaves: FLOOR PLAN 2.94 (12) · GHATIKIA 2.23 (32) · FIRST FLOOR 3.06 (47) · BRICK WORK none → its PRINTED schedule, 6.0 via OCR.** Three of four derive **below** today's 4.0; the 4-vs-5 spread does not exist outside the circular data. Wired, it regressed three sheets — **FLOOR PLAN R-2 98.0 → 94.6 · GHATIKIA 14 rooms → 1 · FIRST FLOOR 19 → 10, R-2 96.9 → 57.1**. Reverted under rule 6. **It confirms 17 Aug from the other side**: drawn doorways are 2.2–3.1 ft, so a leaf-derived seal serves **BREAK CLOSE only** and abandons the **FRAGMENT WELD** the 4.0 kernel is silently also doing. **One derived number cannot serve two jobs any better than one constant could — the split must be into two OPERATIONS.** Kept and reported, not applied: `derived_seal_ft` (DRAWN → PRINTED SCHEDULE → **UNDERIVED**, never a silent default) and **`meta.route.seal.weld_headroom_ft` = applied − derived: 1.06 · 1.77 · 0.94 · −2.00 — the first per-sheet measure of how much WELD each sheet lives on** |
| **STANDING RULE — A CHANGE MUST STATE WHICH ROUTE IT ACTS ON (24 Aug, Rahul)** | Rule 6's "corpus-validate" is not the same as "ran on all four sheets". **FLOOR PLAN is the only sheet reaching the ARC branch**, so **every door result of 19–20 Aug was validated on ONE ROUTE**: the other three ran the change, could not exercise it, and their unchanged numbers read identically to "no regression". **A sheet that cannot reach the branch is not a control, it is an absence** |
| **`meta.route` — THE THREE INVISIBLE FLOORS NOW SAY WHICH BRANCH RAN (22 Aug, additive)** | A cap deletes data; a **floor reroutes the parse**, so every number downstream describes a different algorithm. Six of the nine floors are already visible in output (`meta.source`, `meta.scale.source`, OCR/anchor warnings, `meta.wing`, `built_up_branch.fired`); three were not. Now emitted: **`door_median`** (under 5 snapped doors it returns None and callers drop to `NOMINAL_DOOR_FT`), **`stair_ladder_dedupe`** (skipped under 5 walls; its one caller is `_geometry_wall_segs`, so it doubles as the geometry-vs-layers marker), **`door_symbol_paths`** (a **count**, since arc-vs-leaf is decided per drawing path). **Keys seeded to `not reached`** — for a diff, a missing key and a changed key are different findings. **Two facts visible for the first time, now recorded against those sheets in `ground_truth.json`.** (1) **FLOOR PLAN is the ONLY sheet where the ARC branch fires** — arc 12 / line 120 / leaves 36, against **arc 0** on all three others. `door_swing`, the measured hinge and `opens_ccw` are all read from the drawn arc, so they are **structurally absent** elsewhere, not failing. **Every door result of 19–20 Aug rests on a branch only this sheet reaches — a door fix validated here is validated on one route, not as a general rule.** (2) **BRICK WORK hands the grouper `{arc: 0, line: 0, leaves: 0}`** — no symbol path of either kind — which is the *mechanism* behind 15 of its 17 doors being leafless, where before we had only the symptom. No number moved |
| **400-POINT FOOTPRINT DECIMATION REMOVED — and NOTHING MOVED (22 Aug)** | It bounded the MST's search for the closest pair between footprint components, and those points are what decide **where a bridge goes and how long it reads** against `max_bridge`. All four sheets were over it (**1491 · 2101 · 4159 · 6719**, 3.7–16.8×). The cap existed only because the MST built the whole distance matrix; **`_closest_pair` chunks the rows (512 at a time, exact at any size)** with a per-pair cache, **no new dependency**. **Footprint sqft / outline points identical on all four — 1247.1/42 · 1796.8/59 · 2647.7/209 · 4472.1/521 — as are M-1, polygons, short steps, R-8, both R-2s, doors and sound.** On this corpus it was harmless **by luck**: the true closest pair survived the subsample every time, and had it not, **no instrument could have said so**. The 400 bounded the search space, not the outline, which is why the point count did not rise. Pinned by `test_closest_pair_is_exact_and_uncapped` |
| **THE TWO-PASS SEAL RE-MEASURED — 17 Aug verdict STANDS (22 Aug)** | I expected pair-built walls + 100% face painting to have rescued `DRISHTI_SEAL_MODE=passes`. **They did not.** FLOOR PLAN **R-8 96.5 → 74.0**, footprint 1796.8 → 1327.7, n 8 → 7; **FIRST FLOOR rooms 19 → 7, R-2 → 0.0**; GHATIKIA 14 → 4; BRICK WORK 13 → 10. Structural reason: weld/collinear bridge between **segment ends**, the blanket close closes any gap in the **raster**, including between wall bodies no segment end faces |
| **SEAL PROPOSAL — DERIVE IT FROM THE DRAWING (22 Aug, NOT BUILT, awaiting ruling)** | The tension is now measured: FIRST FLOOR wants **5 ft** (rooms 19 → 22, n 16 → 19, median 96.9 → 98.4), FLOOR PLAN needs **4** (at 5: rooms 16 → 13, `rooms_checked` 8 → 6, ratchet fails). **The p90 DRAWN opening width separates the corpus exactly that way: FLOOR PLAN 3.11 · BRICK WORK 4.70 · GHATIKIA 4.77 · FIRST FLOOR 5.12, against a flat 4.0.** One kernel per sheet, derived not chosen. **Caveat: must come from DRAWN LEAVES, never our own cut widths (circular — the cuts come from the mask the seal made); BRICK WORK draws only 2 leaves so it has no p90 and needs a stated fallback.** Fallback plan: per-wall-run `collinear_bridges` at a derived distance. **Rejected: per-wing** (one wing now holds both blocks) **and per-component** (a doorway has no owning component) |
| **ABSOLUTE-LIMIT SWEEP — two are LIVE AND BEING HIT (22 Aug, reported not fixed)** | (1) ~~the 400-point footprint decimation~~ **FIXED 22 Aug, row above.** (2) **`BORDER_MAXLEN_PT = 900` still live at three call sites** (`_text_scale`, `_overall_dims`, `wall_gap_pairs`) = 31.6 ft on FLOOR PLAN, 158 ft on FIRST FLOOR. Live but unmeasured: `OCR_REFINE_MAX = 40`, `MAX_SEGS = 250000`. **The mirror risk is bigger: NINE absolute FLOORS switch ROUTES silently** — `len(struct) < 30`, `len(gsegs) >= 8`, `len(votes) < 8`, `len(widths) >= 5`, `len(_live_toks) < 50` … **none of the eleven is derived from the drawing.** No other top-N truncation of a parsed quantity exists. Full list in `ground_truth.json` |
| **THE BLOB CAUSE — FOUR CANDIDATES DISPROVED, CAUSE STILL OPEN (22 Aug)** | **(a)** missing partitions — my probe, not the parse. **(b)** wall detection — the TOP block is **BETTER** (79%/73% vs the control's 42%). **(c)** unpainted wall — **disproved outright: BOTTOM 160 faces / 781 ft and TOP 252 faces / 1233 ft are both 100% covered by pair rectangles**, zero partial, zero missing. **(d)** gap width — disproved and **backwards**: median gap 5.47 ft in the block that RESOLVES vs 4.36 ft in the block that does not. **My erosion test is WITHDRAWN** (it ran on the approxPolyDP-simplified `polygon_ft`, blind to a 0.42 ft neck). **The only lever is the global SEAL and it cannot be moved**: at 5 ft FIRST FLOOR reaches 22 rooms / n=19 / median 98.4, but **FLOOR PLAN drops rooms 16 → 13 and `rooms_checked` 8 → 6, failing its ratchet**. **The 17 Aug finding in a new place — ONE KERNEL DOING TWO JOBS**; the top block wants 5 ft where FLOOR PLAN needs 4 |
| **THE FIVE "MISSING PARTITIONS" WERE DOORWAYS — my probe, not the parse (22 Aug)** | The straight line between two adjacent rooms' label centres runs **through the door that connects them**. At four of the five crossings the only drawn line met is a single **2.48–2.99 ft stroke**; at the fifth it is a **2.21 ft `door`-layer line** and its layer-`0` twin. **The partitions are drawn, they pair, and they are built**: drg/dining\|kitchen has 8 struct segments and 9 rectangles including **6.46×0.82 and 6.88×0.82**; bed_W\|toilet_B has faces at x 14.13 / 14.55 running **11.79 ft**. **Nothing is lost at any of the five.** **Fourth metric-geometry error in a row** — after R-8's basis, R-2's sample, `doors_placed_sound`'s clustering and the 14.3 ft "missing wall" |
| **THE TOP BLOCK'S TWO ~590 SQFT BLOBS — STILL UNRESOLVED (22 Aug)** | `585.4` and `603.9` sqft, mirrored, at x 2.8–25.4 / y 81.6–120.4 and y 138.5–176.5, both typed `bedroom`, both unnamed, both `dim_match_pct` 0.0. **Each is FOUR PRINTED ROOMS MERGED**: the 585.4 blob's polygon contains exactly `drg./dining 10'-5"×22'-3"` (231.9), `kitchen 6'-6"×9'-8"` (62.8), `bed room 11'-5"×13'-8"` (156.1), `bed room 10'-11"×13'-3"` (144.7) — **printed sum 595.5 against a measured 585.4 = 98.3%. The area is right; the segmentation is not.** **Wall detection there is BETTER than where rooms DO form**: dimension-anchor endpoints on a detected wall face read **79% and 73% in the blobs against 42% in the bottom-block control** of the same 22.6 × 38.8 ft footprint, which resolves into dining + staircase + kitchen. **Partitions are built between most pairs** (0.40–1.09 ft of wall crossed on the straight line between printed label centres); **five pairs cross 0.00 ft** — drg/dining\|kitchen, puja\|dining, bed_E\|balcony_B, bed_W\|toilet_B, toilet_B\|balcony_B. **The seal is NOT the dial**: sweeping `DRISHTI_SEAL_FT` 4→5→6→7 shrinks the blob 603.9 → 431.0 → 431.0 → 413.6 but never splits it. **CORRECTION: my "room count stays 16 at every value" was the CAP, not the seal.** With the cap gone the same sweep reads **10 / 19 / 22 / 25 / 23 rooms at seals 3 / 4 / 5 / 6 / 8** — the seal IS the dial. **Cause OPEN; see the row above** |
| **R-2's MEDIAN HOLDS WHILE 6 OF 14 ROOMS FAIL (22 Aug)** | FIRST FLOOR: median **98.4**, `rooms_checked` **14**, `worst` **0.0**, **`rooms_off` 6**. Five rooms score exactly 0.0 (603.9 · 585.4 · 424.0 · 283.9 blobs and one 62.0 bathroom) and one 57.1. **The 17 Aug lesson in its other direction: a median cannot see a merge any more than it can see a deletion.** `rooms_off` is the number that sees it and is now reported beside the ratchet |
| **FIRST FLOOR'S 12 UNSOUND DOORS — 4 ARE A METRIC BUG, 5 ARE DOUBLE-WIDTH CUTS, 3 ARE THE KNOWN CLUSTERING ARTEFACT (22 Aug)** | **4 leafless, all at x 38.83**, each sitting on its drawn gap to **0.01 ft** at **exactly** the gap's own width — they fail only `0 ≤ cx ≤ out_w`, because `out_w` is the **printed 38.25** while the built wall faces legitimately run to **39.2**. Same class as the 14.3 ft "missing wall": **fix the metric's geometry, not the parse.** **5 over-cuts**: 4.61–5.14 ft cuts against matched leaves of 2.14–2.23 ft, at (32.13, 146.48) · (33.30, 171.79) · (7.19, 57.51) · (32.13, 111.54) · (33.50, 86.21) — **four of them are two mirrored pairs**, so it is systematic, not noise. **3 clustering artefacts**: 3.00–3.25 ft cuts matched to a leaf **0.92–2.46 ft away**, the 19 Aug nearest-cluster fault. **FLOOR PLAN stays 16/16** |
| **GHATIKIA TWO VIEWS — RECORDED OPEN, NOT BUILT (22 Aug, Rahul)** | The band rule can only **MERGE**, never split, and GHATIKIA's two views already union into ONE wing group at the existing 8 ft proximity stage — so `_band_bridged` is **never called there** and the split direction is **untested on real geometry** (only `test_a_band_nothing_covers_still_splits`, a synthetic raster). Cost today: one 80.0 × 47.8 ft "building", every room twice at Δx ≈43.5 ft, 45 doors / 38 windows / 40 columns across both views, and the blob that wrecks R-2 (60.1, n=14) straddling x 35.1–61.1. A split would need `_wing_groups` to divide a group on an uncrossed interior band — the opposite operation — and would touch the crop, `_in_wing` (9 sites), sx/sy, M-1's denominator and the `rooms_checked ≥ 14` ratchet, which would roughly halve. **Recorded in `ground_truth.json` as `two_views_unhandled_2026_08_22`. Do not build yet** |
| **FIRST FLOOR'S TWO BLOCKS — JOINED, SHIPPED (22 Aug)** | `_wing_groups` now takes a **`cover` raster painted from every drawn primitive at any angle** and merges two groups whose separating band is bridged — **connectivity, not spanning**: one connected component of drawn material touching both band edges. `_segs` buckets a line as horizontal or vertical, so the 19 diagonal hatch strokes were invisible to every wall-derived measure by construction. **FIRST FLOOR 38.2 × 64.2 → 38.2 × 177.3 ft, wings 2 → 1, rooms 11 → 16, `rooms_checked` 8 → 14 with R-2 holding at 98.4, doors 23 → 54, footprint 1652.2 → 4472.1, carpet 1032.6 → 2976.6, common 168.1 → 335.0 (exactly the second staircase, 166.9), M-1 1.10 → 1.09.** The other three sheets are **byte-identical**. **The rule is INERT on GHATIKIA, not correct there** — its two views already union into one wing group at the 8 ft stage, so `_band_bridged` is never called; the real two-views case is still untested outside a synthetic. **The rule can only MERGE, never split.** **sx/sy re-origin verified**: the crop shift was (1.906, −0.177) and is now (0, 0); FIRST FLOOR's kitchen moves (9.63, 21.04) → (11.53, 20.86) = **exactly −sx, −sy**, with area 62.0 and `dim_match_pct` 98.4 unchanged on every bottom-block room. **Balcony 67.9 → 0.0 — and 0.0 is the honest number.** My first explanation was wrong: the pockets are NOT inside a room, they are free space in no room polygon. The 67.9 was **two rooms typed `balcony` at y 110.47 and 148.33 in a build whose own reported envelope was 0–64.167 ft** — reported from beyond the depth it claimed. Railings are identical in both builds (3 runs, all `unclassified`), so B-5's railing path never contributed either way. **Both goldens RE-DERIVED on Rahul's ruling** |
| **THE 14.3 FT OF "MISSING WALL" IS BUILT (21 Aug, measured)** | Traced the 5.3 ft bathroom\|stairs partition through every stage: **pair rectangle 5.00 × 0.83 ft at (27.42, 12.90)–(32.41, 13.73), 10 in thick, and 100% inside `walls_poly`** (4.14 of 4.14 sqft, wp3, no hole). Nothing is lost downstream. **All five lines sit 0.01–0.23 ft from built wall; 14.2 of 14.2 ft (100%) is within 0.25 ft**, and flat-2's 3.3 ft is 100% on the polygon exactly. The reported coordinates are not the drawn faces — the 5.3 ft is given at y 13.9 where the faces are 12.90 / 13.73 — so a zero-width sample line falls just outside a 0.83 ft wall body. **Corpus check: of 674 ft of drawn wall line, 3.1 ft (0.5%) is further than 0.25 ft from built wall.** Same class as the `doors_placed_sound` clustering artefact: **fix the metric's geometry, not the parse.** The x 26–33 core-band suspicion does NOT hold — C.TOILET/passage/lobby were found and destroyed; these five were never lost |
| **OUR OWN FIXTURE HAD A DEFECT (21 Aug)** | `tools/make_sample_plan.py` draws a 3 ft door gap at x 17, y 5–8 that the parser never emitted; `test_sample_all_doors_snap` asserted 6 and passed for weeks. The improved finder found it: **6 → 7**. A synthetic fixture is ground truth we wrote — **check it against its own source, not against the parse** |
| **FIX 3 SHIPPED — gap doors per LOCATION (21 Aug)** | FLOOR PLAN **12 → 16 doors, all 16 SOUND** (12 leafed, 4 leafless). The sheet draws four openings with **no leaf**, so the symbol path is blind at each while the gap finder saw all four and was switched off sheet-wide by one door layer existing anywhere. **Two were not known to be there — the LOBBY doorway (y 7.50) and FLAT-2's balcony opening (y 13.72)**; Rahul expected 14. Gap faces group by **measured pair**, so one wall is one opening and the duplicate is gone structurally (collinear segments merge into a face first, or a wall broken at every doorway pairs segment-by-segment and its gaps vanish). R-8 pin re-derived **96.6 → 96.5** on 0.1 sqft of built-up |
| **W-3 UNIFIED (21 Aug)** | `WALL_GAP_MIN_IN/MAX_IN` + `wall_gap_band()` replace the 3–18 in band hardcoded in five places. In INCHES, converted per sheet — no number moved |
| **BRICK WORK — LEAST TRUSTWORTHY SHEET (21 Aug)** | Doors **11 → 12 → 20 → 17** in two days and **no instrument there can judge it**: no area statement, no room dims, no balcony width, no door layer, **15 of 17 doors leafless**. Recorded in `ground_truth.json`; no movement there is evidence either way |
| **VIEWER: THE FAR ROOMS ARE REACHABLE (20 Aug, frontend only)** | Zoom dollied toward a **fixed** orbit centre at the building's middle, so on a 95 ft plan the east and west ends could never be reached — and inspection is how we now verify every geometry change. Four changes, all in `src/`: **`zoomToCursor`** (the centre follows the pointer), **`enablePan` + `screenSpacePanning`** (right-drag pans, context menu suppressed), **`TrackpadPanControls`** — a Mac two-finger drag IS the scroll gesture and OrbitControls maps every wheel event to dolly, so it is intercepted in the CAPTURE phase and panned instead, with pinch (`ctrlKey`) and coarse mouse notches (`|deltaY| >= 40, deltaX === 0`) left as zoom — and **`FocusPicker`**, double-click any surface to re-target the orbit centre there, keeping the current view direction. **`minDistance` 0.35 / `maxDistance` 400** replace the unbounded defaults. Walk-inside beacons, T/R/F/M and the GSAP `CameraRig` are untouched — CameraRig already kills its tween on `controls.start`, so a pan mid-glide wins. 3 new unit tests; **no parser number moved** |
| **RAILINGS, BALCONY + UTILITY REACH THE 3D (20 Aug, B-4)** | The contradiction resolved: **flat-2's balcony was never built as a balcony** — its railing is a thin double line **3.0 in apart, exactly `wall_rects`'s 3 in floor**, so it paired as a WALL (**9.50 × 0.25 ft rectangle**) and was extruded full storey on an open face; flat-1's railing pairs no such wall, so that balcony was absent entirely. `scene.railings` was read by nothing. Now a run classified `railing` becomes a **half-wall at 3.5 ft**, its `pocket_ft` gets a floor slab, and **wall material lying along a run is cut to the same height** (dropped entirely when the polygon WAS the railing). FLOOR PLAN: **3 railing runs → 6 rail meshes at 3.50 ft, 3 open floors, wall meshes 15 → 13, max wall height still 9.84 ft**. Furniture is no longer staged into a pocket — **the bed in flat-1's utility is gone**. No parser number moved on any sheet |
| **DOORS 1, 2, 3 ARE ONE CAUSE — THE BUILT HINGE IS NOT THE DRAWN HINGE (20 Aug, measured)** | `_add_door_leaf` **discards the measured hinge point** and keeps only which jamb is nearer, then hinges at OUR jamb: **median move 0.77 ft, max 3.56 ft**. The drawn hinge is on a jamb for only **6 of 12**; 3 sit INSIDE the opening (1, 2, 12) and 3 sit OUTSIDE it (5, 6, 7 — by 1.5–2.0 ft). Consequences, all measured: **(a) 5 of 12 leaves are PIERCED by wall material** — 0.31–2.07 sqft, **7 / 13 / 15 / 39 / 52%** of the leaf's plan area inside `walls_poly` (doors 1, 5, 7, 6, 2) and **0.00 on every one of the 6 hinged correctly**; **(b) 3 of 12 swing to the side the drawn arc does NOT sweep** (1, 2, 12 — off by 118°, 46°, 141°; the other 9 sit 2–21° off, which is just the 60° ajar leaf vs the arc-box centre). Item 1 is NOT a `door_swing` failure — it reads `right` correctly; `opens_toward` is measured against the DRAWN leaf direction while the built rest direction comes from OUR jamb choice, so when the two disagree the side flips. **(c) Item 3 is not width** — the built leaf equals the drawn `leaf_ft` on **all 12** (Step 1, 19 Aug); door 2 reads small because **52% of it is buried in the wall**. One more contributor: the opening CUT is **1.06–1.55 ft deep against a measured 0.83 ft wall (1.3–1.9x)**, so the leaf is centred in a band up to 0.36 ft off the wall's own centre plane |
| **STEP 2 COMPLETE — SWING READ 12/12 (19 Aug)** | The blocker was that **a symbol is split across paths**: every leaf lives in a different path from its arc. **The geometry groups them — the leaf IS the radius** (leaf = arc radius to **0.01 ft**, CV **0.000–0.001**, 12 of 12). `door_swing` then reads hinge + sweep: **8 left, 4 right → 4 doors now swing the other way, 8 were right by chance** under the old blanket +60°. Carried into `scene_to_glb`: `opens_toward` sets the sign and the **measured hinge overrides the low-jamb guess**. Expect the same path-split for windows, ventilators, stairs. |
| **BLOCKED-DOORWAY ASK — clear width, not overlap (19 Aug)** | Flags any opening whose **clear** width after obstructions falls below a usable door: **FLOOR PLAN's flat-1 entry leaves 21.3 in of a 3.11 ft opening**; BRICK WORK 21.7 in; GHATIKIA two at 16.4 in; FIRST FLOOR none. Plan Doctor `ask`: *"a column obstructs this doorway, leaving X in clear. Is the column or the door misplaced?"* **Never auto-corrected** — C-7 puts the column where the drawing does. |
| **THE LAST UNSOUND CUT IS A METRIC ARTEFACT (19 Aug)** | The door at (10.4, 13.4) cuts **2.88 ft and its grouped leaf IS 2.88 ft** — correct. `doors_placed_sound` scores against the *nearest drawn cluster* and two doors sit within 3 ft there, so it picks the neighbour's 2.26 ft. **11/12 stands, not tuned**; the metric's clustering is what needs fixing. |
| **STEP 2 (SWING) — superseded by the above** | `door_swing()` written + unit-tested (arc centre = hinge, sweep side = room it opens into, **returns None rather than guessing**). Reads **0 of 12**: measured cause is that **the leaf and the arc are in SEPARATE drawing paths** — the door layer's 12 multi-item paths are pure arc polylines, every segment **0.32–0.33 ft**, no leaf; and a bbox filter cannot group them (every door box caught the same 25 lines). Assembling a symbol needs **arc-path + nearest long line from another path** — a third grouping rule, not built. Nothing regressed; leaves still default to +60°. The over-cut door stays 11/12 — **not tuned to reach 12**. |
| **STEP 3 — flat-1's ENTRY IS A REAL CLASH (19 Aug)** | The cut went **1.7 → 3.11 ft**, but the column at (24.75, 0.00), **1.34 × 0.83 ft, still overlaps 1.34 ft = 43%** of the opening. Rahul's suspicion holds at this one location, and C-7 says the column's orientation is right — so **the drawing puts a column in the doorway**. That is a §0.2 ASK, not a parsing error. |
| **STEP 1 — CUTS NOW SPAN THE DRAWN LEAF (19 Aug)** | Root cause of "thick wall covering the door": **short cuts** — 6 of 12 measured **1.5–1.7 ft against leaves of 2.2–3.2 ft**, each removing half its doorway. **One bug, four sightings** (2.6, 2.9, 2.10, 2.11). Fixed: position and orientation still come from the strip, **the WIDTH now comes from the drawn leaf** — same class as `DOOR_MIN_FT`, anything sized from the strip is sized from the wrong object. New instrument **`meta.doors_placed_sound`** judges placement, not count: **FLOOR PLAN 6/12 → 11/12** (ratchet pinned at the authorised 6), FIRST FLOOR 12/16, GHATIKIA 13/37. **Nothing else moved.** One door still unsound and it is the opposite failure: the cut at (10.4, 13.4) is **2.88 ft against a 2.26 ft leaf** — its swing box is bigger than its leaf. |
| **THE FOUR "NO ENTRANCE" REPORTS RE-READ (19 Aug)** | Three are not missing doors. **2.6 A.TOILET**: drawn 2.3 ft at (80.3, 5.4), cut 2.4 — **sound**; what was seen is the swing (never read → Step 2). **2.9 bedroom 13'6"×10'3"**: drawn 2.9 at (13.4, 19.5), cut 3.0 — **sound**. **2.4/2.5 C.TOILET**: drawn 2.3 at (72.8, 7.1), cut was **4.4 — an over-cut**, corrected by Step 1. **Only 2.2 KITCHEN and 2.3 BALCONY have no drawn leaf at all** — the sheet does not draw one. |
| **COLUMNS ARE FINE — C-7 verified, uniform-size theory disproved (18 Aug)** | Columns pass from `_column_rects` to `scene_to_glb` **unchanged**: `_add_box` carries each one's own w×d, and **26 of 26** are built at their drawn size and axis (**6 long-in-x, 20 long-in-y**, identical in the GLB). No squaring, averaging, rotation or shared size anywhere. **So columns cannot be the cause of "thick wall over the door"** — only **1 of the 6** mis-placed cuts has a column within a wall thickness (flat-1's entry, 2.7), and **0 of the 6 sound ones** do. |
| **THE DOOR DEFECTS ARE ONE MECHANISM (18 Aug)** | The six bad cuts measure **1.5–1.7 ft against drawn leaves of 2.2–3.2 ft** — each cuts about **half** its doorway and leaves the rest standing. **That is the "thick wall covering half the door" at 2.6, 2.9, 2.10, 2.11: one mechanism, four sightings.** Door COUNT is not the gap — the sheet draws **12 distinct door positions and we emit 12**. The sharp case is **C.TOILET (2.4/2.5): a 2.2 ft leaf is drawn at (72, 7) and no 3D cut exists there.** |
| **SWING IS NEVER READ — DR-3 unimplemented (18 Aug)** | `hinge` appears **0 times** in `pdf_vector`; `scene_to_glb` finds none and leaves `ang = +60°`, so **every leaf on every drawing swings the same side of its wall** — right by chance ~half the time (≈6 of 12 here). A missing feature, not a defect of this sheet. |
| **MIRROR CONFIRMED AND FIXED — plan-y → −Z (18 Aug)** | My "not mirrored" ruling was wrong: no geometry axis was negated, but `TOP_VIEW=[0,16,0.01]` with three.js's default up gives screen-up **−Z**, so **plan-north rendered DOWN**. Only rendering the GLB through that basis showed it. **Fixed in the data** (a camera fix is impossible — with y-up and east right, north is necessarily down from above): `_add_box` cz, `_add_poly_prism` row 2, the **door leaf** (hinge *and* swing angle, since a reflection reverses rotation sense), and `roomPoints.roomWorldPoint`. Verified: plan-y −0.2…29.8 → Z −9.08…0.34, **0 meshes on the wrong side**, north UP and east RIGHT. **No parser number moved.** 2 new tests (one on the C.TOILET/A.TOILET landmark) + 2 re-based. |
| **RE-READ WITH NORTH–SOUTH CORRECTED (18 Aug)** | The door finding is a **data** result (cut vs drawn cluster) and stands — in fact **6, not 5**, cuts sit 0.58–0.75 ft off: (25.6, 0.4), (24.2, 16.5), (24.2, 21.9), (40.9, 4.6), (73.3, 5.7), (62.9, 10.1); four snapped onto clusters only **0.1–0.2 ft** wide. **What does change is the room NAMING** — Rahul identified rooms from a mirrored view, so "C.TOILET", "A.TOILET", "the bedroom by the kitchen" must be re-checked against the corrected render before being matched to these coordinates. |
| **3D REVIEW — MIRROR RULED OUT, and my door fix made placement worse (18 Aug)** | **Not mirrored**: plan x→X, plan y→Z, no sign change, uniform positive scale, no rotation; the built GLB matches the scene ranges exactly. What reads as a mirror is the **viewpoint** — plan-north is +Z and the default camera sits at (6,5,8), above the NORTH-EAST looking back, so the sheet is seen from behind its top edge. **A+B: the count improved, the placement degraded** — 5 of the 12 cuts sit **0.58–0.75 ft** from the nearest drawn cluster, and those clusters are only **0.1–0.2 ft wide** (linework fragments, not leaves); the 8 sound ones are 0.14–0.18 ft out against 2.3–3.1 ft clusters. **The golden asserts a COUNT, so it went green on a change that made placement worse.** A mis-placed cut leaves the real opening un-cut → the thick stub of B. **C: balcony, utility and railings never reach the 3D** — `scene_to_glb` consumes only walls, walls_poly, openings, columns+ducts, furniture; `scene.railings` is read by nothing. A `bed` sits at (25.6, 19.1) inside the utility. **D: there is no staircase roof** — `FlatRoof` is one frontend box over the whole bounding volume; the scene has no roof or stair geometry. |
| **ONE CONSTANT PER PURPOSE — LAST RED TEST CLEARED (18 Aug)** | `DOOR_MIN_FT` served **five** purposes. Split into **`DOOR_LEAF_MIN/MAX_FT`** (a real door), **`DRAWN_GAP_MIN/MAX_FT`** (the opening in the linework), and **no floor on the strip span** — the finding, not an omission: a strip is a property of the ROI close, not a doorway. **`− 0.3` deleted.** **FLOOR PLAN doors 8 → 12 of 12 (no overshoot), BRICK WORK held 11/11, GHATIKIA 30/37 (reported, not accepted), FIRST FLOOR 8/16 unchanged.** Judged set all held: R-8 96.7, R-2 98.0 (n=8), FIRST FLOOR R-2 98.4 (n=8), carpet 1190.6, rooms 16, footprint 53% of plot, stilt 94.7%. **The golden passes at 12 and was never adjusted.** |
| **THE DOOR LENGTH IS LOST INSIDE THE FINDER (18 Aug, measured on all 12)** | Scanned along each wall's own perpendicular coordinate: the four failures have openings of **2.06–3.46 ft in `m`** and **0.20–3.20 ft in `m_snap`**, yet their strips span only **1.49–1.61 ft**. Dilation costs 0.3–0.5 ft; **~1 ft more disappears inside `_door_gap_strip`'s directional close**, which splits the gap into parallel components and unions only those passing its own width test. **The mask still has the opening.** And the strip is not the opening: **three SNAPPED doors measure 0.00–0.18 ft of opening on their wall line yet produce 2.24–3.05 ft strips** — so any bound written as if the strip were the door width compares two different objects. |
| **`DOOR_MIN_FT` SERVES FIVE PURPOSES (18 Aug)** | 2.0 ft is simultaneously: the minimum door **leaf** width for a printed tag, the minimum **gap** width in `gap_openings`, the same in the geometry-door fallback, the lower bound of the door-width sanity check, and — via `DOOR_MIN_FT − 0.3` — the minimum **strip span**. **The `− 0.3` exists only to reconcile the last with the first.** Same family as the seal and the built-up formula: a constant serving several purposes cannot be derived from any of them, **and the four failures sit just under its floor because the floor is a compromise**. |
| **PAIR-RECTANGLES DO NOT PAINT THROUGH DOORWAYS — suspicion disproved (18 Aug)** | For all 12 FLOOR PLAN doors, failures and successes alike, **zero pair-rectangles cover the opening**. **How the extent is decided: SEGMENT BY SEGMENT** — `wall_rects` paints only `max(a_i,a_j)..min(b_i,b_j)`, the overlap of the two segments' own spans, and never merges collinear segments, so a face broken at a jamb yields two rectangles that stop there. **The wall already stops where the drawing stops it.** So the door cause is still open and narrower: strips span **1.49–1.61 ft against a 1.70 ft floor** and nothing yet explains why they shortened — not the rectangles, not the pair extent, not `thin`/`thick` (all 12 pass), not aspect. **My follow-up probe was invalid** (it sampled along the door centre line, through the room, returning the 6.01 ft window limit); reported unresolved rather than guessed. |
| **ASPECT PROPOSAL DISPROVED ON REAL GEOMETRY — nothing built (17 Aug)** | Redone with each door's actual swing box and printed width: **snapped doors aspect 1.4–3.9, failed doors 1.1–1.5 — overlapping, no separator.** The square "corner blobs" came from my generic ±1.5 ft box and 3 ft door; they do not exist in the real call. **THE REAL CAUSE: all 12 doors find a strip and all 12 pass `thick ≤ 1.6` (1.06–1.55 ft). The four failures fail the SPAN floor** — spans **1.49 / 1.55 / 1.59 / 1.61 ft** against `DOOR_MIN_FT − 0.3 = 1.70`, **missing by 0.09–0.21 ft**, while the eight that snap span 1.73–4.42. So neither `thin > 1.5`, nor `thick ≤ 1.6`, nor aspect is implicated: under pair-built walls the revealed strip is **55–70% of the door's own printed width**. Stopped, as instructed. |
| **`_door_gap_strip` MEASURED — the constant holds TWO objects apart (17 Aug)** | At the four lost doors the biggest strip the closing reveals is **nearly SQUARE**: 2.73×2.46, 3.22×3.16, 3.16×2.38, 2.79×1.57 ft (**aspect 1.0–1.8**) — a room CORNER, not a doorway. The real door strips sit beside them, **long and thin**: 2.30×0.29 (a=7.8), 1.53×0.33 (a=4.6), 2.50×0.33 (a=7.5), 4.11×0.45 (a=9.1). So `thin > 1.5 ft` is rejecting corner blobs **and** bounding wall thickness — one constant, two jobs, the same shape as the seal. **PROPOSAL (not built): separate by ASPECT** (scale-free, no unit — blobs 1.0–1.8 vs doors 4.6–106), leaving a thickness bound with one job that can then be derived from the measured wall. |
| **GOLDEN RULED RED (17 Aug)** | `snapped >= 11` has had **three** causes since 16 Aug and now measures a live investigation, not a regression. Recorded in `ground_truth.json`: current **8**, pre-pair **10**, pinned **11**, **do not re-baseline** until the strip geometry is understood. *A red test we understand is worth more than a green one we have adjusted to.* |
| **DOOR TOLERANCES RE-DERIVED — 2 of 4 hold, 2 resisted (17 Aug)** | From the sheet's own measured wall W (`_wall_thickness_ft`): **group_tol 1.2 → W** (its job is merging one wall's two faces), **min_flank 0.8 → W** (a jamb is at least a wall thick), **face_tol 0.35 → W/2**. **Effect: neutral on every sheet** — FLOOR PLAN stays 12 doors / **8 snapped**. The two inside `_door_gap_strip` (`thin > 1.5`, `thick ≤ 1.6`) are **not measuring a wall** — they bound the strip the closing reveals (wall + door-mask dilation + kernel). `2×W` → BRICK WORK 11→**3**, FIRST FLOOR 8→**5**; `W + 2×dilation` → FLOOR PLAN 8→**6**. **Both worse everywhere — reverted, reported, not tuned.** Doors stay at 8; the strip geometry must be measured before it can be derived. |
| **DOOR REGRESSION INVESTIGATED — the finder, not the rectangle (17 Aug)** | The four doors that stopped snapping are at **(25, 20), (27, 3), (42, 3), (62, 12) ft**, and **the gap is still open at every one: 75–93% of a 3.2 ft window is free in the wall mask**. Rectangles do not span the openings. Decomposed: lines+close45 = **10**, lines alone = 8, pairs+close45 = 7, **pairs alone = 8 (shipped)** — so **close-45 was NOT inert; my ablation measured rooms/carpet/R-8/R-2 and never doors** (fourth correction this week). **Not inherent, not dial-fixable**: sweeping the door-mask dilation peaks at 11 → **9 of 10**; the finder's `min_flank` / `face_tol` / `group_tol` were derived against a smeared band and need re-deriving against pair-built walls — **a separate one-variable change, not tuned here.** |
| **CARPET −31.3 CONFIRMED AS WALL FOOTPRINT (17 Aug)** | Isolating paint mode: wall band **540.9 → 583.2 sqft (+42.3)**, rooms **16 → 16**, **0.0 sqft from deleted rooms — all thinning.** Walls now occupy their true measured thickness instead of a 0.20 ft smear, so floor they used to overlap stops counting as carpet. R-2 rising to 98.0 / 98.4 is the confirmation. **Snapped doors are now in the standard judged set.** |
| **PAIR-BUILT WALLS SHIPPED (17 Aug)** | `_mask()` paints a filled **rectangle per measured pair** at its own measured thickness; the **inert 0.88 ft closing kernel is removed**; unpaired survivors take the sheet's own median wall (FLOOR PLAN 51 lines = 7% of length, FIRST FLOOR 0%, BRICK WORK 49%). **Both instrumented sheets improve: FLOOR PLAN R-2 97.0 → 98.0 (n=8), FIRST FLOOR R-2 96.8 → 98.4 (n=8)**; R-8 96.6 → **96.7**; rooms 16; footprint 1799.4 = 53% of plot and **94.7% of the printed stilt**; buckets 1307.5. **Two costs, reported: carpet 1203.5 → 1190.6 (−12.9) and snapped doors 10 → 8.** **DILATE 9 → 5, derived by sweep**: at 3 FIRST FLOOR collapses (11 rooms → 7, sample 8 → 5); 5 is the smallest that holds it and beats 9 on both sheets. **`rooms_checked` ratcheted** (FLOOR PLAN ≥8, FIRST FLOOR ≥8, GHATIKIA ≥14). |
| **RASTER ABLATION — what each step is FOR (17 Aug)** | **dilate 9 CONNECTS walls**: without it rooms are lost everywhere (FLOOR PLAN 16→15, GHATIKIA 14→10, FIRST FLOOR 11→9, BRICK WORK 12→11) — yet FLOOR PLAN's carpet RISES to 1241.8 and **R-2 to 99.5**, so it is also what makes rooms too small. **close 45 does NOTHING** (FLOOR PLAN byte-identical without it) — **so my "~0.9 ft band" was read from the code, never measured: the band is 0.20 ft** (50 spans × 316 ft = 62.6 sqft). **erode 5 is dilate's counterweight** (without it carpet 1185.0, R-2 95.7). The raster trades ROOM COUNT against ROOM ACCURACY and dilate is the dial. |
| **WHY THE TOILETS DIED — interior spans + the seal, not band width (17 Aug)** | flat-1's toilet has **3 union spans inside it** (one at y 14.13 cutting its 5.0 ft into 0.7 + 4.2 ft strips, both then in reach of the 4 ft seal); the lift toilet has **6**. Bands cost 0.20 ft per line (8% of a 5 ft room). **The seal is the proximate killer in all three cases** — C.TOILET and the passage (both 3.9 ft) have no interior span at all. **The union's fault is admitting pairs INSIDE rooms.** |
| **PAIR-BUILT WALLS — dependency map (17 Aug)** | `wall_gap_pairs` already measures every gap (79 pairs FLOOR PLAN, 427 FIRST FLOOR), so the input exists. Painting a filled rectangle per pair is confined to **`_mask()`**; every consumer still gets a mask. Must change: (1) `_mask()` paints pairs not lines; (2) **unpaired survivors have no thickness and need a rule**; (3) `walls_poly` from rectangles rather than contours. Unchanged: seal, ring bridging, door-gap fill, wing grouping, open-side flags, duct tests, all px↔ft via NORM_PPX. |
| **`rooms_checked` — report it, and probably ratchet it (17 Aug)** | R-2 held at 97.0 while a verifiable toilet was deleted: the room left the SAMPLE. Counts today — **FLOOR PLAN 8 · GHATIKIA 14 · FIRST FLOOR 8**. Proposal: pin `rooms_checked` beside the median (FLOOR PLAN ≥8, FIRST FLOOR ≥8); dropping dilate takes FIRST FLOOR to **6** while its median only moves 96.8→95.0. |
| **WHAT THE UNION BROKE — measured (17 Aug)** | The 70.6 sqft is **two toilets, not thinning**: every other room is identical to 0.1 sqft, so **70.6 of 70.6 = rooms lost, 0.0 = wall-footprint growth**. **flat-1's toilet — 35.9 sqft against a printed 7'6"×5'0" = 37.5, an R-2 room — is FILLED SOLID (0.0 sqft free space left)**; the second toilet (34.7, no printed dim) is **FRAGMENTED to 7.9 sqft** and dropped under the 18 sqft floor. Neither merged into a neighbour. **A sheet-verifiable room was destroyed → stays off.** **R-2 hid it**: 97.0 over **8** rooms became 97.0 over **7** — the lost room left the sample instead of lowering the score. **Root mechanism: band fattening.** The union adds **62.6 sqft of wall band for 50 spans**, because one line becomes a **~0.9 ft band**; an extra line inside a 5.0 ft toilet leaves under 4 ft and the seal fills the rest — the same family as C.TOILET dying at 3.9 ft. |
| **SIGNATURE UNION — BUILT, MEASURED, LEFT OFF (17 Aug)** | It admits **real wall**: 44 of the 50 new FLOOR PLAN spans have `ar wall` collinear with a face, 1 is pure hatch. (**My "20 are column faces" was an attribution artefact** — `=on` and `=nocol` give identical results, so the column layer contributes nothing.) **R-8 96.6 → 97.2 and the stilt check 94.7% → 95.4% of 1900 — but CARPET 1203.5 → 1132.9 (87.8% → 82.7% of printed 1370) and rooms 16 → 14.** More real wall = more wall footprint = thinner rooms: the total improves while the split worsens. **Degradation on carpet → left OFF** (`DRISHTI_SIG_UNION=off` default; nothing regresses). BRICK WORK would go rooms 12→15, carpet 502→589.6 (reported, not accepted). GHATIKIA and FIRST FLOOR unaffected — they already read by signature. |
| **CORRECTION — LAYER COVERAGE IS NOT WALL COVERAGE (17 Aug)** | The 12 Aug headline "22–100% of wall geometry discarded by layer name" **was half wrong**, and it drove Phase 1 for two weeks. On the fragmented sheets most of the discarded share is **non-wall the signature reader had already correctly rejected** (FIRST FLOOR keeps 14% of layer `0`, GHATIKIA 9%). |
| **LAYER-NAME ADMISSION CLOSED — and the per-line test already exists (17 Aug)** | `_geometry_wall_segs` (the W-1/W-3 pairing signature) is **already the separator** where it runs: FIRST FLOOR's layer `0` holds **1,709 lines and the signature keeps 242 (14%)**; GHATIKIA's holds 1,703 and it keeps **156 (9%)**. **Attempt 8 admitted the 86–91% the signature had already rejected** — hence 102% of plot. There is no separate "layer-0 wall" problem. |
| **PROPOSAL — RUN THE SIGNATURE READER AS A UNION, NOT A FALLBACK (plan only, 17 Aug)** | Today it runs only when named wall layers are absent, so FLOOR PLAN and BRICK WORK never see it. **On FLOOR PLAN it finds 97 spans, 50 not in the named set, and all 50 pass the position gate** — on real walls (north y 29.78, south y 0.00, partitions y 18.73 / 18.30 / 14.13). **So FLOOR PLAN can judge it**: R-8, R-2, footprint ≤ plot and the stilt check all apply. **No fifth drawing is needed** — the question was mis-framed: what is worth admitting is a SIGNATURE, not a layer, and FLOOR PLAN has 50 of them to test on. A sheet that prints areas *and* hides its walls stays valuable but is off the critical path. |
| **PHASE 1 ATTEMPT 8 — LAYER `0` REVERTED; the judging sheet is blind to it (17 Aug)** | On FLOOR PLAN layer `0` adds **nothing**: 10 of 112 candidates admitted (the same `ar stairs` lines), **101 rejected outside the trusted extent** — the gate correctly throws out its 13 lines at y −13.0..−7.9 — so every judged number is identical. Where it matters it is destructive: **FIRST FLOOR footprint 1664.3 → 3819.6 = 102% of its plot (physics violation)**, R-2 96.8 → 95.9; GHATIKIA carpet 1711.3 → 1226.0, R-2 58.6 → 54.2. **Layer `0` carries real wall and everything else unnamed; a pairing test cannot separate them.** Reverted. **Admitting by layer NAME is finished — what remains needs a per-LINE test that FLOOR PLAN can judge.** |
| **R-8 PIN RAISED to 96.6 (17 Aug)** | Evidence per §0.1: attempt 7's ring stopped biting a notch around the staircase. **The same admission read 78.4 on 16 Aug and 96.6 today — only the instrument changed. Six of seven Phase 1 reverts were the instrument rejecting a correct fix.** Standing lesson recorded: when a fix is rejected repeatedly, audit the judge before the fix. |
| **PHASE 1 ATTEMPT 7 — `ar stairs` ADMITTED AND HELD (17 Aug). First success in seven.** 10 of 11 lines passed the gate + pairing test. **R-8 91.8 → 96.6**; carpet 1203.5, rooms 16, buckets 1321.3, R-2 97.0, all unchanged; footprint 53% of plot. Attempt 6 was the identical admission and read R-8 78.4 — **the only thing that changed is the instrument.** **The footprint jumped +94.1 sqft (5.5%)** and Rahul's rule says treat that as a degradation; measured, the premise fails: **88.5 sqft of it is the STAIRCASE zone** (x 30.5–41.2, y 6.8–18.3 — the ring used to bite a notch around it), and against the independent printed **STILT of 1900** the footprint moved **89.6% → 94.7%**. **The ring encloses something it should.** Reported for ruling, not self-approved. |
| **THE LOBBY FLAG SHARPENED: 189.9 → 101.4 sqft (17 Aug)** | With the staircase inside the ring, the open-side flag is now the **LOBBY ALONE** — and closing its south edge gives **94.2 sqft against a printed 96.6, within 2.4 sqft**. Still discarded at the border, still unanswered. **The staircase is now inside built-up but still not a detected SPACE**, so common stays 30.9 vs printed 246. |
| **STEP 1 DONE — built-up is the PLATE FROM THE WALL RING (17 Aug)** | Branch **c** = footprint + projections beyond it. **FLOOR PLAN 1702.2 → 1791.5, R-8 87.2 → 91.8** (pin re-derived with evidence). Both old formulas still reported on `built_up_branch`. **Named pattern recorded: an instrument that FALLS when the parse improves is measuring an artefact of incompleteness** — `wall_material` collapsed 380.9 → 15.1 the moment the ring closed, so six Phase 1 attempts were judged by a measure that punished the fix. Unverifiable elsewhere (no printed statement): BRICK WORK 800.8 → 1128.0, GHATIKIA 2216.7 → 2660.8, FIRST FLOOR 1544.2 → 1731.7. **Plot headroom measured**: FLOOR PLAN uses **51%** of its plot (headroom 1665.7 sqft), FIRST FLOOR **68%** (headroom 790.1) — the tight one; a breach needs lines admitted OUTSIDE the building, which is what attempt 1 did (7,614 sqft on a 2,455 sqft plot). **STOPPED before step 2 as instructed.** |
| **WHAT STILL BLOCKS PHASE 1 — one thing, and it is an instrument (17 Aug)** | All six named blockers are gone. The one left was never named: **built-up = `floor_inside + wall_material`, and `wall_material` collapses when the wall ring CLOSES** — 380.9 sqft today, **15.1** when `ar stairs` was admitted on 16 Aug, because a closed ring becomes one outline with a hole nearly as large. Built-up fell 366 sqft, R-8 to 78.4. **Better wall reading makes our headline instrument worse.** **Smallest safe first admission (proposed, NOT built): (1) re-base built-up on the FOOTPRINT + projections — 1705.3 + 86.2 = 1791.5 = 91.8% of the plate vs today's 87.2%, and it RISES as walls improve; (2) then admit `ar stairs` on FLOOR PLAN alone**, judged on carpet · rooms · footprint ≤ plot, with R-8 finally stable under it. |
| **SEAL FLAG RULED OFF (17 Aug)** | `DRISHTI_SEAL_MODE=passes` stays OFF by default: it gains 5 R-8 points on FLOOR PLAN but puts R-2 at exactly 95.0, on the floor with no margin. **BANKED, waiting on wall detection: +98 sqft carpet, +5.0 R-8**, to be turned on when FIRST FLOOR's walls are read and both instrumented sheets can confirm it. |
| **DEDUPE + THRESHOLD RE-DERIVED (17 Aug)** | **4,335 zero-length segments + 858 duplicates of BRICK WORK's 4,960** are dropped upstream of `keep_structural_lines`. **My 686k-pair performance flag was half wrong**: that count came from my re-derived list taken *before* the building crop — production sees **442** segments there. One number moved: BRICK WORK built-up **803.4 → 800.8** (−2.6, 0.3%, uninstrumented); instrumented sheets identical. **My 1.5 ft space-filling threshold also understated everything**: against each sheet's own wall thickness the blanket fill is **78% / 75% / 68% / 62%** wider-than-a-wall (BRICK WORK / GHATIKIA / FIRST FLOOR / FLOOR PLAN) versus my 17/39/35/42%. |
| **TWO PASSES BUILT — separation is right, and it cannot rescue a fragmented sheet (17 Aug)** | Pass 1 **WELD** (`weld_bridges`: proximity + **along a wall run**, grid-indexed) and pass 2 **BREAK** (`collinear_bridges`). Both work: **FLOOR PLAN gains C.TOILET + the passage — carpet 1203.5 → 1301.5, R-8 87.2 → 92.2**, ducts kept, footprint ≤ plot, R-2 95.0. **FIRST FLOOR still collapses to 2 rooms with 514 welds firing.** Measured reason: the blanket close adds **493.9 sqft of "wall" there, 35% of it wider than 1.5 ft and up to 8.4 ft** — **it is not welding a network, it is SUBSTITUTING for one**, so that sheet's 11 rooms exist *because* the kernel fills space. **What FIRST FLOOR needs is wall DETECTION, not a better seal.** Default left on `blanket` (nothing regresses); `DRISHTI_SEAL_MODE=passes` selects the separated version — **+98 sqft carpet and +5.0 R-8 waiting behind that flag**. |
| **DUCT CONTAINMENT FIXED (17 Aug)** | A void inside a room is still a void: the old rule suppressed both FLOOR PLAN ducts as soon as enlarged rooms covered them. Now the test is whether the duct's interior is already FREE space (it is not — a wall-ringed void reads solid), so containment no longer suppresses. Both ducts survive under either seal mode. |
| **COLLINEAR SEAL — BUILT AND REVERTED (17 Aug)** | Wired in place of the blanket close. **FLOOR PLAN improved exactly as predicted**: C.TOILET + passage returned, carpet **1203.5 → 1313.8 (+110.3)**, **R-8 87.2 → 92.5**, R-2 96.9, footprint 1704.2 ≤ plot. **But FIRST FLOOR — instrumented — collapsed: 11 rooms → 2, R-2 96.8 → 0.0**; GHATIKIA 14 → 2. **Reverted, not tuned.** Cause: those sheets' wall fragments are **not collinear** (the geometry reader emits short offset spans), so the gaps holding them together are not breaks in a run — 246 bridges fired on FIRST FLOOR and none were the ones that mattered. **THE SEAL IS TWO JOBS IN ONE KERNEL** — and the second was NAMED WRONGLY here, corrected 24 Aug: it is **BREAK CLOSE** (doorways and drafting breaks, derived from the drawn leaves) and **OUTER-RING CLOSURE** (envelope gaps, already built as `_free_ring_endpoints` with a relative bound), **not "fragment weld"**. Nothing was welding disconnected interior fragments. **Naming a mechanism wrongly sent us looking for a signature that did not exist**, for a week. Fixing either half still breaks the other; a future fix must do them separately. `collinear_bridges()` + 4 tests kept — the criterion is right. |
| **THE SEAL FIX — MEASURED, NOT BUILT (17 Aug)** | **Removing the seal is ruled out**: at `DRISHTI_SEAL_FT=0` BRICK WORK goes rooms 12→4 (carpet 502→210.6), GHATIKIA 14→3 (R-2 58.6→**0.0**), FIRST FLOOR 11→3 (carpet leaks 1005.7→1972.3), and even FLOOR PLAN worsens (rooms 16→13, R-8 87.2→84.2). **The collinearity principle works on the gaps that matter**: all three large gaps classify as **FACING WALLS (a room)** with no threshold — C.TOILET 25.8, passage 45.1, balcony strip 13.3, each flanked by two parallel walls running along the gap rather than collinear ends. **Inconclusive on 5 small gaps** (2.1–9.3 sqft, 26.1 total) where no wall segment hugs either face — those need a second signal. |
| **THE 93.5 sqft IS NOT ALL CARPET (17 Aug, corrects my own arithmetic)** | Under R-9: C.TOILET **25.8** + passage **45.1** = **70.9 carpet**; the 13.3 strip sits inside flat-2's traced balcony pocket (62.33–71.95, 14.09–17.46) so it is **balcony, excluded**; 9.3 unresolved. **flat-2 → 644.5 vs printed 690, short 45.5 (6.6%)**, not the 22.9 I reported. The two unknown strips: **9.3 sqft at (80.1, 2.6)** between A.TOILET and the east bedroom, **9.1 sqft at (25.9, 2.0)** between flat-1's living room and the common strip — both circulation-shaped, neither labelled. |
| **C.TOILET: OUR SEAL FILLS IT IN — root cause found (17 Aug)** | Its four sides are all drawn (west pair 71.66/72.08, east shared with A.TOILET 76.08/76.49, north y 13.26, south 1.50 ft of wall + a 2.26 ft door). In the unsealed mask `m` the interior is correctly FREE; in `m_env` it is SOLID. **`DRISHTI_SEAL_FT = 4` bridges gaps up to 4 ft and C.TOILET's interior is 3.9 ft** — A.TOILET beside it is 4.5 ft and survives. Not a §0.2 case, not a drafting error: **our bug.** |
| **THE SEAL SWALLOWS 102.5 sqft — INCLUDING THE PASSAGE (17 Aug)** | Free in `m`, solid in `m_env`: **C.TOILET 25.8** (printed 26.0), **flat-2's PASSAGE 45.1 (11.8 × 3.9 ft)**, plus 13.3, 9.3, 9.1 strips. **93.5 sqft of it is in flat-2**, which was short 116.4 → returning it leaves **22.9 short (3.3%)**. **We DO detect circulation and then fill it in** — the same shape of failure as the border test: found, then destroyed downstream. |
| **CARPET CONVENTION (§9 R-9, Rahul 17 Aug)** | Carpet = named rooms **+ PASSAGE/circulation**, excluding balconies, balcony-type spaces (the utility) and all walls. **Carpet stays 1203.5 / 1370 = 87.8%; the 90.5% alternative is withdrawn.** flat-2's 85 sqft unnamed remainder is circulation. §11 now carries: flat assignment must read the printed `FLAT-1`/`FLAT-2` labels, not an x-split. |
| **CARPET GAP LOCATED — CONCENTRATED, not distributed (17 Aug, measured)** | Every room we find is within **1.6–3.9 sqft (~2%)** of its printed size across 8 dimensioned rooms, so boundaries are right; the gap is **whole spaces**. **flat-2's C.TOILET (printed 4'0"×6'6" = 26 sqft) has NO free component at all** — its label at (74.1, 10.7) is inside no room polygon. **flat-2's BALCONY is merged into the 233.4 sqft dining** (label at (67.4, 15.7) IS inside that polygon). Two rooms read OVER, both L-shaped bbox artefacts: living +25.2, dining +5.6. |
| **FLAT ASSIGNMENT — we guess it from x, the sheet states it (17 Aug)** | Splitting by the common strip puts flat-1's **TOILET (34.7)** and **UTILITY (36.1)** in the common band though both belong to flat-1. Returned to flat-1: **629.9 vs printed 680 (short 50.1)**; if the printed carpet includes the utility, **666.0 vs 680 — within 14 sqft (2%)**. flat-2 stays **573.6 vs 690, short 116.4**. The sheet prints `FLAT-1` / `FLAT-2` labels and we do not read them — there is no flat-assignment rule at all. |
| **BASIS SWEEP — all 8 comparisons checked (§10.2 D-9, 17 Aug)** | Two are wrong and now explicit: **flats-only** (reported, never judged) and **projection** (the SHEET is wrong — Rahul's ruling; our 86.2 stands, its 51 omits the utility, flagged as a Plan Doctor `ask`, never reconciled). Five agree: plate built-up, carpet, R-2 room dims (clear ±0.16 ft), B-5 balcony width (±0.13 ft), footprint≤plot. One measured residual: **+5.8 sqft** in the 246. **CARPET'S BASIS IS VALID — 87.8% stands**: printed 1370 = 680+690 flats-only with common excluded, ours is flats-only too, so the 166.5 sqft gap is genuine coverage. Open: if the printed carpet includes the UTILITY, ours is 1239.6 = **90.5%** (2.6 points of uncertainty). Per-flat ours **595.2 / 573.6** vs printed **680 / 690**. **Finding: the same sheet uses TWO conventions** — rooms clear-inside +2 in, the lobby wall-to-wall (14.09 clear vs printed 15'8"). |
| **R-8 RE-BASED TO THE PLATE + FIFTH INSTRUMENT (16 Aug)** | §10.2 **D-8**: printed flats 1705 + common 246 = **plate 1951**, and the sheet self-confirms it — printed **STILT 1900** + **51** sqft of projection. R-8 now compares whole-floor to whole-floor: **87.2% unconfirmed** (pin re-derived, was 99.4 against a flats-only basis), **96.6% confirmed**. Flats-only still reported on its own row. **THE STILT CROSS-CHECK is the fifth instrument and it is free** — `plate − projections ≈ stilt`, from numbers already printed. FLOOR PLAN: **printed 51 vs parsed 86.2 = 31.0%**, kept out of the verdict while unruled (it flipped the grade C→D). **The gap is exactly the utility**: balcony **50.3 matches the printed 51 within 0.7 sqft**; utility **35.8** we count as projecting, the sheet does not. Both 100% outside the ring. |
| **CONFIRMATION PATH BUILT — and it exposed a BASIS ERROR IN R-8 (16 Aug)** | UI card (Confirm / Reject) → `/recompute` → `corrections.confirm_open_sides`, answer stored on the flag so it is never asked twice; the closing edge uses the sheet's **measured envelope thickness**, not a constant. **Confirming FLOOR PLAN's south edge: common 30.9 → 213.6** (182.7 + lift 23.6 + ducts 7.3) vs printed 246; carpet 1203.5, footprint 1705.3 ≤ 3371, buckets 1321.3 → 1504.0 all consistent. **But R-8 falls 99.8 → 89.4 — STOPPED per instruction.** Cause is the instrument, not the parse: printed `built_up_total` **1705 = the two flats only** (870+835), with 246 common listed **separately**, so the printed whole-floor plate is **1951** — against which the confirmed 1884.9 is **96.6%**. **R-8 read 99.8 only because the common area was missing: two errors cancelling.** Default state is unconfirmed, so no number moves until a user answers. |
| **THE 246, CLOSED BY MEASUREMENT (16 Aug)** | lobby+staircase **182.7** (one space, no wall between) + lift **23.6** + ducts **5.0 + 2.3** + **wall material 38.1 measured** inside the block = **251.8 vs printed 246 → residual +5.8 sqft (2.4%), NOT attributed** (if the 246 excludes the ducts it is 244.5, −1.5; that is a candidate, not a finding). Bases per D-4: spaces inner-face/clear, ducts include their drawn faces, block outline 289.4 to outer faces. Block outer **15.62 × 18.50 ft**. **Lobby measures 14.09 ft clear vs printed 15'8" — 14.09 + 2×0.79 = 15.67, so the printed dimension INCLUDES its flanking walls.** |
| **§0.2 ASK PATH BUILT — flag only, no number moved (16 Aug)** | `open_side_regions()` → `meta.open_side_regions` + a Plan Doctor issue at a new level **`ask`** (excluded from grade and score: a question about the drawing is not a defect in us). Discriminator is **three sides backed**, not border-touching. **FLOOR PLAN flags exactly ONE: 189.9 sqft open to the south, backed 100% N/E/W → 184.1 sqft if closed.** It does NOT flag the 985.5 sqft outside component or the 122.7 sqft balcony strip. GHATIKIA flags one 214.0 sqft region open north (reported, not accepted); BRICK WORK and FIRST FLOOR flag nothing. Question surfaced verbatim: *"is there a wall here?"* — **nothing auto-closed, nothing counted.** |
| **THE COMMON AREA IS FOUND, THEN DISCARDED — first real CONTRADICTS (16 Aug)** | The lobby+staircase **already form ONE 189.9 sqft component** (x 27.1–41.2, y −0.2–18.3) in the parser's own sealed mask, with the lift (23.6) and both ducts (5.0 + 2.3) separately enclosed inside its outline. **189.9 + 23.6 + 7.3 = 220.8 against the printed 246**, the rest being internal wall thickness. It is dropped by the **border test**: the south edge is not drawn as a wall, so the region reaches the raster edge and is classified as outside. The south edge IS drawn — a **2 in double line on layer `ar furniture`**, 15.67 ft = the lobby's printed 15'8" — below the 3 in wall minimum. Rahul confirms a wall exists there in reality. **The fix is the ASK path (§0.2), not a parsing change.** |
| **THE NORTH WALL WAS NEVER THE MISSING PIECE (16 Aug, corrects 14 Aug)** | Admitting `ar stairs` gained nothing because the region was already there. Six attempts were spent admitting walls for a space the parser finds correctly and then throws away. |
| **BUILT-UP BRANCH INSTRUMENTED — `built_up_branch` (16 Aug)** | All four sheets fire branch **b** (`floor_inside + wall_material`); the untaken branch **a** (`gross_outer`) would read 1247.9 / 235.9 / 520.2 / 317.6 — **cliffs of 454 to 1697 sqft**. **My "branch flip" diagnosis of attempt 6 was wrong**: the branch never changed, `wall_material` collapsed **380.9 → 15.1** inside branch b when the ring closed. R-8 sits downstream of both. |
| **PHASE 1 ATTEMPT 6 — `ar stairs` TRIED AND REVERTED (16 Aug)** | First attempt since balcony stopped being a mask difference. **The old failure mode is gone — the balcony SURVIVED at 50.8** where five earlier attempts collapsed it to 0, and 10 of 11 lines passed the position gate + pairing test. But FLOOR PLAN degraded by a **different** mechanism: **built-up 1702.2 → 1336.4, R-8 99.8 → 78.4**, footprint 1705.3 → 1799.3. `area_statement` picks between ONE ENCLOSING OUTLINE (`built_up = gross_outer`) and THIN WALL STRIPS (`floor_inside + wall_material`); the admitted lines flipped it from the first to the second and 366 sqft went with it. **And it gained nothing: common stayed 30.9, the lobby still did not enclose, the staircase still did not appear.** Reverted, not tuned. **The next blocker is the built-up SHAPE TEST in `area_statement`, not the balcony.** |
| **§4 D-7 RULING — corner-carved ducts count, implementation DEFERRED (16 Aug)** | A duct is a void enclosed on all sides, standalone or carved into a corner; the overhang test asks a drafting-style question. Rahul: do not loosen it yet — the only evidence is on GHATIKIA and FIRST FLOOR, which fail everything else. Recorded in §4 as D-7, revisit when those sheets are trustworthy. |
| **COMMON AREA: 215.1 OF 246 STILL ABSENT, and it is TWO spaces not one (16 Aug)** | We hold **30.9**: the lift 23.6 (still typed `stairs`) + ducts 7.3. Missing: the **LOBBY** (printed 15'8"×6'2" = **96.6**) and the **STAIRCASE** (**~124 — INFERENCE by subtraction, not printed**) — both in the same core zone (x 27–41), both undetected, both needing walls read by signature. **PHASE 1's BLOCKER IS GONE**: the 14 Aug rule "nothing can be admitted until balcony stops being `foot_ext − foot`" no longer applies — balcony has come from the drawn railing edge since 15 Aug and the mask subtraction is deleted (`foot_ext` now feeds the overlay only), so admitting `ar stairs` cannot collapse the balcony by that mechanism. **The lobby is not the only thing between us and 246 — the staircase is the bigger half.** |
| **DUCTS DETECTED (16 Aug, built) — common area, voids, never solid** | Read from the **drawn rectangle** (`enclosed_boxes`), because the specified raster route is impossible: a 1.00 ft duct interior against a 0.88 ft wall-merge kernel fills solid, so no area floor can reach it (that attempt also admitted a 3.2 sqft false pocket in the test fixture and was reverted). **FLOOR PLAN: 2 ducts, 5.0 + 2.3 sqft — exactly the two Rahul described — common area 23.6 → 30.9, built-up 1694.9 → 1702.2, R-8 99.4 → 99.8.** BRICK WORK 2 (3.7, 3.0), common 75.7 → 82.4; GHATIKIA and FIRST FLOOR 0. Carpet and R-2 unchanged everywhere. Ducts carry `void: true` — no floor, no walk-in beacon, never solid structure in 3D. **Two impostor shapes are rejected**: a wall body sliced by cross-walls (its faces overhang the box) and a door opening drawn as its own rectangle (as narrow as the wall itself, measured per sheet). |
| **R-8 RATCHET RAISED to 99.4** (actual **99.8**) | Evidence per §0.1 in `ground_truth.json`: the cause is the utility (36.1 sqft) and the two ducts (7.3 sqft) — spaces that were in no bucket at all — not tuning. Pinned at the authorised 99.4, not the achieved 99.8. **Only ONE red ratchet remains: the golden `snapped >= 11`.** |
| **DUCTS RE-MEASURED — my "2 of 26 columns are ducts" was WRONG (16 Aug)** | The REAL ducts are on layer **`ar wall`** as plain 4-line rectangles: **x 25.58–26.58, y 7.89–12.90 = 1.00 × 5.01 ft (5.0 sqft)** and **x 25.58–26.58, y 4.75–7.06 = 1.00 × 2.31 ft (2.3 sqft)**. Every column is **0.83 × 1.33 ft** on layer `column`. They match in **neither** dimension (D-6: a duct is sized by maintenance reach, a column by load) and were **never in the column set — the count of 26 is correct**. What I called ducts were the two columns bracketing them. **The real gap is DETECTION**: at 5.0 and 2.3 sqft both fall under the 18 sqft small-room floor, so they are invisible to the parser and absent from common area. |
| **X-IN-A-RECTANGLE IS DEAD, and it would have been worse than feared (16 Aug)** | Rahul: FIRST FLOOR draws columns as bold rectangles with a bold cross, BRICK WORK as a plain rectangle with a cross. Measured here: **all 26 FLOOR PLAN columns carry a true corner-to-corner X** plus 41–44 hatch strokes. The proposed test would have voided the column set on **3 of 4 sheets**. C-2 and D-1 were measured anyway and separate nothing: the two mis-called boxes sit at 7 same-size neighbours at 10–20 ft (dead centre of the grid) and **on** wall junctions — the column predicate. |
| **THE 12.33 FT "FALSE POSITIVE" IS THE UTILITY (16 Aug, correction)** | Called a false positive in four reports. It is the tracer correctly seeing flat-1's utility: 12.33 ft run, 1 turn, both ends on wall, depth **4.91 ft** against a printed **4'6"**, at x 25.6–33.2, y 19.1–24.1. Per CE-5 the utility IS balcony-type, so this is a TRUE positive rejected only because the printed-width list is balcony-only (`printed_widths(toks, "UTI")` already reads 4.5). Not fixed — that is a build. |
| **CHHAJA EXPORTED FOR RULING (16 Aug)** | `overlays/10-chhaja-only-FIRST-FLOOR.png` (403 lines) and `10-chhaja-only-GHATIKIA.png` (19). Hatched bands on the OUTER wall at window/opening positions = sunshades in plan. **BRICK WORK and FLOOR PLAN have NO chhaja layer**, so the requested BRICK WORK export would be blank — the ruling has to be made on the neelachala pair. |
| **FOURTH INSTRUMENT BUILT — `meta.dimension_anchors` (15 Aug, additive)** | `server/dimensions.py` (pure) + 10 tests. Per dimension: value, both endpoints, nearest detected wall face, distance; summary = endpoints landing within 0.5 ft. **BRICK WORK 65.5% (97/148 over 74 dimensions) — the sheet blind on R-8, R-2 and B-5 now has an instrument**; FIRST FLOOR 60.4% (134/222, 111 dims); GHATIKIA 55.8% (29/52); **FLOOR PLAN 43.4% (33/76)**. Route per sheet: `dim` LAYER (FLOOR PLAN, BRICK WORK — extension lines followed to the edge per D-2) or TEXT (the neelachala pair). **Feeds nothing**; no number moved on any sheet. **LOCATED 16 Aug — they are SHEET FURNITURE, not missing walls** (my 15 Aug reading corrected): of FLOOR PLAN's 29 red endpoints, **8 = AREA STATEMENT table rules, 8 = sheet frame corners, 12 = the ARCHITRAVE logo, 1 = a leader line to the plot boundary. Zero are missing wall faces.** All sit on the `dim` layer. Excluding sheet furniture, FLOOR PLAN scores **33/45 = 73.3%** (BRICK WORK 66.4%, GHATIKIA 55.8%, FIRST FLOOR 57.5%). PNGs: `overlays/8-dimension-anchors-FLOOR-PLAN.png`, `overlays/9-dimension-anchor-red-zoom.png`. **VALUE FILTER BUILT 16 Aug (D-3)** — a candidate line with no value near its midpoint is not a dimension: **FLOOR PLAN 43.4 → 79.4%** (38 candidates → 17), **BRICK WORK 65.5 → 70.2%** (74 → 47), the two text-route sheets unchanged (value-anchored by construction). Still additive, still feeding nothing. |
| **ARROW INSTRUMENT — FEASIBILITY (15 Aug), superseded by the build above** | §10.2 D-7. Endpoint-to-nearest-detected-wall-face: **BRICK WORK 61% ≤0.5 ft / 83% ≤1 ft over 74 dimension lines — the sheet blind on all three existing instruments**; FIRST FLOOR **76% / 81%** over 121 anchored dimensions (median 0.00 ft); GHATIKIA 55% / 78% over 26; **FLOOR PLAN only 42% / 42%** over 38. Two routes: a `dim`/`dimension` LAYER (FLOOR PLAN, BRICK WORK) or LIVE TEXT anchoring the nearest long line (FIRST FLOOR, GHATIKIA). BRICK WORK has **zero live words** — layer route or OCR only. Feasible on all four; extraction quality, not the idea, is the open question. |
| **TWO BLOCKS, ONE BUILDING — the tool discards most of it (15 Aug, measured)** | `wing auto-pick: wing 1 is the floor plan (rooms=7, doors=12)` — the WING SPLITTER keeps one block and drops the other with a warning only. Reported: **38.25 × 64.17 ft**. Both blocks kept: **41.6 × 180.6 ft**. Missing: the top block, 96.7 ft deep, **3 of 5 flats**. FIRST FLOOR's R-2 96.8 therefore measures room sizes **in one block**, not the building. Candidate general rule (Rahul's, and it holds here): *an empty band splits a sheet only if NOTHING crosses it* — on the other three sheets there is **no empty band ≥6 ft at all**, so the rule is inert there; the corpus contains **no true two-views sheet**, so it is untested against the case it must reject. **Measured, not built.** |
| **BLOCK DEPTHS — the 6.6 ft is RESOLVED (15 Aug)** | Top block **96.7 ft** measured wall extent (the sheet prints no vertical dimension for it). Bottom block **70.8 ft** measured against printed **64'-2"** — **not an error**: the printed dimension is wall-to-wall EXCLUDING the bottom-left balcony, ours INCLUDES it (§10.2 D-4). The `41'` on the opposite side is a PART dimension excluding a 6'7" duct near the lift (D-5). **State the basis in every printed-vs-measured comparison.** |
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

## OPEN — state as of 28 Aug 2026 (written for a cold return)

Four buckets: **CLOSED** (do not reopen), **MEASURED, UNEXPLAINED** (we know the
number, not the cause), **OPEN** (next action known), **HELD** (Rahul's call).

| item | bucket | state + next action |
|---|---|---|
| **THE SEAL** | **CLOSED — DO NOT REOPEN** | The seal and the outer ring are **one operation in two pieces**, not two sharing a constant: `_free_ring_endpoints` hunts gaps in a mask whose doorways are already closed, and fed the raw mask the footprint fell on all four sheets (−17% to −58%). Four attempts, the last three a full session each. The only remaining idea — bridge between drawn SEGMENT ends only, ignoring raster gaps (`seg_px` is already passed in) — is **not to be attempted** until something else makes it cheap. |
| **GHATIKIA two views** | **CLOSED — shipped** | `_empty_bands` splits a group when its interior holds a band with zero ink across the full perpendicular extent, measured on `cover`. Inert on all three single-view sheets. **Do not move this to the wall mask** — there FIRST FLOOR shows a 14.01 ft empty band and splits back into the two blocks ruled one building. |
| **FIRST FLOOR two blocks** | **CLOSED — shipped** | Joined by the band rule (terrace hatch, 19 diagonal strokes). `rooms_checked` 8 → 16. |
| **GHATIKIA scale** | **CLOSED — shipped at ppf 7.189** | Refit from printed room dims, accepted on **dimension anchors 56% → 69%**. Two later attempts to improve it were rejected by the same instrument. |
| **GHATIKIA's remaining 9%** | **MEASURED, UNEXPLAINED** | The nine single-label rooms read **0.9131 ± 0.0362 (S/N 2.4)** — a real systematic residual, implied ppf 6.564. **We have no correction that survives an independent test**: filtering the refit sample to single-label rooms tightened every internal statistic and R-2, and **dropped the anchors 69% → 65%**. Not a pending fix. Next action: none until a non-fitted signal for scale exists. |
| **FIRST FLOOR's two ~590 sqft blobs** | **MEASURED, UNEXPLAINED** | Merges by the corrected discriminator (5, 4 and 5 printed labels inside). **The bottom block isolates 8 of 9 printed spaces (89%); the top block 7 of 19 (37%)**, at 1.9 labels/room against 1.0. Ruled out: missing partitions · wall detection (the top block reads **better**) · unpainted wall (both 100%) · gap width (the resolving block's are **wider**) · doorway necks (test withdrawn) · the seal. **Unnamed: why a more finely subdivided flat fails to separate when its walls read better.** |
| **FIRST FLOOR plot check** | **CLOSED — live** | **4472.1 / 11500 = 38.9%**, `plot_source` `user`. Rahul's figure reaches the parse through the 22 Aug user-entry path, applied **by the eval** — the parser still does not read `ground_truth.json` and must not. GHATIKIA and BRICK WORK remain **blind and say so**. |
| **FIRST FLOOR envelope coverage** | **MEASURED, UNEXPLAINED** | The scorecard's **71% uncovered is STALE** — it was measured while the splitter dropped a block. With both blocks built: **19.0%** over 499 ft (FLOOR PLAN 3.2%, GHATIKIA 22.1%). Still 6× FLOOR PLAN. A 19% question, not a 71% defect. |
| **ppf → footprint is NON-LINEAR** | **MEASURED, ONE CAUSE RULED OUT** | Extent tracks ppf smoothly; **footprint STEPS**. On GHATIKIA, ppf 7.17 → 7.19 moves footprint **1555.5 → 1996.8 (+28.4% on a +0.28% input, ~100×)**, as accepted ring bridges go 135 → 141 — six openings appear at once. **`min_gap` is RULED OUT (28 Aug):** derived from the measured wall it makes the gap/wall ratio ppf-invariant and **the step remains** (+17.1%, +12.6%, +13.6%) — and it broke the judged set on all four sheets, so it was reverted. **The binning is RULED OUT too (28 Aug):** bins move 109 → 110 and bin-edge proximity *falls* across the step; the W-3 band is flat at 360 pairs. **The wing bbox is RULED OUT too — that was a correlation.** `_seg_px` comes from ALL of `struct`, unfiltered by wing; `keep_structural_lines` already *receives* 309 at 7.17 and 320 at 7.19. **THE CONSTANT IS NAMED: `th_max = 0.92 * ppf` in `_geometry_wall_segs`** — the 11-in ceiling of a band **local to that function**, in POINTS, scaling with ppf against geometry fixed in points. Across the step: lines **685 = 685**, `L<6` drops **1010 = 1010** (neither crosses); `th_max` 6.5964 → 6.6148 pt, pairs **188 → 197**, and pairs within 1% **above** the ceiling **26 → 0** — the cluster crosses en masse. **`wall_gap_pairs` stayed flat because it uses W-3's 3–18 in; this function has its own 3–11.04 in.** The **21 Aug W-3 unification fixed five sites and missed this sixth**. **FIX BUILT AND REVERTED (29 Aug):** switching to `wall_gap_band(ppf)` **smoothed the curve** (−0.2% to −0.6% per step, no jump) **and killed the wing flicker** — diagnosis confirmed. But **FIRST FLOOR moved (+5.6%)** and **GHATIKIA's anchors fell 69% → 62%** because the new segments knocked out its scale refit (ppf 7.189 → 8.8, R-2 83.5 → 61.3). **Substantive finding: W-3's own band is not derived either** — 18 in is 1.8× FLOOR PLAN's measured wall but **4.5× GHATIKIA's**; unifying swaps a band too narrow on one sheet for one too wide on three. The right target is a band as a **multiple of the measured wall**, across all six sites. Ruled out so far: `min_gap` · the run binning · the W-3 band (flat at 360) · the wing bbox. **Second, worse instability: the wing AUTO-PICK flips** — at ppf 7.15 GHATIKIA builds the RIGHT view, at 7.13/7.17/7.19 the LEFT. **A 0.3% input change silently swaps which drawing every number describes, and no output says so.** **The auto-pick is ANNOUNCED (shipped): `wing_pick` carries the score, runner-up, margin, and — because INDEX IS NOT IDENTITY — the chosen wing's `origin_ft`/`bbox_ft`.** At ppf 7.1485 and 7.150 GHATIKIA builds the RIGHT view (origin x 53.6) while `index` stays 0; it **flickers**, and footprint moves <1% across it. A one-unit margin raises a §0.2 ASK — **which does not fire at the flicker point; only the origin catches that**. Component-touch membership was **not built** — its premise was the bbox, which is disproved. **`footprint ≤ plot` is our only physics check and reads a quantity that can jump 28% on a 0.3% input.** Judge any future ppf change against this curve, not a single point. |
| **`threshold_margins` — "no threshold on a cluster" as an INSTRUMENT (29 Aug, shipped)** | **CLOSED — built** | Per threshold: nearest gap-histogram peak, distance, and the population within 5% that would cross **together**. **Reproduces the known cliff** (GHATIKIA `geom_max` 11.04 → peak 11, dist 0.04, 30 pairs) **and found a NEW one: BRICK WORK's `W3_min = 3.0 in` sits exactly on its dominant 3 in peak, 38 pairs, live at FIVE sites.** Needs a `sizing` split or it cries wolf — a median lands on its own peak by definition. **Deepest finding: `min_flank = W` is on a peak on all four sheets BY CONSTRUCTION** — W is the median of the distribution it filters, so it sits at the **mode**. |
| **`min_flank = W` at the mode** | **OPEN — standing rule 4 (31 Aug)** | **Never derive a SELECTING threshold from a statistic of the distribution it selects from.** W is the median gap and `min_flank` filters gaps, so it sits at the **mode** — on a peak on all four sheets, **38 / 18 / 122 / 61 pairs within 5%**, by construction. `face_tol = W/2` the same on two. A statistic may **size** something; it must never **select** within its own population. |
| **BRICK WORK `W3_min` on its own peak** | **OPEN — live latent cliff (31 Aug)** | Its median wall **is 3.0 in** and W-3's floor **is 3.0 in** — dominant class on the threshold, **38 pairs within 5%**, floor live at **five sites**, on the sheet with no instruments and a door count that has moved 11 → 12 → 20 → 17. Found by `threshold_margins` on its first run. Not fixed. |
| **`meta.threshold_margins`** | **CLOSED — emitted (31 Aug)** | One definition, computed in the parser; the scorecard consumes it rather than re-deriving (the `wing_at`/`wing_pick` trap). Includes the sizing/selecting split. |
| **W-3's band** | **OPEN — but NOT as a multiple (29 Aug)** | **A multiple band is arithmetically impossible and the wrong model.** It can agree with an absolute band at exactly one wall thickness, and FLOOR PLAN's is 10.0 in against GHATIKIA's 4.0 in: **0.30–1.80× holds FLOOR PLAN exactly and costs GHATIKIA −29%; 0.75–4.50× holds GHATIKIA and costs FLOOR PLAN −32%.** And the data says why — gap peaks are at **4–5 in and 9–11 in on three of four sheets**: masonry classes are **absolute**, so the median wall is a **mix**, not a scale. **The defect was that the private 11.04 in ceiling sat ON GHATIKIA's 11 in external-wall peak.** The rule is **"no threshold may sit on a cluster"** — 3–18 in satisfies it everywhere; 3–11 cannot. **ANSWERED: it cannot, the guard is not the problem, and the band admits NON-WALL.** Of the pairs 3–18 in newly admits (GHATIKIA 53, FIRST FLOOR 48), **83% and 75% re-use a face already in a real wall** — 26%/33% span a room between two opposite walls, a further 57%/42% pair a real face with a stray. At best 9 and 12 are genuine. FLOOR PLAN is unharmed only because 18 in is **1.8×** its 10 in wall, against **4.5×** GHATIKIA's and **3.6×** FIRST FLOOR's. Under the unified band GHATIKIA's refit reads S/N **0.95** against a guard of 1.0 — the median barely moves (0.817 → 0.84) while the **scatter rises 0.105 → 0.168 (+60%)**, because 78 pairs at 11–18 in (2.75–4.5× that sheet's 4 in wall) are admitted. **Loosening the guard would mask the over-admission.** The refit collapse and FIRST FLOOR's +5.6% are one cause seen twice. |
| **`L < 6 pt` · `BORDER_MAXLEN_PT` · `abs(d) < 0.5 pt`** | **OPEN — reported, none crossing** | `L < 6 pt` means 0.12 / 0.21 / 0.83 / **1.05 ft** per sheet. `BORDER_MAXLEN_PT` = 17 / 32 / 125 / 158 ft; **BRICK WORK sits at 88% of its cap**. `abs(d) < 0.5 pt` is categorical, discarding **22% of FIRST FLOOR's linework** — and is why the terrace hatch is invisible to the wall reader. |
| **`join_tol` = 0.35 ft, fixed** | **OPEN — ninth multi-purpose constant** | `join_tol = 0.35 * NORM_PPX` is a constant in FEET, never derived from the drawing, and it bins wall runs in `_free_ring_endpoints`. Recorded 28 Aug on Rahul's instruction; **not to be fixed in the current change**. |
| **The nine route floors** | **OPEN — 3 emitted, 1 inferable, 5 invisible** | Emitted: `door_median` · `stair_ladder_dedupe` · `door_symbol_paths`. Inferable: `len(struct) < 30` (ladder reads "not reached" on the layers route) — but the **margin** is never visible. Invisible: `len(gsegs) >= 8`, `len(votes) < 8`, `len(close) < 8`, `len(_live_toks) < 50`, `len(_live_all) < 50`. **The one to watch: GHATIKIA's `door_median` sample is 8 against a floor of 5 — the closest any sheet sits to any floor — on the sheet whose door count has moved 45 → 22 → 18.** Four fewer snapped doors and every caller drops to `NOMINAL_DOOR_FT`. |
| **A. Door frame** | **HELD — Rahul's call** | Geometry in hand; +36–117 meshes. **Only reaches the ARC route, i.e. FLOOR PLAN alone.** |
| **B. `doors_placed_sound` position** | **CLOSED — shipped** | `hinge_on_cut` ratcheted 12/12; `leaf_inside_plan` 11/12 reported not ratcheted (the miss is the CE-5 utility door and is correct). Pinned on **one route**. |
| **BRICK WORK door count** | **HELD — no movement is evidence** | 11 → 12 → 20 → 17 in two days, and no instrument on that sheet can judge it. It hands the symbol grouper **0 paths**, so all its doors are leafless. |
| **GHATIKIA's 3 merges** | **OPEN** | `dining` 292.9 (4 labels), `dining` 271.7 (3), `stairs` 57.1 (1 label, and it is **LIFT** — the shaft merged along its length with the staircase). These are the whole of that sheet's residual boundary error. |

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

## CLOSE THE LOOP — full-corpus overlay pass (31 Aug 2026)

Overlays for all four sheets in `overlays/close-the-loop/` as `BEFORE-*.png` and
`AFTER-*.png`, registered to the sheet, drawing walls · rooms · doors · windows ·
columns · **ducts** · **railings** · footprint · footprint_ext · dimension
anchors · rejected linework.

| # | defect | class | done | before → after |
|---|---|---|---|---|
| 1 | overlay never drew **railings** or **ducts**, though the parser finds both | A (instrument) | filled both layers; added a `ducts` layer | a found duct and a missed duct were indistinguishable → now distinct |
| 2 | **geometry leaked into the discarded view** — `footprint_ext` crossed the gutter, a door was drawn there. `_seg_px` built from ALL of `struct`, unfiltered by wing | A | filtered `_seg_px` through `_in_wing` | GHATIKIA fp **1997.0 → 1738.4**, fp x max **53.7 → 44.1**, stray openings **1 → 0**; anchors **69% → 69%**, R-2 **83.5 → 83.6** (n=12); other 3 sheets unchanged |
| 3 | a **20.0 sqft balcony room in the discarded view** — the balcony builder consumed the pre-split railing trace | A | filtered at the **consumer** (the trace must stay unfiltered: it sizes the canvas) | GHATIKIA rooms **14 → 13**, balcony **39.6 → 19.6**, stray rooms **1 → 0**; nothing else moved |
| 4 | `doors_placed_sound` scores width, **never jambs** | B — **not fixed**, hard line | emitted `both_jambs` | FLOOR PLAN **15/16** · BRICK WORK 15/15 · GHATIKIA 13/18 · **FIRST FLOOR 31/54 while `sound` reads 42/54** |
| 5 | "rooms overlapping wall material" (4) | **my audit was wrong** | none | all four are **ducts** — wall-ringed voids by design (§4 D-5) |
| 6 | "doors on no wall" (7) | **my audit was wrong** | none | a **gap door sits in the gap**; the right test is wall on both flanking sides |
| 7 | every room scoring <80% | open, cause known | none | **all are MERGES; not one is scale-like** on any sheet |

**Class C — for Rahul.** (i) Should an **unsnapped** door be emitted at all?
FIRST FLOOR emits 26 of 54 unsnapped — tags we read but could not place against
a wall — and they are built in 3D at an unverified position. (ii) Should
`both_jambs` fold into `sound`, and at what floor? (iii) The four standing ASKs
are unchanged: the lobby open side, two columns in doorways, and GHATIKIA's
one-room/one-door wing near-tie. (iv) FIRST FLOOR's 7 red dimension anchors sit
on the **diagonal site boundary**, not on walls — sheet furniture, like FLOOR
PLAN's logo; confirm they should stay excluded.

**Not clean, and here is what is left:** the FIRST FLOOR blobs (cause unknown,
every structural candidate eliminated), GHATIKIA's 3 merges, the `min_flank`
mode problem, BRICK WORK's `W3_min` latent cliff, and the ppf step's remaining
mechanism inside `_geometry_wall_segs`.

## §13 PLAN REGIONS — step A shipped (31 Aug 2026)

**The splitter's job changed, not its threshold: ENUMERATE regions, never pick
one and discard the rest.** A sheet may carry several plans; five plans on one
sheet and five separate sheets must both work. Full ruling in
PLAN-READING-RULES §13.

`meta.regions` — emission only, read by nothing, **no number moved**:

| sheet | regions | size ft | title near | built | basis |
|---|---|---|---|---|---|
| BRICK WORK | 1 | 30.0 × 49.1 | — | ✓ | one region |
| FLOOR PLAN | 1 | 95.8 × 30.2 | — | ✓ | one region |
| **GHATIKIA** | **2** | 43.9 × 58.9 · 42.9 × 58.9 | **"FLOOR PLAN"** · **"TYPICAL FLOOR PLAN"** | [0] only | already separate at the 8 ft proximity stage |
| FIRST FLOOR | 1 | 42.0 × 177.7 | "terrace / FLOOR PLAN" | ✓ | **merged: drawn material covers the band** |

**Both signals AGREE on both multi-block sheets** — GHATIKIA two regions/two
titles, FIRST FLOOR one joined region/one title. **The corpus does not contain
Rahul's counter-case** (three towers, one title, gaps between), which is exactly
why neither signal may decide. Next: **B, the ASK**; then **C, build the region
the user names**.

**Also shipped 31 Aug — an unsnapped door is not a door.** Retyped
`door_unverified`, kept and countable, out of every door count and out of the 3D
(dropped before `poly_bands`, so it cuts no wall). **FLOOR PLAN 16 → 16 ·
BRICK WORK 17 → 17 · GHATIKIA 18 → 8 · FIRST FLOOR 54 → 28.** `both_jambs` stays
reported, not folded into `sound`. FIRST FLOOR's 7 red anchors confirmed as sheet
furniture on the diagonal site boundary.

**Gotcha for anyone reading region evidence:** `_wing_groups` runs **twice** on a
sheet that scale-refits, and the scene comes from the second pass. GHATIKIA needs
the empty-band split at ppf 8.80 but not at 7.189, where the gutter already
exceeds the 8 ft proximity threshold.

## The two-pass ambiguity, and §13 step B (31 Aug 2026)

**`parse` re-enters itself for the scale refit, and the two passes build
different drawings.** Only GHATIKIA refits today. Every emitted field except the
column count differs:

| field | pass 1 (ppf 8.80) | pass 2 (ppf 7.189, shipped) |
|---|---|---|
| **which half is built** | **origin x 43.5 — the RIGHT view** | **origin x −0.2 — the LEFT view** |
| region basis | split on a zero-ink band | already apart at the 8 ft proximity stage |
| rooms · doors · unverified | 7 · 20 · 2 | 13 · 8 · 10 |
| windows · columns | 19 · 20 | 14 · **20** |
| footprint · M-1 | 1099.0 · 1.15 | 1738.4 · 1.07 |
| R-2 · carpet · anchors | 60.7 (n=7) · 659.3 · 56% | 83.6 (n=12) · 1167.4 · 69% |
| **measured wall** | **6.22 in** | **4.01 in** |
| latent cliffs | W3_min, geom_min, face_tol | face_tol, min_flank, geom_max |

Both are right for their own pass. **`meta.parse_pass` {index, ppf,
from_scale_refit}** now ships on every scene and each region carries its own
`pass`/`ppf` — a value from this sheet without its pass is ambiguous, and a diff
that mixes passes compares two different parses.

**§13 step B shipped.** Regions are keyed by **origin, never index** (`r@0,0`,
`r@53,0`). A multi-region sheet raises a §0.2 ASK naming every region — key,
size, position, title text, built — and asking what each is, and **where no title
can be read, what floor it is**. **If a printed area statement is read on a
multi-region sheet, the per-floor figures are dropped and R-8 reads BLIND for
both** — never the built region, never the larger; the plot survives. Defensive
and **unexercised by this corpus**. Supersedes the wing near-tie ASK.

**Also: half the doors on both geometry-route sheets were unverified** — GHATIKIA
10/18, FIRST FLOOR 26/54, against **0/16 and 0/17** on the layers-route sheets.
A door count on a geometry-route sheet was a count of door *tags*.

Next: **§13 step C** — build the region the user names.

## The re-parse trigger, and which pass is right (31 Aug 2026)

**Trigger, measured.** Two halves: `|median − 1| > stdev` is **derived and
dimensionless** (both sides measured from the sheet, so it cannot drift with
scale); **`min_sides = 8` is a fixed count — the eleventh constant.**

| | observed | trigger | nearest | distance |
|---|---|---|---|---|
| signal-to-noise | 0.03 · 0.12 · **1.74** | **1.0** | 1.74 | **0.74**, inside a 14× empty gap |
| side samples | 0 · 14 · 16 · 32 | `min_sides` 8 | 14 | 6 |

**Safe by the cluster rule — it sits on nothing.** But the distribution is three
points: one sheet disagreeing by 22% and two by under 1%, **nothing in between**,
so the trigger is unexercised anywhere near its own value.

**`meta.parse_passes` emitted** — `{count, built_pass, by_pass[], pass_ppf[]}`,
a tuple over **all** passes including the discarded one (a change to a discarded
pass can change which pass is discarded). `pass_ppf` is **row data, never
hashed**. Single-pass sheets use the same shape.

**Caveat found while building it: the origin key is itself pass-dependent.**
GHATIKIA keys `r@0,0`+`r@44,0` on pass 1 and `r@0,0`+`r@53,0` on pass 2 — the key
is in **feet**, and feet move with ppf, so those are the **same physical region**
under two scales. Origin keying survives enumeration *reordering*, which is what
it was adopted for; it does not survive a *scale* change.

## The separator is the ink, not a distance (31 Aug 2026)

**Defect, named independent of either pass:** region separation rested on
`gap_ft = 8` **feet**, and feet move with ppf — so GHATIKIA separated on a
zero-ink band at ppf 8.80 and on mere proximity at 7.189. **The two passes agreed
on two regions by coincidence, not by agreement.**

**Fix, one variable.** Two groups stay separate **only if a clean gutter runs
between them** (a run of zero-ink lines ≥ `EMPTY_BAND_MIN_FT` across the band).
Proximity is demoted to grouping connected components of one drawing.
`_band_crop` is shared by `_band_ink` and `_band_bridged`, and `_band_ink` uses
the same run-width predicate as `_empty_bands`, so separator and splitter can
never disagree about where the band is.

| sheet | regions | basis | judged |
|---|---|---|---|
| BRICK WORK | 1 | one region | fp 1247.1 · anchors 70% |
| FLOOR PLAN | 1 | one region | fp 1796.8 · 79% · R-2 98.0/8/0/90.4 |
| **GHATIKIA** | **2** | **separate: a band with NO INK between them** | fp 1738.4 · 69% · R-2 83.6/12/2 |
| **FIRST FLOOR** | **1** | **merged: ink in the band** (the terrace) | fp 4472.1 · 60% · R-2 96.9/16/7 |

**Scale-invariance verified:** GHATIKIA now reports the same basis on **both**
passes (8.80 and 7.189). **Nothing moved.**

**My first attempt was wrong** — `_band_ink` asked "is there *any* ink in the
band", which one stray dimension line would defeat by welding two plans together.
A synthetic test caught it before the corpus did. **Caveat recorded, not
guarded:** a single line across the *full width* of a gutter still merges two
drawings — that is the ruled test's semantics, and it is what makes FIRST FLOOR's
terrace a join. Unexercised in this corpus.

**OPEN — `min_sides = 8` is the eleventh constant.** A fixed count of side
samples gating the refit; counts are 0 · 14 · 16 · 32, nearest margin 6. **And
the refit trigger is unexercised near its own value:** observed S/N 0.03 · 0.12 ·
1.74 against a trigger of 1.0 — one sheet at 22%, two under 1%, nothing between,
a 14× empty gap. Safe by the cluster rule and untested where it fires. **Needs a
fourth and fifth sheet, not a derivation from three samples.**

## The 3D defect sheet (1 Sep 2026)

`overlays/defect-sheet/` — **19 images + `INDEX.md`**, written for a single
30-minute review. Each image is 3D on the left, the matching crop of the drawing
on the right, one line of finding, and a colour key. Read the index top to
bottom: eight suspected defects first, ranked by likely-real × costly, then
eleven confirm-items.

**Rendered without pyrender or pyglet** (neither is installed): a small
orthographic rasteriser projects the same meshes `scene_to_glb` builds and
paints them with a painter's algorithm. **The GLB is metric and Y-up** — my first
pass assumed Z-up and rendered every "top-down" as an elevation, and my first
mesh measurements read metres as feet. Both caught and corrected before the sheet
was built.

**The four findings that came out of building it:**

| finding | measured |
|---|---|
| **Floor slab is the wall bounding box, not the footprint** | +66% FIRST FLOOR · +58% FLOOR PLAN · +47% GHATIKIA · +21% BRICK WORK. Floors the gap between FIRST FLOOR's two blocks. |
| **Two railing meshes are the whole pocket extruded** | FLOOR PLAN `railing_0` 54.2 sqft and `railing_3` 38.8 sqft solid at 3.50 ft, over a 51.0 sqft balcony and a 37.0 sqft utility. The other four railings, and both on FIRST FLOOR, are correct 0.25 ft rails. |
| **No staircase mesh on any sheet** | rooms typed `stairs` exist (21.4 · 168.1 · 166.9 · 57.1 sqft); no stair geometry anywhere. |
| **No roof or ceiling mesh on any sheet** | the viewer's flat box is the only thing overhead. |

Heights confirmed correct: wall 9.84 ft · door head 7.00 ft · railing 3.50 ft ·
window sill 2.6 ft. **Nothing in the parser was changed to produce this sheet.**

## Defect-sheet review: rulings, fixes, and two withdrawals (1 Sep 2026)

**Rulings.** Q1 staircase → build actual steps (S-6), queued. Q2 roof/ceiling →
build, but **not yet** — the floor plan reading must be verified first and that
needs the ceiling absent. Q3 FIRST FLOOR's gap → **slab it as terrace**, first
floor only. Q4 the column in flat-1's entrance is **correct as drawn**; ASK
closed.

**Fixed.** The floor slab is now the **footprint polygon**, not the wall bounding
box — FIRST FLOOR 7396 → **4463** sqft, FLOOR PLAN 2841 → **1794**, GHATIKIA
2548 → **1736**, BRICK WORK 1503 → **1246**. The mesh renames `floor` → `floor_0`
and the viewer is unaffected (it matches `name.includes('floor')`); the one test
asserting the exact string was re-derived to the viewer's own contract. **Ducts
no longer build as solid full-height `column_i` boxes** — they were concatenated
onto the column list, so a shaft became structure and the name hid it. Now a thin
shaft ring named `duct_i_k`, void left open (§4 D-5). Latent: `scene["ducts"]` is
empty on all four sheets today.

**Two of my eight defects were WRONG and are withdrawn.**

| withdrawn | what was actually true |
|---|---|
| balcony and utility "solid blocks" | **The railings are correct.** I measured the mesh **bounding box** and called it area. True rail areas **5.16 / 3.18 / 3.08 sqft** — 0.25 ft thick, 3.50 ft high, 2–3 sided, floor slab inside. **Fifth time an audit's own geometry was the fault, and the costliest: it consumed a ruling.** |
| GHATIKIA rendered 180° out | **My renderer, not the model or the viewer.** At a top-down camera `right = cross(fwd, up)` degenerates and its **sign flips**. It affected every top view. Now keyed on elevation — the degenerate magnitude at el 89.9 is 0.0017, which sailed past a 1e-3 guard. The 2D overlay always registered correctly, which was the evidence the scene was right. |

**Ground truth corrected (§0.1).** FLOOR PLAN's `windows_expected: "in wall layer
(not extractable yet)"` is **wrong — no windows are drawn on that sheet at all**.
Written in July, never verified, then quoted by me as "~11 unbuilt windows".
Superseded text kept visible. **Third ground-truth entry found wrong** (plot
twice, now this): an unverified entry in the truth file is worse than an absent
one, because it is quoted with the authority of a measurement.

**Still to build:** staircase steps · terrace slab over FIRST FLOOR's gap ·
roof/ceiling (later, by ruling) · GHATIKIA's stair flight-divider read as a wall
and its lift · then GHATIKIA's doors · gbuffer segClass.

## Build list from the defect review — 3 of 6 shipped (1 Sep 2026)

| # | item | result |
|---|---|---|
| 1 | **Staircase as actual steps (Q1)** | **GHATIKIA only: 17 risers of 6.9 in, tread 8.3 in** from an 11.7 ft flight and a 9.84 ft storey. The count is derived (riser = H/n exactly, so the flight climbs one storey); the tread comes from the drawn length. **No sheet draws a clean tread ladder** — best pitches 0.84 ft (FIRST FLOOR ×3–4) and 0.77 ft (GHATIKIA ×3) — so the ruling's second branch applied. **Refused, with reasons on `meta.stairs_built`:** FLOOR PLAN's `stairs` room is 4.7×4.6 ft, aspect 1.03 — the **lift**, mistyped; FIRST FLOOR's two are 14×16 ft — whole stair **cores**. Steps in a lift are worse than none. |
| 2 | **Terrace slab (Q3)** | The band two regions merged across is recorded in feet and slabbed. **FIRST FLOOR: x 1.91–41.83, y 66.68–80.69 (39.9 × 14.0 ft)**, matching the measured band. No other sheet has a join. |
| 5 | **`gbuffer` segClass** | Door leaves and railings fell through to `other`, corrupting the conditioning maps. Added `door` · `railing` · `stair` · `terrace`, `duct`→column, ordered before the broader tests so `floor_open_*` stays floor. 3 new tests, 35 passing. |

**Still open:** 3 — GHATIKIA's stair flight-divider built as a wall, and the lift
read wrong (S-4 generalised, not per-sheet) · 4 — GHATIKIA's doors · 6 — roof and
ceiling (Q2, deliberately last).

**Two bugs I caught in my own patches:** the terrace band was read *after* the
merge had already replaced and popped the groups; and it came out of cv2 as
numpy `int32`, which is not JSON-serialisable and broke two cascade tests.
Anything reaching `meta` must be a plain Python type.

**Orientation anchor chain recorded** per sheet for the scorecard (north arrow →
staircase/lobby → corner rooms/balconies → n/a). **No sheet in the corpus prints
a north arrow**, so every entry falls to the second link or lower; BRICK WORK has
no anchor at all and is recorded **n/a**, not assumed.

## Item 3 — the divider, and a staircase built in the lift (1 Sep 2026)

**Rahul's report was right and the cause was not what either of us named.** The
divider itself (a 0.75 ft pair at x 15.2/16.0) is **not built**; what stands
across GHATIKIA's flight is a **surviving TREAD PAIR** — 3.22 ft, 9.2 in thick,
full storey height — kept by `_drop_stair_ladders`' rule "the outermost rungs
are usually the stair enclosure walls".

| measured | result |
|---|---|
| is that premise true? | **No. All 26 rungs** across GHATIKIA's 2 flights and FIRST FLOOR's 3 chains have thickness **= 1.00× the ladder's own pitch** — every rung is two adjacent treads. Per S-4 none is a wall |
| drop them all | GHATIKIA fp **1738.4 → 1720.0**, doors 8 → 11, R-2 83.6 → 82.4 |
| cost on the judged sheet | **FIRST FLOOR common area 335.0 → 40.8** (both staircases stop being spaces), built-up 4505.9 → 4291.2, **carpet RISES 3010.1 → 3195.8** as the stair leaks into it, R-2 96.9 → 95.7, rooms 19 → 18 — the 24 Aug carpet/R-2 **REGRESSION** signature |
| verdict | **REVERTED.** Those two rungs are the only thing enclosing both FIRST FLOOR stair cores — a fake wall doing an envelope job, the same shape as the seal. Helps the uninstrumented sheet, costs the judged one → HARD LINE. **Rahul rules** |

**And Q1's staircase is WITHDRAWN — I built it inside the lift.** GHATIKIA's
room typed `stairs` is the **LIFT** (printed `LIFT 1.63x1.57` = 5.35 × 5.15 ft,
printed 27.5 vs our 57.1, `dim_match_pct` **0.0**) merged with the space south
of it; the real flight is **8 ft west**. Aspect 2.41 said "flight" and it was a
shaft. **Room type is a guess; the tread ladder is drawn.**

`meta.stair_ladders` now carries every drawn ladder in scene feet — box, tread
count, drawn pitch, axis climbed, wing-filtered at the consumer:
**GHATIKIA 1 flight (8 treads @ 9.2 in) · FIRST FLOOR 2 staircases, each a
dog-leg of 2 flights (7 + 5 @ 10.0 in) · FLOOR PLAN 0 · BRICK WORK 0.**

**Nothing builds, and the refusal is the instrument.** The riser is derived
(`H / treads drawn`), so it is also the check: **GHATIKIA 14.8 in · FIRST FLOOR
9.8 in** against the human band 5–9 in. Flights are missing, and the cause is
already on the open list — GHATIKIA's second flight is drawn as **four 0.6 ft
dashes per tread** and `L < 6 pt` (**0.83 ft** on that sheet) deletes it. Fixing
that constant is the next move on stairs, one variable.

**Judged set byte-identical on all four sheets** — fp 1247.1 / 1796.8 / 1738.4 /
4472.1, anchors 70/79/69/60%, R-2 98.0 (n=8) / 83.6 (n=12) / 96.9 (n=16),
M-1 1.13/1.06/1.07/1.09, doors 17/16/8/28. 4 new tests.

## The twelfth constant, rung 1, and a wrong cause of mine (1 Sep 2026)

**`L < 6 pt` is gone — and it was NOT what hides GHATIKIA's second flight.**

| | |
|---|---|
| what it was | six PAGE POINTS = **0.12 / 0.21 / 0.83 / 1.05 ft** across the corpus |
| derived from | **the pairing rule in its own function**: two faces must overlap `min_ovl` to be a wall, so a line shorter than `min_ovl` can never be a wall face. Not the page, and **not the population it selects** (26 Aug rule 4 — line length is exactly that population) |
| cost | **provably redundant with a test already made below; every number on all four sheets identical** |
| stated openly | the floor is now `min_ovl = 2.0 ft` — an absolute in FEET. The constant **changed unit, it did not vanish** |

**My named cause was wrong — the seventh measurement artefact.** Running with
`L >= 0`, GHATIKIA does not move at all (same ladder, fp 1738.4, 13 rooms). The
gate is **`min_ovl`**: the second flight's treads are **four 0.6 ft dashes
each**, and no two dashes overlap 2 ft.

**Deriving `min_ovl` from the measured wall: BUILT, MEASURED, NOT SHIPPED.**
Both geometry-route sheets improve on every instrument — **GHATIKIA anchors
69% → 92%, R-2 83.6 (n=12) → 95.5 (n=15), rooms 13 → 18 · FIRST FLOOR anchors
60% → 69%, R-2 96.9 (n=16) → 98.1 (n=28), rooms 19 → 35** — and the two
layers-route sheets do not move. **But footprint jumps +45% / +27% (1738.4 →
2516.8, 4472.1 → 5671.9) and it builds THREE FAKE STAIRCASES on GHATIKIA out of
tile hatch** (18–21 "treads" at 4.4 in pitch; risers 5.6–6.6 in, inside the human
band, so the riser check does not catch them). Second variable, **Rahul rules**.

**Rung 1 built: `meta.north_arrow_deg` — and it reads None on all four.** A north
arrow is a closed narrow spike, clear of the plan, **with a lone `N`**; bearing
base → apex, clockwise from sheet-up. Two things the build taught: the aspect
must be measured **along the shape's own axis**, never its bounding box (a 45°
spike has a near-square box, so a bbox test rejects exactly the non-orthogonal
sheets); and **the `N` is required** — without it FLOOR PLAN's only spike is a
**5.0 ft sliver of the ARCHITRAVE logo** and the reader gave a confident
**81.8°**. `live_words` ships beside the verdict: BRICK WORK has **0**, so "no
`N`" there is an extraction limit, not a fact about the drawing.

**CONTRADICTION with the scorecard, reported not resolved:** it says FLOOR PLAN
prints a north arrow; measured here it does not. Bearing + chirality recorded per
sheet in `ground_truth.json` (`orientation_bearing_chirality_2026_09_01`) —
**every bearing UNRULED** with its rung; **chirality settled on three of four**
(as drawn, not mirrored), FIRST FLOOR convention only.

Judged set unmoved: fp 1247.1 / 1796.8 / 1738.4 / 4472.1 · plot 53% on FLOOR
PLAN, three blind and saying so · anchors 70/79/69/60% · R-2 98.0/8/0/90.4 ·
83.6/12/2 · 96.9/16/7 · M-1 1.13/1.06/1.07/1.09 · R-8 pin held. 8 new tests.

## The fake-stair finding, and what actually separates a flight from a floor (1 Sep 2026)

**`min_ovl` from the measured wall — RULED: do not ship, trade recorded.** The
strongest single improvement measured on both geometry-route sheets, blocked by
two things no instrument watches.

| | GHATIKIA | FIRST FLOOR | FLOOR PLAN / BRICK WORK |
|---|---|---|---|
| anchors | **69 → 92%** | **60 → 69%** | unmoved |
| R-2 | **83.6 (n=12) → 95.5 (n=15)** | **96.9 (n=16) → 98.1 (n=28)** | unmoved |
| rooms | 13 → 18 | 19 → 35 | unmoved |
| **footprint** | **1738.4 → 2516.8 (+45%)** | **4472.1 → 5671.9 (+27%)** | unmoved |
| **and** | **3 fake staircases from tile hatch** | — | — |

`footprint ≤ plot` is **blind** on both sheets. **If footprint ever gains an
independent judge, this is the first thing to retry.**

**What separates a flight from a tiled floor — measured on all four sheets.**

| candidate | real flights | GHATIKIA hatch | verdict |
|---|---|---|---|
| tread **count** | 5–8 | 18–21 | **fails** — the derived bound from the riser band is 13–24, which *contains* the hatch |
| run **length** | 3.32–5.86 ft | 6.83–7.66 ft | **fails** — separates only with a tuned bound |
| flight **width** | 3.23–3.53 ft | 1.83–1.85 ft | separates, but needs a width we do not measure |
| **drawn TREAD** | **9.2–10.1 in** | **4.4 in** | **WINS — no new number.** Band is the same `2R + T = 25 in` relation the riser band comes from: R 5–9 in → **T 7–15 in**, a 2.6 in margin |

**The riser is inferred, the tread is measured.** The hatch's implied riser is
5.6–6.6 in — comfortably *inside* the human band, which is exactly why the riser
check passed three fake staircases. `server/stairs.py` holds the relation **once**
and both the parser and the builder import it; rejects are kept on
`meta.stair_ladders_rejected` with their reason, because a filter that deletes
silently is how the 16-room cap hid.

**Rung 1 is unreachable on this corpus** — four sheets, four reasons, zero north
arrows. Contradiction with the scorecard resolved in the parser's favour: FLOOR
PLAN has 24 live words, none `N`, and its only spike is the ARCHITRAVE logo.
That is a finding about the corpus, not the rung.

Judged set unmoved: fp 1247.1 / 1796.8 / 1738.4 / 4472.1 · anchors 70/79/69/60% ·
R-2 98.0/8/0/90.4 · 83.6/12/2 · 96.9/16/7 · M-1 1.13/1.06/1.07/1.09 · 4 checks
green · 4 new tests (12 today).

## COLD-SHEET AUDIT — what a drawing we have never seen would do (2 Sep 2026)

Written **before** Rahul's three new sheets arrive. Measured from the code and
the four sheets' own route/threshold output, not from memory.

### 1. Derived per sheet vs inherited from this corpus

| DERIVED on a cold sheet | from what | evidence today |
|---|---|---|
| `ppf` (scale) | 4 routes: printed room dims · dimension text · column box · CAD units | **28.47 · 5.70 · 51.80 · 7.19** — one per sheet, all four routes exercised. 3 of 4 are in `GUESSED_SCALES` and say so |
| `_W` measured wall | median pair gap | **0.834 · 0.421 · 0.250 · 0.334 ft** — a 3.3× spread |
| `door_median` | median snapped door | needs **≥5** snapped, else `NOMINAL_DOOR_FT` |
| `derived_seal_ft` | p90 drawn leaves → printed schedule → UNDERIVED | 2.94 · 3.06 · 3.75 · 2.73 — **reported, not applied** |
| scale refit ratio | printed dims vs measured, `|median−1| > stdev` | fires on 1 of 4 |
| `max_bridge`, `_min_room_px`, stair tread/pitch, plot | the wall run · the raster · the drawn ladder · printed or user | plot **printed on 1 of 4**, unknown-and-says-so on 3 |

| INHERITED (identical on any sheet) | value | note |
|---|---|---|
| W-3 band | **3–18 in**, five sites | 1.8× FLOOR PLAN's wall, **4.5×** GHATIKIA's |
| `_geometry_wall_segs` band | **3–11.04 in** | the sixth site, still private |
| `min_ovl` | **2.0 ft** | now also the line-length floor |
| `_SEAL_FT` | **4.0 ft** | every sheet's derived value is **lower** |
| `NORM_PPX` · `join_tol` · `EMPTY_BAND_MIN_FT` | 50.9 px/ft · 0.35 ft · 1.0 ft | |
| raster floors | wall spec **2.32 sqft**, hole **0.96 sqft**, pad **0.196 ft** | look like px, are feet |
| building constants | wall 9.843 ft · door head 7.0 · sill 3.0 · column 1.0 ft · nominal door 3.0 | locked, not measured |
| **eleven COUNT floors** | `min_sides 8` · `len(struct) 30` · `gsegs 8` · `votes 8` · `close 8` · `live_toks 50` · `live_all 50` · `walls 5` · `rungs 4` · `OCR_REFINE_MAX 40` · `MAX_SEGS 250k` | dimensionless, so scale-proof — and **corpus-tuned**. Closest margin today: GHATIKIA's `door_median` sample is **8 against a floor of 5** |
| human bands | riser 5–9 in, tread 7–15 in (`2R+T=25`) | refuse only; never select |

### 2. What goes blind, by missing input (general dependency, not per sheet)

| missing from the sheet | blind | still live |
|---|---|---|
| printed **area statement** | **R-8**, the stilt cross-check, `printed_area_verified/mismatch`, efficiency vs printed | R-2, anchors, M-1, footprint≤plot |
| printed **room dims** | **R-2** (all four of its quartet), the **scale refit** (no sample), B-5 balcony width, `room_dims_*` | R-8, anchors, M-1 |
| **door layer / drawn leaves** | `door_swing`, `opens_ccw`, hinge, `doors_placed_sound` leafed branch, `derived_seal_ft` from leaves | gap openings, leafless soundness |
| **live text** (0 words) | every OCR-free path: room names, printed widths, north `N`, titles, region ASK | pure geometry |
| **plot** (no statement, no user entry) | `footprint ≤ plot` — **our only physics check** | everything else |
| **named wall layers** | nothing — falls to the geometry route, a **different algorithm** (`meta.route` says which) | |
| **north arrow** | rung 1 of the orientation chain — **absent on all four today** | |
| **worst case**, all of the above | R-8 · R-2 · B-5 · plot · swing · orientation | anchors, M-1, `doors_placed_sound`, `threshold_margins`, `wall_face_quality` |

### 3. Constants whose real-world meaning moves with scale

Corpus range **5.7–51.8 pt/ft**, a 9× spread already.

| page-unit constant | @2 pt/ft | @5.7 | @51.8 | @100 pt/ft |
|---|---|---|---|---|
| `BORDER_MAXLEN_PT = 900` | **450 ft** | 158 ft | 17.4 ft | **9.0 ft — deletes every long wall** |
| `WALL_MINLEN_PT = 8` | **4.0 ft — real partitions read as brick hatch** | 1.40 | 0.154 | 0.08 ft — hatch admitted as wall |
| `TEXT_MED_MAXLEN_PT = 5` | **2.5 ft — a wall layer reads as outlined text and is discarded whole** | 0.88 | 0.097 | 0.05 ft |
| `abs(d) < 0.5 pt` axis test | 0.25 ft of slop — skew walls pass as orthogonal | 0.09 | 0.010 | **0.005 ft — almost nothing is axis-aligned, the wall reader finds nothing** |

**All four are absurd at one end or the other, and BRICK WORK already sits at
88% of its `BORDER_MAXLEN_PT` cap at 51.8 pt/ft.** `L < 6 pt` was the fifth and
was removed 1 Sep. Everything else is in feet or inches and is scale-proof by
construction; the count floors are dimensionless and unaffected.

### 4. Loud vs silent — the failure modes we actually have

| fails LOUDLY (raises or flags) | trigger |
|---|---|
| `no scale` · `not a layered CAD PDF` · `wall mask empty` · `wing N out of range` | raise `ValueError`, cascade falls to ML |
| **`plan raster too large — scale looks wrong`** | extent × 50.9 px > 36 Mpx = **117.9 ft square**. Catches a 10× scale error — **and also a genuine 150 ft plot plan**, which would be a loud FALSE failure |
| `envelope_tiny` (<12 ft) · `envelope_huge` (>600 ft) · `no_rooms` · `no_doors` | `batch_eval.health_flags`, no ground truth needed |
| doctor `fail`: `footprint_exceeds_plot` · `printed_area_mismatch` · `room_dims_mismatch` · `scale_door_mismatch` · `envelope_implausible` | need printed data — **silent when the sheet prints none** |
| doctor `ask`: `plot_area_unknown` · `space_open_on_one_side` · `doorway_obstructed_by_column` | a question, never auto-corrected |

| fails SILENTLY — the real risk | why nothing catches it |
|---|---|
| **a wrong scale within 2×** | envelope stays 12–600 ft, rooms and doors still form; with no printed dims the refit has no sample and R-2 no judge. **Every number is then confidently wrong and self-consistent** |
| **the wing/region auto-pick** | index is not identity; `wing_pick.near_tie` is `true` on GHATIKIA today. A 0.3% ppf change silently swaps which drawing every number describes |
| **which parse PASS is built** | `parse` re-enters itself; the two passes disagree on nearly everything. `meta.parse_pass` says which — read by nothing |
| **route change** | layers vs geometry is a different algorithm; identical-looking output |
| **a threshold sitting on a cluster** | `threshold_margins` reports it; BRICK WORK's `W3_min` is on its own 3 in peak with **38 pairs** and nothing acts on it |
| **merged rooms** | R-2's median cannot see a merge — `rooms_off` can (**7 of 16** on FIRST FLOOR) and is reported, not ratcheted |
| **the seal at 4.0 ft** | every sheet's derived value is lower; the excess does envelope work no instrument attributes |
| **footprint** | **no independent judge at all** unless the plot is printed or entered |

**The one-line summary: a cold sheet that prints nothing fails silently, and a
cold sheet drawn at an unusual scale fails loudly for the wrong reason.** The
first thing to check on each new drawing is `meta.route`, `meta.parse_pass`,
`meta.scale.source` and `meta.plot_source` — before any number is read.

## READ THIS FIRST on any result (standing protocol, 2 Sep 2026, Rahul)

**Before any number, read four fields.** They say which algorithm produced the
number, at what scale, and whether anything can contradict it:

| field | question it answers |
|---|---|
| `scale_verified` / `refusals[]` | **is the scale backed by anything printed?** If false, no ft/sqft/₹ below is usable |
| `meta.route` | layers or geometry, and which of the invisible floors were reached |
| `meta.parse_pass` | which of the self-re-entrant passes built this scene |
| `meta.plot_source` | printed · user · unknown — `footprint ≤ plot` is blind when unknown |

## The cold-sheet guard — refuse, don't warn (2 Sep 2026)

**Correction first: my audit line "3 of 4 are in `GUESSED_SCALES`" was WRONG —
it is ONE**, and Rahul's ruling inherited the wrong number. Under his own
definition (not from printed dimension text or a printed statement) the guessed
set is **two** of four, and GHATIKIA's is rescued by the refit that corrected it.

**Verification is by EVIDENCE, never by route name:** printed dimension text or a
printed statement set the scale, **or** the printed-dimension refit had a usable
sample — printed dims had the chance to contradict it and either corrected it or
did not.

| sheet | scale.source | verdict |
|---|---|---|
| FLOOR PLAN | `room_dim_text` | ✅ printed dimension text set the scale |
| FIRST FLOOR | `dimension_text` | ✅ printed dimension text set the scale |
| **GHATIKIA** | `cad_units` | ✅ **printed room dims corroborated it (14 sides)** — and the evidence lives in the **discarded** pass, so the guard is applied again from outside |
| **BRICK WORK** | `column_box_12in` | ❌ **REFUSED** — nothing printed, 0 side samples |

**What a consumer sees:** `scene.scale_verified` and `scene.refusals[]` at the
**top** of the scene, not in `meta`; Doctor `warn` → **`fail scale_unverified`**
(BRICK WORK grade **C → D**); `batch_eval` **4/4 → 3/4 clean** with a
`scale_unverified` flag. **A missing verdict is not a pass** — an older scene
with no `verified` key falls back to the guess list, because absence of a
contradiction is not confirmation. **No parse number moved on any sheet.**

## Plausibility without printed data — reported, NOT built

| check (a fact about buildings) | catches 2×? | measured today |
|---|---|---|
| **door width 2.5–3.5 ft** | **YES, both directions** | 2.95 · 2.88 · 2.88 · 2.74 ft → 2× reads 5.5–5.9, 0.5× reads 1.37–1.48. **Already exists as `_door_scale_sanity`, gated to `GUESSED_SCALES` so it runs on ONE sheet — ungating it is the whole build** |
| **stair tread 7–15 in** | **yes**, where a ladder exists (2 of 4) | 9.2 · 10.0 in → 2× reads 18.4–20.0 |
| room side 4–25 ft | **weak, and false-positives today** | FIRST FLOOR's largest side is **38.8 ft** — a merge, not scale; and a 10 ft room at 2× is still inside |
| wall 3–18 in | **NO — cannot, by construction** | the band **selects** the walls, so the median sits inside it at any scale (3.0 · 10.0 · 4.0 · 5.0 in). **Rule 4: a quantity selected by a band can never police that band** |
| storey 9–10 ft | no | not in a plan |

**Closest live margin in the codebase: `BORDER_MAXLEN_PT` at 88% on BRICK WORK**
(17.4 ft cap at 51.8 pt/ft). Recorded, not fixed, on Rahul's instruction.

Judged set unmoved: fp 1247.1 / 1796.8 / 1738.4 / 4472.1 · anchors 70/79/69/60% ·
R-2 98.0/8/0 · 83.6/12/2 · 96.9/16/7 · M-1 1.13/1.06/1.07/1.09 · 3 new tests.

## The two scale checks, and what they actually catch (2 Sep 2026)

**Built as ruled.** `_door_scale_sanity` **ungated** — it ran on one sheet of
four (`scale.source in GUESSED_SCALES`) and now runs on every sheet, because a
door being 2.5–3.5 ft is a fact about buildings, not about how we derived the
scale. **Auto-correction stays gated to a guess:** a door-width guess must never
silently overrule a printed dimension. `stairs.tread_scale_check` is the second,
and it reads **every ladder drawn, accepted AND rejected** — reading only the
accepted list would be circular, since that list is filtered *by* the tread band.

**Neither fires anywhere today:** door medians **2.95 · 2.88 · 2.88 · 2.74 ft**;
treads **9.2 · 10.0 in** on the two sheets that draw one, `blind` on the others.

**Then I injected the error the guard exists for** — `ppf_hint` at 0.5× and 2×,
all four sheets, 8 cases:

| outcome | cases |
|---|---|
| RAISES loudly (raster guard) | GHATIKIA 2×, FIRST FLOOR 2× |
| caught by **DOOR** | FLOOR PLAN 2× (median 4.44 ft) |
| caught by `no_rooms` | BRICK WORK 0.5× |
| **NOT CAUGHT** | **BRICK WORK 2× · FLOOR PLAN 0.5× · GHATIKIA 0.5× · FIRST FLOOR 0.5×** |

**Worst case: BRICK WORK at 2× parses to 29 rooms, 22 doors and a door median of
3.01 ft** — a completely plausible reading of a building twice its real size.

**The cause is rule 4, and it applies to the checks themselves:** doors are
*selected* by a width band in feet, so their median sits inside that band at any
scale — at 0.5× the finder just admits a different population (2.92–3.22 ft).
The tread check reads `None` at every wrong scale because the ladder detector's
thresholds are in feet too: **blind rather than wrong, which is honest but is
still not a catch.** Both are kept — they cost nothing, neither false-positives,
and `door_median_ft` / `tread_median_in` now ship as measurements on every sheet.

## What escapes rule 4 — candidates for a blind sheet (reported, NOT built)

A check can police the scale only if its quantity was **not selected by a band
in feet**. Measured at 0.5×/1×/2× across the corpus; **no band below is fitted to
these four sheets** — each is a fact about buildings, and the eval corpus sets
the numbers once, in the open.

| candidate | building fact | what it catches |
|---|---|---|
| **median room area** | a habitable room is not under ~35 sqft; a bathroom not under ~15 | **the strongest.** BRICK WORK at 2× reads a median room of **5.0 sqft** while its door median reads a perfect 3.01 — it catches the one case nothing else does |
| built-up per floor | a residential floor is not ~200 sqft | GHATIKIA + FIRST FLOOR at 0.5× (**241.9 · 218.8 sqft**); misses FLOOR PLAN (480.2) |
| rooms per 1000 sqft | ~1 room per 100–250 sqft | mixed — catches FLOOR PLAN 2× (1 per 572), misses BRICK WORK 2× (1 per 106) |
| area per dwelling | a flat is 300–1500 sqft | strong, but needs a unit count we do not read — the printed `FLAT-1`/`FLAT-2` labels, or a kitchen count |
| doors per room | ~1 door per room | does not separate (0.76 at 2× is plausible) |

Judged set unmoved: fp 1247.1 / 1796.8 / 1738.4 / 4472.1 · anchors 70/79/69/60% ·
R-2 98.0/8/0 · 83.6/12/2 · 96.9/16/7 · M-1 1.13/1.06/1.07/1.09 · doors 17/16/8/28.
Four checks green; 1 test re-derived on the ruling, 2 added.

## Median room area — built, and it earns its place (2 Sep 2026)

**Why it works when the others cannot:** a room is found by **enclosure**, never
by a size band in feet, so unlike the door median (selected by a door band) and
the measured wall (selected by 3–18 in) its area is free to come out absurd.

**Band = code minima, quoted, not fitted to any drawing we hold.** NBC of India
2016: habitable room 7.5 m² · kitchen 5.0 · bathroom 1.8 · **WC 1.1 m² = 11.8
sqft — the smallest enclosed room the code permits at all.** Upper bound is the
same argument inverted: a room cannot exceed a whole minimum dwelling —
**PMAY/RERA 1-BHK carpet 30 m² = 322.9 sqft**. `server/plausibility.py`.

**Acceptance was the injection test, not the corpus** — `server/scale_injection.py`,
kept as a standing harness:

| outcome | before | now |
|---|---|---|
| RAISES (raster guard) | GHATIKIA 2×, FIRST FLOOR 2× | same |
| door | FLOOR PLAN 2× | same |
| `no_rooms` | BRICK WORK 0.5× | same |
| **room_median** | — | **BRICK WORK 2×** — 29 rooms, 22 doors, door median a perfect **3.01 ft**, median ROOM **5.0 sqft** |
| NOT CAUGHT | 4 | **3** (all 0.5×) |
| **total** | **4/8** | **5/8** |

**False-positive check passed on the cold sheet:** Typical Floor Plan reads
median room **114.1 sqft**, verdict true, **zero refusals**. Next candidate,
not built: **built-up per floor** would take it to 7 of 8 (it catches GHATIKIA
and FIRST FLOOR at 0.5×, 241.9 and 218.8 sqft).

**Caveat on the cold sheet's headline, in the parser's own terms.** Its scale
comes from `room_dim_text` — the printed room dimensions — and **R-2 then
compares measured rooms against those same numbers**. That is the trap already
recorded for the scale refit, applied to the `room_dim_text` route itself.
FLOOR PLAN survives it (anchors **79%**); the cold sheet **prints no dimension
lines and reads 0 anchors**. So the highest R-2 in the corpus sits where nothing
independent can contradict the scale: **99.0 over 10 rooms, `rooms_off` 4 of 10,
anchors 0, plot unknown, no area statement.**

| on the cold sheet | fires | silent |
|---|---|---|
| instruments | R-2 (99.0/10, off 4) · M-1 **1.08** · `doors_placed_sound` · `wall_face_quality` · `threshold_margins` | **R-8** (no area statement) · **stilt cross-check** · **footprint ≤ plot** (`plot_source` unknown) · **dimension anchors (0)** · **north arrow** |
| plausibility | scale **verified** (printed dim text) · door **2.88 ft** · tread **10.0 in** · median room **114.1** | — |
| a guess nothing can contradict | **the scale itself** — verified only by the same printed numbers R-2 scores against | |

## Built-up per floor, the ML-path guard, and where outline noise comes from (2 Sep 2026)

**Built-up per floor built — injection test 5/8 → 7/8.** Same escape from rule 4:
the footprint is a **traced ring**, not a quantity chosen by a threshold in feet.
Band is the same quoted minimum — a floor holds at least one dwelling and
built-up ≥ carpet, so it cannot be under **PMAY/RERA 1-BHK 30 m² = 322.9 sqft**.
**No upper bound is asserted**: a floor may legitimately carry fifty flats, so a
maximum would be a number from our corpus, not from a building.

| injection | caught by |
|---|---|
| BRICK WORK 0.5× | **builtup**, no_rooms |
| BRICK WORK 2× | room_median |
| GHATIKIA 0.5× · FIRST FLOOR 0.5× | **builtup** (241.9 · 218.8 sqft) |
| GHATIKIA 2× · FIRST FLOOR 2× | RAISES (raster guard) |
| FLOOR PLAN 2× | door (4.44 ft) |
| **FLOOR PLAN 0.5×** | **still not caught** — 480.2 sqft is a legal floor area |

**Cold sheet passes both:** median room 114.1 sqft, built-up 1436.3 sqft, **zero
refusals**.

**The ML path now gets the guard.** `scene_builder.scene_from_segments` assumes a
**40 ft plan width** and stamps `assumed_width` — the definition of an unverified
scale — yet the refusal lived only on the vector path, the one least likely to
need it. `_apply_scale_guard` moved into `plausibility.scale_guard` (pure, no
parser import) and both paths call it, so they cannot disagree. An ML scene now
returns `scale_verified: false` + a `scale_unverified` refusal.

**Outline noise — measured, mask and trace, NOT bridging.**

| finding | measured on all five parsed sheets |
|---|---|
| **1. the mask is already jagged** | raw footprint contour holds **503 · 458 · 1266 · 5935 · 183** points, **95%+ shorter than one wall** |
| **2. the trace preserves it** | `approxPolyDP` epsilon is **2.0 raster px = 0.039 ft — the thirteenth constant** — i.e. **0.05×–0.16×** of each sheet's own wall (0.83/0.83/0.42/0.33/0.25 ft). **A tolerance finer than a wall cannot remove steps shorter than a wall** |
| **3. bridging: NOT established** | short steps within 2W of a bridge read **9/15 and 12/34** where bridges are few (31, 17) but **97/97 and 315/319** where they are many (73, 196) — on those, nearly any point is near *some* bridge. **The test measures bridge density, not cause. Reported inconclusive** |
| **simulated, not built** | at a derived epsilon of **W/2**: outline **42→27 · 59→26 · 163→92 · 521→234 · 25→10** points |

**Proposal, one variable, awaiting ruling: derive `approxPolyDP`'s epsilon from
the sheet's own measured wall.**

**A PDF does not guarantee vectors.** `ganganagar plan.pdf` carries **no
linework** and routed to the raster path, where it skipped for want of an ML
reader. **The extension is not the route** — `meta.source` is, and it belongs in
the read-first protocol beside `route`, `parse_pass`, `scale.source` and
`plot_source`.

Judged set unmoved: fp 1247.1 / 1796.8 / 1738.4 / 4472.1 · anchors 70/79/69/60% ·
R-2 98.0/8/0 · 83.6/12/2 · 96.9/16/7 · M-1 1.13/1.06/1.07/1.09. Four checks green;
4 new tests.

## Outline epsilon derived, and a basis measurement that contradicts the scorecard (2 Sep 2026)

**The thirteenth constant is gone.** `approxPolyDP` ran at a fixed **2.0 raster px
= 0.039 ft** — **0.05×–0.16×** of each sheet's own wall — so it could not remove a
step shorter than a wall. Now **W/2**, the same reading already used for
`face_tol`, floored at 2.0 px where the wall cannot be measured.

| sheet | outline pts | short steps | polygon area | `footprint_sqft` · M-1 |
|---|---|---|---|---|
| BRICK WORK | 42 → **27** | 15 → **0** | −0.00% | 1247.1 · 1.13 unchanged |
| FLOOR PLAN | 59 → **26** | 34 → **5** | +0.53% | 1796.8 · 1.06 unchanged |
| GHATIKIA | 163 → **92** | 97 → **2** | +0.03% | 1738.4 · 1.07 unchanged |
| FIRST FLOOR | 521 → **234** | 319 → **30** | −0.08% | 4472.1 · 1.09 unchanged |
| cold sheet | 25 → **10** | 15 → **0** | +0.03% | 1436.3 · 1.08 unchanged |

Outline noise **36–61% → 0–19%**. Area holds because it is structural, not lucky:
**`footprint_sqft` is the pixel count of the filled ring, not the polygon's area.**

## Basis detection — the statistic works; my numbers contradict the scorecard's

**Statistic:** per printed side, **deficit = printed − measured**, over rooms with
exactly **one** printed label (`printed_labels_in_room == 1` — an independent
exclusion, never the ratio itself), **MAD** for scatter, plus **corr(deficit,
printed size)** — the additive/multiplicative separator.

| sheet | W | n | deficit ft | S/N | deficit/W | corr | reads as |
|---|---|---|---|---|---|---|---|
| GHATIKIA | 0.33 | 22 | **+0.900** | 3.39 | **2.69** | 0.49 | large — but **2.7 walls**, and corr 0.49 says **scale-like**, matching its known 9% residual |
| FLOOR PLAN | 0.83 | 16 | +0.041 | 0.85 | 0.05 | −0.27 | clear-inside |
| FIRST FLOOR | 0.42 | 24 | −0.062 | 0.39 | −0.15 | 0.40 | clear-inside |
| cold Typical (19.06) | 0.83 | 16 | +0.039 | **11.14** | 0.05 | 0.40 | clear-inside |
| **First Floor Plan** | **0.39** | 14 | **−0.120** | 0.94 | −0.31 | −0.48 | clear-inside |
| **Typical Floor Plan** | **0.38** | 14 | **−0.101** | 0.87 | −0.27 | −0.50 | clear-inside |
| BIJAYALAXMI-02 | 0.43 | 22 | −0.040 | 0.32 | −0.09 | −0.12 | clear-inside |

**A magnitude test is essential — a bare S/N would have lied:** the cold sheet
reads **S/N 11.14** on a deficit of **0.039 ft**, perfectly consistent and
physically nothing.

**CONTRADICTION, reported not resolved.** I cannot reproduce ~0.8 ft anywhere.
The two sheets named read **−0.120 and −0.101 ft** — we measure *larger* than
printed, not smaller — on **14 of 39 rooms** carrying a printed dim; and **their
measured wall is 0.39 / 0.38 ft, not 0.8** (gaps bimodal: 4.2–4.6 in internal,
11.2–11.3 in external, so 0.8 ft is neither). **R-2 not adjusted.** What would
settle it: the scorecard's own definition of "per-side deficit" and of "wall
thickness".

Four checks green; judged set unmoved apart from the outline shape.

## The contradiction, measured per room (2 Sep 2026)

**Standing rule first:** *a consistency statistic without a magnitude test will
confidently report a phenomenon that does not exist.* The cold sheet's deficit
reads **S/N 11.14** — the tightest signal in the corpus — on **0.039 ft**.

**1. Same room set.** All four rooms the scorecard names are present on **both**
sheets, with the same printed values.

| room | printed (ours) | our bbox measured | deficit per side |
|---|---|---|---|
| kitchen | 7.50 × 8.00 | 7.80 × 8.43 | **−0.30 / −0.43** |
| kitchen | 7.00 × 8.33 | 7.25 × 8.51 | −0.25 / −0.17 |
| bathroom | 5.00 × 6.17 | 4.70 × 6.21 | **+0.30** / −0.04 |
| stairs | 5.17 × 5.33 | 5.25 × 5.30 | −0.08 / +0.03 |

**We read LARGER than printed on 6 of 8 sides, by 0.15–0.43 ft. Nothing near 0.8,
and the sign is opposite.**

**2. "Measured" = the room polygon's bbox extent**, and those polygons are **free
space in the sealed raster**, so the dilate/erode pair leaks into the wall band —
which is exactly the 0.2–0.4 ft over-read above. A deficit taken from the **drawn
wall faces** would be a different quantity and could carry the opposite sign.
**This is the most likely place the two measurements diverge.**

**3. "Per side" = each dimension separately** here, not half a room total.

**4. Where 0.8 could have come from — three candidates, all live on these sheets:**

| candidate | value | note |
|---|---|---|
| 2 × median wall | **0.752 / 0.770 ft** | the room's two walls added |
| external gap peak | **0.917 ft** | the 11 in mode |
| **the parser's own fallback `_wall_thickness_ft(...) or 0.83`** | **0.83 ft** | what our code substitutes when it cannot measure a wall — and also FLOOR PLAN's real wall. **The likeliest number to have travelled between sessions unlabelled** |

Our measured median wall is **0.376 / 0.385 ft**, from a **bimodal** distribution
(105–124 pairs at 4 in, 135–139 at 11 in). **0.8 is neither mode.**

**5. An unrelated finding the dump forced out: 30 of 39 "rooms" on both sheets are
`duct`** — every one a strip **0.93–0.95 ft** on its short side, i.e. the 11 in
external-gap peak. They are **wall cavities read as enclosed voids**. Any
statistic taken over "all rooms" on these sheets is taken over **77% wall
cavity**, which is itself a plausible route to a deficit measured on the wrong
population. Recorded, not fixed.

**R-2 not adjusted either way.** Settling it needs one thing from the scorecard:
its per-room deficit for those four rooms, with its own "measured" value beside
our bbox extents above.

## Ducts, and the median of a bimodal wall (2 Sep 2026)

**Their error accepted:** 0.83 ft was DHAL-01's wall read from another JSON row —
the sixth audit-geometry error this month, and the number our own fallback
`_wall_thickness_ft(...) or 0.83` uses. Per-dimension vs per-face halves their
0.7–0.9 to **0.35–0.45**, which is our **0.39**. **Magnitude settled; only the
sign is open.** Centroid list posted to `docs/HANDOFF-TO-SCORECARD.md`.

**Where the duct strips actually land — the hypothesis is disproved, not deferred.**

| | Typical Floor Plan | First Floor Plan |
|---|---|---|
| rooms typed `duct` | **30 of 39** | **30 of 39** |
| their area | **117.5 sqft** | **118.0 sqft** |
| in **carpet**? | **no** — `duct` ∈ `COMMON_TYPES` | no |
| in **R-2's sample**? | **no** — 0 carry a printed dim; sample is 7 real rooms | no |
| in **common area**? | **yes — 117.5 of 145.2 = 81%** | **118.0 of 145.7 = 81%** |
| in 3D? | no — `void: True` | no |

**So they cannot explain the sign flip.** What they *do* break is the
**common-area line**, on sheets where R-8 is blind and nothing can contradict it.

**The median-of-a-mix problem, in a new place.** On both sheets the gap
distribution is **bimodal — 105–124 pairs at 4 in, 135–139 at 11 in** — and
`_wall_thickness_ft` returns **0.376 / 0.385 ft**, a number describing **neither
wall**. That is the 29 Aug finding ("masonry classes are absolute, so the median
wall is a mix") and the 31 Aug rule arriving together in one function, **live at
five call sites**: `_W` for the door grouper (with the `or 0.83` fallback that
started this contradiction), the door cut depth, the **new outline epsilon**, the
wall-line report, and `meta`'s measured-wall figure. **The right quantity is
probably per wall — internal or external — not one median for the sheet.**
Recorded, not fixed.

**R-2 not adjusted.** Nothing in the parser changed this turn.

## The ducts explained, and an R-2 defect I cannot reproduce (2 Sep 2026)

**Settled, and neither measurement was wrong:** I scored 24 sides including cavity
strips, the scorecard scored 5 real rooms — different populations, opposite signs.
**Resolved by comparing centroids, not by arguing.** Standing consequence: *a
statistic quoted between sessions must name its population, not just its value.*

**Q1 — do the strips enter carpet? NO.**

| | Typical Floor Plan | First Floor Plan |
|---|---|---|
| `duct` rooms | 30 of 39 | 30 of 39 |
| their area | 117.5 sqft | 118.0 sqft |
| carpet | **excluded** (`duct` ∈ `COMMON_TYPES`) | excluded |
| **common area** | **117.5 of 145.2 = 81%** | **118.0 of 145.7 = 81%** |
| R-2 sample | **0 of them** — sample is 7 real rooms | 0 |
| 3D | nothing — `void: True` | nothing |

**Q2 — a label attaching to a strip does not reproduce here.** All 30 ducts carry
`printed_labels_in_room = 0` and no printed dim. Nor can I reproduce the R-2
figures quoted: **no room on any of the nine sheets reads `dim_match 0.0` with a
printed 8.0 × 7.5**, and **no sheet reads R-2 74.6**. The 7.5 × 8.0 kitchen exists
on exactly these two sheets and reads **7.80 × 8.43 at 92.0%** (and 7.80 × 8.41 at
92.2%); their R-2 is **95.2 / 7** and **95.1 / 7**, `rooms_off` **0**. Nearest to
74.6 is DHAL-01 at **73.9 with `rooms_checked` 1**. **Which sheet, which pass,
which parser build?** — that is what would close it.

**Q3 — the convention we had never met, and it is the valuable answer.** Read the
linework at one detected duct: a closed box **0.94 × 5.86 ft on layer `wall`**,
four sides **plus two corner-to-corner diagonals** — the cross our golden sheets
draw inside *columns*, here on an elongated **structural pier**, on the wall layer
rather than `column`.

**`enclosed_boxes` already tests for this** — a box "as narrow as the wall" is a
wall body, not a void — **and the bimodal median defeats it**:

| `wall_ft` passed | duct boxes found |
|---|---|
| `None` / **0.376** (the bimodal median we compute) | **72** |
| **0.917** (the sheet's real 11 in external wall) | **36** |

**So the duct explosion is not a duct-rule failure — it is the median-of-a-mix
failure arriving through the duct rule.** The fix is per-wall thickness (internal
vs external), at all five call sites, not a change to the duct rule.

**A hypothesis of mine disproved before reporting:** I expected the 11.04 in
`_geometry_wall_segs` ceiling to be rejecting these walls (their pairs measure
11.19–11.34 in). **Both sheets run the LAYERS route, so that function never
executes on them.** Checked before claiming.

**R-2 not adjusted. Nothing in the parser changed this turn.**

## Free-text area statements, and what the 30 cavity boxes really are (2 Sep 2026)

**Item 2 SHIPPED — two blind sheets are now instrumented.** A printed area
statement need not be a table: Patrapada prints `B.U.A=1129.27 sq.ft.` /
`C.A=1043.98` / `SUPER B.U.A=1648.23` as live text **inside the drawing**, so the
table reader found no header and returned `None`. `parse_free_text_areas` is
positional-free — the value may be glued to the tag or be the **next** token
(both occur on one sheet); `SUPER` in the preceding token is never built-up; and
**the total is identified by ARITHMETIC, not position**: 1129.27 + 1147.22 =
**2276.49** against a printed **2543.61**, so the plate is not the sum and the
**267.12 remainder is the common area** — FLOOR PLAN's 1705 + 246 = 1951 shape,
derived. Tried **second**, never first; **golden corpus byte-identical**.

| now readable on both sheets | printed | parsed | R-8 |
|---|---|---|---|
| built-up (plate) | 2543.6 | **1139.8** | **44.8%** |
| built-up (flats only) | 2276.5 | 1139.8 | 50.1% |
| carpet | 2116.7 | **365.1** | **17.2%** |

**We were parsing under half of these sheets and nothing could say so.**

**Item 1 MEASURED, NOT BUILT — the hatch attribution is only a fifth of it.**
Classified all 30 cavity boxes on Typical Floor Plan:

| what they are | count |
|---|---|
| within 8 ft of a **TOILET** label — the tile hatch | **6** |
| containing two **corner-to-corner diagonals** — crossed rectangles, `0.94 × 5.86 ft` on layer `wall`: structural **piers**, the cross our golden sheets draw inside *columns* but here elongated and on the wall layer | **24** |

**A hatch filter fixes 6 of 30.** The high-leverage fix is the one already named:
`enclosed_boxes` rejects a box "as narrow as the wall", and it returns **72 boxes
at `wall_ft=0.376`** (the bimodal median we compute) against **36 at `wall_ft=0.917`**
(the sheet's real external wall). **The median-of-a-mix is the cause; per-wall
thickness is the fix** — not a duct change and not a hatch filter. Awaiting your
ruling on which to build.

**Queued with evidence, not started:** (3) DHAL-01 is a **stilt parking layout** —
a sheet TYPE we do not read, the first real case for the sheet-type check.
(4) **22 printed room dimensions, 7 scored** — a reading failure, not a sheet
limitation. (5) **Flat membership is printed** (`FLAT NO.-101/201/301/401`, size
10.9 vs 9.1 for room labels) — it closes the flat-boundary problem open since
20 Aug, and the numbering also states which floors the plan repeats on.

## Three items: one premise failed, one shipped, one measured (3 Sep 2026)

**The 17 missed dimensions are NOT a `_dim_tokens` defect — measured before
building.** `dimension_pairs` already reads **19 of ~22** printed dimensions on
both Patrapada sheets, correctly, in feet-inches. A dimension on its own line
parses as a pair on its own; no two-line rule is needed.

| stage | number |
|---|---|
| printed dimensions on the sheet | ~22 |
| **read by `dimension_pairs`** | **19** |
| **rooms available to attach to** | **9 real** (+ 30 cavity boxes) |
| **attached → R-2's sample** | **7** |

**Twelve dimensions are read and thrown away for want of a room to hold them.**
The newly-readable R-8 says the same thing from the other side — **built-up
44.8%, carpet 17.2% of printed**. Items 1 and 4 are **one root cause: the parse
finds under half of this plan.** A two-line label rule would have changed nothing.

**R-2 now names its basis and emits both.** Area squares the per-side error — a
room 5% small on both sides scores **90.2 on area, 95.0 per side**. `summary()`
carries `basis: "area"` plus `median_side_match_pct`, `worst_side_match_pct`,
`sides_checked`. **Area numbers untouched, so every ratchet still measures what
it measured.**

| sheet | AREA | PER-SIDE | gap |
|---|---|---|---|
| FLOOR PLAN | 98.0 (n 8) | 97.4 | −0.6 |
| GHATIKIA | 83.6 (n 12) | 91.2 | **+7.6** |
| FIRST FLOOR | 96.9 (n 16) | 91.8 | **−5.1** |
| Typical / First Floor Plan | 95.2 / 95.1 (n 7) | 96.6 / 96.8 | +1.4 / +1.7 |
| cold Typical (19.06) | 99.0 (n 10) | 99.2 | +0.2 |

**"Systematically ~11 points harsher" does not reproduce as a general rule** —
real and large on GHATIKIA, **reversed** on FIRST FLOOR. Direction is per sheet,
not constant.

**Flat membership reads cleanly; the carpet figure does not yet.** Labels
`101/201/301/401` at (23.3, 56.7) ft and `102/202/302/402` at (27.5, 29.0) ft,
glyph height **10.88 vs 9.1** for room labels — one size larger, as described,
and the numbering states the plan repeats on floors 1–4. Nearest-label
assignment splits **5 / 4 rooms**, giving per-flat carpet **264.0 / 169.5 sqft
against printed C.A 1043.98 / 1072.69 — 25% and 16%.** **The membership read is
sound; the carpet is dominated by the same room-detection failure**, so wiring it
would ship a printed-looking number that is four times wrong. Reported, not
wired, pending the room fix.

Four checks green; judged set unmoved; 3 tests added, 1 re-derived on the ruling.

## Correction, the open edge, and printed flat membership (3 Sep 2026)

**Correction first — I did not build a stacked-token fix.** Last round I reported
the premise **failed** (`dimension_pairs` already reads 19 of ~22) and built
nothing. Measured on my parse right now:

| quoted | my measurement |
|---|---|
| R-2 5 → 21 | **`rooms_checked` 7**, median 95.2 (area) / 96.6 (per side) |
| `built_up_per_floor` fires | **it does not** — 1101.7 sqft, above the 322.9 floor. What fires is **`rooms_implausible`**, median room **4.4 sqft** |
| `space_open_on_one_side` 1138.5 sqft | **218.8 sqft**, open north, bbox x 28.8–41.7, y 58.4–78.4 |

**The 2 Sep provenance rule, in the other direction:** the figures crossing
sessions were the scorecard's, read as mine. Both sides must name the run.

**Q1 — the open edge IS drawn, on layer `0`, and it is a railing.** At the
region's open side the sheet draws **three parallel lines spanning 12.16–12.62 ft
at y 78.23 / 77.95 / 77.76 — gaps 0.28 and 0.19 ft = 3.4 and 2.3 in**. That is the
**railing** signature (1.9–3.0 in), not the wall band (3–18 in). So: **not missing
walls, not a ring failure.** These sheets run the **layers** route, where layer
`0` never reaches the wall reader — the 12 Aug "layer names lie" finding, closed
for the *geometry* route on 17 Aug and **still open for the layers route**. The
sheet prints four BALCONY labels, so the honest reading is an **open balcony whose
railing we discard by layer name**.

**Q2 — what else was silent only because nothing could contradict it.** On these
two sheets, before the free-text areas were read: R-8, the stilt cross-check,
carpet-vs-printed, per-flat carpet, and the `rooms_implausible` refusal all had
no printed figure to fire against. **The room-median check was the only one that
could speak without printed data, and it is the one now refusing.**

**Item 5 SHIPPED — flat membership from the printed label.** `meta.flat_labels`
plus `room["flat"]` on every non-duct room.

| | Typical Floor Plan | First Floor Plan |
|---|---|---|
| labels | `101/201/301/401` (23.33, 56.72) · `102/202/302/402` (27.52, 28.96) | same |
| glyph height | **0.921 ft** vs **0.78 ft** for room labels | same |
| rooms assigned | 5 / 4 | 5 / 4 |
| **per-flat carpet** | **264.0 / 169.5 sqft** | 264.7 / 169.5 |
| printed C.A | **1043.98 / 1072.69** | same |
| match | **25% / 16%** | 25% / 16% |

**We no longer split flats on an x-coordinate we chose ourselves** — the problem
open since 20 Aug. **The 25%/16% gap is not the membership rule**: it is the same
room-detection failure R-8 reports as 44.8% built-up. **The membership is sound;
the carpet number must not be shown to a user until the rooms are found.** Zero
labels on all four golden sheets — nothing there moves.

Four checks green; judged set byte-identical.

## Layer names lie, on a new drafter — reported, not built (3 Sep 2026)

**There is no `Ceiling` layer on any sheet in the corpus.** Enumerated all nine
parseable sheets: **zero contain "ceil"**. Patrapada's eleven are `0` (4,812
lines, 53%), `RENDERED FURNITURES` (2,526), `wall` (1,466), then `FURNITURE`,
`plan`, `staircase`, `A-FURN`, `Chajja`, `01-Gr.Floor`, `text`, `1st flo`.
**Third cross-session figure this round that does not reproduce** — after R-2 21
(mine: 7) and the 1138.5 sqft open side (mine: 218.8). **The disease is real; the
layer name is `0`.**

**What separates the hatch from the walls on the same layer — the existing
W-1/W-3 signature already does, and no hatch filter is needed for it.**

| layer | lines | **PAIRED** (partner 3–18 in, ≥2 ft overlap) | share that pairs |
|---|---|---|---|
| **`0`** | 4,812 | **323** | **7%** |
| `wall` | 1,466 | **179** | 12% |

**64% of this sheet's wall-signature geometry sits on the layer we discard by
name.** On layer `0` the separation is stark: 323 lines pair, 4,489 do not —
hatch, furniture and text outline have no partner at a wall thickness. Collinear
merging first is worth nothing here (323 → 286): the fragments are short but the
wall faces are already whole.

**Why I have not built it.** These sheets take the **layers** route, where the
signature reader is never consulted — that is the fix, and it is the 17 Aug
proposal. But the 17 Aug measurement on FLOOR PLAN cost **carpet 1203.5 → 1132.9
and rooms 16 → 14**: more admitted wall means more wall footprint and thinner
rooms. **The position gate (`paired_extent` / `inside_extent`) is the guard, and
it must be measured on all four golden sheets before any admission.**

**Before table (unchanged this turn), for the after comparison:**

| sheet | footprint | R-2 (area) | n | M-1 |
|---|---|---|---|---|
| BRICK WORK | 1247.1 | — | — | 1.13 |
| FLOOR PLAN | 1796.8 | 98.0 | 8 | 1.06 |
| GHATIKIA | 1738.4 | 83.6 | 12 | 1.07 |
| FIRST FLOOR | 4472.1 | 96.9 | 16 | 1.09 |

**Recorded verbatim, because it is the summary of the whole episode:** *nothing in
the parse changed when the areas were read. Only what we could SEE changed. The
building was 4.6% of printed all along.* **An instrument does not improve a parse
— it stops a wrong parse from looking right.**

**An artefact caught in my own probe before reporting:** `keep_structural_lines`
returns `(segs, stats)`, and my first pass measured `len()` of the **tuple** — 2,
on every sheet and every layer. Had it been reported it would have said the
pairing test finds nothing at all. **Eighth this month; caught, not published.**

# ==========================================================================
# STATE OF THE CORPUS — 3 Sep 2026. Read this first on a cold return.
# ==========================================================================

## Read before any number (standing protocol)

`scale_verified` / `refusals[]` · `meta.route` · `meta.parse_pass` ·
`meta.plot_source` · `meta.source` (a PDF does not guarantee vectors).

## Every instrument, every sheet — one table

| sheet | fp | rooms | ducts | R-2 area | n | R-2 side | anchors | M-1 | R-8 | carpet | common | plot | scale | refusals |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BRICK WORK | 1247 | 13 | 2 | — | — | — | 70% | 1.13 | — | 581 | 82 | unknown | **✗** | scale_unverified |
| FLOOR PLAN | 1797 | 16 | 2 | **98.0** | 8 | 97.4 | 79% | 1.06 | **96.5** | 1191 | 29 | printed | ✓ | — |
| GHATIKIA | 1738 | 13 | 0 | 83.6 | 12 | 91.2 | 69% | 1.07 | — | 1167 | 57 | unknown | ✓ | — |
| FIRST FLOOR | 4472 | 19 | 0 | 96.9 | 16 | 91.8 | 60% | 1.09 | — | 3010 | 335 | unknown | ✓ | — |
| DHAL-01 *(stilt parking — different sheet type, do not fix)* | 94 | 1 | 0 | 73.9 | 1 | 85.7 | — | 1.08 | — | 0 | 20 | unknown | ✓ | builtup_implausible |
| DHAL-02 | 1192 | 42 | **31** | 96.7 | 11 | 97.7 | 100% | 1.12 | **40.4** | 388 | 300 | unknown | ✓ | rooms_implausible |
| First Floor Plan | 1101 | 39 | **30** | 95.1 | 7 | 96.8 | 50% | 1.07 | **44.8** | 366 | 146 | unknown | ✓ | rooms_implausible |
| Typical Floor Plan | 1102 | 39 | **30** | 95.2 | 7 | 96.6 | 62% | 1.07 | **44.8** | 365 | 145 | unknown | ✓ | rooms_implausible |
| Typical FP (19.06) | 1436 | 10 | 0 | **99.0** | 10 | 99.2 | — | 1.08 | — | 926 | 122 | unknown | ✓ | — |
| ganganagar | — | — | — | — | — | — | — | — | — | — | — | — | — | **no vector linework — raster path** |

**Four golden sheets unmoved by everything shipped today.**

## OPEN — what closed today, what is newly open, next action

| item | state | next action |
|---|---|---|
| **outline noise** | **CLOSED** — epsilon derived at W/2; 36–61% → 0–19%, area ≤0.53% | — |
| **free-text area statements** | **CLOSED** — `parse_free_text_areas`; three sheets newly instrumented | — |
| **flat membership** | **CLOSED** — `meta.flat_labels` + `room["flat"]` from the printed label; 0 labels on the golden four | per-flat carpet is 25%/16% of printed and must not reach a user until the rooms are found |
| **R-2 basis** | **CLOSED** — `basis: "area"` + per-side emitted; area untouched | — |
| **cold-sheet guard** | **CLOSED** — both routes; ML path too | — |
| **plausibility** | **CLOSED** — room-median + built-up; injection **7/8** | the remaining miss is FLOOR PLAN 0.5× (480 sqft is a legal floor) |
| **layer names lie, LAYERS route** | **NEWLY OPEN — the biggest item** | layer `0` carries **323 paired lines vs `wall`'s 179** — 64% of wall signature discarded by name. Fix = run the signature reader on the layers route, **gated by `paired_extent`/`inside_extent`**; 17 Aug says a naive union costs FLOOR PLAN carpet 1203.5→1132.9, rooms 16→14. **Measure the gate on all four golden sheets first** |
| **cavity strips as ducts** | **NEWLY OPEN — no safe filter found** | 30/30/31 on three sheets. **Paired-only removes ALL of them (57→0) but also kills FLOOR PLAN's 2 real ducts (3→0). `wall_ft=0.917` halves them but FLOOR PLAN's 1.00 ft ducts then fail the same test.** Neither is safe. Needs a discriminator that is not width and not pairing |
| **`_wall_thickness_ft` median-of-a-mix** | OPEN | bimodal 4 in/11 in returns 0.376 ft, describing neither wall; **five call sites**. Probably per-wall (internal vs external) |
| **room detection on Patrapada** | OPEN — the root cause | 9 real rooms found where the sheet prints ~22; R-8 44.8%, carpet 17%. Everything else on those sheets is downstream of this |
| **`BORDER_MAXLEN_PT`** | OPEN — closest live margin | **88% on BRICK WORK**. Do not fix yet (ruled) |
| **DHAL-01 sheet type** | OPEN | stilt parking layout — the first real case for the sheet-type check. **Do not "fix" it** |
| **raster/ML input** | OPEN — investigation only | CubiCasa repo + weights absent, TensorFlow absent, torch 2.13 with MPS. `ganganagar plan.pdf` is the first real raster case |

## Correction, and three duct discriminators that do not work (4 Sep 2026)

**There is no Hough gate and no Ceiling fix in this codebase.** Verified first
thing: `grep Hough server/*.py` → nothing; **R-8 on both Patrapada sheets reads
44.8%**, not 88.1% / 86.9%. Last round I reported the layers-route admission as
**measured and NOT built** (323 paired lines on layer `0` vs 179 on `wall`), under
the standing "report before building" instruction; the A–D queue that followed did
not authorise it. **Fourth cross-session attribution error in two days** — after
R-2 21 (mine 7), the 1138.5 sqft open side (mine 218.8), and the `Ceiling` layer
(no sheet in the corpus has one). **No §12 entry is written for a fix that does
not exist; the 12 Aug thread stays open.** The provenance rule needs its other
half: *a number crossing sessions must name its run; a change crossing sessions
must name its diff.*

**Q1 — one filter does not serve both. Three candidates tested, none safe.**

| discriminator | cavity boxes | FLOOR PLAN's 2 real ducts | verdict |
|---|---|---|---|
| **paired-only** | 57/57/53 → **0** | 3 → **0** | deletes the real ones too |
| **`wall_ft = 0.917`** | 57 → 21 | its ducts are **1.00 ft** vs 0.917 → fail the ±10% test | same failure |
| **repeating-family** (parallel neighbours of the box's long sides) | 66–94 neighbours | **87–219 neighbours** | **real ducts score HIGHER** |

**The reason is physical and worth keeping: a real duct sits INSIDE a tiled
toilet, so every hatch-proximity signal flags it too.** Pitch CV does not
separate either (0.70–1.03 vs 1.11–2.43). **A safe discriminator must be neither
width, nor pairing, nor hatch-proximity.** Nothing built.

**Q2 — flat membership is shipped** (landed 3 Sep): `meta.flat_labels` +
`room["flat"]`. `101/201/301/401` at (23.33, 56.72) and `102/202/302/402` at
(27.52, 28.96), glyph **0.921 ft vs 0.78** for room labels; rooms split **5 / 4**;
per-flat carpet **264.0 / 169.5 sqft** against printed C.A **1043.98 / 1072.69 =
25% / 16%**. Membership sound; the gap is room detection. **0 labels on the
golden four.**

**Q3 — the eight-sheet table is the one written above under "STATE OF THE CORPUS"
and it is current**: nothing in `server/` changed this turn, and the judged four
re-verified at 1247 / 1797 / 1738 / 4472, R-2 98.0/8 · 83.6/12 · 96.9/16,
M-1 1.13 / 1.06 / 1.07 / 1.09.

**The scorecard's `raw_coverage` (25.9% / 24.9% against 42–66% elsewhere) is a
prediction our parse has not yet answered** — it needs the layers-route admission,
which remains measured and unbuilt.

## Poché: the "duct" strips are filled WALLS — my cavity reading was wrong (5 Sep 2026)

`overlays/poche/1-poche-vs-ducts-FULL.png` · `2-crop-one-external-wall.png`
(layers: 1 maroon fills · 2 our duct strips · 3 `walls_poly` · 4 raw linework).

**Decisive before the render: 30 of 30 duct strips lie INSIDE a single maroon
fill (>60% of the strip's area); ZERO straddle two.** A cavity between two skins
would have straddled. Typical Floor Plan carries **94 maroon fills, RGB
(0.6, 0.10588, 0.11765), 42,662 pt², median 11.16 × 11.16 pt, longest 267 pt** —
and **11.16 pt = 0.945 ft**, exactly the width I called a cavity. The crop shows
the strips running continuously around the LIFT and along the external edge, with
`walls_poly` sitting *beside* them. **`enclosed_boxes` is not finding voids: it is
tracing the outline of SOLID WALL and calling the material a shaft.**

| sheet | filled objects | total area pt² | note |
|---|---|---|---|
| BRICK WORK | **1435** | **337,591** | all black poché |
| FLOOR PLAN | **775** | **530,262** | 723 black + 52 red |
| Typical Floor Plan | 800 | 43,865 | **94 maroon** = the walls |
| First Floor Plan | 795 | 33,500 | same drafter |
| DHAL-02 | 839 | 43,876 | 145 maroon |
| DHAL-01 | 664 | 9,943 | parking layout — do not fix |
| GHATIKIA | 2 | 11 | geometry route |
| neelachala FIRST FLOOR | 34 | 97 | geometry route |
| Typical FP (19.06) | 0 | 0 | — |
| ganganagar | 1 | — | a white page rectangle |

**Six of ten sheets draw substantial poché and we read none of it as wall — we
read only LINES.** The two that draw almost none are the two on the geometry
route. **This is a bigger surface than the layer-name thread: a wall may be drawn
as a filled SHAPE, and nothing in the parser looks at fills at all.**

No code changed.

## The two poché measurements, and a fourth failed discriminator (5 Sep 2026)

**1 — FLOOR PLAN's fills are not wall; the two sheets are opposite.**

| | fills inside the plan | union area | median fill | outside the plan | ∩ `walls_poly` |
|---|---|---|---|---|---|
| **FLOOR PLAN** | 363 | **42.9 sqft** | **0.090 sqft** (glyphs, hatch dots) | **412** (title block, logo, table) | **2.4%** |
| **Typical FP** | 331 | **157.3 sqft** | 0.007 sqft | 0 | **97.6%** |

The 530,262 pt² headline was **bbox area summed over overlapping glyphs**, not
material. **On our most-tuned sheet there is neither a double-count risk nor
missed wall — its walls are line pairs, which is why it parses well.** On Typical
FP the poché is **already inside `walls_poly`**. So a fill reader would
**double-count where poché exists and admit lettering where it does not**.

**2 — the 94 vs 184 discrepancy is a double count, reconciled exactly.** Every one
of the 94 maroon paths carries maroon as **both `fill` and `color`**: fill-matches
94, stroke-matches 94, *either* 94, *both* 94. Counting the two lists separately
gives **188 paths / 85,323 pt²** against 184 / 83,885 — within 2%. Mine: one row
per distinct path. Theirs: one row per colour match, summed over fill and stroke.

**3 — the obvious fix is measured dead.** "Reject a box inside solid wall
material": duct boxes lie inside `walls_poly` at **Typical FP 99.7% median (30/30
over 90%), DHAL-02 100.0% (31/31), and FLOOR PLAN's two REAL ducts at 100.0%,
BRICK WORK's at 99.6%.** A real duct is a void **ringed** by wall, so it reads
solid by design — the 17 Aug §4 D-5 ruling. **Four discriminators now measured,
all unsafe: width · pairing · hatch-proximity · wall-containment.**

**Proposal, not built.** Do **not** build a fill reader. The defect is narrower:
`enclosed_boxes` traces rectangles out of the **outline of wall material**. The
one untried signal is *whose* boundary the box sits on — **one single filled/solid
component (poché → material) versus faces of several different wall runs (a real
shaft carved between walls)**. Judged on the golden four by: FLOOR PLAN and BRICK
WORK must keep **2 ducts each**, and their footprint, R-8, R-2 and M-1 must not
move; Typical FP and DHAL-02 should go **30/31 → 0**.

## Boundary provenance — the fifth discriminator, and the first that holds (5 Sep 2026)

**A real shaft is bounded by faces of several wall runs; a poché box is the
boundary of ONE filled shape.** Overlap between a box and the single fill it sits
in: **50.0–50.3% where poché is drawn, 0.0–0.6% on FLOOR PLAN and BRICK WORK** —
a **49-point empty band**, so the 25% threshold clears the cluster rule by a wide
margin. Filtered **at the consumer**, so `enclosed_boxes` stays pure; a unit test
pins the finder's own behaviour unchanged.

| sheet | ducts | rooms | footprint | R-2 quartet | M-1 |
|---|---|---|---|---|---|
| FLOOR PLAN | **2 → 2** | 16 | 1796.8 | 98.0 / 8 / 0 / 90.4 | 1.06 |
| BRICK WORK | **2 → 2** | 13 | 1247.1 | — | 1.13 |
| GHATIKIA | 0 → 0 | 13 | 1738.4 | 83.6 / 12 / 2 / 0.0 | 1.07 |
| FIRST FLOOR | 0 → 0 | 19 | 4472.1 | 96.9 / 16 / 7 / 0.0 | 1.09 |
| Typical FP | **30 → 0** | 39 → **9** | 1101.7 | 95.2 / 7 / 0 / 92.0 | 1.07 |
| First Floor Plan | **30 → 0** | 39 → **9** | 1101.1 | 95.1 / 7 / 0 / 92.2 | 1.07 |
| DHAL-02 | **31 → 0** | 42 → **11** | 1191.8 | 96.7 / 11 / 1 / 53.8 | 1.12 |

**All four golden numbers identical to the decimal.** On the three poché sheets
the `rooms_implausible` refusal **clears** (median room **4.4 → 34.7 / 35.0 /
38.1 sqft**) and common area falls to the real figure (**145.2 → 27.7**).

**R-2's sample does not move, and the prediction was wrong for a reason already
measured.** The quartets are byte-identical before and after: **not one of the 91
cavity boxes ever carried a printed dimension** (`printed_labels_in_room` 0 on all
of them, measured 2 Sep). **They were never in R-2's sample — they were in the
room COUNT and in COMMON AREA.** R-2's 7 is still bounded by room *detection* —
19 printed dimensions read against 9 real rooms — which this fix does not touch
and which remains the open root cause.

**Also recorded: an area summed from bounding boxes is not an area.** FLOOR PLAN's
"530,262 pt² of poché" was 775 overlapping path bboxes, mostly filled letter
glyphs; the true union inside the plan is **42.9 sqft**. Same family as the
mesh-bbox railing error of 1 Sep.

Four checks green; 1 test added.

## Where the corpus actually stands — every instrument, every sheet (5 Sep 2026)

**Correction first: the provenance test was already built when the ruling arrived**
— the ruling confirms what shipped, and **no ranking was ever proposed**. Four
figures in it are not from this parse: ducts **30/30/31 → 0** (not 28→0), rooms
**39→9, 39→9, 42→11** (not 34→6), **R-8 44.8%** (not 88.1%), and **layer names are
NOT gone as a gate** — that remains measured and unbuilt (layer `0`: 323 paired
lines vs `wall`'s 179). Fifth attribution round in three days.

| sheet | fp | rooms | ducts | R-2 area | n | off | worst | R-2 side | anchors | M-1 | R-8 | carpet | common | scale | refusals |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BRICK WORK | 1247 | 13 | **2** | — | — | — | — | — | 70% | 1.13 | — | 581 | 82 | **✗** | scale_unverified |
| **FLOOR PLAN** | **1797** | 16 | **2** | **98.0** | 8 | 0 | 90.4 | 97.4 | 79% | 1.06 | **96.5** | 1191 | 29 | ✓ | — |
| GHATIKIA | 1738 | 13 | 0 | 83.6 | 12 | 2 | 0.0 | 91.2 | 69% | 1.07 | — | 1167 | 57 | ✓ | — |
| FIRST FLOOR | 4472 | 19 | 0 | 96.9 | 16 | 7 | 0.0 | 91.8 | 60% | 1.09 | — | 3010 | 335 | ✓ | — |
| DHAL-01 *(stilt parking — different sheet type)* | 94 | 1 | 0 | 73.9 | 1 | 1 | 73.9 | 85.7 | — | 1.08 | — | 0 | 20 | ✓ | builtup_implausible |
| DHAL-02 | 1192 | **11** | **0** | 96.7 | 11 | 1 | 53.8 | 97.7 | 100% | 1.12 | **40.4** | 388 | 201 | ✓ | — |
| First Floor Plan | 1101 | **9** | **0** | 95.1 | 7 | 0 | 92.2 | 96.8 | 50% | 1.07 | **44.8** | 366 | 28 | ✓ | — |
| Typical FP (19.06) | 1436 | 10 | 0 | **99.0** | 10 | 4 | 0.0 | 99.2 | — | 1.08 | — | 926 | 122 | ✓ | — |
| Typical Floor Plan | 1102 | **9** | **0** | 95.2 | 7 | 0 | 92.0 | 96.6 | 62% | 1.07 | **44.8** | 365 | 28 | ✓ | — |
| ganganagar | — | — | — | — | — | — | — | — | — | — | — | — | — | — | **no vector linework** |

**Judged criteria met:** FLOOR PLAN and BRICK WORK keep **2 ducts each**, lose no
rooms (16 / 13), and footprint · R-8 · R-2 · M-1 are identical to the decimal.

**The poché surface is narrower than the census implied.** Six sheets draw fills;
only **three draw WALLS as fills** — the three where the filter fired. FLOOR PLAN's
775 and BRICK WORK's 1,435 are lettering and hatch dots (0.09 sqft median, 2.4%
overlap). **The missing wall on the cold sheets is not poché — it is the
layer-name gate**, which is the largest item still open.

## M-2: does the MODEL match the parse? (5 Sep 2026, `server/model_check.py`)

Every instrument until now measured the **parse**. FLOOR PLAN read R-8 96.5 with
a slab 58% too large, no staircase and no ceiling — right numbers, wrong
building. M-2 compares the built meshes against the scene they were built from,
so it needs **no printed data and no human reading an image**.

| sheet | built floor % of fp | volume % of fp×H | meshes | outside fp | slope y | door err ft (med/max) | built as nothing |
|---|---|---|---|---|---|---|---|
| BRICK WORK | 101.5 | **21.3** | 158 | 4 | 0.998 | 1.47 / 2.51 | **ducts, railings** |
| FLOOR PLAN | 109.6 | **26.0** | 140 | 6 | 0.938 | 1.44 / 2.52 | **ducts, stairs** |
| GHATIKIA | 105.1 | **21.1** | 154 | 9 | 0.983 | 1.62 / 2.52 | stairs |
| FIRST FLOOR | **116.8** | **19.4** | 308 | **55** | 1.001 | 1.42 / 2.73 | stairs |
| DHAL-01 | 113.7 | 53.2 | 47 | 27 | 1.088 | 1.76 / 2.58 | railings, stairs |
| DHAL-02 | 107.7 | 44.9 | 444 | **163** | 0.988 | 1.71 / 2.74 | railings, stairs |
| First Floor Plan | 112.6 | 63.4 | 379 | **180** | 1.001 | 1.69 / 2.31 | stairs |
| Typical FP (19.06) | 102.6 | 20.7 | 81 | 1 | 0.990 | 1.63 / 2.38 | — |
| Typical Floor Plan | 112.4 | 63.0 | 379 | **177** | 1.001 | 1.69 / 2.31 | stairs |

**What it found that no parse number can see.** (1) **Built volume is 19–63% of
footprint × storey on every sheet** — there is no ceiling and no roof anywhere.
(2) **Built floor exceeds the footprint on all nine** (101.5–116.8%): balcony and
utility slabs sit outside the wall ring. (3) **Meshes outside the footprint:
163–180 on the poché sheets and 55 on FIRST FLOOR** against 1–9 elsewhere. (4)
**Elements built as nothing: ducts on both golden sheets** (they were split into
`duct_i_k` shafts on 1 Sep and emit no mesh), **railings on three**, and
**stairs on seven of nine**.

**Two artefacts caught in the metric before publishing.** The door **offset**
(~1.5 ft median everywhere) is expected — a door mesh is the leaf swung open, so
half a leaf of offset is correct, and it is labelled as such rather than reported
as a defect. And the **slope read ~1.0 on all eight sheets and on a deliberately
stretched fixture**, because meshes were matched to cuts by NEAREST: a metric
that cannot come out wrong is not a metric. Now paired **by index, in the
builder's own index space** — the first attempt indexed the door-only list and
reported a 17 ft median error on FLOOR PLAN. **It still cannot see a global
mirror** (nearest or not, a mirrored model has a mesh beside every cut) — the
same blind spot §12 records for 18 Aug, where only a render caught it. Said in
the docstring rather than implied.

4 new tests. No parser number moved — M-2 reads the scene, it does not change it.

# ==========================================================================
# STATE OF THE CORPUS — 5 Sep 2026, end of day. Read this first.
# ==========================================================================

**Read before any number:** `scale_verified` / `refusals[]` · `meta.route` ·
`meta.parse_pass` · `meta.plot_source` · `meta.source`.

## Parse + model, every sheet

| sheet | fp | rooms | ducts | R-2 area | n | off | R-2 side | anc | M-1 | R-8 | carpet | common | vol% | outside fp | stairs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BRICK WORK | 1247 | 13 | 2 | — | — | — | — | 70% | 1.13 | — | 581 | 82 | 21.3 | 8.4% | — |
| **FLOOR PLAN** | **1797** | 16 | 2 | **98.0** | 8 | 0 | 97.4 | 79% | 1.06 | **96.5** | 1191 | 29 | 26.0 | 22.6% | — |
| GHATIKIA | 1738 | 13 | 0 | 83.6 | 12 | 2 | 91.2 | 69% | 1.07 | — | 1167 | 57 | 21.1 | 23.9% | refused 14.8 in |
| FIRST FLOOR | 4472 | 19 | 0 | 96.9 | 16 | 7 | 91.8 | 60% | 1.09 | — | 3010 | 335 | 19.4 | 31.0% | refused 9.8 in |
| DHAL-01 *(stilt parking — do not fix)* | 94 | 1 | 0 | 73.9 | 1 | 1 | 85.7 | — | 1.08 | — | 0 | 20 | 53.2 | **49.0%** | — |
| DHAL-02 | 1192 | 11 | 0 | 96.7 | 11 | 1 | 97.7 | 100% | 1.12 | 40.4 | 388 | 201 | 44.9 | **59.4%** | — |
| First Floor Plan | 1101 | 9 | 0 | 95.1 | 7 | 0 | 96.8 | 50% | 1.07 | 44.8 | 366 | 28 | 63.4 | **58.2%** | — |
| Typical FP (19.06) | 1436 | 10 | 0 | **99.0** | 10 | 4 | 99.2 | — | 1.08 | — | 926 | 122 | 20.7 | 3.9% | **20 risers @ 5.9 in** |
| Typical Floor Plan | 1102 | 9 | 0 | 95.2 | 7 | 0 | 96.6 | 62% | 1.07 | 44.8 | 365 | 28 | 63.0 | **58.4%** | — |
| ganganagar | — | — | — | — | — | — | — | — | — | — | — | — | — | — | no vector linework |

## OPEN — next action for each

| item | state | next action |
|---|---|---|
| **meshes outside the footprint** | **NEWLY OPEN — the real version of queue item 2** | **Typical FP 58.4% (178 meshes) · First Floor Plan 58.2% (181) · DHAL-02 59.4% (164, x max 89.5 on an 87 ft plate) · DHAL-01 49.0% (27, x max 44.7 on a 16 ft plate)**. GHATIKIA is NOT one of them (x max 44.1 on a 0..44 footprint). Find what is built beyond the ring and why |
| **no ceiling / no roof** | OPEN — M-2's biggest signal | built volume is **19–63%** of footprint × storey on every sheet. Rahul deferred this on 1 Sep until the plan reading is verified |
| **ducts build no mesh** | OPEN | `duct_i_k` shafts emit nothing on FLOOR PLAN and BRICK WORK (2 each) |
| **railings build no mesh** | OPEN | DHAL-01, DHAL-02, BRICK WORK |
| **layer names lie, LAYERS route** | OPEN — largest parse item | layer `0` carries **323 paired lines vs `wall`'s 179**. Gate with `paired_extent`; 17 Aug says a naive union costs FLOOR PLAN carpet 1203.5→1132.9 |
| **room detection on Patrapada** | OPEN — root cause of R-8 44.8% | 19 printed dimensions read, 9 real rooms to attach them to |
| `_wall_thickness_ft` median-of-a-mix | OPEN | bimodal 4/11 in returns 0.376 ft — neither wall. Five call sites |
| `BORDER_MAXLEN_PT` | OPEN | 88% on BRICK WORK. Do not fix yet (ruled) |
| raster/ML input | OPEN | CubiCasa repo + weights absent, TF absent. `ganganagar` is the first real case |
| **CLOSED today** | — | poché boundary provenance (91 cavity boxes → 0, golden byte-identical) · M-2 built · orientation recorded for all ten sheets · staircase machinery confirmed working |

**Queue items 1 and 2 were not built: their figures do not reproduce.** Walls are
at **0.78–0.98×** expected volume, never 1.75–2.11 — and below 1 is correct,
since openings cut material out. GHATIKIA builds nothing beyond x 44.1. **Fixing
what was described would have moved the wrong sheets.**

## The wing frame, and what is really built outside the footprint (5 Sep 2026)

**The GHATIKIA wing contradiction is a FRAME, not a bug.** Pass 1 has
`shift_ft = [43.536, −0.195]` and `wing.bbox_ft = [43.5, −0.2, 80.2, 48.0]` —
**the shift IS the bbox origin**. Subtract it and you get **0.0..36.6**, exactly
that pass's footprint (−0.3..36.6) and every field quoted.

| | `wing.bbox_ft` | `shift_ft` | footprint x | agree? |
|---|---|---|---|---|
| pass 1 (discarded) | 43.5 .. 80.2 | **43.536** | −0.3 .. 36.6 | only after subtracting the shift |
| **pass 2 (built)** | −0.2 .. 43.7 | −0.196 | 0.0 .. 44.1 | yes |

**`wing.bbox_ft` is the last field left in PRE-SHIFT sheet coordinates; every
scene field is POST-SHIFT.** On the built pass the shift is ~0 so they coincide
and the mismatch is invisible — **it only shows on the discarded pass, which is
what a route key derived from `wing.bbox_ft` reads.** The scene's own fields are
the authority. Until the field states its frame, **a route key should use
`regions[].key` (already origin-based) or `parse_pass` + the built footprint.**

**And my own outside-footprint metric is part artefact.** M-2 tests each mesh's
**axis-aligned bbox**, and a wall prism or a slab traced from an L-shaped ring
has a bbox that legitimately overhangs. Hence `floor` — one mesh which *is* the
footprint polygon — reports **33–67% "outside" on every sheet**, and `wall_p`
15–54%. **The 22.6% baseline is mostly this, not defects.**

**What survives the artefact is furniture, and it is real:**

| sheet | family | n | outside | mesh x-max vs plan |
|---|---|---|---|---|
| DHAL-02 | `furn_bed` | 30 | **100.0%** | 86.0 vs 87.1 |
| Typical FP | `furn_bed` | 30 | **98.8%** | 40.6 vs 41.6 |
| both | `furn_sidetable` / `furn_table` | 36 / 10 | 99–100% | — |
| **DHAL-01** | `furn_sidetable` | 16 | 100% | **44.7 vs a 15.8 ft plate** |

Two distinct cases: on DHAL-02 and Typical FP furniture sits **inside the plan
but outside the wall ring**; DHAL-01 stages furniture **three times beyond the
drawing**. Next action: trace `furnish`'s staging frame — it is the only
consumer that places meshes from room coordinates rather than from the ring.

**Same family as the mesh-bbox railing error (1 Sep) and the bbox area sum
(5 Sep): a bounding box is not a shape.** M-2 should test the mesh's plan
polygon, not its bbox — recorded, not changed.

## `meta.glb` shipped; chhajja is not built at all (5 Sep 2026)

**Chhajja: seventh attribution.** No `chhajja` mesh family exists on any of the
nine parseable sheets — the word appears only in three *comments* in
`pdf_vector.py`. Two sheets carry a `chhajja` **layer** (FIRST FLOOR 403 lines,
GHATIKIA 19) and it reaches no mesh. **A chhajja builder would have added meshes
to fix a number that no chhajja produces.** The 22% baseline was measured last
turn: my own **bbox artefact** (`floor`, one mesh which *is* the footprint
polygon, reads 33–67% "outside" because an L-shaped ring has an overhanging
bbox) plus **furniture staged outside the ring**. Worth building later on its own
merits — a sunshade is genuinely missing from every model.

**The wing contradiction, settled (restated):** `wing.bbox_ft` is the last field
in **pre-shift SHEET** coordinates; every scene field is **post-shift**. Pass 1
has `shift_ft = [43.536, −0.195]` and `wing.bbox_ft = [43.5 … 80.2]`; subtract
the shift and it is **0.0..36.6**, exactly that pass's footprint. **Both are
right, in different frames**, and it only shows on the **discarded** pass — which
is what a route key derived from `wing.bbox_ft` reads. **Key on
`regions[].key`** (already origin-based) or `parse_pass` + the built footprint.

**`meta.glb` — five fields, one computation, one owner** (written by
`_build_scene`, where meshes and scene exist together), each payload carrying its
own `units` and `axis`:

| sheet | outside% | wall vol | orphans | missing% | seg uncl% |
|---|---|---|---|---|---|
| BRICK WORK | 6.2 | 0.911 | 0 | 33.3 | 0.0 |
| FLOOR PLAN | 16.2 | 0.975 | 0 | 28.6 | 0.0 |
| GHATIKIA | 18.0 | 0.939 | 0 | 16.7 | 0.0 |
| FIRST FLOOR | 21.2 | 0.933 | 0 | 20.0 | 0.0 |
| DHAL-01 | **48.9** | 0.788 | 0 | 40.0 | 0.0 |
| DHAL-02 | **57.3** | 0.778 | 0 | 40.0 | 0.0 |
| First Floor Plan | **54.7** | 0.840 | 0 | 20.0 | 0.0 |
| Typical FP (19.06) | **3.6** | 0.980 | 0 | **0.0** | 0.0 |
| Typical Floor Plan | **54.9** | 0.841 | 0 | 20.0 | 0.0 |

**Wall volume is never above 1.0** — 0.778–0.980 — so no sheet double-builds
walls. `orphan_meshes` is 0 and `seg_unclassified_pct` 0.0 everywhere: every mesh
family maps to a gbuffer class. Two new tests; **no parse number moved**.

## The DHAL sheets: both candidates negative, a third cause found (5 Sep 2026)

**Test 2 clears DHAL-02 completely.** Page 1191×842 pt at ppf 11.697 = **101.8 ×
72.0 ft**; the plan reads **87.1 × 37.8 ft** and fits with room to spare. Scale is
`cad_units` **verified by 20 printed side samples**, the free-text reader parses
its whole statement (**plate 2950.0 · built-up 2709.9 · carpet 2541.34 · common
240.1 derived · super 3739.66**), and **R-2 reads 96.7 / 11 / 1**. **No scale
error, and no 260 ft** — my measurement was mesh x-max **89.5 against an 87.3 ft
footprint, i.e. 2.2 ft of balcony.**

**Test 1 is absent too:** neither DHAL sheet has an `A-WALL-PATT` layer.
DHAL-02: `0` (5623) · `RENDERED FURNITURES` (2038) · `wall` (973) · `ELEWIN`.
DHAL-01: `RENDERED FURNITURES` (2281) · `hatch floor` (2247) · `wall` (136).

**The real cause is DHAL-01, and it is the opposite of what we assumed.**

| | DHAL-01 | DHAL-02 (same project) |
|---|---|---|
| ink extent at its own ppf | **88.1 × 46.9 ft** | — |
| built region | **15.8 × 11.7 ft**, footprint **94.1 sqft** | 87.1 × 37.8 |
| `wall`-layer lines | **136** | **973** |
| dropped as border/boundary | **67 unpaired mega-lines** | — |

**Its 49% "outside footprint" is not furniture placed wrongly — the furniture is
right and the ENVELOPE is missing.** Same root as Patrapada's R-8 44.8%: **the
layers route reads only what the drafter happened to name `wall`.**

**A hole in my own cold-sheet guard, found while measuring this.** DHAL-01
reports `scale_verified: true` from "printed dimension text" — on **5 agreeing
votes but an R-2 sample of ONE room**. `SCALE_REFIT_MIN_SIDES = 8` guards the
*refit* route; **nothing guards the DIRECT route**, so a scale from a single
readable dimension carries the same confidence as one corroborated by 20 sides.
The guard separates printed from guessed but not well- from barely-corroborated.
Recorded, not changed — a second variable, on a sheet ruled off-limits.

Nothing built this turn; judged set untouched.

## Routing is not the fix — measured before building (5 Sep 2026)

**The question asked: what does DHAL-01's geometry route produce? Answer: the
same envelope.**

| sheet | as-is | `force_geometry` |
|---|---|---|
| **DHAL-01** | 15.6 × 11.5 ft · fp 94 · 1 room | **15.6 × 11.5 ft** · fp 174 · 2 rooms |
| **FLOOR PLAN** | 95.2 × 29.8 · fp **1797** · 16 rooms · R-2 98.0/8 | 94.3 × 23.5 · fp **576** · **3 rooms** · **R-2 0.0/2** |
| **BRICK WORK** | 29.6 × 48.7 · fp **1247** · 13 rooms | 28.2 × 38.8 · fp **262** · **1 room** |
| GHATIKIA | fp 1738 · R-2 83.6/12 | fp 2271 · **R-2 99.5/12** |
| FIRST FLOOR | fp 4472 · R-2 96.9/16 | **identical** (already geometry) |
| DHAL-02 | fp 1192 · 11 rooms · R-2 96.7/11 | fp **2510** · 18 rooms · **R-2 99.5/16** |
| Typical Floor Plan | fp 1102 · 9 rooms · R-2 95.2/7 | fp **2902** · 15 rooms · R-2 88.3/13 |

**Two findings that change the design.**

1. **DHAL-01's missing envelope is NOT a layer-name failure.** It reads
   15.6 × 11.5 ft on *both* routes, so admission is not what bounds it — wall
   **detection** is. On a stilt parking plan the walls are genuinely sparse
   (open parking, columns), and 88.1 ft of ink is mostly `RENDERED FURNITURES`
   and `hatch floor`. It should be re-examined as a **sheet type**, with
   DHAL-02 as the control, not as a layer-gate case.
2. **A route switch is disqualified: both golden layers-route sheets collapse**
   — FLOOR PLAN to 3 rooms and R-2 0.0, BRICK WORK to 1 room. The gain is real
   but sits on the other sheets (DHAL-02 and GHATIKIA improve on *both* coverage
   and R-2; Typical FP gains coverage and loses 6.9 R-2 points on a sample that
   nearly doubles — the pre-authorised direction).

**So the fix must be ADMISSION by signature layered ON TOP of the layers route,
position-gated — not a route switch.** That is the 17 Aug union, which cost
FLOOR PLAN carpet 1203.5 → 1132.9 and rooms 16 → 14; the `paired_extent` gate is
what has to make the difference, and it must be measured on the golden four
before anything ships. **Nothing built.**

## OPEN — added this turn

| item | state | next action |
|---|---|---|
| **layer-name gate** | OPEN — largest item, design changed today | not a route switch; signature admission on top of the layers route, `paired_extent`-gated. Golden four must not move |
| **DHAL-01 envelope** | **RECLASSIFIED** — not a layer-gate case | same 15.6 × 11.5 on both routes; treat as a **sheet type** (stilt parking) with DHAL-02 as control |
| **`scale_verified` has no minimum sample on the direct route** | OPEN | DHAL-01 reads `true` from 5 votes with an R-2 sample of **one room**. `SCALE_REFIT_MIN_SIDES = 8` guards the refit; nothing guards `room_dim_text`. The guard separates printed from guessed, not well- from barely-corroborated |

## `envelope_fragment` built; the railing defect does not exist (7 Sep 2026)

**Railings: eighth attribution, checked before building.** Every railing mesh on
every sheet that has one already measures **3.50 ft = 1.067 m** — Rahul's 21 Aug
half-height ruling — min 3.50, max 3.50, on all six sheets that build them. **No
3.05 m railing, no 32 ft `railing_1`.** The 20 Aug fix did generalise. **A build
here would have lowered correct geometry.**

**The pairing ratio is disqualified by measurement.** Paired share of all drawn
lines: **BRICK WORK 0.1%** (252 of 230,253) · **FLOOR PLAN 0.2%** (205 of
100,403) · **DHAL-01 1.1%** (51 of 4,781). **Our two most-trusted sheets pair a
smaller fraction than the sheet we want to refuse** — "admits thousands, pairs
almost none" describes FLOOR PLAN better than DHAL-01.

**B built on the right quantity: plan extent vs the DRAWN INK extent.**

| sheet | plan / ink |
|---|---|
| **DHAL-01** | **4.3% → REFUSED** |
| FLOOR PLAN · GHATIKIA · BRICK WORK | 41.8 · 42.0 · 47.7% |
| First Floor Plan · DHAL-02 · Typical FP | 55.4 · 55.8 · 64.2% |
| FIRST FLOOR · Typical FP (19.06) | 65.6 · 76.1% |

A **37-point empty band**, so the 20% floor clears the cluster rule by a wide
margin. The refusal names what was found and why nothing is offered.

**A first attempt failed and the reason is rule 4 in a new place.** Taking the
ink extent from `struct` read **100% on eight sheets of nine and separated
nothing** — `struct` is our own filtered, wing-cropped selection, so an extent
from it equals the plan by construction. **A quantity derived from the selection
cannot judge the selection.** The raw ink includes the title block and sheet
frame, which is exactly why it discriminates.

**DHAL-01 now refuses (`envelope_fragment` + `builtup_implausible`); no other
sheet changes and no parse number moves.** Four checks green; 2 new tests.

## C answered: a stilt has almost no walls (7 Sep 2026)

**The refusal is the correct permanent outcome for that sheet type. Nothing built.**

DHAL-01's **51 paired lines all sit in one 15.7 × 11.5 ft cluster** at
x 37.0–52.7, y 11.3–22.8 — and the sheet's own text puts **`STAIRCASE
8'-0"X14'-11"` at (42.5, 13.9)** and **`LIFT 5'-2"X5'-4"` at (49.3, 14.2)**
exactly there.

| what the sheet is | evidence |
|---|---|
| the parsed "building" is the **stair + lift core** | printed 8.0 + 5.17 ft side by side = 13.2 ft against our 15.6 ft including walls |
| the rest of the floor is parking | **`13'-0" WIDE DRIVE WAY`** label at (38–51, 30.4); bays bounded by painted lines, not walls |
| its ink is not walls | **`hatch floor` 2,247 · `RENDERED FURNITURES` 2,452 · `wall` 140 · `0` 171** |
| its real structure is invisible to us | **`_column_rects` returns 0 on BOTH DHAL sheets** — a stilt is a column grid, and we detect no columns |

**There is no wall enclosure to find, and no pairing fix would find one.** The
parse already found everything enclosed on the sheet and correctly declines to
call it a building. **A column-grid reader is a different pipeline, not a pairing
change** — recorded, not proposed.

**Two sessions, two errors, one cause: a bbox is not a dimension.** The
scorecard's railing Z measured the bounding box of a merged multi-segment mesh
(an L-shaped railing's box includes the diagonal); its chhajja and slab findings
fall the same way. On my side: the mesh-bbox railing "solid block" (1 Sep), the
bbox area sum that made 775 letter glyphs look like 530,262 pt² of poché
(5 Sep), and M-2's own outside-footprint share, which reads 33–67% for a slab
that *is* the footprint polygon. **The provenance rule now has three parts: a
number must name its RUN, a change must name its DIFF, and a dimension must name
whether it is a bbox or a shape.**

**And the lesson from `envelope_fragment` worth keeping:** my first attempt took
the ink extent from `struct` — our own filtered selection — and read **100% on
eight sheets of nine**. **A quantity derived from the selection cannot judge the
selection; the denominator must come from outside the thing being judged.**

## The ninth attribution, and the column reader (7 Sep 2026)

**The 3.05 m railing came from neither session.** Rahul wrote the number,
attributed it to the scorecard, and sent it as a fix to build. The scorecard
never reported it — its Z field read **zero violations on all nine sheets** and
refuted 3.05 m by measurement; its hardening since confirms **all 2,046 meshes
across all nine sheets carry at most 2 distinct Y levels**, so its height figures
were exact. My measurement found railings at **3.50 ft on every sheet that builds
them** — the 21 Aug ruling, already generalised. **The error was in the message,
not in either measurement**, and measuring before building is what stopped
correct geometry from being lowered.

**C stands: refusal is the correct permanent outcome for a stilt plan.** And one
new measurement strengthens it — **the column reader is 100% layer-name gated:**

| sheet | `_column_rects` candidates | column-ish layer |
|---|---|---|
| FLOOR PLAN · BRICK WORK · GHATIKIA | 3,352 · 38 · 80 | `COLUMN` / `column` |
| **FIRST FLOOR · both Patrapada · both DHAL · 19.06 · ganganagar** | **0** | **none** |

**Six of ten sheets detect no columns at all**, because no layer carries the
name. On a stilt that is decisive: **its columns ARE its structure, and its
drafter did not name a layer `column`** — so a stilt is invisible twice over,
once through walls it does not have and once through columns we cannot see.

Everything else in the C answer is unchanged: DHAL-01's 51 paired lines are the
stair-and-lift core (`STAIRCASE 8'-0"X14'-11"`, `LIFT 5'-2"X5'-4"` printed
exactly there), the rest of the floor is `13'-0" WIDE DRIVE WAY`, and its ink is
`hatch floor` 2,247 + `RENDERED FURNITURES` 2,452 against `wall` 140. **No
pairing fix would find enclosure that is not drawn.** DHAL-01 is already refused
on plan-vs-ink extent (4.3% against 41.8–76.1%), which is the right outcome.

**Recorded, not proposed:** a column-grid reader is a different pipeline, and
un-gating `_column_rects` from the layer name is its own change — the same shape
as the wall layer-name thread, and it should not be started inside this one.

## Column un-gate: attempted, stopped on the judged criterion (7 Sep 2026)

**Built as a probe, reverted.** Admit any box of aspect 0.6–1.6 and 8–48 in short
side carrying **two corner-to-corner diagonals**, from any layer, keeping the
layer route and the downstream dominant-size cluster.

| sheet | columns now | un-gated | verdict |
|---|---|---|---|
| **FLOOR PLAN** | **26** | **37** | **golden sheet moves → STOP** |
| GHATIKIA | 20 | 20 | unchanged — and it has **0 X-marked boxes**, so its columns are plain rectangles |
| FIRST FLOOR · Typical FP · First Floor Plan | 0 | **1 · 6 · 6** | small gains |
| DHAL-01 | 0 | 3 | and its footprint moves 94 → 79 |
| Typical FP (19.06) | 0 | **0** | no gain |

**The X is not the column signature — it is one drafter's column signature.**
GHATIKIA has 20 columns and none of them is X-marked; FLOOR PLAN's 11 false
positives come from `Text` and `Boundary Limit` layers, square glyph cells with
crossing strokes. **What C-2/C-4 also name and this probe did not use — repeating
on a 10–20 ft grid, and sitting on a wall junction — is the discriminator that
would reject a glyph.** That is the next attempt, not this one. Nothing shipped.

## Chhajja depth: tenth attribution — it is not built, so it cannot be unbounded

**No chhajja mesh exists on any sheet** (measured 5 Sep, re-confirmed); the word
appears only in three comments. **The 4.9 ft figure is real but belongs to the
UTILITY** — recorded 16 Aug as *"the 12.33 ft false positive IS THE UTILITY,
depth 4.91 ft against a printed 4'6""* — a 0.41 ft gap, **9%, already inside the
10% proportional tolerance** shipped the same day.

**And balcony depth is already printed-driven.** B-5 has matched a railing
pocket's depth against the sheet's printed balcony width since 14 Aug: FLOOR
PLAN's balcony reads **3.92 ft against a printed 4'-0"**. **The ASK path the
ruling asks for already exists for balcony, and there is no chhajja consumer to
attach one to.** Nothing built.

**Both items on the board unchanged:** the column reader is still layer-name
gated (six of ten sheets read 0), and chhajja is still unbuilt — a real gap, but
a *missing feature*, not an unbounded value.

# ==========================================================================
# STATE OF THE CORPUS — 7 Sep 2026, end of day. Read this first.
# ==========================================================================

**Read before any number:** `scale_verified` / `refusals[]` · `meta.route` ·
`meta.parse_pass` · `meta.plot_source` · `meta.source`.

## Parse + model, every sheet

| sheet | fp | rooms | cols | R-2 area | n | off | R-2 side | anc | M-1 | R-8 | carpet | outside% | wallVol | missing% | refusals |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BRICK WORK LAYOUT.pdf | 1247 | 13 | 15 | — | — | — | — | 70% | 1.13 | — | 581 | 6.2 | 0.911 | 33.3 | scale_unverified |
| FLOOR PLAN.pdf | 1797 | 16 | 26 | 98.0 | 8 | 0 | 97.4 | 79% | 1.06 | 96.5 | 1191 | 16.2 | 0.975 | 28.6 | — |
| NEELACHALA HOMES GHATIKI | 1738 | 13 | 20 | 83.6 | 12 | 2 | 91.2 | 69% | 1.07 | — | 1167 | 18.0 | 0.939 | 16.7 | — |
| neelachala FIRST FLOOR.p | 4472 | 19 | 0 | 96.9 | 16 | 7 | 91.8 | 60% | 1.09 | — | 3010 | 21.2 | 0.933 | 20.0 | — |
| BIJAYALAXMI DHAL-01.pdf | 94 | 1 | 0 | 73.9 | 1 | 1 | 85.7 | — | 1.08 | — | 0 | 48.9 | 0.788 | 40.0 | envelope_fragment,builtup_implausible |
| BIJAYALAXMI DHAL-02.pdf | 1192 | 11 | 0 | 96.7 | 11 | 1 | 97.7 | 100% | 1.12 | 40.4 | 388 | 57.3 | 0.778 | 40.0 | — |
| First Floor Plan.pdf | 1101 | 9 | 0 | 95.1 | 7 | 0 | 96.8 | 50% | 1.07 | 44.8 | 366 | 54.7 | 0.84 | 20.0 | — |
| Typical Floor Plan - (1s | 1436 | 10 | 0 | 99.0 | 10 | 4 | 99.2 | — | 1.08 | — | 926 | 3.6 | 0.98 | 0.0 | — |
| Typical Floor Plan.pdf | 1102 | 9 | 0 | 95.2 | 7 | 0 | 96.6 | 62% | 1.07 | 44.8 | 365 | 54.9 | 0.841 | 20.0 | — |
| ganganagar plan.pdf | — | | | | | | | | | | | | | | **no segments on wall/window layers - no** |

## OPEN — what closed today, what is newly open, next action

| item | state | next action |
|---|---|---|
| **projection depth** | **CLOSED today** — `meta.projection_depth` + doctor `ask`/`warn` | reported, never snapped (snapping would move carpet). The ASK is **defensive**: every projection on this corpus has a printed depth |
| **`_page_drawings` dropped `fill`** | **CLOSED today** — carried through | it made a whole build a silent no-op; check what a rebuilt dict drops before trusting a negative result |
| **column reader is layer-name gated** | **OPEN — two attempts, both reverted** | X route moved FLOOR PLAN 26→37 (glyph cells on `Text`/`Boundary Limit`); fill route moved it 26→**80** on 113 letter glyphs and cost Typical FP / First Floor Plan their envelope (fp 1101→785, rooms 9→4), with BRICK WORK and DHAL-02 raising. **Next: the discriminator neither used — repeating on a 10–20 ft grid, and sitting on a wall junction** |
| **columns on 6 of 10 sheets** | OPEN | FIRST FLOOR, both Patrapada, both DHAL, 19.06 read **0**; none has a column-ish layer |
| **wall layer-name gate** | OPEN — largest parse item | layer `0` carries **323 paired lines vs `wall`'s 179**. Not a route switch (that collapses FLOOR PLAN to 3 rooms) — signature admission on top of the layers route, `paired_extent`-gated |
| **room detection on Patrapada** | OPEN — root of R-8 44.8% | 19 printed dimensions read, 9 real rooms to attach them to |
| **no ceiling / no roof** | OPEN — M-2's biggest signal | built volume 19–63% of footprint × storey everywhere; deferred by ruling until the plan reading is verified |
| **meshes outside the footprint** | OPEN, partly artefact | M-2 tests a **bbox**, so a slab that *is* the footprint reads 33–67% "outside". Real part: furniture staged outside the ring on DHAL-02 / Patrapada |
| **chhajja** | OPEN — a missing feature, not a bad value | no chhajja mesh on any sheet; the `chhajja` layer (FIRST FLOOR 403 lines, GHATIKIA 19) reaches nothing |
| **ducts / railings build no mesh** | OPEN | ducts on FLOOR PLAN + BRICK WORK (2 each); railings on DHAL-01, DHAL-02, BRICK WORK |
| **`scale_verified` has no minimum sample on the direct route** | OPEN | DHAL-01 reads `true` from 5 votes with an R-2 sample of **one room** |
| **`_wall_thickness_ft` median-of-a-mix** | OPEN | bimodal 4/11 in returns 0.376 ft — neither wall. Five call sites |
| **`BORDER_MAXLEN_PT`** | OPEN | 88% on BRICK WORK. Do not fix yet (ruled) |
| **stilt sheet type** | **CLOSED — refusal is permanent** | DHAL-01 refused on plan-vs-ink (4.3% against 41.8–76.1%). A stilt is a column grid with one core; no pairing fix would find enclosure that is not drawn |
| **raster / ML input** | OPEN | CubiCasa repo + weights absent, TF absent. `ganganagar` is the first real case — a PDF with no vector linework |

**Eleven attribution errors are now recorded across both sessions.** The standing
defence is unchanged and it has worked every time: **measure before building.**
The rule has three parts — a number crossing sessions must name its RUN, a change
must name its DIFF, and a dimension must name whether it is a BBOX or a SHAPE.

## C-2 measured: neither signal separates — do not build (7 Sep 2026)

**Measured on CLUSTERED objects.** Raw candidates are useless: a column's hatch
strokes each share its bbox, so nearest-neighbour reads 0.0 for everything.

| set | objects | NN spacing (p50) | distance to wall face (p50) |
|---|---|---|---|
| **BRICK WORK columns** (known good) | 14 | **6.6 ft** | **0.3 ft** |
| **FLOOR PLAN columns** (known good) | 26 | **9.5 ft** | **0.4 ft** |
| **GHATIKIA columns** (known good) | 40 | **10.1 ft** | **10.0 ft** |
| FLOOR PLAN `other` — the 108 glyphs | 108 | **1.7 ft** | **10.8 ft** |
| the zero sheets' candidates | 7–163 | 3.6–8.7 ft | 0.8–27.9 ft |

**Neither signal survives all three known-good sheets.**
- **"Sits on a wall junction" fails on GHATIKIA** — its real columns sit a
  **median of 10 ft** from a wall face.
- **C-2's own 10–20 ft grid fails on BRICK WORK** — its real columns repeat at
  **6.6 ft**.

A NN floor near 5 ft would keep all three and reject FLOOR PLAN's glyphs — but it
is **fitted to our own three sheets** (rule 4), and it **gains nothing**: the zero
sheets' candidates sit at NN 3.6–4.7 ft and would be rejected too.

**And they should be — their pool is not columns.** Typical Floor Plan's 75
candidates are `wall` 22 · `furniture` 18 · `0` 17 · `rendered furnitures` 14,
only 6 of them filled; **FIRST FLOOR's 361 are 310 on layer `0` plus 50 DOOR
SYMBOLS.**

**Three routes now measured and rejected — X, fill, and C-2 grid+junction.** The
next attempt needs a signal none of them used, or **the honest answer is that
these sheets draw no columns at all**, the way a stilt draws no walls.

**And the finding worth keeping from the failed fill route:** `_page_drawings`
dropped `fill`, so the route saw `None` everywhere, changed nothing, and **read as
a clean pass on all four golden sheets**. An exception would have been found in
seconds. **An absence that looks like a negative result is worse than an error** —
a route that fires nowhere must be proved to have *fired* before its result is
believed.

Nothing built. Judged set unchanged: cols **15 / 26 / 20 / 0**, fp 1247 / 1797 /
1738 / 4472.

## T-2a junction gate: a real signal that still fails the criterion (7 Sep 2026)

**Measured, not built.** Distance from each clustered candidate to the nearest
wall junction — **my numbers, which are not the ones quoted to me**:

| set | n | dist to junction (p50) | within 1.0 ft |
|---|---|---|---|
| BRICK WORK columns (known good) | 14 | **0.76 ft** | 10 of 14 |
| FLOOR PLAN columns (known good) | 26 | **0.79 ft** | 17 of 26 |
| GHATIKIA columns (known good) | 40 | **10.47 ft** | 13 of 40 |
| **FLOOR PLAN's 108 glyphs** | 108 | **11.20 ft** | **3 of 108** |

**The signal is strong where it works** — a **97% rejection** of the glyphs that
defeated both earlier routes. **But it cannot gate the existing columns**: at
1.0 ft it passes only 17/26, 10/14 and 13/40, so gating the layer route breaks
all three golden sheets.

**And applied additively it still moves every one of them:**

| sheet | now | + junction candidates not already columns | would be |
|---|---|---|---|
| BRICK WORK | 15 | +3 | **18** |
| FLOOR PLAN | 26 | +2 | **28** |
| GHATIKIA | 20 | +2 | **22** |
| FIRST FLOOR | 0 | +36 | 36 |
| DHAL-02 · Typical FP · First Floor Plan · 19.06 · DHAL-01 | 0 | +8 · +1 · +1 · +2 · +1 | — |

**The criterion is EXACTLY, so A stops here. B and C are not started — both run
through A's gate.** Whether those 2–3 boxes are columns we currently *miss* is the
open question, and it is a question about the golden sheets' own truth, not about
the gate.

**Recorded for later from T-1, both real, neither started.**
1. **We ignore line weight almost entirely.** It is the primary signal in every
   drafting convention — heaviest = cut = structure. Nothing in the parser reads
   stroke width, which is why a letter and a column have been indistinguishable
   in three separate attempts.
2. **Chhajja is above the cut plane**, so it should be dashed or omitted, never
   built as cut material. T-1b generalises it: **a dashed line inside the
   envelope is something above the plane — neither a wall nor a room boundary.**

Nothing built. Judged set unchanged: cols **15 / 26 / 20 / 0**, fp 1247 / 1797 /
1738 / 4472.

## The junction dispute settled — and the extras identified (7 Sep 2026)

**My own 10.47 ft was the artefact.** It measured GHATIKIA's **40 raw COL-layer
candidates**, not the **20 detected columns**. On the detected columns:

| definition | FLOOR PLAN | BRICK WORK | GHATIKIA |
|---|---|---|---|
| **A** centre → **junction** | p50 **0.79** (max 12.79) | **0.76** (6.32) | **0.72** (5.14) |
| **B** centre → wall **endpoint** | 0.49 (max 9.21) | 0.32 (0.43) | 0.44 (0.73) |
| **C** **edge** → nearest **face** | **0.00** (max 0.00) | **0.00** (0.00) | **0.00** (0.11) |

**So neither offered reading of GHATIKIA is right: (b) is refuted — T-2a holds on
all three golden sheets — and (a) is not needed; its walls are not implicated.**
The junction test has **no walls-must-be-right dependency** on this evidence.

**The quoted "0.02 ft" is definition C, and C is not a junction test** — it
measures *is this box embedded in wall material*, which a column is by
construction. **C does not gate:** it passes **22 of FLOOR PLAN's 108 glyphs**,
and on the poché sheets nearly everything (43 of 45, 101 of 163), because wall
material covers most of the plan. A separates best; none is clean.

**The 2–3 extras are NOT missed columns. No re-baseline needed.**

| sheet | what they actually are |
|---|---|
| **FLOOR PLAN** (2) | **door swing arcs** on layer `all door` — 37.3 × 37.2 in and 26.6 × 26.6 in, **15 drawing items** each; an arc polyline whose bbox is square and inside C-4's band |
| **BRICK WORK** (3 of 8) | **hatch cells** on layer `hatch` — 8.1–12.0 in, **1 item** each |
| **GHATIKIA** (3) | a door arc (24.3 × 23.1 in on `door`), a wall stub (9.2 × 14.6 in on `wall`), one 11.4 in box on layer `0` |

**The gate admits arcs and hatch cells — a false-positive mode. 26 / 15 / 20
stand unchanged.**

**The next candidate signal falls straight out of the dump and needs nothing
new: ITEM COUNT.** FLOOR PLAN's real columns carry **41–44 hatch strokes**; a door
arc carries **15**; a hatch cell carries **1–4**. That is the discriminator none
of the four attempts used, and it is geometric, not a layer name.

**A, B and C all remain unbuilt.** Judged set unchanged: cols 15 / 26 / 20 / 0,
fp 1247 / 1797 / 1738 / 4472.

## Item count measured — it does not separate. A not built (7 Sep 2026)

**My own 41–44 was the wrong population, again.** Per drawing dict:

| set | items per box | strokes inside the box |
|---|---|---|
| **FLOOR PLAN columns** | p50 **3** (884 with 3, 574 with 2), max 5 | **333–337** |
| **BRICK WORK columns** | 1–5 | **2–9** |
| **GHATIKIA columns** | 1–2 | **2–5** |
| FLOOR PLAN's door arcs | **15** | — |
| FLOOR PLAN's 108 glyphs | 1–508 | 0–457 |
| BRICK WORK's `other` | 1–443 | 2–849 |

**Real columns carry 1–5 items and the false positives carry MORE** — FLOOR
PLAN's door arcs are 15 — so a "high item count" gate rejects every real column
and admits the arcs. The 41–44 came from the 16 Aug record and counts hatch
strokes **inside a column's area across all paths** — a different quantity.
**Measured that way it also fails: FLOOR PLAN's columns carry 333–337 strokes,
BRICK WORK's 2–9, GHATIKIA's 2–5.** No band holds across the three golden sheets,
because **FLOOR PLAN hatches its columns densely and the other two do not.**

**Five routes now measured and rejected: X-mark · fill · C-2 grid+junction ·
item count · stroke density.** B and C are not started — both gate behind A.

**Two things recorded as asked.**
1. **The "0.02 ft" was definition C, edge-to-nearest-face** — not a wrong number,
   a **right number to a different question**. C asks *is this box embedded in
   wall material*, which a column is by construction: 0.00 on 26/26, 14/14 and
   40/40, and it passes 22 of 108 glyphs. **A number crossing sessions must carry
   its DEFINITION, not only its run and its diff.**
2. **T-2a survived its first test against our corpus** — detected columns sit
   **0.79 / 0.76 / 0.72 ft** from a wall junction under definition A. The first
   time the theory section has been checked and held.

Nothing built. Judged set unchanged: cols **15 / 26 / 20 / 0**, fp 1247 / 1797 /
1738 / 4472.

## Line weight: a real signal, still not a gate — sixth rejection (7 Sep 2026)

**The PDF carries stroke width, and it ranks exactly as T-1a says.**

| sheet | distinct widths | columns | walls | the false positives |
|---|---|---|---|---|
| **FLOOR PLAN** | 8 (0.0–0.96) | **0.840** exactly | 0.840–0.960 | **glyphs 0.120** (7× lighter) · door arcs **0.000** · hatch 0.600 |
| **GHATIKIA** | 8 (0.0–1.44) | **1.440** exactly | 0.960–1.440 | doors 0.240 — cuts candidates **138 → 16** |
| **BRICK WORK** | **2 (0.0, 0.72)** | 0.720 | 0.720 | **0.720 — everything** |

**BRICK WORK is plotted at a single weight and cannot be read this way. That is a
sheet property, not a failure** — and it is the case that decides this.

**Combined with the junction gate:**

| sheet | now | weight + junction adds | would be |
|---|---|---|---|
| **FLOOR PLAN** | 26 | **0** | **26 ✓** (the weight kills both door arcs, width 0.000) |
| **BRICK WORK** | 15 | +8 | **23 ✗** (hatch cells carry the same 0.72 as its walls) |
| **GHATIKIA** | 20 | +1 | **21 ✗** |
| FIRST FLOOR · 19.06 | 0 | 0 | 0 |
| DHAL-02 · First Floor Plan · Typical FP · DHAL-01 | 0 | +5 · +2 · +1 · +1 | — |

**A filled column has no stroke weight, so `fill` must count as heaviest** — that
is how the poché sheets are handled above, and it holds.

**Six routes now measured and rejected: X-mark · fill · C-2 grid+junction · item
count · stroke density · line weight.** By the standing framing, the conclusion
follows: **stop looking for a property of the BOX. Columns need the GRID (T-2b) —
and the grid is drawn and currently discarded as plot boundary.**

**And the sixth number passed without its definition:** "41–44 hatch strokes" was
the 16 Aug record's count of strokes **inside a column's area across all paths**,
not items in a drawing dict. Both were measured, both fail, and the result
**inverts** the claim: real columns carry **1–5 items**, door arcs **15**. **A
number crossing sessions must carry its DEFINITION** — the third clause of the
provenance rule, beside the run and the diff.

Nothing built. Judged set unchanged: cols **15 / 26 / 20 / 0**, fp 1247 / 1797 /
1738 / 4472.

## No sheet carries a drawn structural grid (7 Sep 2026)

**A mechanical finding first: `get_drawings()` reports ZERO dashed paths on all
ten sheets.** PDF export flattens dash patterns into individual strokes — which
is why our own dash-dot detector works on stroke *geometry*, not the `dashes`
attribute. Detected geometrically there are 5–76 constant-pitch families per
sheet, but they are hatch rows, tile grids and dimension ticks.

**Applying T-2b's own test — a family CROSSING the plan and TERMINATING IN A
BUBBLE:**

| sheet | crossing families | ending at a circle | circle paths on the sheet |
|---|---|---|---|
| BRICK WORK | 10 | **0** | **1** |
| FLOOR PLAN | 3 | 1 | **358** (door arcs, glyph curves — coincidence) |
| GHATIKIA | 1 | **0** | 114 |
| **DHAL-01** (the stilt) | **0** | **0** | 141 |
| Typical FP · First Floor Plan | **0** | 0 | 455 / 457 |
| DHAL-02 | 8 | 8 | **859** — coincidence at that density |

**T-2b's premise is absent from this corpus.** These are architectural working
drawings for small residential buildings; **the structural grid lives on the
consultant's sheet, which we do not have.** Questions 3–5 are moot — there is no
drawn grid to test columns against. **That is the ceiling of this route, and it
is a corpus property, not a failure.**

**But the columns carry a lattice of their own — the salvageable half of T-2a.**
Clustering known column centres at 1.0 ft:

| sheet | columns | x-lines | y-lines | share an x-line | share a y-line | bay spacings |
|---|---|---|---|---|---|---|
| FLOOR PLAN | 26 | 11 | 8 | **25 / 26** | 23 / 26 | 8.9–13.9 ft |
| BRICK WORK | 15 | 4 | 8 | **15 / 15** | 11 / 15 | 8.8–12.2 ft |
| GHATIKIA | 20 | 7 | 10 | **19 / 20** | 17 / 20 | 6.7–11.0 ft |

**The grid is inferable from the columns even though it is not drawn**, and the
spacings are the structural bays T-2a predicts. **A candidate lying on a line
shared by two or more already-detected columns is the untried discriminator —
and unlike the six rejected ones it is a property of the SET, not of the box.**

**Its limit, stated plainly: it needs a seed of known columns, so it can only
extend a sheet that already reads some — which is exactly what the six zero
sheets do not have.** Measured, not built.

**And line weight is kept, not discarded:** it kills door arcs outright at width
0.000 and is T-1a's primary signal. It belongs in a combined reader; it cannot
gate alone, and **BRICK WORK at two distinct widths is the case that decides
that — a sheet property, not a failure.**

## Inferred lattice rejected; north from the compass shipped (7 Sep 2026)

**Seventh rejection.** A candidate on a line shared by two or more detected
columns: **FLOOR PLAN 26 → 45, BRICK WORK 15 → 28, GHATIKIA 20 → 26** — a column
*line* crosses the whole plan, so text, hatch, `boundary limit` and `ar-ic`
glyphs sit on it. **Adding both the junction gate and line weight narrows it but
does not close it:**

| sheet | now | lattice + junction + weight | verdict |
|---|---|---|---|
| **FLOOR PLAN** | 26 | **26** | ✓ holds exactly |
| **BRICK WORK** | 15 | **20** (5 hatch cells) | ✗ |
| **GHATIKIA** | 20 | **21** (1 `wall` box) | ✗ |
| the six zero sheets | 0 | **0** | adds nothing — it needs a seed |

**BRICK WORK defeats every combination because it is plotted at ONE line weight
and its hatch cells sit at junctions on column lines.** Not shipped. **Seven
routes now rejected: X-mark · fill · C-2 grid+junction · item count · stroke
density · line weight · inferred lattice.**

**T-2b's premise is absent from this corpus** — the rule is right and the *input*
is missing, which is not the same as a rule being wrong. **And for whoever
reaches for it next: PDF export flattens dash patterns into individual strokes,
so `get_drawings()` reports ZERO dashed paths on all ten sheets.**

## The Vastu north defect — fixed

`main.py` took `north_deg` as a query parameter **defaulting to 0.0** and passed
it straight to `vastu.analyze`, so **every Vastu analysis assumed north is up**
and a sheet printing a compass to the contrary was silently overruled. Now
`Query(None)`, defaulting to **`meta.north_arrow_deg`**; an explicit parameter
still wins.

**The reader was blind to the compass FORM** — it required a closed narrow spike,
and a rose is a **circle with an `N` beside its needle**. It now reads **93.8° on
`Typical Floor Plan - (1st,2nd,3rd)`**, the sheet that demonstrably prints one.

**A rim guard was necessary, and it is a ratio not a constant.** Four sheets place
an `N` at **0.16–0.26 radii** — at the rose *centre*, where the bearing is
meaningless — and returned 0.0, 1.1, **162.9 and 164.6°**, the last two **the same
drawing at two scales disagreeing by 1.7° on a quantity that must be identical**.
Requiring **0.4–1.6 radii** leaves exactly the one real compass.

**The field carries its own units and frame:** `"degrees clockwise, 0 = plan +y"`
and `"rotated page = scene/plan frame; page rotation already applied"` — **because
FLOOR PLAN parses at page rotation 270 and the two frames differ.**

Judged set unchanged: cols 15 / 26 / 20 / 0, fp 1247 / 1797 / 1738 / 4472; four
checks green; 1 new test.

## Chhajja built; column thread closed; Vastu north shipped (7-8 Sep 2026)

**Chhajja: 403 drawn items that produced no geometry at all.** The cause was
mundane — **the layer is spelled `chhaja`, one J**, it is correctly in
`GEOM_SKIP` so it never reaches the wall reader, and **nothing else ever consumed
it**. Not built wrong: not built.

A chhajja is drawn as a **hatched band**, not an outline — FIRST FLOOR's 403
strokes have a **median length of 0.40 ft** and group into bands whose bbox is
the sunshade. Built per **T-1 at lintel level** from the scene's own door head
(**7.0 ft**), **0.4 ft thick**, never at storey height, because a chhajja sits
**above the cut plane** and the plan states only its extent.

| sheet | bands | area | meshes |
|---|---|---|---|
| **neelachala FIRST FLOOR** | **25** | **45.2 sqft** | 25 at z 7.0–7.4 ft |
| **GHATIKIA** | **4** | 5.6 sqft | 4 (second view filtered at the consumer) |
| all others | 0 | — | — |

**No parse number moves on any sheet.**

## OPEN — the column thread is CLOSED

**Seven routes measured and rejected: X-mark · fill · C-2 grid+junction · item
count · stroke density · line weight · inferred lattice.** On this corpus
**columns cannot be found by any property we have been able to measure**, and
**BRICK WORK defeats every combination** — plotted at one line weight, with hatch
cells sitting at wall junctions on column lines, so weight, position and lattice
all pass them. **It reopens when a NEW INPUT arrives — a structural sheet, a DWG
with layers intact, or a drawing convention we have not met — not when another
filter is proposed.**

**Product defect closed: every Vastu analysis shipped to date assumed north is
up.** `main.py` defaulted `north_deg` to 0.0 and passed it to `vastu.analyze`, so
a sheet printing a compass was silently overruled. Two things about the fix are
the lesson:
1. **The reader was blind to the compass FORM, not to the compass** — it wanted a
   closed spike; a rose is a circle with an `N` beside the needle. Same class as
   the door symbol split across paths (19 Aug).
2. **The rim guard is a ratio, and the evidence for it is the reader
   contradicting itself:** four sheets returned 0.0, 1.1, **162.9 and 164.6°**
   from an `N` at 0.16–0.26 radii — the rose *centre* — and **the last two are the
   same drawing at two scales disagreeing by 1.7° on a quantity that must be
   identical.** A reader whose two readings of one drawing disagree has proved its
   own result invalid. Requiring 0.4–1.6 radii leaves the one real compass, at
   **93.8°**.

Four checks green; judged set unchanged: cols 15 / 26 / 20 / 0, fp 1247 / 1797 /
1738 / 4472, R-2 98.0/8 · 83.6/12 · 96.9/16.

## The chhaja spelling, the seg class, and the render runbook (8 Sep 2026)

**A spelling variant made a 403-item element invisible for the life of the
project.** The layer is **`chhaja` — one J** — and every search we ran, including
the T-1 theory work and the entire layer-name thread, spelled it `chhajja` or
`chajja`. It sat correctly in `GEOM_SKIP`, so it was properly excluded from the
wall reader and **nothing ever consumed it**. No instrument fired, because every
instrument we have compares **our own reading against our own reading**. **It took
a check that asks "the sheet has this — do we?"** — an *inventory* question rather
than a consistency question, and **that is a class of instrument we do not
otherwise have.**

**And the same week re-created a defect we fixed on 1 Sep:** the 25 new chhajja
meshes would have painted as `other` in `gbuffer.ts`. **`chhajja: '#b4a882'`
added.** The rule: **a mesh family and its seg class are one change, never two.**

## Render: `docs/RENDER-FIRST-RUN.md` — one page, runnable without reading code

**`docs/RENDER-TEST-PLAN.md` does not exist in this repo** (checked 8 Sep; the
render docs present are `RENDER-QA.md` and `DEPLOY-GPU.md`). The runbook is
written from the code instead.

| | |
|---|---|
| install | `pip install -r requirements-visualize.txt` → `python fetch_models.py` → check `models_status()` |
| weights | SDXL base ~7 GB · canny ControlNet ~2.5 GB · depth ControlNet ~2.5 GB = **~12 GB** (fp16 only). Seg ControlNet ~5 GB is optional — **skip it on run one** |
| run | `uvicorn main:app --port 8000` → `npm run dev` → upload FLOOR PLAN → stand inside a room → **Visualize** |
| first-run env | `RENDER_TIMEOUT_S=600`, `MAX_CONCURRENT_RENDER=1` |
| runtime | **~30–60 s per 1024² image** at 28 steps, plus a one-off 1–3 min while weights load into VRAM |
| judge | geometry lock → surface separation → artifacts. Ignore style on run one |

**The conditioning question, answered: not a blocker.** The renderer reads **no
scene field** — it takes uploaded PNGs — so a July renderer cannot be broken by
any parser schema change. **But the premise about the maps is stale:** railings
and door leaves have not segmented as `other` since **1 Sep**, and
`meta.glb.seg_unclassified_pct` reads **0.0% on all nine parseable sheets**. The
one real gap was **`chhajja`**, which we created ourselves on 7 Sep and fixed
today. **FLOOR PLAN carries no chhajja at all**, so its maps were already clean —
and the seg ControlNet is off by default on a first run, so the segmentation map
is not even consumed until the optional 5 GB model is cached.

`npm run test` 35 passed; `npm run build` clean.

## Terrace: already built. Lift: nothing to build from (15 Sep 2026)

**The terrace slab shipped on 1 Sep and is still there.** `terrace_0` on
neelachala FIRST FLOOR at **x 1.91–41.83, y 66.68–80.69 = 39.9 × 14.0 ft =
559.3 sqft**, z −0.25 → 0.0, built from
`regions[0].join_evidence.joined_bands_ft` — the band the two blocks were merged
across, recorded in feet at merge time so the 3D need not re-derive it. **The
chhajja shape does not repeat here: drawn, read for the band test, and built.**

**And the hatch covers the gap only — it does not wrap the lower block.** Length
is what settles it:

| 45° strokes | count | median | midpoint y |
|---|---|---|---|
| ≥ 10 ft | 29 | 16.2 ft | spread **−2.7 … 73.7** (door arcs and other hatch mixed in) |
| **≥ 20 ft** | **10** | **21.9 ft** | **72.5 … 73.7** — dead centre of the 66.68–80.69 band |

Their x extent of −8.4 … 41.7 is the **stroke** geometry, not the terrace: a 22 ft
stroke at 45° crossing a 14 ft band necessarily reaches ~14 ft beyond its own
midpoint in x. **The built slab already matches the band exactly, and footprint
stays 4472.1 — a terrace is not building footprint.** Nothing to build.

## The lift: zero detected on any sheet

| | lift | stairs | lobby |
|---|---|---|---|
| all nine parseable sheets | **0** | 0–2 | 2 sheets |

**"We detect lifts and build nothing distinct" is wrong in its first half — there
is nothing to build from.** The lift is being typed `stairs`, which is recorded
twice already: FLOOR PLAN's 21.4 sqft `stairs` room is **4.7 × 4.6 ft, aspect
1.03 — the lift, mistyped** (1 Sep); GHATIKIA's 57.1 sqft `stairs` room is **the
lift merged along its length with the staircase**, its one printed label reading
`LIFT 1.63x1.57` (2 Sep).

**L-6 needs a lift DETECTOR before it can have a builder**, and the discriminator
is already measured and unused: **a lift is a small isotropic shaft (aspect ≈ 1.0)
where a staircase is a long flight (aspect ≥ 1.6)**, and the sheet often prints
the word. That is a detection change, not the shaft-building change asked for —
recorded, not built.

Nothing built this turn. Judged set unchanged: fp 1247 / 1797 / 1738 / 4472,
cols 15 / 26 / 20 / 0.

## L-6 shipped: lifts 0 → 7 of 9, no parse number moved (15 Sep 2026)

**Lifts were not detected at all** — `furnish` folded `lift`/`elevator` into
`stairs`, so zero rooms typed `lift` on any of ten sheets. Two routes, label
first:

1. **`lift` is now its own type AHEAD of `stairs`** in `_ROOM_KEYWORDS`. The
   sheets print the word, and printed data wins (§0.1) — **5 of 7 are typed by
   the printed label.**
2. **The geometric fallback is the test `_stair_flight` already used** to refuse
   building steps in a lift — isotropic is a shaft, aspect ≥ 1.6 is a flight —
   moved into `stairs.is_lift` so parser and builder share one definition.

| sheet | lift | stairs | carpet | common | stair meshes |
|---|---|---|---|---|---|
| FLOOR PLAN | **1** (label) | 0 | 1191.1 | 28.7 | 0 |
| GHATIKIA | **1** (label) | 0 | 1167.4 | 57.1 | 0 |
| **FIRST FLOOR** | 0 | **2** (cores, correctly kept) | 3010.1 | 335.0 | 0 |
| DHAL-01 · DHAL-02 | 1 · 1 (label) | 0 | 0.0 · 387.9 | 20.4 · 201.1 | 0 |
| First Floor Plan · Typical FP | 1 · 1 (label) | 0 | 365.9 · 365.1 | 27.7 | 0 |
| Typical FP (19.06) | **2** (1 label, 1 geometric) | 0 | 925.7 | 122.3 | **20** |
| BRICK WORK | 0 | 0 | 581.3 | 81.6 | 0 |

**`lift` was added to `COMMON_TYPES` in the same change — which is why carpet,
common and footprint are identical to the decimal on all nine parseable sheets**,
and why the 20 stair meshes on the 19.06 sheet survive (the builder reads
`stair_ladders`, not room type).

**A size bound was not optional, and the first build proved it:** aspect alone
typed FIRST FLOOR's **166.9 and 168.1 sqft stair CORES** as lifts, because a core
is roughly square. **`LIFT_MAX_SQFT = 67.3`** (NBC residential shaft ≈ 2.5 × 2.5 m
= 6.25 m²), quoted not fitted — our own lifts measure **20.4–57.1 sqft**. The
label route is deliberately unbounded: if the sheet prints LIFT, the sheet wins.

**GHATIKIA separately, as asked.** Its lift is typed **only by the printed
label**. The room is the lift merged with the staircase along its length —
**4.85 × 11.71 ft, aspect 2.41** — so `is_lift` correctly reads it as a flight
and refuses. Its 57.1 sqft is the merged pair, not the shaft (printed 5.35 × 5.15
= 27.5). **Aspect cannot see inside a merge; the merge must be split first** —
the same open item as the FIRST FLOOR blobs.

**L-4 (build the shaft — walls, no floor) NOT started**, per "one variable after
the typing lands". The typing landed this turn.

Four checks green; judged set unchanged: fp 1247 / 1797 / 1738 / 4472, cols
15 / 26 / 20 / 0. 2 new tests.

## One bedroom traced end to end — the enclosure is NOT the failure (15 Sep 2026)

**Room:** `BEDROOM` + `10'-2"X12'-0"` at (6.72, 21.87) on Typical Floor Plan.

| edge | extent | wall material built |
|---|---|---|
| south | y 18.38–18.85, x 0.94–13.29 | **100.0%** |
| north | y 30.34–31.29, x 1.70–13.29 | **99.9%** |
| east | x 14.50–14.97, y 22.52–30.34 | **100.0%** |
| **west** | x 0.0–0.94, y 18.85–30.34 | **66.9%** |
| interior at (7.5, 24.5) | — | **free**, and **no room polygon exists there** |

**All four walls are built, the interior is free, and the single open run is one
gap of 3.75 ft at y 22.65–26.40** — a window in the external wall, and **0.25 ft
INSIDE the 4.0 ft seal**, so the seal should close it and the room should form.

**So the cause is downstream of enclosure.** That is a different defect from every
room failure recorded so far — C.TOILET was the seal *filling* a 3.9 ft room; the
lobby was a region found and then *discarded* at the border. Here the region is
not found at all.

**And the west wall over this room is a single unpaired line**, which is the
likeliest reason the gap does not seal. Over y 18.85–30.34 the only vertical is
**x = 0.00 on layer `0`, a 32.22 ft line** — there is **no partner at x 0.94
anywhere in that span** (the `plan` line at x 0.94 runs y 31.29–40.33; the `wall`
line at x 0.94 runs y 41.27–47.13 — both north of the room). The horizontal walls
stop at x 0.94, so the inner face is *implied but never drawn*.

**W-1/W-3 needs a pair.** An unpaired line survives only inside the paired extent
and is then painted at the sheet's **median** wall — which here is the bimodal
**0.376 ft**, not the 0.94 ft the drawing implies. **That is the median-of-a-mix
open item arriving in a third place.**

Measured, nothing proposed. Judged set unchanged.

## The implied face: real, and it names each sheet's own wall (15 Sep 2026)

**Method:** for each unpaired long line, the offsets at which perpendicular runs
**terminate** against it, accepting only an offset that **at least two
perpendiculars agree on** (±0.08 ft).

| sheet | consistent implied faces | dominant offsets | that sheet's measured wall |
|---|---|---|---|
| **Typical FP** | 25 of 84 unpaired | **0.47 ×6 · 0.95/0.94 ×6** | 5.6 in / 11.3 in |
| First Floor Plan | 23 | **0.94 ×7 · 0.47/0.48 ×5** | same drawing |
| DHAL-02 | 22 | **0.44 ×8** | 0.43 |
| GHATIKIA | 36 | **0.38 ×11 · 0.33 ×4** | 0.334 |
| BRICK WORK | 9 | **0.25 ×4** | 0.25 |
| FLOOR PLAN | 15 | **0.83 ×2** | 0.834 |

**The dominant cluster on every sheet is that sheet's own measured wall. The face
is on the drawing — drawn by the walls that meet it, not by its own line.** The
prediction holds.

**But it is not the 168-into-168 conversion, and the reason is a second cluster.**
Only **25 of 84** unpaired lines on Typical FP get a consistent face; the rest
have no agreeing perpendicular at all. And **five of six sheets show a second
cluster at 1.25–1.45 ft**, roughly 3× the internal wall (Typical FP 1.34 ×6,
First Floor Plan 1.34 ×6, DHAL-02 1.25/1.26 ×6, BRICK WORK 1.35/1.45, GHATIKIA
1.45 ×2). **Those are perpendiculars terminating at the FAR face of a wall
beyond** — admitting them would paint a 1.34 ft wall where none exists.

**FLOOR PLAN would gain 15 candidates and it is a golden sheet**, so nothing can
ship until the offset is constrained to a **measured wall mode** of that sheet —
**which is the median-of-a-mix item again, now as a filter rather than a
thickness.** The two threads are the same thread.

Reported, nothing proposed, nothing built. Judged set unchanged.

## `wall_modes` built — and the judged condition is unsatisfiable (27 Sep 2026)

**Every sheet in the corpus is multi-modal.** The ruling assumed some sheets are
unimodal, so a median→mode swap would be a no-op there. It is not:

| sheet | median | modes | classes (in × count) | heaviest |
|---|---|---|---|---|
| BRICK WORK | 0.250 | 2 | 2.13×101 · 6.53×57 | 0.177 ✗ |
| **FLOOR PLAN** | **0.834** | 3 | **5.0×24** · 12.0×23 · **10.0×18** | **0.417 ✗** |
| GHATIKIA | 0.334 | 5 | 3.86×256 · 9.0×86 · 11.0×30 | 0.322 ≈ |
| FIRST FLOOR | 0.421 | 6 | 4.42×156 · 10.0×114 · 2.0×50 | 0.369 ✗ |
| Typical FP | 0.376 | 2 | 4.05×284 · 11.0×135 | 0.338 ✗ |
| DHAL-02 · First Floor Plan · 19.06 · DHAL-01 | — | 3·2·3·3 | — | ✗ except 19.06 |

**No sheet is unimodal, and the heaviest mode is not the wall** — partitions
outnumber external walls, so FLOOR PLAN's dominant class is **5.0 in** while its
real wall (and its median) is **10 in**. The dominant mode differs from the
median on **7 of 9**.

**So "replace the median with the mode" has no safe form.** `wall_modes` is
**emitted and not consumed**; `_wall_thickness_ft` is untouched and **no number
moves anywhere**. Derivation: the same 1-inch histogram as `gap_peaks_in`, with
**adjacent bins merged** — a 4 in wall drawn at 4.2 and 4.6 in is one wall.

**But the FILTER job does not need a single thickness, and that is the way
through.** Deciding which implied offsets are admissible needs only *does this
offset match any of the sheet's classes* — an offset at a mode is a face, an
offset at ~3× a mode is a wall beyond. **That job is unblocked today; the
thickness job is not, and may never be, because the drawing does not state which
class an unpaired line belongs to.**

**The two jobs looked like one and are not** — the same shape as the seal
(17 Aug) and `min_flank` (31 Aug): one number asked to do two jobs, separable
only by admitting that one of them has no answer.

**Also recorded:** the implied face is the **first time theory predicted a
measurable property of the drawing and the corpus confirmed it on all six
sheets**.

**Next single variable: implied-face admission, gated on `wall_modes`.** Four
checks green; judged set unchanged — fp 1247 / 1797 / 1738 / 4472, rooms
13/16/13/19, cols 15/26/20/0. 2 new tests.

## Implied faces: safe, and blocked upstream (28 Sep 2026)

**Built.** `implied_partners` synthesises the missing partner at an offset that
**≥2 perpendicular terminations agree on**, admitted **only within 20% of one of
that sheet's own `wall_modes`**.

| sheet | implied faces | fp | rooms | carpet | R-2 |
|---|---|---|---|---|---|
| **FLOOR PLAN** | 1 | **1796.8** | 16 | 1191.1 | 98.0 / 8 |
| **BRICK WORK** | 1 | **1247.1** | 13 | 581.3 | — |
| **GHATIKIA** | 0 | **1738.4** | 13 | 1167.4 | 83.6 / 12 |
| **FIRST FLOOR** | 0 | **4472.1** | 19 | 3010.1 | 96.9 / 16 |
| Typical Floor Plan | 1 | 1101.7 → **1117.8** | 9 | 365.1 | 95.2 / 7 |
| First Floor Plan · DHAL-02 · 19.06 · DHAL-01 | 1 · 0 · 0 · 0 | unchanged | — | — | — |

**The four golden sheets are byte-identical** — the unfiltered version would have
given FLOOR PLAN **15 false candidates**, and the class gate keeps every one out.
That was the test, and it passes.

**But the yield is 1 face per sheet, against the 25 consistent faces I measured
on Typical FP — and the reason is decisive.** `implied_partners` runs on
`struct`, and on a layers-route sheet **`struct` holds only wall-LAYER lines**.
The 84 unpaired lines carrying those 25 faces are on **layer `0`**, which never
enters `struct` at all. **The implied face is downstream of the layer-name gate
and cannot fix the three sheets while that gate excludes the very lines whose
faces are implied.**

**The thickness an unpaired line is painted at is still the MEDIAN** — said
plainly, because the mode work implies otherwise. `_wall_thickness_ft` is
untouched, and per the eighth-constant finding that job may have no answer at
all: no sheet is unimodal and the heaviest mode is not the wall.

**And the silent-no-op repeated within three weeks.** The first build placed the
synthesis beside `struct`, where `ppf` does not yet exist — it raised NameError
inside its own `except` and did nothing on all nine sheets, **while every judged
number stayed identical, which reads exactly like a clean pass.** Same shape as
`_page_drawings` dropping `fill`. **`meta.implied_faces` now emits the count**, so
the route must prove it fired.

**Next, and it is now the only thing standing between us and the three sheets:
admit layer-`0` lines that carry the wall signature.** Four checks green; 1 new
test.

## Implied faces: rejection counted, gains still blocked upstream (30 Oct 2026)

**The work was already built on 28 Sep (now committed in `f088a9a`); this turn
added the one thing the gate report needed — the off-class rejection count.**
`implied_partners` returns `(faces, rejected)`: an offset ≥2 perpendiculars agree
on but which matches **no** wall class is the far face of a wall *beyond*, and it
is **counted, not dropped silently**.

| sheet | implied admitted | rejected at ~3× | fp | carpet | R-8 | plan/ink |
|---|---|---|---|---|---|---|
| **BRICK WORK** | 1 | **2** | **1247.1** | 581.3 | — | 47.7% |
| **FLOOR PLAN** | 1 | 0 | **1796.8** | 1191.1 | **96.5** | 41.8% |
| **GHATIKIA** | 0 | 0 | **1738.4** | 1167.4 | — | 42.0% |
| **FIRST FLOOR** | 0 | 0 | **4472.1** | 3010.1 | — | 65.6% |
| Typical Floor Plan | 1 | **2** | 1101.7 → **1117.8** | 365.1 | 44.8 → **45.4** | 64.2% |
| First Floor Plan | 1 | **2** | 1101.1 | 365.9 | 44.8 | 55.4% |
| DHAL-02 · 19.06 · DHAL-01 | 0 | 0 | unchanged | — | 40.4 | — |

**The golden four are byte-identical** — and unfiltered, FLOOR PLAN would have
taken **15 false candidates**. The class gate is doing exactly its job.

**But the expected gains do not arrive, and the cause is upstream and measured.**
`implied_partners` runs on `struct`, and on a **layers-route** sheet `struct`
holds only wall-LAYER lines: **524 segments reach the reader against 838 long
lines on the sheet, 378 of them on layer `0`.** The traced bedroom proves it
exactly — its west wall is a **32.22 ft line at x = 0.00 on layer `0`** — so the
reader never sees the very line whose face is implied, and the room at
(7.5, 24.5) is **still not found**.

**The thickness an unpaired line is painted at is still the MEDIAN.** Said
plainly: `_wall_thickness_ft` is untouched. Per the eighth-constant finding that
job may have no answer — no sheet is unimodal, and the heaviest mode is not the
wall (FLOOR PLAN's dominant class is 5 in against a real wall of 10 in).

**Verified end to end:** GLB still builds on both a moved and a golden sheet
(Typical FP 379 meshes / 455.7 KB, FLOOR PLAN 140 / 142.0 KB), `wall_volume_ratio`
0.841 / 0.975, `seg_unclassified_pct` 0.0%. Four checks green.
