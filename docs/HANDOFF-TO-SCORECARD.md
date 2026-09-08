# Handoff: parser session -> scorecard session

Append-only. One line per change that moves a number, written BEFORE the
scorecard measures it, so the prediction is on record first.

Format: date | change | sheets I expect to move | what I predict your
instruments show.

---

2026-08-31 | **No coordination files existed when I started.** `runs/`,
`runs/sweeps/CHECK-PENDING.md` and `docs/HANDOFF-TO-PARSER.md` are all absent in
this worktree (`~/3D-React-Viewer`, branch `fix/z-fighting`), so I had no
pre-registered checks to honour and no measurements of yours to use. If you have
written them in `~/3D-React-Viewer-score`, they have not reached this tree.

2026-08-31 | **`meta.threshold_margins` is emitted** (shipped 31 Aug, before this
task). One definition, computed in the parser, for you to consume rather than
re-derive — two derivations of one number is the `wing_at`/`wing_pick` trap.
Carries `gap_peaks_in`, `wall_in`, and per threshold `value_in`,
`nearest_peak_in`, `distance_in`, `pairs_within_5pct`, `kind`
(`selecting`|`sizing`) and `latent_cliff`, plus a `latent_cliffs` roll-up.
A **sizing** threshold on its own peak is NOT a cliff — a median lands on its own
dominant peak by definition. Corpus read: BRICK WORK `[W3_min, geom_min,
min_flank]` · FLOOR PLAN `[face_tol, min_flank]` · GHATIKIA `[face_tol,
min_flank, geom_max]` · FIRST FLOOR `[min_flank]`. **No parse number moved.**

2026-08-31 | **`meta.route.wing_pick` carries `origin_ft` and `bbox_ft`** (shipped
28 Aug). Index is not identity: GHATIKIA builds its RIGHT view at ppf 7.1485 and
7.150 while `chosen` stays 0. Use the ORIGIN, not the index, to say which half
was built. **No parse number moved.**

2026-08-31 | PREDICTION, before building | **Wing-filtering `_seg_px`.**
`_footprint_from_walls` is handed `_seg_px`, built from ALL of `struct` with no
wing filter, so on a multi-wing sheet the outer ring bridges to segments in the
DISCARDED view. Visible in the overlay: GHATIKIA's `footprint_ext` runs
diagonally across the gutter and a door is drawn on a column in the other view.
Measured: GHATIKIA footprint spans x 0.0..53.7 while its built wing ends at
x 43.7 — **10 ft of footprint in a view we did not build**; 1 opening and 1
balcony room (20.0 sqft) sit there too.
**I predict:** GHATIKIA footprint FALLS from 1997.0 (the gutter reach is
removed); the stray opening and the 20.0 sqft balcony disappear; `footprint_ext`
stops crossing the gutter. **FLOOR PLAN, FIRST FLOOR and BRICK WORK do not move
at all** — all three are single-wing, where `wbox_ft is None` makes the filter a
no-op. If any of those three moves, the filter is wrong and I will revert it.

2026-08-31 | SHIPPED | **Wing-filtered `_seg_px`.** Prediction above HELD
exactly. GHATIKIA footprint **1997.0 -> 1738.4 (-12.9%)** and its footprint now
stops at x **44.1** instead of 53.7 — the ten feet in the other view are gone,
and 258.6 sqft is almost exactly that strip (9.6 ft x ~27 ft). The stray opening
and the `footprint_ext` diagonal across the gutter are both gone. **anchors held
at 69%**, R-2 83.5 -> **83.6** at n=12. **FLOOR PLAN 1796.8, FIRST FLOOR 4472.1,
BRICK WORK 1247.1 — all unchanged to the decimal, as predicted.**

2026-08-31 | PREDICTION, before building | **Wing-filtering the RAILING tracer.**
Same root cause, second consumer: `railings.trace` is fed lines from the WHOLE
sheet, so on GHATIKIA it traces the right view's mirrored runs too — the pockets
come in mirrored pairs at dx ~53.3 ft ([4.43, 27.52 ...] and [57.72, 27.52 ...]).
One of them is classified `railing` and becomes a **20.0 sqft balcony room at
x 57.7-60.8, inside the DISCARDED view**.
**I predict:** GHATIKIA loses exactly that room — rooms 14 -> 13 — and its
balcony area falls by about 20 sqft. Footprint, R-2 and anchors should NOT move,
because the room sits outside the footprint and carries no printed dimension.
**FLOOR PLAN, FIRST FLOOR and BRICK WORK unchanged** (single wing, filter is a
no-op). If a judged sheet moves, I revert.

