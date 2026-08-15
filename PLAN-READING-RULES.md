# PLAN READING RULES — v1

**Status:** working specification. Rahul dictates the ground reality; Claude writes it here; Claude Code builds against THIS file, not against chat paraphrase.
**Scope:** Indian residential floor plans (CAD PDF, DWG, scan).
**Date:** 10 Aug 2026 · Source drawings: Neelachala / Architrave sheets.

---

## 0. The governing principle

**Read what is drawn with certainty. Ask about what is not. Never guess.**

Every rule below carries a certainty mark:

| Mark | Meaning | Parser behaviour |
|---|---|---|
| **CERTAIN** | The drawing states it unambiguously | Use it. No prompt. |
| **ASK** | The drawing is silent or ambiguous | Use a stated default, flag it, offer the user a correction |
| **ELEVATION** | Cannot be known from a floor plan at all | Flag it; offer elevation upload |
| **CONTRADICTS** | The drawing states something a building cannot be — a DRAFTING ERROR, not a parsing gap | **FLAG and ASK.** Show the user what was read and why it is implausible. **NEVER auto-correct** (deferred until 3D generation is reliable) |

A number the tool cannot justify must never be presented as fact.

**CONTRADICTS — worked example (14 Aug 2026, confirmed by Rahul).** FLOOR PLAN's
lobby reads as a **15.7 ft opening in an external wall on a FIRST FLOOR plan**,
on a floor with no street entrance. In reality that is a wall with a window;
the thin line drawn across the opening is a drafting error. **No reading rule
can reach that truth, because the drawing is wrong.** Catching a drafting error
before site is the tool's highest-value moment for a builder — treat this as a
FEATURE, not an edge case.

---

## 0.1 VERIFICATION FIRST

**Where a sheet carries its own AREA STATEMENT, opening schedule, or printed
room dimensions, those are ground truth. Any parser output that contradicts
them is wrong until proven otherwise.**

This check runs **BEFORE** any diagnosis of a suspected parser error. Read the
sheet's own numbers first, compare, and only then reason about what the code
did. A correction proposed without this check is a guess, however plausible
its arithmetic.

**Re-baselining a golden number.** A golden number may be re-baselined **ONLY
when the drawing's own printed data disproves it**, and only with the evidence
and the superseded value recorded in `plans/ground_truth.json`. A golden may
**NEVER** be changed to make new code pass. The old number stays visible in the
file: a corrected observation is part of the record, not a deletion.

**A gap can never be longer than the wall it is a hole in.** When closing the
outer wall ring, a bridge may not exceed the material length of the collinear
wall RUN it sits in. Reject longer spans and log them. The bound is relative to
the wall, not a guessed constant, and not the building's shorter side — on a
95×30 ft strip the balcony faces run along the LENGTH, so a 42 ft opening can
be legitimate while a 96 ft one is the sheet. (Corrected 11 Aug 2026; the
shorter-side version was wrong for exactly that reason.) Where the flanking
walls are shorter than the gap, the space beyond is not a room behind an
opening — it is a balcony or open side, and §10 governs it, not ring bridging.

**UNITS — decide per sheet, never mix.** Indian sheets use feet-inches and
metres, sometimes across one project (GHATIKIA prints `3.43x4.04` in metres;
neelachala FIRST FLOOR prints `13'6" X 10'3"`). Decide by how the number is
written and by plausibility, never by assumption: feet carry `'` and `"`; a
bare decimal under ~7 is almost always metres. A residential room is 2.4–6.0 m
or 8–20 ft. Cross-check the result against the measured scale and require
consistency across the sheet — where the two disagree by more than 2x, our
READING is wrong (the sheet is still ground truth), so keep the previous scale
and flag for review rather than ship an impossible building. One sheet, one
unit: minority-unit readings are misreads and get dropped.

**The building can never be bigger than its land.** Where the plot area is
known — printed on the sheet, or from verified plot dimension text — a computed
footprint above it is a physical impossibility, not a tolerance question. It
**FAILS**; it does not warn. Where the sheet states no plot, the check is
skipped: an unknown plot is not evidence of anything. (This is the check that
disqualified the fixed-kernel footprint: at a 14 ft seal, neelachala FIRST
FLOOR computed 2,563 sqft of building on a 2,455 sqft plot.)

**A quantity derived from the difference between two intermediate masks is
NOT a measurement of the thing it is named after.** Drishti's balcony line is
computed as `foot_ext MINUS foot` — the gap between two internal footprint
masks — so it does not measure balconies at all; it measures how much those two
masks happen to disagree. One eligibility change to the wall ring took it from
42.7 sqft to 0.0 while no balcony on the drawing changed. Any such quantity is
hostage to every upstream change and cannot be ratcheted, because a genuine
improvement upstream destroys it. **Balcony must eventually come from what is
DRAWN** — reading the open edge itself per B-1/B-4 — not from a mask
subtraction. The same test applies to any future figure: name the drawn thing
it measures, or it is not a measurement.

`plans/ground_truth.json` is mode **444 (read-only) on purpose** — the guard
that makes an edit to it a deliberate act rather than an accident. Unlock it
only for an authorised re-baseline, and **restore 444 immediately afterwards**.

**Worked example — FLOOR PLAN.pdf (10 Aug 2026).** The sheet states its own
built-up area: **870 + 835 = 1705 sqft**. The parser reports **1693.3 sqft** —
a **99.3% match**, so the scale on this sheet is right. That single comparison
disproved a proposed scale correction (derived from median door width reading
3.81 ft) which would have shrunk every dimension by ~27% and made the built-up
number **38% wrong**. The sheet's own statement caught in one line what a chain
of geometric inference got backwards.

