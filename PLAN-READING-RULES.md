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

A number the tool cannot justify must never be presented as fact.

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
2. **B-2** — The open face has either a **railing/grill** or a **parapet wall 3–4 ft high**. The floor plan usually cannot tell you which. `ELEVATION`
3. **B-3** — Default: parapet 3'6" if unknown, flagged, user-correctable.
4. **B-4** — Do not build the open face as a full-height wall.
5. **B-5** — Balcony area is usually counted separately from carpet in Indian practice. Report it separately. `ASK`

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
| 11 Aug 2026 | **§0.1 re-baselining rule added** — a golden number moves only when the drawing's own printed data disproves it, with evidence + superseded value recorded in `ground_truth.json`; never to make new code pass. First application: FLOOR PLAN.pdf envelope 113.9x35.6 -> 95.2x29.8 (R-2 median match 61.5% -> 96.4%, scale 23.80 -> 28.47 pt/ft, door gap and printed stilt agreeing) | Rahul |
| 11 Aug 2026 | **TG-5 BUILT, out of §11 deferred** — `opening_schedule.py` reads the sheet's own schedule and overrides `DOOR_W_FT` / `WIN_FT` / `LEGEND`. Verified on BRICK WORK LAYOUT.pdf: W now 6'0" sill 2'6" (was 4'0" sill 3'0"). Rows that cannot be read whole are dropped, never half-read | Rahul |