2026-08-31 | SHIPPED | **Wing-filtered the BALCONY builder** (the pocket
consumer at `_rail_runs_raw`, which is traced BEFORE the wing split because it
sizes the canvas). Prediction HELD exactly: GHATIKIA rooms **14 -> 13**, balcony
**39.6 -> 19.6** (-20.0, the stray to the decimal), stray-view rooms **1 -> 0**.
Footprint 1738.4, R-2 83.6 at n=12, anchors 69% — all unchanged. FLOOR PLAN,
FIRST FLOOR, BRICK WORK unchanged to the decimal.

2026-08-31 | SHIPPED, additive | **`doors_placed_sound.both_jambs`.** The width
rule scores a cut against its drawn leaf and the leafless rule against a drawn
gap; NEITHER asks whether the opening has wall on BOTH SIDES. New count:
FLOOR PLAN **15 of 16** · BRICK WORK **15 of 15** · GHATIKIA **13 of 18** ·
FIRST FLOOR **31 of 54, while its `sound` reads 42 of 54**. Reported, NOT folded
into `sound` — that needs a ruling, and 1-of-16 on the only sheet that can judge
placement is too thin to validate a fix against. **No parse number moved.**

2026-08-31 | NOTE for your door checks | a door sits IN a wall gap by
construction, so "is there wall under the cut" is the WRONG test and will report
every gap opening as broken. Test for **wall on both flanking sides**. Two of my
own audit heuristics were wrong this way before I caught them (the other flagged
every DUCT as a room overlapping wall — a duct is a wall-ringed void, so it
overlaps wall by design).

2026-08-31 | PREDICTION, before building | **Unsnapped doors become
`door_unverified`** (Rahul's ruling: a door we could not place against a wall is
a wrong number presented as fact). They stay in `scene.openings` — visible and
countable — but leave the door COUNT and the 3D build. Both the leaf
(`scene_to_glb` keys on `type == "door"`) and the WALL CUT (`poly_bands` cuts for
any opening with a footprint, regardless of type) must go.
Unsnapped today: **FLOOR PLAN 0 of 16 · BRICK WORK 0 of 17 · GHATIKIA 10 of 18 ·
FIRST FLOOR 26 of 54.**
**I predict:** FLOOR PLAN and BRICK WORK door counts DO NOT MOVE (16 and 17) —
neither has an unsnapped door, so the judged door ratchet (>=16) and
`doors_placed_sound` 16/16 on FLOOR PLAN are untouched. GHATIKIA falls to **8**
doors and FIRST FLOOR to **28**. Footprint, R-2, anchors and M-1 should not move
on any sheet: an unverified door was never load-bearing for area. If a judged
number moves I revert.

2026-08-31 | SHIPPED | **Unsnapped doors are now `door_unverified`.** Prediction
HELD: FLOOR PLAN 16 and BRICK WORK 17 unchanged (neither had an unsnapped door),
**GHATIKIA 18 -> 8**, **FIRST FLOOR 54 -> 28**. Footprint, R-2, anchors and M-1
unchanged on all four. They stay in `scene.openings`, flagged `unverified`, and
build nothing in 3D — `scene_to_glb` drops them before `poly_bands`, so they cut
no wall either. `doors_placed_sound` now reports on placed doors only:
FLOOR PLAN 16/16, BRICK WORK 15/15, GHATIKIA 5/8, FIRST FLOOR 18/28.

2026-08-31 | SHIPPED, emission only | **`meta.regions` enumerates every plan
region** (§13): `extent_ft`, `size_ft`, `mask_area_px`, `built`,
`title_text_near`, and `join_evidence.basis`. BRICK WORK 1 · FLOOR PLAN 1 ·
**GHATIKIA 2** ("FLOOR PLAN" built, "TYPICAL FLOOR PLAN" not) · FIRST FLOOR 1
(merged, basis "drawn material covers the band"). **No number moved.**
NOTE for your fingerprint: `_wing_groups` runs TWICE on a sheet that scale-refits
(GHATIKIA), and the scene comes from the SECOND pass — at ppf 8.80 its two views
need the empty-band split, at 7.189 they are already apart at the 8 ft proximity
stage. If you compare region bases across runs, compare the built pass.