---

## 1. What is NOT the building

Before anything else, these must be excluded from geometry, area and 3D.

| Element | How it looks | Rule | Certainty |
|---|---|---|---|
| Plot boundary | Very thick **dash-dot** line enclosing everything | Ignore entirely. Not a wall. Not the envelope. | CERTAIN |
| Setback line | Thin line (often red/coloured) inside the plot boundary | Ignore. Marks the buildable limit, not the building. | CERTAIN |
| Dimension lines | Thin lines with arrowheads/ticks at both ends, carrying a number, sitting OUTSIDE the building | Ignore as geometry. **Read the number** — it is a scale anchor. | CERTAIN |
| Leader lines | Thin line from a tag circle to the element it names | Ignore as geometry. Use only to link tag → element. | CERTAIN |
| Grid/centre lines | Long thin dashed lines crossing the whole sheet | Ignore. | CERTAIN |
| Diagonal hatch outside the building | Repeating parallel diagonal strokes over open ground | Not building. Marks open terrace/open space. | ASK — full rule deferred, see §11 |
| Title block, legends, tables, north mark, signatures | Text boxes and tables, usually a corner or edge band | Ignore entirely as geometry. | CERTAIN |

**BOUNDARY HIERARCHY (ruling, 14 Aug 2026).**
1. **Plot boundary** = the **OUTERMOST** line. Usually dash-dot black, but *outermost* is the reliable test and dash-dot only the usual form. Measured signature on FLOOR PLAN: **11 collinear strokes of 6.3–6.7 ft at a constant 3.1 ft gap** — a repeating dash pattern. A railing, by contrast, is a **single unbroken stroke** per line. That gap structure separates them where length and position both failed.
2. **Setback** = an inward OFFSET of the plot boundary — 2 / 3 / 4.5 / 6 m depending on building height.
3. **Building edges** sit inside the setback, though real drawings show projections crossing it.

**Consequence:** the building envelope is the outermost extent of WALLS, never the plot boundary.

---

## 2. Walls

**Signature:** two parallel lines with a gap between them. The gap IS the wall thickness — measure it, never assume it.

| Type | Gap | Rule | Certainty |
|---|---|---|---|
| External wall | wide (**10 inches** in the reference sheets) | Load-bearing envelope | CERTAIN |
| Internal partition | narrow (**5 inches** in the reference sheets) | Room divider | CERTAIN |

**Rules:**

1. **W-1** — A wall is a pair of parallel lines. A single line is not a wall.
2. **W-2** — Measure the gap. Do not hardcode 10"/5". Different projects use 9"/4.5". Cluster the measured gaps on the sheet: the wide cluster = external, the narrow cluster = internal.
3. **W-3** — Sanity band: any measured gap below 3 inches or above 18 inches is not a wall. Reject it.
4. **W-4** — Walls form closed loops around rooms. A gap in the loop is an opening (door/window/arch), not a broken wall.
5. **W-5** — Wall lines may be interrupted by columns, doors and windows. Continuity across those interruptions must be inferred, not required.
6. **W-6** — Wall height is NOT on the floor plan. Default **3.0 m (9.843 ft)** floor-to-floor, which is what the code already uses (`pdf_vector.WALL_HEIGHT_FT`, `scene_builder.WALL_HEIGHT_FT`). The user may override it by entry, or by uploading an elevation. `ASK`

---

## 3. Columns

**Signature varies per sheet.** Some sheets draw columns solid black filled; others as a box with an X across the corners. Within a single sheet the convention is consistent.

**Rules, applied in this order:**

