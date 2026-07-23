#!/usr/bin/env python3
"""Migrated from drishti/tools/scene_to_glb.py.
scene.json (feet, z-up) -> real 3D model (.glb). glTF is Y-up, so plan-Z (height)
-> Y and plan-Y (north) -> Z. Walls are tiled into boxes that skip opening voids.

Use as a library:   build_glb(scene_dict, "out.glb")
Or from the CLI:     python scene_to_glb.py scenes/bedroom.scene.json out.glb
"""
import sys
import json

FT = 0.3048  # feet -> metres


def interval_boxes(w, H, openings):
    """Tile a wall into solid (x0,x1,y0,y1,z0,z1) boxes, skipping opening voids."""
    out = []
    lo_w = w["x0"] if w["axis"] == "x" else w["y0"]
    hi_w = w["x1"] if w["axis"] == "x" else w["y1"]

    def _clamp(o):
        # CLAMP the opening span to the wall extent, so a stray/oversize `along`
        # can't stretch a wall past its ends or spawn a floating box
        a0 = max(min(o["along"][0], o["along"][1]), lo_w)
        a1 = min(max(o["along"][0], o["along"][1]), hi_w)
        return (a0, a1, o["z"][0], o["z"][1])

    ops = sorted(_clamp(o) for o in openings
                 if o.get("wall") == w["id"] and o.get("along") and o.get("z"))
    ops = [op for op in ops if op[1] - op[0] > 0.01]      # drop clamped-away
    if w["axis"] == "x":
        fy0, fy1 = w["y0"], w["y1"]; cur = w["x0"]
        for s0, s1, zb, zt in ops:
            if s0 > cur: out.append((cur, s0, fy0, fy1, 0, H))
            if zb > 0:   out.append((s0, s1, fy0, fy1, 0, zb))
            if zt < H:   out.append((s0, s1, fy0, fy1, zt, H))
            cur = max(cur, s1)
        if cur < w["x1"]: out.append((cur, w["x1"], fy0, fy1, 0, H))
    else:
        fx0, fx1 = w["x0"], w["x1"]; cur = w["y0"]
        for s0, s1, zb, zt in ops:
            if s0 > cur: out.append((fx0, fx1, cur, s0, 0, H))
            if zb > 0:   out.append((fx0, fx1, s0, s1, 0, zb))
            if zt < H:   out.append((fx0, fx1, s0, s1, zt, H))
            cur = max(cur, s1)
        if cur < w["y1"]: out.append((fx0, fx1, cur, w["y1"], 0, H))
    return out


def _add_box(meshes, b, rgba, name=None):
    import trimesh
    x0, x1, y0, y1, z0, z1 = b
    sx, sy, sz = (x1 - x0) * FT, (z1 - z0) * FT, (y1 - y0) * FT       # Y = height
    cx, cy, cz = (x0 + x1) / 2 * FT, (z0 + z1) / 2 * FT, (y0 + y1) / 2 * FT
    if sx <= 0 or sy <= 0 or sz <= 0:
        return
    m = trimesh.creation.box(
        extents=(sx, sy, sz),
        transform=trimesh.transformations.translation_matrix((cx, cy, cz)))
    m.visual.face_colors = rgba
    meshes.append((name or f"part_{len(meshes)}", m))


def _hexrgba(h, a=255):
    h = h.lstrip("#")
    return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a]


def poly_bands(wall, H, openings):
    """Split a POLYGON wall (walls_poly entry) into z-bands, subtracting window
    footprints in the bands their [sill, head] covers. Returns
    [(shapely geometry, z0, z1), ...] - geometry may be Polygon or MultiPolygon."""
    from shapely.geometry import Polygon, box as sbox
    from shapely.ops import unary_union
    poly = Polygon(wall["outer"], wall.get("holes") or None)
    if not poly.is_valid:
        poly = poly.buffer(0)
    wins = [(sbox(*o["footprint"]), o["z"][0], o["z"][1])
            for o in openings if o.get("footprint")]   # windows AND doors
    wins = [w for w in wins if w[0].intersects(poly)]
    if not wins:
        return [(poly, 0.0, H)]
    edges = sorted({0.0, H, *(z for _, zb, zt in wins for z in (zb, zt) if 0 < z < H)})
    bands = []
    for z0, z1 in zip(edges, edges[1:]):
        cut = [g for g, zb, zt in wins if zb <= z0 and zt >= z1]
        geom = poly.difference(unary_union(cut)) if cut else poly
        if not geom.is_empty:
            bands.append((geom, z0, z1))
    return bands