2026-08-31 | SHIPPED, additive | **`meta.parse_pass` + per-region `pass`/`ppf`.**
`parse` re-enters itself once for the scale refit and THE TWO PASSES BUILD
DIFFERENT DRAWINGS. On GHATIKIA every field except the column count differs:
origin x **43.5 (RIGHT view) on pass 1 vs -0.2 (LEFT) on pass 2**, rooms 7/13,
doors 20/8, windows 19/14, footprint 1099.0/1738.4, M-1 1.15/1.07, R-2 60.7 at
n=7 / 83.6 at n=12, carpet 659.3/1167.4, anchors 56%/69%, **measured wall 6.22 in
/ 4.01 in**, and the latent-cliff list. Columns hold at 20.
**Read `meta.parse_pass = {index, ppf, from_scale_refit}` before diffing that
sheet** — a value without its pass is ambiguous and a mixed diff compares two
parses. Corpus: BRICK WORK / FLOOR PLAN / FIRST FLOOR pass 1; GHATIKIA pass 2.
**No number moved.**

2026-08-31 | SHIPPED | **Regions keyed by ORIGIN, never index** — adopted exactly
as you specified. `meta.regions[*].key` is `r@{x},{y}`: GHATIKIA is `r@0,0`
(built) and `r@53,0`. Pin against the key, not the index.

2026-08-31 | SHIPPED | **R-8 goes BLIND on a multi-region sheet.** If a printed
area statement is read where more than one region exists, the per-floor figures
(built_up, carpet, common, stilt, flats) are DROPPED with an ASK — never attached
to the built region and never to the larger. The PLOT survives: a site area is
not per-region. **Unexercised by this corpus** — the only sheet with a printed
statement (FLOOR PLAN) has one region — so treat it as unproven on real data.

2026-08-31 | SHIPPED | **Unsnapped doors are `door_unverified`** (reported
earlier). The split is the ROUTE: geometry-route sheets had GHATIKIA 10/18 and
FIRST FLOOR 26/54 unverified; layers-route sheets had 0/16 and 0/17. If you track
door counts, a geometry-route count before today was a count of door TAGS.

2026-08-31 | SHIPPED, additive | **`meta.parse_passes` to your spec.**
`{count, built_pass, by_pass[...], pass_ppf[...]}`. `by_pass` is a tuple over
ALL passes INCLUDING the discarded one — each with `pass`, `ppf`, `route`,
`regions` and `wing_origin_ft` — because a change to a discarded pass can change
which pass is discarded. **`pass_ppf` is row data: do not hash it.** It is
continuous, so hashing would make every scale change read as a route change.
Single-pass sheets emit the SAME SHAPE with `count: 1`, so you never have to tell
"one pass" from "field missing". Corpus: BRICK WORK / FLOOR PLAN / FIRST FLOOR
count 1; GHATIKIA count 2, `pass_ppf [8.8, 7.189]`, built_pass 2.
**No number moved.**

2026-08-31 | WARNING on the origin-key rule we both adopted | **the origin key is
itself PASS-DEPENDENT.** GHATIKIA keys `r@0,0` + `r@44,0` on pass 1 and
`r@0,0` + `r@53,0` on pass 2 — the key is in FEET and feet move with ppf, so
`r@44,0` and `r@53,0` are the SAME PHYSICAL REGION under two scales. Keying by
origin survives enumeration REORDERING, which is what it was adopted for, but it
does NOT survive a scale change. **Pin within a pass, or key on something
scale-free.** The `built` flag flips too: pass 1 builds the RIGHT view, pass 2
the LEFT.

2026-08-31 | MEASURED | **The re-parse trigger.** Two halves: `|median - 1| >
stdev` is DERIVED and dimensionless (both sides measured from the sheet);
`min_sides = 8` is a FIXED COUNT — the eleventh constant. Margin of the derived
half, reported as `threshold_margins` would: observed S/N **0.03, 0.12, 1.74**,
trigger at **1.0**, nearest observation 1.74, **distance 0.74**, inside a 14x
empty gap. **Safe by the cluster rule** — but the distribution is three points
and there is nothing within 0.74 of the trigger, so it is unexercised near its
own value. Sample counts against `min_sides`: 0 / 14 / 16 / 32.

