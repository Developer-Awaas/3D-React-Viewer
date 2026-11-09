# Drishti daily log — 4 to 5 Sep 2026

Moved verbatim out of CLAUDE.md on 10 Nov 2026 to keep the build-loaded
file short. Nothing below is summarised or reworded.

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

