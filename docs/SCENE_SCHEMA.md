# scene.json - CANONICAL geometry schema

Migrated from the drishti reference (`3D Project viewer/drishti/parser/SCHEMA.md`)
and adopted as the single source of truth for the React Viewer. Supersedes the old
`pipeline/SCHEMA.md` (room-centric). This is the format CubiCasa's detection is
translated INTO, and that `server/scene_to_glb.py` builds 3D FROM.

## Convention (decided)
All coordinates in **feet**, origin bottom-left, **z is up**. The viewer/builder maps
plan-Z (height) -> three.js/glTF-Y at render time.

## Fields
    meta.wall_height_ft   number   extrusion height (3 m default = 9.843 ft)
    meta.scale.source     string   e.g. "dimension_text" (how real size was set)
    wall_types            external/internal nominal thickness (ft)
    walls[]   { id, axis:"x"|"y", x0,x1,y0,y1, type:"external"|"internal" }
              footprint is the rectangle x0..x1 by y0..y1
    walls_poly[] { id, outer:[[x,y],...], holes:[[[x,y],...],...] }
              EXACT wall footprints as polygons (vector-PDF path) - supports
              angled walls; rooms appear as holes. A scene uses walls[]
              (raster/CubiCasa path) or walls_poly[] (vector path) or both.
    openings[]{ id, type:"window"|"door",
                EITHER wall:<wall id> + along:[a,b]   (box-wall path)
                OR     footprint:[x0,y0,x1,y1]        (polygon-wall path)
                z:[bottom,top] sill/head (window) or 0..door-height (door)
                door extras: hinge:"x0"|"x1", swing:"in"|"out"
                polygon-path door extras: footprint = the DOORWAY STRIP on the
                  wall (parser fills the CAD jamb gap so the z cut leaves a
                  header/lintel above the door, as built on site);
                  swing_area:[x0,y0,x1,y1] = leaf+arc box (for door placement
                  /swing animation in viewers; NOT a cut) }
    columns[] { id, x,y,w,d, kind:"column" }
    ducts[]   { id, x,y,w,d, kind:"duct" }
    rooms[]   { name, label_dim, w_ft, d_ft }
    furniture[]{ id, type, x,y,w,d,h }

## How openings become 3D
Box walls are tiled into solid sub-boxes that skip the opening void:
- window -> wall below sill + wall above head, gap in the middle.
- door   -> full-height gap; hinge tells which end the cut lands on.
Implemented in `server/scene_to_glb.py` (`interval_boxes`) - unit-tested.
Polygon walls are split into z-bands; in each band the union of window
footprints whose [sill,head] covers it is 2D-subtracted (`poly_bands`).

## Two input routes (server router in /scene)
- **Vector CAD PDF** (has wall/plan/window/column OCG layers) ->
  `server/pdf_vector.py` reads geometry per layer -> walls_poly + window
  openings + columns. Exact, no AI. Scale: dominant column box = 12 in,
  else the width_ft parameter. Doors from arcs = Step D2.
- **Raster image / flat PDF** -> CubiCasa detects wall pixels -> `walls.py`
  vectorizes to centre-lines -> Step B converts centre-line + `wall_types`
  thickness into box wall footprints + openings from door/window detections.
