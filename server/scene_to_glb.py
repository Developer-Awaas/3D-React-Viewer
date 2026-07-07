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
    ops = sorted(((o["along"][0], o["along"][1], o["z"][0], o["z"][1])
                  for o in openings if o.get("wall") == w["id"]))
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


def _add_box(meshes, b, rgba):
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
    meshes.append(m)


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


def _add_poly_prism(meshes, geom, z0, z1, rgba):
    """Extrude a shapely Polygon/MultiPolygon plan footprint (feet) from z0..z1
    and place it in glTF axes (X=x, Y=height, Z=plan-y), like _add_box."""
    import numpy as np
    import trimesh
    if z1 - z0 <= 0 or geom.is_empty:
        return
    polys = getattr(geom, "geoms", [geom])
    M = np.array([[FT, 0, 0, 0], [0, 0, FT, 0], [0, FT, 0, FT * z0], [0, 0, 0, 1.0]])
    for pg in polys:
        if pg.is_empty or pg.area <= 0:
            continue
        m = trimesh.creation.extrude_polygon(pg, height=z1 - z0)
        m.apply_transform(M)
        if m.volume < 0:
            m.invert()
        m.visual.face_colors = rgba
        meshes.append(m)


def build_glb(scene, out_path):
    """Build a .glb from a scene dict (the canonical scene.json)."""
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
        _add_box(meshes, (min(xs), max(xs), min(ys), max(ys), -0.25, 0), _hexrgba("#e8e4da"))  # floor
    openings = scene.get("openings", [])
    for w in walls:
        for b in interval_boxes(w, H, openings):
            _add_box(meshes, b, _hexrgba("#cfcabd"))
    for w in walls_poly:
        for geom, z0, z1 in poly_bands(w, H, openings):
            _add_poly_prism(meshes, geom, z0, z1, _hexrgba("#cfcabd"))
    for c in scene.get("columns", []) + scene.get("ducts", []):
        _add_box(meshes, (c["x"], c["x"] + c["w"], c["y"], c["y"] + c["d"], 0, H), _hexrgba("#9aa0a6"))
    pal = {"bed": "#7f77dd", "sidetable": "#5dcaa5", "cupboard": "#ef9f27",
           "commode": "#378add", "basin": "#1d9e75", "shower": "#85b7eb"}
    for f in scene.get("furniture", []):
        _add_box(meshes, (f["x"], f["x"] + f["w"], f["y"], f["y"] + f["d"], 0, f.get("h", 2.0)),
                 _hexrgba(pal.get(f["type"], "#d85a30")))
    trimesh.Scene(meshes).export(out_path)
    tris = sum(len(m.faces) for m in meshes)
    print(f"wrote {out_path}: {len(meshes)} meshes, {tris} triangles")
    return out_path


def main(scene_path, out_path):
    with open(scene_path) as f:
        build_glb(json.load(f), out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
