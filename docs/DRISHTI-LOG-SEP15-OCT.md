# Drishti daily log — 15 Sep to 30 Oct 2026

Moved verbatim out of CLAUDE.md on 10 Nov 2026 to keep the build-loaded
file short. Nothing below is summarised or reworded.

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