1. **C-1 — Establish the sheet's column signature first.** Find the smallest marker shape that (a) repeats many times and (b) sits on or at wall lines. That shape is this sheet's column. Do not assume a global convention.
2. **C-2 — Columns repeat on a grid.** Regular spacing, typically 10–20 ft, many instances. Something that appears once or twice is not a column.
3. **C-3 — Columns sit on wall lines** — embedded in walls, at wall junctions, at building corners.
4. **C-4 — Size sanity band.**
   - Below **8 inches** → not a column (drawing artefact)
   - Above **48 inches (4 ft)** → not a column in residential
   - Reference bands (Indian RCC residential):
     - IS 456 absolute minimum: 200 mm (8")
     - Practical site minimum: 230 mm (9")
     - Seismic zone III/IV/V (Bhubaneswar = III): min 300 mm (12") shorter side above G+1
     - G+5/6: ~380 × 450 mm (15"×18")
     - G+7: ~450 × 450 mm (18"×18")
     - G+10 to G+25: 600–900 mm, up to ~1200 mm (48") in tall towers
5. **C-5 — Aspect ratio.** Columns are rarely longer than 1:3. A long thin slot is not a column.
6. **C-6 — Columns are a scale anchor, but a weak one.** The existing "column = 12 inches" assumption is unsafe: 9-inch column plans come out ~33% wrong. Only use column width for scale when no dimension text exists, and always flag it.
   - **The 12-inch assumption applies to the column's SHORT side, never the long side.** A column is a rectangle (see C-5): its short side is the dimension the reference bands in C-4 constrain, and the one that stays near the practical minimum across storey counts. The long side varies freely and anchors nothing.
   - **CODE FIX PENDING** — `pdf_vector._scale_ppf` pins `max(r.width, r.height)`, i.e. the LONG side. That is wrong. It must use the short side. On a near-square column the error is small; on a 9"×15" column it scales the whole building by 1.6x.

---

## 4. Ducts and shafts

**Signature:** often the same marker as columns (box with X), but distinguished by size, position and repetition.

| Test | Duct | Column |
|---|---|---|
| Repetition | appears once or twice | repeats on a grid |
| Position | beside a toilet, behind the lift, along a corridor, at a flat boundary | on wall junctions, on the structural grid |
| Size | 4–15 sqft of floor area (≈2'×2' to 3'×5') | see C-4 |
| Purpose | plumbing and electrical risers | structure |

**Rules:**

1. **D-1** — Same marker + not on the grid + adjacent to toilet/kitchen/lift/corridor → duct.
2. **D-2** — Size alone CANNOT separate duct from column. The bands overlap (a 25-storey column can be 4 ft; a duct can be 2 ft). Position and grid-repetition decide.
3. **D-3** — A duct is a void. It is enclosed, has no door on the flat side, and is not habitable space.
4. **D-4** — Ducts count in built-up area but never in carpet area.

---

## 5. Lift

**Signature:** a large box, usually with an X across it, with **LIFT** written inside or beside it.

1. **L-1** — Text label is the primary signal. If "LIFT" is written, it is a lift.
2. **L-2** — Position: in the lobby / common area, adjacent or near to the staircase.
3. **L-3** — Size: too large to be a column. Reference sizes seen: 5'×5', 1.63×1.57 m.
4. **L-4** — A lift is an enclosed shaft. It must be built as an enclosed volume in 3D, not left open.
5. **L-5** — Lift is common area. Not carpet. Counts in the building's common area (see §9).

---

## 6. Staircase

**Signature:** a box containing many closely-spaced parallel lines (the treads), usually split by a partition separating the up-flight from the down-flight, with an **UP** arrow.

1. **S-1** — Many parallel lines + UP arrow → staircase.
2. **S-2** — The horizontal/central partition separating two flights is common but NOT always present. A single-flight staircase has no partition.
3. **S-3** — **Position is decisive.** A staircase is in common area — lobby, corridor, stair-hall. Never inside a bedroom or a flat's private room.
4. **S-4** — The tread lines must not be read as walls. They are floor markings.
5. **S-5** — Staircase is common area. Not carpet.

---

## 7. Cupboard / wardrobe

**Signature:** closely-spaced parallel lines, similar to a staircase at first glance.

1. **CB-1** — Inside a private room (bedroom especially), against a wall, no UP arrow, no flight partition → cupboard.
2. **CB-2** — **Position decides.** A cupboard cannot be in a common area; a staircase can. This is the primary separator from a staircase.
3. **CB-3** — A cupboard is furniture, not structure. It must not be read as a wall.
4. **CB-4** — Cupboard footprint stays inside carpet area (it does not subtract).

---

## 8. Openings

### 8.1 Doors

**Signature:** a **gap in the wall** plus a **quarter-circle arc**.

1. **DR-1** — The gap in the wall IS the door opening. Its width is the door width — measure it.
2. **DR-2** — One straight edge of the quarter circle is the hinge side, sitting in the wall gap. The other straight edge is the door leaf when open.
3. **DR-3** — The arc tells you the **swing direction** and **which room it opens into**.
4. **DR-4** — Tagged D, D1, D2, D3, SD with a circle. Typical Indian residential:
   - D1 main entrance **3'6"**
   - D2 bedrooms and kitchen ~3'0"
   - D3 bathrooms and balconies ~2'6"
   - SD sliding door ~7'0"
   - **CODE FIX PENDING** — `tag_openings.DOOR_W_FT["D1"]` is 3.25 (3'3"). It must be 3.5. Where a sheet carries its own door schedule, that schedule overrides this table (TG-5, and §0.1).
5. **DR-5 — Footprint validation.** An "opening" wider than 6 ft or thicker than 1.6 ft is not a door — it is merged wall geometry. Demote it.
6. **DR-6 — 3D representation:** show the leaf **open at the swing angle** for now. (Interim decision; to be revisited.)
7. **DR-7** — Door height is not on the floor plan. Default 7'0" (matches every reference schedule). `ASK`

### 8.2 Windows

**Signature:** within the wall's two thick lines, the wall is interrupted and **2 thin parallel lines** run along the wall. Nested inside the wall thickness.

1. **WN-1** — Window = 2 thin lines nested inside the 2 thick wall lines. (3-line variants exist in some conventions; not yet seen in the reference set — add when encountered.)
2. **WN-2** — The window's length along the wall IS its width. Measure it.
3. **WN-3** — Tagged W, W1, W2, W3 with a circle. This is the SINGLE window table; there is no second one. Typical Indian residential:

   | Tag | Width × height | Sill |
   |---|---|---|
   | W1 main living areas | ~5'0" × 4'0" | **3'0"** |
   | W2 standard bedrooms | ~4'0" × 4'0" | **3'0"** |
   | W3 kitchen/utility | ~3'0" × 3'0" | **3'6"** (above counter datum) |

   - **CODE FIX PENDING** — the code holds TWO conflicting tables: `pdf_vector.LEGEND` (sills 3'0" / 3'0" / 3'6") and `tag_openings.WIN_FT` (sill 2'6" for all three). Which one fires depends on the detection path, so the same tag can produce two different sills. Both must be reconciled to the table above, ideally by deleting one and sharing the other.
4. **WN-4 — Windows are NOT always drawn.** Some sheets (e.g. FLOOR PLAN.pdf) omit them entirely. When absent: **do not invent them.** Report "windows not marked on this drawing" and offer user entry or an elevation. Currently the tool guesses — this must stop. `ASK`
5. **WN-5** — Window height and sill are not on the floor plan. Use the tag defaults above and flag them. `ELEVATION`

### 8.3 Ventilators

**Signature:** drawn like a window, but small.

1. **V-1** — Tagged V or V1.
2. **V-2** — If untagged and the opening is small AND sits in a **toilet** wall → ventilator, not a window. Toilet-context knowledge is required; size alone is insufficient.
3. **V-3** — Typical size ~2'0" × 2'0" (varies), sill high, around 5'0". Never as large as a window.
4. **V-4** — In 3D, place at high level, not at window sill level.

### 8.4 Tag linking

1. **TG-1 — Read the geometry first, then link the tag.** Do not depend on tags to find an element. Tags are labels on what the drawing already shows.
2. **TG-2** — A tag circle may sit outside the wall with a dashed leader pointing at the element. The tag is often NOT on the element.
3. **TG-3** — Link each tag to the nearest matching element along the leader / along that wall.
4. **TG-4** — If two openings sit close together, there will be two tags. Match count to count; if they do not match, flag rather than guess.
5. **TG-5** — Letter + number: **D** = door, **W** = window, **V** = ventilator. The number is a size variant defined in the sheet's opening schedule when one exists — **read that schedule first** if present; it overrides all defaults above.
   - **BUILT** (11 Aug 2026) — `server/opening_schedule.py`, verified on BRICK WORK LAYOUT.pdf ("SCHEDULE OF DOOR & WINDOW", 8 rows, read via OCR). Its W is 6'0" × 4'6" sill 2'6", where our default said 4'0" sill 3'0" — the sheet now wins. No schedule on the sheet ⇒ the defaults above still apply.
   - A row that cannot be read WHOLE is dropped, never half-read: width and height are taken positionally from either side of the `X`, so an unreadable width can never be filled by the height.

---

## 9. Rooms and areas

1. **R-1** — A room is a closed loop of walls. Doorway gaps must be bridged to close it, or the room leaks and disappears.
2. **R-2** — Room name and dimensions are printed inside the room in most sheets ("bed room 11'-5" X 12'-6""). Read them. They are also a scale anchor.
3. **R-3** — Balconies are rooms with one open side. They must still be closed as spaces.
4. **R-4** — Carpet = sum of enclosed room areas inside the flat.
5. **R-5** — Common area (lift, staircase, lobby) is NOT carpet. It is counted separately, per floor, and shown separately.
6. **R-6** — Built-up = carpet + wall material + the flat's share of ducts.
7. **R-7** — Super built-up = carpet × loading factor. Loading applies to CARPET, not built-up.
8. **R-8** — Where a sheet carries its own AREA STATEMENT table, **read it and compare**. A mismatch between parsed and printed areas is the single strongest accuracy signal available. Report both.

---

## 10. Balconies

1. **B-1** — A balcony is enclosed on 3 sides and open on 1 (the outer face).
2. **B-2** — The open face has either a **railing/grill** or a **parapet wall 3–4 ft high**. The floor plan usually cannot tell you which. `ELEVATION` / `ASK`
   - **RULING (14 Aug 2026).** Railings in these buildings are **2–3 in steel**. The 1.9 in vs 3.0 in difference measured on FLOOR PLAN's two balconies is **sloppy drafting, not different construction** — both are railings.
   - **Resolution path: USER ENTRY.** The tool ASKS which the open face is (railing or parapet, and its height) before building it in 3D, alongside the elevation upload of §11. It must never decide silently.
   - **POSITION IS NOT PART OF THE RULE (ruling, 14 Aug 2026).** A balcony is not always on the outer edge — it can face an internal open space. The measured data agrees independently: the position gate REJECTS flat-1's genuine railing (x −4..−2, outside the trusted wall extent) and PASSES 12 of 14 plot-boundary strokes. Wrong in both directions; dropped.
   - **B-2a RAILING CONTINUITY (ruling, 14 Aug 2026) — replaces per-edge classification.** Follow the thin double line as a connected RUN, tracing in every direction as walls are traced, not as separate pairs. If the run turns and rejoins the building wall at both ends, the balcony has railing on **3 sides**; if it only spans the front, **1 side**. The shape comes from the trace. This dissolves the balcony-end problem: an end is never detected separately, it is part of one run. Measured on FLOOR PLAN: flat-1's balcony is 13.0 ft + 3.8 ft + 3.8 ft = **20.6 ft in one run with 2 turns**, both ends landing on the building wall at x = 0.
   - **Signature (measured, FLOOR PLAN):** a railing is a thin double line, gap 1.9–3.0 in, **9.5–15.2 ft long**, with **no third parallel line** within a wall thickness. A door leaf mispaired against a wall face looks similar on gap but is **~2.5 ft long and always has that third line** (8 of 8 measured). Length and the third-line test separate them; overlap fraction does NOT (1.00 for every class).
3. **B-3** — Default: parapet 3'6" if unknown, flagged, user-correctable.
4. **B-4** — Do not build the open face as a full-height wall.
5. **B-5** — Balcony area is usually counted separately from carpet in Indian practice. Report it separately. `ASK`

---

## 10.1 Covered but not enclosed

**A space can be part of the building without being enclosed by walls.** A
lobby open to the street, a balcony open on its outer face, a porch or portico
— all are roofed, all sit inside the building line, all are counted by the
architect, and none of them close a wall loop. Geometry alone cannot decide
them: **geometry says outside, the architect says inside.**

FLOOR PLAN.pdf is the worked case. The sheet prints `LOBBY 15'8" X 6'2"`
(96.6 sqft) and counts it inside its printed 246 sqft common area, yet the
lobby has **no wall on its south side (a 15.7 ft entrance) and none on its
east**, so the footprint contour correctly traces around it and every
enclosure-based rule discards it.

1. **CE-1** — Such a space IS part of the building for area purposes. It counts
   in built-up, and per its type in carpet (never), common (lobby, porch) or
   the balcony line (B-5).
2. **CE-2** — It is identified by being **inside the building line AND carrying
   a printed label or dimension** — never by wall enclosure. A printed
   `LOBBY 15'8" X 6'2"` is the architect stating that this space exists and how
   big it is (§0.1: printed data is ground truth).
3. **CE-3** — It must NOT be built as an enclosed volume in 3D, and its open
   side must never become a wall (B-4 generalised).
4. **CE-4 — STILL OPEN, but narrowed (14 Aug 2026).** Rahul's ruling: **the lobby is enclosed on all four sides in reality** — CE-4 was partly chasing a DRAFTING ERROR (see CONTRADICTS in §0). **Balconies remain the genuine case** for this category. Do not close CE-4.
5. **CE-4 (original wording) — OPEN QUESTION, awaiting ruling.** *What makes a space "inside the
   building line" when it has no wall on two sides?* Candidates seen but not
   chosen: the slab/roof edge; the column grid; the outermost paired wall runs
   projected across the opening; the printed label's own position. No answer is
   recorded here on purpose — an invented rule would be a guess, and this
   category exists precisely because geometry under-determines it.

---

## 11. Deferred — to be written

- Diagonal hatch marking open terrace on a typical floor plan (§1) — awaiting the full sheet
- 3-line window variant — awaiting an example
- Chhajja / sunshade projections: currently read as floating wall fragments; must be treated as projections, not walls
- Multi-flat sheets: splitting one sheet into per-flat modules
- Sloped / curved walls
- Mezzanine, loft, double-height
- **Elevation-file upload** — the resolution path for everything a floor plan
  genuinely cannot state: wall height (W-6), window sill and head height
  (WN-5, V-3), and balcony railing vs parapet (B-2, B-3). Until it exists,
  those stay defaults marked `ASK` / `ELEVATION`, never facts.

---

## 12. Change log

| Date | Change | Source |
|---|---|---|
| 10 Aug 2026 | v1 — walls, columns, ducts, lift, staircase, cupboard, doors, windows, ventilators, tags, rooms, balconies, exclusions | Rahul, from FLOOR PLAN.pdf + neelachala sheets |
| 10 Aug 2026 | **§0.1 VERIFICATION FIRST added** — a sheet's own area statement / opening schedule / printed room dimensions are ground truth and are checked BEFORE diagnosing any suspected parser error. Worked example: FLOOR PLAN.pdf states 870 + 835 = 1705 sqft built-up vs parser 1693.3 (99.3%), which disproved a proposed scale correction that would have made the number 38% wrong | Rahul |
| 10 Aug 2026 | **C-6 extended** — the 12-inch column assumption applies to the column's SHORT side, never the long side. Flagged CODE FIX PENDING: `pdf_vector._scale_ppf` pins `max(width, height)` | Rahul |
| 10 Aug 2026 | **DR-4 corrected** — D1 main entrance is 3'6" (was "~3'6" (some sheets 3'3")"). Flagged CODE FIX PENDING: `tag_openings.DOOR_W_FT["D1"]` is 3.25 | Rahul |
| 10 Aug 2026 | **W-6 corrected** — wall height default is 3.0 m (9.843 ft), matching the code; the 10 ft figure is removed. Certainty mark changed `ELEVATION` → `ASK` (user entry or elevation upload overrides) | Rahul |
| 10 Aug 2026 | **WN-3 consolidated** — one sill table only: W1 3'0", W2 3'0", W3 3'6". Flagged CODE FIX PENDING: `pdf_vector.LEGEND` and `tag_openings.WIN_FT` disagree (2'6" vs 3'0") and must be reconciled to it | Rahul |
| 10 Aug 2026 | **§11 deferred** — added elevation-file upload as the resolution path for wall height, sill height, and balcony railing vs parapet | Rahul |
| 11 Aug 2026 | **R-5 / L-5 / S-5 BUILT** — lift, staircase and lobby are split out of carpet into a separate `common_area` line (`area_statement.COMMON_TYPES`); built-up covers carpet + common, so the split never deducts common area from the plate. Tiny-room floor lowered 28 → 18 sqft ONLY for spaces fully ringed by wall (L-4), which recovers FLOOR PLAN's 5'x5' lift. FLOOR PLAN: carpet 1032.6 → 842.9 (expected dip), common 213.4 vs printed 246, R-8 79.2% → 80.6% | Rahul |
| 15 Aug 2026 | **B-5 FALLBACK BAND — MEASURED AND DISQUALIFIED IN ITS OBVIOUS FORM.** Absent a printed balcony width, "a balcony is shallower than any HABITABLE room on the sheet" gives FLOOR PLAN a 6.33 ft band, which **ADMITS the 4.91 ft lobby false positive** — the one run that must always be rejected. Widening the base to EVERY printed room drops the band to **4.50 ft** (a bathroom), which rejects 4.91 and keeps 3.92 and 3.37. But neither rescues a blind sheet: BRICK WORK carries **0 of 10** printed room dimensions so no band can be computed on the very sheet that draws 3 balconies, and GHATIKIA (0/38) and FIRST FLOOR (0/50) pass no candidate run at all. **A fallback derived from printed room dims cannot help sheets whose printed dims are unreadable** — the same root cause, one layer along. Not wired | Rahul |
| 15 Aug 2026 | **GHATIKIA's -354.5 sqft recorded as "artefact removed, unverifiable"** in `ground_truth.json`, not as an unexplained movement: it lost the identical `foot_ext - foot` artefact FLOOR PLAN did, for the identical reason, but has no instrument that can confirm or refute it (R-8 blind, 0 of 38 runs classified). Reasoned, not accepted | Rahul |
| 14 Aug 2026 | **A value can be wrong because of how the IMAGE WAS CROPPED, not because of the geometry.** FLOOR PLAN's footprint read 1709.5 at a 10 px canvas pad and 1705.3 with real background around it: the west wall face abutted the canvas edge, where OpenCV's border handling shields it from the erode. 4.2 sqft of pure cropping artefact. New check: before explaining a number by the drawing, ask whether the raster's EDGE is touching it | Rahul |
| 14 Aug 2026 | **B-5 BALCONY FILTER — depth must match a PRINTED width.** A railing run is a balcony only if it ends on wall (>=2), turns (>=1) AND its enclosed depth matches a width the sheet prints, within 0.25 ft. FLOOR PLAN: flat-1 3.92 vs printed 4'0" ✅, flat-2 3.37 vs 3'6" ✅, and the lobby run's 4.91 ft matches neither -> REJECTED (it read 37.3 sqft of balcony before this). Sheets printing no balcony width claim nothing: BRICK WORK 3 runs -> 0. **No printed width, no claim** — the rule uses the drawing, never a threshold | Rahul |
| 14 Aug 2026 | **BALCONY NOW MEASURED FROM ITS DRAWN EDGE (B-1/B-4); `foot_ext - foot` DELETED.** Each classified run is closed against the wall it returns to and filled; wall pixels are subtracted; the run is drawn on a scratch mask only, so the open face is still never built as a wall. FLOOR PLAN balcony 42.7 (artefact) -> **50.8 measured**, built-up 1650.7 -> 1658.8, R-8 96.8 -> **97.3**, carpet/common/rooms/R-2 unchanged. **The seal is not wall**: subtracting the 4 ft-sealed `m_env` filled a 3.37 ft balcony solid and lost it — subtract the UNSEALED mask | Rahul |
| 14 Aug 2026 | **`max_bridge = min(wall_mask.shape)` FIXED** — a canvas-unit constant in `_footprint_from_walls`, the same class as BORDER_MAXLEN_PT. Now the building's shorter side in FEET from the wall mask's own extent. No number moved (the canvas grew only in the long axis), and `test_bridge_cap_does_not_move_with_the_canvas` pins it: the same ring on a raster 800 px larger must give the same footprint | Rahul |
| 14 Aug 2026 | **`balcony = foot_ext - foot` WAS NEVER MEASURING THE BALCONY.** FLOOR PLAN's flat-1 balcony is at **x -3.92..0.00 ft, WEST of the linework origin** — off-canvas, because the raster was exactly the wall extent. No pocket can form for a region that is not in the image. The 42.7 sqft figure measures **how far the ring bridging reached outside the raster**, nothing more. A ratchet protected for three days is an ARTEFACT. New rule: a number whose value depends on the size of the canvas is not a measurement of the building | Rahul |
| 14 Aug 2026 | **CANVAS EXTENSION built (one variable).** The raster now covers geometry outside the wall extent, bounded by the traced RAILING RUNS and nothing else — never the page, never the plot (the plot boundary is dash-dot and is dropped before a run exists). FLOOR PLAN 4865 -> 5065 px (+3.93 ft west, covering flat-1's balcony); BRICK WORK's bound falls inside its wall extent so its canvas is unchanged; GHATIKIA + FIRST FLOOR classify 0 runs, so no bound and no change (the no-trusted-wall constraint again). Frame (`x0`/`y0`/`d_ft`) deliberately UNCHANGED, so a feature outside the wall extent reads as a negative foot coordinate, which is what it is | Rahul |
| 14 Aug 2026 | **A 10 px canvas pad was hiding 4.2 sqft.** The only number that moved from the canvas alone: FLOOR PLAN footprint 1709.5 -> 1705.3, built-up 1654.6 -> 1650.7, R-8 97.0 -> 96.8. Cause measured exactly — the footprint's west edge moves from **x -0.20 ft to x -0.06 ft**, i.e. 0.14 ft over the 29.8 ft west side = 4.2 sqft. At a 10 px pad the west wall face abutted the canvas edge, where OpenCV's border handling shields it from the 5 px erode; given real background it now erodes like every other face. **The old number was the wrong one** — it was inflated by a border artefact | Rahul |
| 14 Aug 2026 | **ROOT BLOCKER, now confirmed across THREE features — "no trusted wall, no anchor".** The position gate (GHATIKIA 744/779 real lines rejected, FIRST FLOOR gate uncomputable), Phase 1 admission (both sheets collapsed or inflated past their plot), and now railing classification (**0 of 38 GHATIKIA, 0 of 50 FIRST FLOOR** — `ends_on_wall` is always 0) all fail on the same two sheets for the same reason. It is not a per-feature problem: **every feature that needs to know where the building is inherits it.** Nothing keyed on trusted walls will work on those sheets until they get a signature-derived anchor | Rahul |
| 14 Aug 2026 | **Railing feed-in ATTEMPTED and REVERTED** — railing runs as room-mask boundaries + balcony measured as the pocket behind them. FLOOR PLAN degraded: balcony 42.7 -> **0.0**, built-up 1654.6 -> 1251.8, R-8 97.0 -> ~73. Cause: flat-1's balcony sits at **x -4..0 ft, WEST of the linework origin x0**, so it is outside the raster entirely and can never be measured as a pocket in that mask. The mask-subtraction balcony survives only because `foot_ext` is built from bridges that reach outside the extent. **Direct balcony measurement needs the raster to cover the balcony first** — a canvas/extent problem, not a tracer problem | Rahul |
| 14 Aug 2026 | **RULING 1 — B-2a railing CONTINUITY** replaces per-edge classification: trace the thin double line as a connected run; ends rejoining the wall = railing on 3 sides. Measured: flat-1's balcony is one 20.6 ft run (13.0+3.8+3.8) with 2 turns | Rahul |
| 14 Aug 2026 | **RULING 2 — §1 boundary hierarchy**: plot boundary = OUTERMOST line (dash-dot usual, outermost reliable); setback = inward offset 2/3/4.5/6 m by height; building edges inside the setback, projections may cross. Measured dash-dot signature: 11 collinear strokes, 6.3-6.7 ft, constant 3.1 ft gaps vs a railing's single unbroken stroke | Rahul |
| 14 Aug 2026 | **RULING 3 — new certainty mark CONTRADICTS**: the drawing states something a building cannot be. A drafting error, not a parsing gap. FLAG and ASK, showing what was read and why it is implausible; NEVER auto-correct. Worked example: FLOOR PLAN's lobby as a 15.7 ft opening in an external wall on a first floor with no street entrance | Rahul |
| 14 Aug 2026 | **RULING 4 — CE-4 narrowed**: the lobby is enclosed in reality, so CE-4 was partly chasing a drafting error. Balconies remain the genuine covered-but-not-enclosed case. CE-4 stays open | Rahul |
| 14 Aug 2026 | **NAMED CONSTRAINT — "bootstrapping from named layers cannot work where the named layers are empty".** The position gate that admits candidate geometry needs a trusted building extent to gate against, and that extent comes from the named wall layers. On GHATIKIA the named layers yield a 0.3 ft sliver (x 1.4-50.5, y 13.1-13.4) which rejects 744 of 779 real lines; on neelachala FIRST FLOOR they yield NOTHING, so the gate cannot be computed and everything passes (that is how it inflated to 47.6 x 185.3 ft). **The two sheets that most need admission — 97% and 100% of their wall geometry discarded by name — are exactly the two with no trusted base.** Any Phase 1 admission must therefore anchor on something derived from SIGNATURE (e.g. the geometry reader's own output), not on the named layers | Rahul |
| 14 Aug 2026 | **NAMED METHOD RULE — "one variable per measurement, or the result attributes to nothing".** Phase 1 attempt 1 changed the admitted layers AND widened the wall band 3-11 -> 3-18 in, in one step. FLOOR PLAN's R-8 fell 97.0 -> 78.6 and two sheets collapsed, and nothing in the result says which change did it. A measurement over two variables is not a measurement | Rahul |
| 14 Aug 2026 | **The footprint<=plot check earned its keep** — Phase 1 attempt 1 produced neelachala FIRST FLOOR at 7,614 sqft of building on a 2,455 sqft plot, and the physics check caught it automatically with no human looking. First time a §0.1 rule stopped a bad build on its own | Rahul |
| 14 Aug 2026 | **NAMED PATTERN — "a physically impossible result disqualifies the instrument, not the world".** The connectivity test for W-7 returned **100% of external walls with ZERO ends touching the wall network** — walls meet at corners, so that cannot be true of the building; it is true only of the measurement. Likely causes, both flagged at the time: a 0.35 ft point-to-segment tolerance applied to raw un-extended line ends, and an ad-hoc pairing that found 2 tile pairs where `wall_gap_pairs` finds 28. **Connectivity is therefore UNDEMONSTRATED, not ruled out** — it remains the most promising untested signal for W-7 and must be remeasured with the real pairing and a corner-aware tolerance. Rule: when a measurement contradicts physics, fix the instrument before drawing any conclusion from it, in either direction | Rahul |
| 12 Aug 2026 | **§10.1 COVERED BUT NOT ENCLOSED added** — a new category for spaces that are roofed and inside the building line but open on one or more sides (lobby, balcony, porch). They are part of the building for area purposes, identified by printed label/dimension rather than by wall enclosure, and never built as enclosed volumes. Prompted by FLOOR PLAN's lobby: printed `15'8" X 6'2"` = 96.6 sqft and counted in the sheet's 246 sqft common area, but open on its south (15.7 ft entrance) and east sides, so the footprint contour correctly excludes it. **CE-4 left OPEN for Rahul's ruling**: what makes such a space "inside the building line" | Rahul |
| 12 Aug 2026 | **NAMED PATTERN — "a mask difference is not a measurement".** Balcony area = `foot_ext - foot`, the difference between two intermediate footprint masks. It is named for balconies but measures mask disagreement: one wall-ring eligibility change moved it 42.7 -> 0.0 sqft with no balcony on the drawing changing, and it silently took 400 sqft of built-up with it (R-8 97.0 -> 73.4). **Design flaw, not tuning**: such a quantity cannot be ratcheted, since improving the ring destroys it. Balcony must come from the DRAWN open edge (B-1/B-4). Recorded in §0.1 | Rahul |
| 12 Aug 2026 | **NAMED PATTERN — "a tolerance in page units dies when the scale moves".** `_column_rects` matched column boxes with `abs(max(w,h) - ppf*1ft) < 0.6` — 0.6 POINTS, which only worked while ppf happened to equal the box. The 11 Aug scale correction (23.80 -> 28.47 pt/ft) left it behind and FLOOR PLAN went **26 columns -> 0**, silently: no test asserted columns and batch_eval did not print them. **Rule: any tolerance expressed in page units must be DERIVED from scale, never hardcoded.** Fixed to C-4's 8-48 in band on the SHORT side (C-6), all ppf-derived; columns + footprint_sqft now printed by batch_eval; pinned by `test_corpus_golden.py::test_floor_plan_columns`. Found by the Phase 0 wall overlay on its first run | Rahul |
| 12 Aug 2026 | **C-4 floor applied with a 10% margin** — GHATIKIA's columns measure 7.0-8.4 in on the short side, so a hard 8 in floor cut one real cluster in half (40 columns -> 0). The margin exists because OUR SCALE is itself uncertain there (C-6 unfixed), not because the rule is wrong | Rahul |
| 12 Aug 2026 | **Columns excluded from the wall-gap distribution** — a column box is two parallel lines a column apart, and it produced the LARGEST cluster in the first W-2 measurement (24 of 79 pairs at 12 in on FLOOR PLAN), which the wall classification would have inherited. Excluded in `wall_gap_distribution` only; `GEOM_SKIP` untouched because the parser's geometry path reads it | Rahul |
| 11 Aug 2026 | **NAMED PATTERN — "a correct TOTAL is not evidence of a correct SPLIT".** FLOOR PLAN's built-up reads 98.8% of the printed 1705, yet its parts are wrong in opposite directions: balcony 310.6 sqft against roughly 60 sqft of printed 4'0"+3'6" strips, carpet 842.9 against a printed 1370. The over and the under cancel. This is the SAME cancellation as the morning's whole-plan case (a 1.2x scale inflation cancelling 40% missing rooms), one level down. **`test_bucket_split_preserves_the_total` CANNOT catch this** — it only checks the sum. Each bucket needs its own instrument against printed data (R-2 does this for rooms; balcony and common have none yet) | Rahul |
| 11 Aug 2026 | **Per-face balcony split ATTEMPTED and REVERTED** — banding the space within the sheet's printed balcony width (4'0") of each rejected span swept a 4 ft strip along the whole 96 ft and 42 ft spurious spans, yielding a 208.9 sqft "balcony" of outside ground at (85.9, 5.4) and dropping built-up 98.8% -> 96.0%. Reverted to one honest region. The band is the wrong primitive: the depth bound belongs on the RESULTING region's short side, and the spurious spans must be eliminated first. `room_dims.printed_widths` (reads 4'0" / 3'6" / utility 4'6") is built and tested, ready for the next attempt | Rahul |
| 11 Aug 2026 | **NAMED PATTERN — "a bucket change can silently empty the total".** Splitting the lift/stair/lobby OUT of carpet also removed them from BUILT-UP, because built-up was computed as `carpet + wall_material` and carpet had just shrunk. R-8 fell 79.2% → 68.1% for a change that added information. **Rule: any change that moves an item between buckets must assert the TOTAL is unchanged.** Enforced by `test_area_report.py::test_bucket_split_preserves_the_total` | Rahul |
| 11 Aug 2026 | **A bogus bridge inflated an ACCEPTED result** — FLOOR PLAN's R-8 97.5% (accepted 11 Aug) rested on a 96 ft bridge across a 95 ft building. The relative bound exposed it; the honest figure was 79.2%. Lesson: a result that improves an instrument is not thereby verified — check WHAT produced the improvement, especially when a bound was absent | Rahul |
| 11 Aug 2026 | **Bridge bound CORRECTED** — was "no longer than the building's shorter side", now "no longer than the wall run it sits in". Reason: on a 95x30 ft strip the balcony faces run along the LENGTH, so the shorter-side bound rejected a legitimate 42 ft opening. Measured effect on FLOOR PLAN: the 42 ft span is still rejected under the corrected rule (its flanking wall run holds only 14.8 ft of material), so R-8 reads 79.2%, not the ~97.5% expected — the 97.5% had depended on a bogus 96 ft bridge. Long open faces are balconies (§10), not ring gaps | Rahul |
| 11 Aug 2026 | **R-2 median below 80% is now a Doctor FAIL** (was 75%), same class as an R-8 mismatch. First application: GHATIKIA at 58.6% across 14 rooms — under-segmentation, recorded in `ground_truth.json` | Rahul |
| 11 Aug 2026 | **§0.1 units rule added** — unit decided per sheet by notation + plausibility (feet carry ' and "; bare decimals under ~7 are metres), cross-checked against the measured scale (>2x disagreement ⇒ reject OUR derivation, keep the previous scale, flag), never mixed within a sheet. Implemented in `room_dims.one_unit` + the scale cross-check in `pdf_vector`. **The cross-check earned itself immediately**: GHATIKIA's metric labels derived 33.7 pt/ft against the column-box 8.8, which would have shipped a **2.75 ft building**; the clause rejected our derivation and kept the working scale | Rahul |
| 11 Aug 2026 | **§0.1 relative bridge bound added** — a ring bridge longer than the building's shorter side is rejected and logged; relative, not a constant | Rahul |
| 11 Aug 2026 | **§0.1 footprint-vs-plot physics check added** — a footprint above a known plot area FAILS (never warns); skipped when no plot is stated. Enforced in `plan_doctor` + `tests/test_footprint.py`. Footprint now comes from the outer wall RING (W-1), bridged jamb-to-jamb, replacing a fixed-kernel morphological close whose kernel was a guess at the widest opening | Rahul |
| 11 Aug 2026 | **§0.1 re-baselining rule added** — a golden number moves only when the drawing's own printed data disproves it, with evidence + superseded value recorded in `ground_truth.json`; never to make new code pass. First application: FLOOR PLAN.pdf envelope 113.9x35.6 -> 95.2x29.8 (R-2 median match 61.5% -> 96.4%, scale 23.80 -> 28.47 pt/ft, door gap and printed stilt agreeing) | Rahul |
| 11 Aug 2026 | **TG-5 BUILT, out of §11 deferred** — `opening_schedule.py` reads the sheet's own schedule and overrides `DOOR_W_FT` / `WIN_FT` / `LEGEND`. Verified on BRICK WORK LAYOUT.pdf: W now 6'0" sill 2'6" (was 4'0" sill 3'0"). Rows that cannot be read whole are dropped, never half-read | Rahul |
