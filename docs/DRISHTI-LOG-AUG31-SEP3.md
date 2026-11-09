# Drishti daily log — 31 Aug to 3 Sep 2026

Moved verbatim out of CLAUDE.md on 10 Nov 2026 to keep the build-loaded
file short. Nothing below is summarised or reworded.

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

