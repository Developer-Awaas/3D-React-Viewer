# Project Requirements — 2D plan → 3D conversion

## 0. The golden rule
Garbage in, garbage out. Output quality is decided MORE by input quality than by how
clever the code is. Better input → better output, every time.

## 1. Input quality hierarchy (best → worst)
| Tier | Input | Result | Why |
|------|-------|--------|-----|
| A | **DXF / DWG** (vector CAD) | Near-perfect, automatic | Walls/doors/furniture are exact NAMED objects on layers — read, don't detect |
| B | **Clean line PNG/PDF** (black walls on white, high-DPI, no furniture, axis-aligned, scale given) | Good walls automatically | Detection is reliable on crisp, simple line art |
| C | **Stylised / coloured / furnished plan** (like "THE ZENITH") | Rough massing only | Furniture, fills, text, rotation confuse pixel detection |
| D | **Photo / phone scan** (skew, shadows, low contrast) | Poor without ML | Needs a trained, augmentation-robust model |

If you can get Tier A or B, the job becomes easy. Tier C/D is where ML is required.

## 2. What makes an input "better" (concrete checklist)
- **Format:** DXF/DWG if at all possible; else PNG/PDF.
- **Resolution:** ≥ 300 DPI; walls at least a few pixels thick.
- **Contrast:** pure black lines on white; no grey washes.
- **Scale:** include a dimension or scale bar, OR tell us the real building width (metres).
- **Orientation:** axis-aligned (not rotated/skewed).
- **Cleanliness:** walls clearly heavier than furniture lines; ideally a wall-only version
  (furniture on a separate layer you can hide) for the wall pass.
- **Framing:** one plan per image, cropped to the building, no title block/border.
- **Consistent line weights:** structural walls thicker than partitions (lets us tell them apart).

## 3. How each element is interpreted (the features/signals)
### Walls
- Darkness (the blackest marks) + **thickness** (drawn as two parallel lines).
- **Length & straightness** (long continuous runs).
- **Connectivity** into closed loops (rooms).
- Thickness variation → structural vs partition walls.

### Edges / corners / openings
- **Corner:** two walls meeting at ~90° → snap endpoints to a shared point.
- **Door:** a GAP in a wall run, usually with a quarter-circle swing arc.
- **Window:** a gap with thin parallel lines or a "W" label.
- Rule used: small gap = opening to keep; large gap may = missing wall to close.

### Furniture
- A closed sub-shape INSIDE a room (not part of the wall network).
- **Size range** (bed ~2.0×1.5 m, sofa, toilet…), **internal pattern** (mattress hatch),
  and **context** (toilet against a wall, bed in a "BEDROOM").
- Cannot be done by thresholds → needs template matching (identical symbols) or an ML
  object detector (varied symbols).

## 4. Features / components required to do the job
| Capability | Tier A (DXF) | Tier B (clean image) | Tier C/D (messy/photo) |
|-----------|--------------|----------------------|------------------------|
| Wall extraction | DXF layer parse (`ezdxf`) | CV: threshold→Hough→pair→merge | ML segmentation (U-Net) |
| Openings | from DXF blocks | gap + arc detection | ML segmentation |
| Rooms | from closed polylines | flood-fill segmentation | ML segmentation |
| Furniture | named blocks → place models | template match (weak) | ML object detection (YOLO) |
| Scale | real units in file | scale bar / user input | user input |
| Vectorize → extrude → GLB | ✅ (built) | ✅ (built) | ✅ (built) |
| Viewer | ✅ (built: R3F / model-viewer) | ✅ | ✅ |

The vectorize→extrude→GLB→viewer half is DONE. Only the "recognition" half changes by tier.

## 5. If we go the ML route — requirements
- **Labelled data:** CubiCasa5K / R2V / RPLAN, or synthetic plans (free labels).
- **Compute:** a GPU (Colab/Kaggle free tier is enough to start).
- **Models:** segmentation (walls/doors/rooms) + object detection (furniture).
- **Pipeline glue:** augmentation, training loop, ONNX export, then feed masks into the
  existing extrude→GLB code.
- **Metrics / success criteria:** wall IoU > ~0.8, furniture mAP, and "does the room
  count + layout match the plan" on a held-out test set.

## 6. Recommended decision
- Need it fast and accurate now → **Tier A: get the DXF**, parse with `ezdxf`. Best ROI.
- Image-only, clean plans → **Tier B**: the CV pipeline already works; tune it.
- Must handle any messy plan automatically → **Tier C/D**: commit to the ML project.