_DOOR_LEAF = _hexrgba("#6b4a2f")     # walnut leaf


def _door_opening_rect(o, walls_by_id):
    """The door void as (x0,y0,x1,y1) plan-ft. Prefers the vector `footprint`;
    else derives it from the wall the door sits on + its `along` span (ML path
    doors carry no footprint). None if it can't be located."""
    fp = o.get("footprint")
    if fp and len(fp) == 4:
        x0, y0, x1, y1 = (float(fp[0]), float(fp[1]), float(fp[2]), float(fp[3]))
        return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)
    w = walls_by_id.get(o.get("wall"))
    along = o.get("along")
    if not w or not along or "axis" not in w:
        return None
    a0, a1 = sorted((float(along[0]), float(along[1])))
    wy0, wy1 = sorted((float(w["y0"]), float(w["y1"])))
    wx0, wx1 = sorted((float(w["x0"]), float(w["x1"])))
    if w["axis"] == "x":
        return a0, wy0, a1, wy1
    return wx0, a0, wx1, a1


def _add_door_leaf(meshes, o, rect, H, name):
    """A real door LEAF standing AJAR in the opening — hinged at one jamb and
    swung ~60 deg into the swing arc — so a doorway reads as an openable
    designer door instead of an empty hole. Built for EVERY door (vector or
    ML). glTF axes: X=plan_x, Y=height, Z=plan_y (same as _add_box)."""
    import math
    import trimesh
    x0, y0, x1, y1 = rect
    zt = float((o.get("z") or [0, H])[1] or H)
    zt = min(zt, H) if zt > 0 else H
    run_x = (x1 - x0) >= (y1 - y0)          # does the wall run along X?
    width = (x1 - x0) if run_x else (y1 - y0)
    if width < 0.5 or zt <= 0:
        return
    THICK = 0.14                             # leaf thickness (ft)
    if run_x:
        rdx, rdy = 1.0, 0.0
        hinge = (x0, (y0 + y1) / 2.0)        # hinge at the low-x jamb, mid-thickness
    else:
        rdx, rdy = 0.0, 1.0
        hinge = ((x0 + x1) / 2.0, y0)        # hinge at the low-y jamb
    ang = math.radians(60.0)                 # ajar angle
    if str(o.get("hinge", "")).endswith("1"):
        ang = -ang                           # hint flips the swing side
    phi = math.atan2(-rdy, rdx)              # local +X -> run direction (about Y)
    Wm, Hm, Tm = width * FT, zt * FT, THICK * FT
    tf = trimesh.transformations
    M = (tf.translation_matrix((hinge[0] * FT, 0.0, hinge[1] * FT))
         @ tf.rotation_matrix(phi + ang, (0, 1, 0))
         @ tf.translation_matrix((Wm / 2.0, Hm / 2.0, 0.0)))
    leaf = trimesh.creation.box(extents=(Wm, Hm, Tm), transform=M)
    leaf.visual.face_colors = _DOOR_LEAF
    meshes.append((name, leaf))


