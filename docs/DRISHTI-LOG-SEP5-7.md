# Drishti daily log — 5 to 7 Sep 2026

Moved verbatim out of CLAUDE.md on 10 Nov 2026 to keep the build-loaded
file short. Nothing below is summarised or reworded.

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