2026-08-31 | PREDICTION, before building | **Region separation moves off the 8 ft
proximity threshold onto the zero-ink band test.** Today two groups stay separate
if their bboxes are more than `gap_ft = 8` FEET apart — a distance that moves
with ppf, which is why GHATIKIA separates for a different reason on each pass
(zero-ink band at 8.80, proximity at 7.189). Ink is ink at any scale; feet are
not. New rule: two groups remain separate ONLY if the band between them carries
NO ink; otherwise they merge. Proximity is demoted to what it was for — grouping
connected components of one drawing.
**I predict:** GHATIKIA still enumerates **2** regions, but the basis becomes the
zero-ink band on BOTH passes. **FIRST FLOOR stays ONE region** — its terrace
hatch puts ink in the band, so the test says joined; if it splits, the 22 Aug
ruling has been silently reversed and I stop. FLOOR PLAN and BRICK WORK stay
single-region. No judged number should move on any sheet.

2026-08-31 | SHIPPED | **The separator is the ink, not a distance.** Prediction
HELD: GHATIKIA still 2 regions, FIRST FLOOR still 1, FLOOR PLAN and BRICK WORK
single, and **no judged number moved** (fp 1247.1 / 1796.8 / 1738.4 / 4472.1;
anchors 70/79/69/60%; R-2 98.0 n=8, 83.6 n=12, 96.9 n=16; M-1 1.13/1.06/1.07/
1.09). **The point of the change: GHATIKIA now reports basis 'separate: a band
with NO INK between them' on BOTH passes (ppf 8.80 and 7.189)** — before, pass 1
said zero-ink band and pass 2 said proximity, so the region basis was
scale-dependent and your cross-pass diffs on that sheet were comparing two
different separation rules. `join_evidence.separated_by` now carries
`{empty_band_pairs, ink_in_band_pairs}` if you want the counts.

2026-09-01 | DELIVERABLE, no code change | **3D defect sheet** in
`overlays/defect-sheet/` (19 images + INDEX.md) for Rahul's review. **No parser
file was touched and no number moved** — suite 521, batch_eval 4/4.
Four findings you may want instruments for, all from the model rather than the
2D: (1) the **floor slab is the wall bounding box, not the footprint** — +66% /
+58% / +47% / +21% by sheet, and it floors the gap between FIRST FLOOR's blocks;
(2) **two of FLOOR PLAN's six railing meshes are the whole pocket extruded to
3.50 ft** (54.2 sqft over a 51.0 sqft balcony, 38.8 over a 37.0 utility) while
the other four and both of FIRST FLOOR's are correct 0.25 ft rails; (3) **no
staircase mesh exists on any sheet** though four rooms are typed `stairs`;
(4) **no roof or ceiling mesh on any sheet**. Heights are right: wall 9.84 ft,
door head 7.00 ft, railing 3.50 ft.
NOTE if you ever measure the GLB: **it is metric and Y-up.** I read metres as
feet on my first pass and rendered a "top-down" as an elevation on my second.

2026-09-01 | ORIENTATION ANCHOR CHAIN, per Rahul's ruling, for your check.
Chain: north arrow -> staircase/lobby -> corner rooms/balconies -> n/a.
**No sheet in this corpus prints a north arrow**, so every entry falls to the
second link or lower - worth knowing before you build the check.
Expected bearing is `north = +plan_y` in the parsed frame on all three sheets
that have an anchor. FLOOR PLAN: lift+stair core at x 27-41 ft on the east half
of a 95.2 x 29.8 ft plate, plate runs east-west. FIRST FLOOR: two stair cores at
(12.8, 37.9) and (12.8, 133.9), both west, building runs north-south 42.0 x
177.7 ft. GHATIKIA: STAIRCASE + LIFT at the TOP-CENTRE of the built left region
- **the most useful anchor in the corpus, since that is the sheet where a
180-degree error was caught**. BRICK WORK: **n/a** - no arrow, no staircase
room, no titles; record as unknown rather than assume. Full detail in
ground_truth.json -> orientation_anchor_chain_2026_09_01.

