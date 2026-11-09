# Drishti daily log — 7 to 8 Sep 2026

Moved verbatim out of CLAUDE.md on 10 Nov 2026 to keep the build-loaded
file short. Nothing below is summarised or reworded.

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

