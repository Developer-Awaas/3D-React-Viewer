# 3D defect sheet - REVIEWED 1 Sep 2026

**Two of my eight defects were WRONG and are withdrawn. Read this first.**

| withdrawn | why |
|---|---|
| 3 and 4, the balcony and utility "solid blocks" | **The railings are correct.** I measured each mesh's BOUNDING BOX and called it area. True rail areas are 5.16 / 3.18 / 3.08 sqft - 0.25 ft thick, 3.50 ft high, 2-3 sided, with a floor slab inside. `09` and `11` now show the top-down proof. |
| the GHATIKIA 180-degree flip | **My renderer, not the model.** At a top-down camera my basis vector flipped sign, rotating every top view. The 2D overlay always registered correctly on that sheet. Fixed; `13` is re-rendered. |

**Fixed since the review:** the floor slab is now the footprint polygon on
every sheet (FIRST FLOOR 7396 -> 4463 sqft, FLOOR PLAN 2841 -> 1794,
GHATIKIA 2548 -> 1736, BRICK WORK 1503 -> 1246); ducts no longer build as
solid `column_i` boxes.

**Confirmed and closed:** the column in flat-1's entrance is correct as
drawn - 21 in clear is what the drawing says.

**Still to build:** staircase as actual steps (Q1) - terrace slab over
FIRST FLOOR's gap (Q3) - roof/ceiling (Q2, deliberately after the floor
plan reading is verified) - GHATIKIA's stair flight-divider being read as a
wall, and its lift - then GHATIKIA's doors.

---

## Fixed since the review

| image | what it now shows |
|---|---|
| `01-floor-slab-first-floor.png` | **FIXED.** Slab was 7396 sqft under a 4463 sqft footprint (+66%) and floored the gap between the blocks. It is now the footprint ring. **Q3 still open: the gap needs a terrace slab.** |
| `02-floor-slab-floor-plan.png` | **FIXED on every sheet.** FLOOR PLAN 2841 -> 1794, GHATIKIA 2548 -> 1736, BRICK WORK 1503 -> 1246 sqft. |
| `16-ducts-not-built.png` | **FIXED.** Ducts were built as solid full-height boxes named `column_i`. Now a thin shaft ring named `duct_i_k`, void left open. Latent - no sheet emits ducts today. |

## Withdrawn - my error, not the model

| image | what is actually true |
|---|---|
| `09-balcony-railing-CORRECT.png` | Rail area **5.16 sqft**, 0.25 ft thick, 3-sided, floor slab inside. I reported the mesh **bounding box** (54.2 sqft) as area. |
| `11-utility-railing-CORRECT.png` | Rail area **3.08 sqft**, not the 38.8 sqft bounding box I reported. |
| `13-ghatikia-split.png` | The 180-degree flip was **my renderer**. Re-rendered and it now matches the drawing. The scene and the viewer were always correct. |

## Still open - to build

| image | what is wrong |
|---|---|
| `03-no-staircase-floor-plan.png` | **No staircase on any sheet.** Rooms are typed `stairs`; no stair mesh exists. Q1: build actual steps (S-6). |
| `04-no-staircase-first-floor.png` | Both FIRST FLOOR staircases missing - 168.1 and 166.9 sqft. Walk the model and you fall through. |
| `05-no-roof.png` | No roof or ceiling. Q2: build, but **after** the floor plan reading is verified - checking that needs the ceiling absent. |
| (GHATIKIA, no image yet) | The staircase's **middle flight-divider is built as a wall**, and the lift is read wrong. S-4 says tread lines are not walls; the divider is the same rule. Then its doors. |

## Closed - correct as drawn

| image | ruling |
|---|---|
| `06-entrance-column-clash.png` | The column in flat-1's entrance is **correct**. 21 in clear is what the drawing says. Not an error. |

## Confirm - believed right

| image | what to confirm |
|---|---|
| `19-railings-correct.png` | A correct railing: 0.25 ft thick, 3.50 ft high, slab behind. |
| `07-doors-hinge-swing.png` | 16 doors hinged at the drawn hinge, swing read from the arc, head 7.00 ft. |
| `08-door-into-room.png` | A second door with the opposite swing sense. |
| `12-wall-thickness.png` | Walls at measured thickness (0.83 ft), full height 9.84 ft. |
| `10-balcony-floor.png` | The balcony's open face is not built as a wall, and it has a slab. |
| `14-first-floor-two-blocks.png` | Both blocks as one building. **Q3: the gap gets a terrace slab, first floor only.** |
| `15-first-floor-doors-missing.png` | 26 of 54 door tags build nothing - we could not place them against a wall gap. |
| `17-brick-work-overview.png` | BRICK WORK overall. No instrument can judge this sheet. |
| `18-floor-plan-overview.png` | FLOOR PLAN overall - every judged number rests on it. |

---

### What is NOT in this sheet, and why

- **Room-boundary errors on GHATIKIA and FIRST FLOOR.** Known and measured, but
  they are 2D - they show in the numbers, not in the model.
- **Anything I could only justify with a number.** If a defect needs a
  measurement to see, it does not belong in a 30-minute visual review.