def _add_poly_prism(meshes, geom, z0, z1, rgba, name=None):
    """Extrude a shapely Polygon/MultiPolygon plan footprint (feet) from z0..z1
    and place it in glTF axes (X=x, Y=height, Z=plan-y), like _add_box."""
    import numpy as np
    import trimesh
    if z1 - z0 <= 0 or geom.is_empty:
        return
    polys = getattr(geom, "geoms", [geom])
    M = np.array([[FT, 0, 0, 0], [0, 0, FT, FT * z0], [0, FT, 0, 0], [0, 0, 0, 1.0]])
    for k, pg in enumerate(polys):
        if pg.is_empty or pg.area <= 0:
            continue
        m = trimesh.creation.extrude_polygon(pg, height=z1 - z0)
        m.apply_transform(M)
        if m.volume < 0:
            m.invert()
        m.visual.face_colors = rgba
        meshes.append((f"{name}_{k}" if name else f"part_{len(meshes)}", m))


# Parametric furniture: each plan footprint becomes a small assembly of boxes
# (a bed gets frame+mattress+pillows, a sofa gets seat+back+arms, ...) so
# uploaded plans render RECOGNIZABLE furniture, not flat slabs. Muted real-
# world colours; the viewer keeps vertex colours on furn_* meshes by name.
_WOOD = _hexrgba("#8a6a48")
_WOOD_DARK = _hexrgba("#6f5238")
_MATTRESS = _hexrgba("#f1ecdf")
_PILLOW = _hexrgba("#fbfbf6")
_BLANKET = _hexrgba("#b0653f")
_FABRIC = _hexrgba("#7d8fa3")
_SANITARY = _hexrgba("#f4f6f7")
_GRANITE = _hexrgba("#55585c")


def _furn_frame(f):
    """Footprint -> (x0, x1, y0, y1, along_x): along_x = long axis is X."""
    x0, y0 = f["x"], f["y"]
    return x0, x0 + f["w"], y0, y0 + f["d"], f["w"] >= f["d"]