2026-09-01 | SHIPPED, three of six | **Staircase as actual steps** (GHATIKIA only
- 17 risers of 6.9 in; FLOOR PLAN's `stairs` room is the LIFT and FIRST FLOOR's
are merged stair CORES, so both build nothing and say why on
`meta.stairs_built`). **Terrace slab** over a joined band (`join_evidence
.joined_bands_ft`) - FIRST FLOOR only, x 1.91-41.83 y 66.68-80.69.
**gbuffer segClass** now classes door / railing / stair / terrace / duct instead
of dropping them into `other`. **No judged number moved:** fp 1247.1 / 1796.8 /
1738.4 / 4472.1, anchors 70/79/69/60%, R-2 98.0 n=8, 83.6 n=12, 96.9 n=16.

## Orientation, 1 Sep 2026 — one delivered, one CONTRADICTED

**1. `meta.north_arrow_deg` is emitted.** Signature: a closed narrow spike
(3–6 vertices, aspect measured **along its own axis**, never its bounding box —
a 45° arrow has a near-square box), clear of the plan, **with a lone `N`**.
Bearing runs base → apex, **clockwise from sheet-up**; 0 means the sheet is
already north-up. `meta.north_arrow` carries `{deg, why, live_words, rung}`.

**It reads `None` on all four sheets, and my prediction is that it will keep
reading None until a fifth sheet arrives.**

| sheet | deg | live words | why |
|---|---|---|---|
| FLOOR PLAN | **None** | 24 | 1 spike candidate, **no `N`** |
| BRICK WORK | None | **0** | 0 candidates — and no live text at all, so "no `N`" is an extraction limit here |
| GHATIKIA | None | 231 | 0 candidates |
| FIRST FLOOR | None | 359 | 0 candidates |

**2. CONTRADICTION — your request says FLOOR PLAN prints a north arrow. Measured
here, it does not.** 24 live words, none `N`/`NORTH`; 6413 drawing paths, 775
filled; the single isolated spike outside the plan is a **5.0 ft sliver of the
ARCHITRAVE logo at (74.3, −10.7)**. Without the `N` requirement the reader
returned a confident **81.8°** for it — which is exactly why the `N` is
required. Per the coordination rule I am stopping and reporting both rather than
overriding you. **If you have located an arrow, send its page coordinates and I
will read it.**

**3. Bearing + chirality are recorded** in `ground_truth.json` →
`orientation_bearing_chirality_2026_09_01`. **Every bearing is UNRULED**, with
the rung reached: rung 1 is absent corpus-wide, and rung 2 (a staircase or lobby
position) fixes which **edge** a core sits on, not a bearing in degrees.
**Chirality is settled on three of four** — as drawn, not mirrored: FLOOR PLAN
on the C.TOILET/A.TOILET landmark, BRICK WORK and GHATIKIA on overlay
registration. FIRST FLOOR is convention only and says so.

**Also new and useful to you: `meta.stair_ladders`** — the drawn tread ladders
in scene feet (box, tread count, drawn pitch, axis climbed), wing-filtered.
GHATIKIA 1 · FIRST FLOOR 4 · FLOOR PLAN 0 · BRICK WORK 0. It locates the
staircase from the drawing rather than from a room type, which is what rung 2
should anchor on.

## The centroid list — basis dispute, 2 Sep 2026

Per your test and mine. **Measured = the bbox of `polygon_ft`, so both sides
measure the same quantity.** If your centroids differ from these, we are scoring
different rooms and the basis question has not been asked yet.

Note before reading: **`_wall_thickness_ft` returns 0.376 / 0.385 ft on these
sheets from a BIMODAL 4 in / 11 in mix** (105-124 pairs at 4 in, 135-139 at 11 in)
— the median-of-a-mix problem, live at five call sites. And **30 of 39 rooms on
each sheet are `duct`**: 0.93-0.95 ft strips at the 11 in peak, i.e. wall
cavities. They carry NO printed dimension, so they are absent from both lists
below — but they are **81% of the common-area figure** (117.5 of 145.2 sqft).

**Typical Floor Plan.pdf** — every room carrying a printed dimension (parse pass 2, ppf 11.806, `cad_units`)

| type | centroid x,y ft | printed | measured (bbox of polygon_ft) | deficit per dim |
|---|---|---|---|---|
| kitchen | **36.24, 34.29** | 7.50 × 8.00 | 7.80 × 8.43 | -0.30 / -0.43 |
| kitchen | **23.92, 72.58** | 7.00 × 8.33 | 7.25 × 8.51 | -0.25 / -0.17 |
| bathroom | **32.50, 55.22** | 4.67 × 7.25 | 4.87 × 7.33 | -0.21 / -0.08 |
| bathroom | **36.33, 18.60** | 4.50 × 7.50 | 4.79 × 7.62 | -0.29 / -0.12 |
| bathroom | **13.84, 3.49** | 4.50 × 7.00 | 4.20 × 7.01 | +0.30 / -0.01 |
| bathroom | **37.21, 49.30** | 5.00 × 6.17 | 4.70 × 6.21 | +0.30 / -0.04 |
| stairs | **3.85, 44.17** | 5.17 × 5.33 | 5.25 × 5.30 | -0.08 / +0.03 |

**First Floor Plan.pdf** — every room carrying a printed dimension (parse pass 2, ppf 10.295, `cad_units`)

| type | centroid x,y ft | printed | measured (bbox of polygon_ft) | deficit per dim |
|---|---|---|---|---|
| kitchen | **36.24, 34.29** | 7.50 × 8.00 | 7.80 × 8.41 | -0.30 / -0.41 |
| kitchen | **23.92, 72.58** | 7.00 × 8.33 | 7.29 × 8.49 | -0.29 / -0.15 |
| bathroom | **32.49, 55.22** | 4.67 × 7.25 | 4.89 × 7.37 | -0.23 / -0.12 |
| bathroom | **36.33, 18.59** | 4.50 × 7.50 | 4.79 × 7.62 | -0.29 / -0.12 |
| bathroom | **13.84, 3.46** | 4.50 × 7.00 | 4.24 × 7.01 | +0.26 / -0.01 |
| bathroom | **37.21, 49.31** | 5.00 × 6.17 | 4.70 × 6.21 | +0.30 / -0.04 |
| stairs | **3.85, 44.18** | 5.17 × 5.33 | 5.25 × 5.30 | -0.08 / +0.03 |

**Your error found and accepted:** 0.83 ft was DHAL-01's wall read from another
row; and per-dimension vs per-face halves 0.7-0.9 to 0.35-0.45, which is our
0.39. **The magnitude was never in dispute — only the sign is.**

**Our sign:** we read LARGER than printed on 10 of 14 dimensions. Our room
polygons are FREE SPACE in the sealed raster, so the dilate/erode pair leaks
into the wall band — a 0.2-0.4 ft over-read. **If your `measured` comes from the
drawn wall FACES rather than the raster, that is a different quantity and would
carry the opposite sign.** That is the one thing left to compare.

## Chhajja height convention — for HEIGHT_RULES (8 Sep 2026)

New element, shipped 7–8 Sep. It was **403 drawn items producing zero meshes**
until now: the layer is spelled **`chhaja`, one J**, correctly in `GEOM_SKIP` so
it never reaches the wall reader, and nothing else ever consumed it.

| field | value |
|---|---|
| mesh name | `chhajja_{i}` |
| **thickness** | **0.4 ft** (0.122 m) |
| **elevation** | **lintel — the scene's own door head**, i.e. `max(opening.z[1])` over doors; **7.0 ft fallback** when a sheet has no doors |
| built z-range | **7.0 → 7.4 ft** on both sheets that carry one |
| convention (T-1) | a chhajja sits **ABOVE the 4 ft cut plane**, so the plan states only its **extent**. It is **thin**, sits **well below the storey** (9.843 ft), and **projects beyond the wall** — it is never cut material and must never be storey height |
| where it appears | **neelachala FIRST FLOOR 25 bands / 45.2 sqft · GHATIKIA 4 bands / 5.6 sqft** · zero on the other eight |
| derivation | a chhajja is drawn as a **hatched band**, not an outline: FIRST FLOOR's 403 strokes have a median length of 0.40 ft and group into bands whose bbox is the sunshade |

**Also fixed on our side so your seg audit is not affected:** `src/three/gbuffer.ts`
gains a **`chhajja`** class (`#b4a882`). Without it the 25 new meshes would have
painted as `other`.

**And a correction to the premise in the request:** railings and door leaves have
**not** segmented as `other` since **1 Sep** — `door`, `railing`, `stair` and
`terrace` classes were added then, and `seg_unclassified_pct` reads **0.0% on all
nine parseable sheets** in `meta.glb`. The only class that was missing is the one
above, which we created ourselves this week.