def _add_furniture(meshes, f, i):
    t = f.get("type", "box")
    x0, x1, y0, y1, ax = _furn_frame(f)
    nm = lambda part: f"furn_{t}_{i}_{part}"
    B = lambda box, rgba, part: _add_box(meshes, box, rgba, name=nm(part))
    if t == "bed":
        B((x0, x1, y0, y1, 0.35, 1.2), _WOOD, "frame")
        B((x0 + 0.25, x1 - 0.25, y0 + 0.25, y1 - 0.25, 1.2, 1.9), _MATTRESS, "mattress")
        # pillows at the head end (start of the long axis); blanket over the rest
        if ax:
            B((x0 + 0.4, x0 + 1.9, y0 + 0.5, y0 + (y1 - y0) / 2 - 0.15, 1.9, 2.2), _PILLOW, "pillow0")
            B((x0 + 0.4, x0 + 1.9, y0 + (y1 - y0) / 2 + 0.15, y1 - 0.5, 1.9, 2.2), _PILLOW, "pillow1")
            B((x0 + 2.3, x1 - 0.15, y0 + 0.2, y1 - 0.2, 1.9, 2.05), _BLANKET, "blanket")
        else:
            B((x0 + 0.5, x0 + (x1 - x0) / 2 - 0.15, y0 + 0.4, y0 + 1.9, 1.9, 2.2), _PILLOW, "pillow0")
            B((x0 + (x1 - x0) / 2 + 0.15, x1 - 0.5, y0 + 0.4, y0 + 1.9, 1.9, 2.2), _PILLOW, "pillow1")
            B((x0 + 0.2, x1 - 0.2, y0 + 2.3, y1 - 0.15, 1.9, 2.05), _BLANKET, "blanket")
    elif t == "sofa":
        B((x0, x1, y0, y1, 0.3, 1.35), _FABRIC, "seat")
        if ax:  # back along the far long edge, arms at the short ends
            B((x0, x1, y1 - 0.55, y1, 0.3, 2.5), _FABRIC, "back")
            B((x0, x0 + 0.45, y0, y1, 0.3, 1.9), _FABRIC, "arm0")
            B((x1 - 0.45, x1, y0, y1, 0.3, 1.9), _FABRIC, "arm1")
        else:
            B((x1 - 0.55, x1, y0, y1, 0.3, 2.5), _FABRIC, "back")
            B((x0, x1, y0, y0 + 0.45, 0.3, 1.9), _FABRIC, "arm0")
            B((x0, x1, y1 - 0.45, y1, 0.3, 1.9), _FABRIC, "arm1")
    elif t == "cupboard":
        B((x0, x1, y0, y1, 0.0, 0.35), _WOOD_DARK, "plinth")
        B((x0, x1, y0, y1, 0.35, 6.5), _WOOD, "body")
        B((x0 - 0.04, x1 + 0.04, y0 - 0.04, y1 + 0.04, 6.5, 6.7), _WOOD_DARK, "top")
    elif t == "table":
        leg = 0.18
        for k, (lx, ly) in enumerate(((x0, y0), (x1 - leg, y0),
                                      (x0, y1 - leg), (x1 - leg, y1 - leg))):
            B((lx, lx + leg, ly, ly + leg, 0.0, 2.3), _WOOD_DARK, f"leg{k}")
        B((x0 - 0.05, x1 + 0.05, y0 - 0.05, y1 + 0.05, 2.3, 2.5), _WOOD, "top")
    elif t == "chair":
        B((x0 + 0.1, x1 - 0.1, y0 + 0.1, y1 - 0.1, 0.0, 1.4), _WOOD, "seat")
        if ax:
            B((x0 + 0.1, x0 + 0.35, y0 + 0.1, y1 - 0.1, 1.4, 2.8), _WOOD_DARK, "back")
        else:
            B((x0 + 0.1, x1 - 0.1, y0 + 0.1, y0 + 0.35, 1.4, 2.8), _WOOD_DARK, "back")
    elif t == "sidetable":
        B((x0, x1, y0, y1, 0.0, 1.5), _WOOD, "body")
        B((x0 - 0.04, x1 + 0.04, y0 - 0.04, y1 + 0.04, 1.5, 1.62), _WOOD_DARK, "top")
    elif t == "commode":
        if ax:  # tank against the start of the long axis, bowl in front
            B((x0, x0 + 0.55, y0 + 0.05, y1 - 0.05, 0.0, 2.4), _SANITARY, "tank")
            B((x0 + 0.55, x1 - 0.15, y0 + 0.2, y1 - 0.2, 0.0, 1.35), _SANITARY, "bowl")
        else:
            B((x0 + 0.05, x1 - 0.05, y0, y0 + 0.55, 0.0, 2.4), _SANITARY, "tank")
            B((x0 + 0.2, x1 - 0.2, y0 + 0.55, y1 - 0.15, 0.0, 1.35), _SANITARY, "bowl")
    elif t == "basin":
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        B((cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3, 0.0, 2.3), _SANITARY, "pedestal")
        B((x0, x1, y0, y1, 2.3, 2.65), _SANITARY, "bowl")
    elif t == "counter":
        B((x0, x1, y0, y1, 0.0, 2.6), _hexrgba("#7a6a55"), "body")
        B((x0 - 0.05, x1 + 0.05, y0 - 0.05, y1 + 0.05, 2.6, 2.8), _GRANITE, "top")
    elif t == "bathtub":                                   # G4
        B((x0, x1, y0, y1, 0.0, 1.85), _SANITARY, "tub")   # white outer shell
        B((x0 + 0.3, x1 - 0.3, y0 + 0.3, y1 - 0.3, 1.35, 1.8),
          _hexrgba("#dfe8ec"), "water")                    # inset recess
    else:
        B((x0, x1, y0, y1, 0.0, f.get("h", 2.0)), _hexrgba("#d85a30"), "body")


def _build_scene(scene):
    """Scene dict -> (trimesh.Scene, meshes) shared by build_glb / build_glb_bytes."""
    import trimesh
    H = scene["meta"]["wall_height_ft"]
    meshes = []
    walls = scene.get("walls", [])
    walls_poly = scene.get("walls_poly", [])
    xs = [w["x0"] for w in walls] + [w["x1"] for w in walls] \
        + [p[0] for w in walls_poly for p in w["outer"]]
    ys = [w["y0"] for w in walls] + [w["y1"] for w in walls] \
        + [p[1] for w in walls_poly for p in w["outer"]]
    if xs:
        # floor slab under THIS wing's walls (scenes are one wing each, so the
        # wall extent IS the wing footprint)
        _add_box(meshes, (min(xs), max(xs), min(ys), max(ys), -0.25, 0),
                 _hexrgba("#e8e4da"), name="floor")
    openings = scene.get("openings", [])
    for i, w in enumerate(walls):
        for j, b in enumerate(interval_boxes(w, H, openings)):
            _add_box(meshes, b, _hexrgba("#cfcabd"), name=f"wall_{i}_{j}")
    for i, w in enumerate(walls_poly):
        for j, (geom, z0, z1) in enumerate(poly_bands(w, H, openings)):
            _add_poly_prism(meshes, geom, z0, z1, _hexrgba("#cfcabd"),
                            name=f"wall_p{i}_{j}")
    # a real door LEAF standing ajar in every door void (D1): reads as an
    # openable designer door, not a hole. Named 'door_*' so the viewer gives it
    # a wood finish. Works for vector (footprint) and ML (wall+along) doors.
    walls_by_id = {w["id"]: w for w in walls if "id" in w}
    for i, o in enumerate(openings):
        if o.get("type") == "door":
            rect = _door_opening_rect(o, walls_by_id)
            if rect:
                _add_door_leaf(meshes, o, rect, H, name=f"door_{i}")
    # glass panes in the window voids (slightly inset to avoid z-fighting);
    # the viewer swaps 'glass_*' meshes to a translucent material by NAME
    for i, o in enumerate(openings):
        if o.get("type") == "window" and o.get("footprint"):
            x0, y0, x1, y1 = o["footprint"]
            zb, zt = o["z"]
            pad = 0.05
            _add_box(meshes, (x0 + pad, x1 - pad, y0 + pad, y1 - pad,
                              zb + pad, zt - pad),
                     [176, 212, 232, 110], name=f"glass_{i}")
    for i, c in enumerate(scene.get("columns", []) + scene.get("ducts", [])):
        _add_box(meshes, (c["x"], c["x"] + c["w"], c["y"], c["y"] + c["d"], 0, H),
                 _hexrgba("#9aa0a6"), name=f"column_{i}")
    for i, f in enumerate(scene.get("furniture", [])):
        _add_furniture(meshes, f, i)
    sc = trimesh.Scene()
    if not meshes:
        # a geometry-less scene (no walls/poly/furniture/columns/glass) would
        # make trimesh raise "Can't export empty scenes!" — add a tiny invisible
        # floor marker so export always yields a valid GLB instead of crashing
        _add_box(meshes, (0.0, 1.0, 0.0, 1.0, -0.01, 0.0),
                 _hexrgba("#e8e4da"), name="floor")
    for name, m in meshes:
        sc.add_geometry(m, node_name=name, geom_name=name)
    return sc, meshes


def build_glb(scene, out_path):
    """Build a .glb from a scene dict (the canonical scene.json)."""
    sc, meshes = _build_scene(scene)
    # include_normals: without it trimesh writes POSITION-only primitives and
    # three.js-based viewers light them as NaN -> solid black (found 2026-07-14
    # when the window glass rendered black; our app also guards client-side,
    # but the DOWNLOADED .glb must stand on its own in any viewer)
    sc.export(out_path, include_normals=True)
    tris = sum(len(m.faces) for _, m in meshes)
    import logging
    logging.getLogger("drishti.glb").info(
        "wrote %s: %d meshes, %d triangles", out_path, len(meshes), tris)
    return out_path


def build_glb_bytes(scene):
    """Build a .glb from a scene dict and return the bytes (no temp file)."""
    sc, _meshes = _build_scene(scene)
    return sc.export(file_type="glb", include_normals=True)


def main(scene_path, out_path):
    with open(scene_path) as f:
        build_glb(json.load(f), out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
