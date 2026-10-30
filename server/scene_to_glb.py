#!/usr/bin/env python3
"""Migrated from drishti/tools/scene_to_glb.py.
scene.json (feet, z-up) -> real 3D model (.glb). glTF is Y-up, so plan-Z (height)
-> Y and plan-Y (north) -> Z. Walls are tiled into boxes that skip opening voids.

Use as a library:   build_glb(scene_dict, "out.glb")
Or from the CLI:     python scene_to_glb.py scenes/bedroom.scene.json out.glb
"""
import sys
import json
import math

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
    # PLAN-Y MAPS TO -Z (18 Aug 2026, Rahul's ruling). With y-up and east on
    # the right, a camera above looking down puts +Z at the BOTTOM of the
    # screen — so mapping plan-north to +Z rendered every top view MIRRORED
    # north-south. No geometry axis was negated, which is why a coordinate
    # check could not see it; the mirror lived in the view basis. Negating
    # here is the only fix that holds from every camera (§12).
    sx, sy, sz = (x1 - x0) * FT, (z1 - z0) * FT, (y1 - y0) * FT       # Y = height
    cx, cy, cz = (x0 + x1) / 2 * FT, (z0 + z1) / 2 * FT, -(y0 + y1) / 2 * FT
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
    ML). glTF axes: X=plan_x, Y=height, Z=-plan_y (same as _add_box)."""
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
    # the MEASURED hinge (from the arc centre) wins over the low-jamb guess:
    # a door hinged at the far jamb swings from the wrong post without it
    _h = o.get("hinge")
    if isinstance(_h, (list, tuple)) and len(_h) == 2:
        if run_x and abs(_h[0] - x1) < abs(_h[0] - x0):
            hinge = (x1, (y0 + y1) / 2.0)
            rdx = -1.0
        elif (not run_x) and abs(_h[1] - y1) < abs(_h[1] - y0):
            hinge = ((x0 + x1) / 2.0, y1)
            rdy = -1.0
    ang = math.radians(60.0)                 # ajar angle
    # DR-3 (19 Aug 2026): the swing side now comes from the DRAWN ARC, read by
    # pdf_vector.door_swing(). Before this, `hinge` was never set by the parser
    # and every leaf defaulted to +60 deg — right by chance about half the time.
    # `opens_toward` is measured in PLAN space; the -Z mapping already negates
    # the whole rotation below, so the sign is applied here in plan terms.
    # SWING SENSE (20 Aug 2026): `opens_ccw` is the cross product of the drawn
    # symbol's SHUT and OPEN arc ends, in plan — the only unambiguous form.
    # `opens_toward` is measured against the drawn LEAF, which the drafter
    # draws shut on some doors and open on others, so it is not a fixed frame:
    # FLOOR PLAN's two `right` doors needed OPPOSITE signs. Kept as the
    # fallback for openings that carry no arc.
    # plan angle = psi - ang (the -Z mapping negates the rotation), so a
    # counter-clockwise swing needs a NEGATIVE ang.
    if o.get("opens_ccw") is not None:
        ang = -ang if o["opens_ccw"] else ang
    elif o.get("opens_toward") == "right":
        ang = -ang
    elif str(o.get("hinge", "")).endswith("1"):
        ang = -ang                           # legacy ML hint
    phi = math.atan2(-rdy, rdx)              # local +X -> run direction (about Y)
    Wm, Hm, Tm = width * FT, zt * FT, THICK * FT
    tf = trimesh.transformations
    # plan-y -> -Z (18 Aug 2026): the hinge negates like every other point,
    # AND the swing angle negates with it — the flip is a REFLECTION, so a
    # rotation about Y reverses sense; without this the leaf would swing to
    # the wrong side of its own doorway.
    M = (tf.translation_matrix((hinge[0] * FT, 0.0, -hinge[1] * FT))
         @ tf.rotation_matrix(-(phi + ang), (0, 1, 0))
         @ tf.translation_matrix((Wm / 2.0, Hm / 2.0, 0.0)))
    leaf = trimesh.creation.box(extents=(Wm, Hm, Tm), transform=M)
    leaf.visual.face_colors = _DOOR_LEAF
    meshes.append((name, leaf))


def _add_poly_prism(meshes, geom, z0, z1, rgba, name=None):
    """Extrude a shapely Polygon/MultiPolygon plan footprint (feet) from z0..z1
    and place it in glTF axes (X=x, Y=height, Z=-plan-y), like _add_box."""
    import numpy as np
    import trimesh
    if z1 - z0 <= 0 or geom.is_empty:
        return
    polys = getattr(geom, "geoms", [geom])
    # row 2 is NEGATED: plan-y -> -Z, so plan-north renders UP in a top view
    M = np.array([[FT, 0, 0, 0], [0, 0, FT, FT * z0], [0, -FT, 0, 0], [0, 0, 0, 1.0]])
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



# S-6: A STAIRCASE IS ACTUAL STEPS, NOT A BLOCK (1 Sep 2026, Rahul).
#
# THE STAIRCASE IS WHERE THE TREADS ARE DRAWN. My first version built the steps
# from the bbox of a room typed `stairs`, and GHATIKIA showed what that costs:
# the room typed `stairs` there is the LIFT - its one printed label reads
# "LIFT 1.63x1.57" (5.35 x 5.15 ft) - merged along its length with the space
# south of it, so the steps were built INSIDE THE LIFT SHAFT while the real
# flight sat 8 ft to the west. Room TYPE is a guess; the tread ladder is drawn.
#
# `meta.stair_ladders` carries each drawn ladder: its box in scene feet, the
# number of treads, the drawn pitch, and which axis it climbs. Everything below
# comes from those except the riser, and the riser is DERIVED: a staircase
# climbs exactly one storey, so riser = H / (all treads in this staircase).


from stairs import riser_ok, STAIR_MIN_ASPECT   # ONE definition, shared


def _overlaps(room, box):
    """Does a room polygon's bbox overlap a ladder box? Pure."""
    p = room.get("polygon_ft") or []
    if not p:
        return False
    xs, ys = [q[0] for q in p], [q[1] for q in p]
    return (min(max(xs), box[2]) > max(min(xs), box[0])
            and min(max(ys), box[3]) > max(min(ys), box[1]))


def _stair_cores(ladders):
    """Group drawn ladders into staircases: a dog-leg's two flights meet at a
    landing, so their boxes touch. Connected components under "boxes within one
    tread pitch of each other". Pure."""
    out = []
    for L in ladders:
        b, p = L["box_ft"], max(L.get("pitch_ft") or 0.0, 0.1)
        hit = [c for c in out
               if any(min(b[2], o["box_ft"][2]) - max(b[0], o["box_ft"][0]) >= -p
                      and min(b[3], o["box_ft"][3]) - max(b[1], o["box_ft"][1]) >= -p
                      for o in c)]
        if hit:
            hit[0].append(L)
            for extra in hit[1:]:           # this ladder joins two components
                hit[0].extend(extra)
                out.remove(extra)
        else:
            out.append([L])
    return out


def _stair_steps(core, H):
    """One staircase (list of drawn ladders) -> (steps, why). Steps are
    (x0, x1, y0, y1, z0, z1).

    The riser is the only assumed number and it is derived, not chosen: the
    flights of one staircase climb one storey between them, so
    riser = H / total treads drawn. Tread depth, width, position and count are
    all the drawing's own.

    ponytail: flight ORDER and climb DIRECTION are read from the shared landing
    (a flight climbs toward the next flight's box), which is right for a
    dog-leg; a single detected flight defaults to climbing +along, since the UP
    arrow is not read yet. Read the arrow if a plan ever climbs the wrong way.
    """
    n_tot = sum(int(L["treads"]) for L in core)
    if n_tot < 2:
        return [], "fewer than 2 treads drawn"
    riser = H / n_tot
    # THE DERIVED RISER IS ALSO THE CHECK. A staircase climbs one storey, so
    # H / (treads drawn) must come out a riser a person can walk. When it does
    # not, we have not found all the flights, and building what we did find
    # would put a visibly wrong staircase in the model. The band is the human
    # one (NBC/IS residential riser 150-190 mm = 5.9-7.5 in), widened to
    # 5.0-9.0 in so a real stair is never refused; it REFUSES, it never selects.
    if not riser_ok(riser):
        return [], (f"{n_tot} treads drawn over {len(core)} flight(s) implies a "
                    f"{riser * 12:.1f} in riser - not a riser, so flights are "
                    f"missing; refusing to build a staircase we cannot place")
    order = sorted(core, key=lambda L: (L["box_ft"][1], L["box_ft"][0]))
    steps, done = [], 0
    for f, L in enumerate(order):
        x0, y0, x1, y1 = L["box_ft"]
        n = int(L["treads"])
        along_x = L.get("climbs") == "x"
        lo, hi = (x0, x1) if along_x else (y0, y1)
        nxt = order[f + 1] if f + 1 < len(order) else (order[f - 1] if f else None)
        up = True
        if nxt is not None:
            c = (nxt["box_ft"][0] + nxt["box_ft"][2]) / 2.0 if along_x else \
                (nxt["box_ft"][1] + nxt["box_ft"][3]) / 2.0
            up = (c > (lo + hi) / 2.0) if f + 1 < len(order) else \
                 (c < (lo + hi) / 2.0)
        t = (hi - lo) / n
        for i in range(n):
            k = i if up else n - 1 - i
            a, b = lo + k * t, lo + (k + 1) * t
            box = (a, b, y0, y1, 0.0, (done + i + 1) * riser) if along_x else \
                  (x0, x1, a, b, 0.0, (done + i + 1) * riser)
            steps.append(box)
        done += n
    return steps, (f"{n_tot} risers of {riser * 12:.1f} in over "
                   f"{len(core)} drawn flight(s), treads "
                   + " + ".join(f"{int(L['treads'])} at "
                                f"{L['pitch_ft'] * 12:.1f} in" for L in order))


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
    # THE SLAB IS THE FOOTPRINT, NOT THE BOUNDING BOX (1 Sep 2026, Rahul).
    # It used to be `min(xs)..max(xs) x min(ys)..max(ys)` - the wall EXTENT -
    # on the reasoning that one wing's wall extent is its footprint. It is not:
    # a building is not a rectangle. Measured on the defect sheet, the slab ran
    # +66% over the footprint on neelachala FIRST FLOOR (7396 against 4463
    # sqft), +58% on FLOOR PLAN, +47% on GHATIKIA and +21% on BRICK WORK - it
    # floored every L-shaped notch and the whole gap between FIRST FLOOR's two
    # blocks. `footprint_ft` is the outer wall ring and is already in this
    # frame, so the slab is simply that polygon.
    _fp_poly = scene.get("footprint_ft") or []
    _slab = None
    if len(_fp_poly) >= 3:
        try:
            from shapely.geometry import Polygon as _SPoly
            _slab = _SPoly(_fp_poly)
            if not _slab.is_valid:
                _slab = _slab.buffer(0)
        except Exception:
            _slab = None
    if _slab is not None and not _slab.is_empty:
        _add_poly_prism(meshes, _slab, -0.25, 0.0,
                        _hexrgba("#e8e4da"), name="floor")
    elif xs:
        # no footprint polygon (a scene with walls but no ring): fall back to
        # the old extent box rather than leaving the model with no ground
        _add_box(meshes, (min(xs), max(xs), min(ys), max(ys), -0.25, 0),
                 _hexrgba("#e8e4da"), name="floor")
    # UNVERIFIED openings build NOTHING and cut NOTHING (31 Aug 2026,
    # Rahul). Dropped here rather than at each use, because `poly_bands`
    # cuts for ANY opening carrying a footprint regardless of type - a wall
    # cut at an unverified position asserts placement just as loudly as a
    # door leaf does.
    openings = [o for o in scene.get("openings", [])
                if not o.get("unverified")]
    # --- RAILINGS AND THE SPACES BEHIND THEM (20 Aug 2026, B-4) -------------
    # `scene.railings` was read by NOTHING, so no balcony or utility reached
    # the 3D. Flat-2's balcony looked built only because its railing is a thin
    # double line 3.0 in apart, which is exactly `wall_rects`'s 3 in floor: it
    # pairs as a WALL and was extruded full height on an OPEN face, against
    # B-4. Here a classified railing run becomes a half-wall at RAIL_FT, its
    # pocket gets a floor slab, and any wall material lying along the run is
    # cut down to the same height instead of standing full storey.
    RAIL_FT, RAIL_T = 3.5, 0.25
    _rail_runs = [r for r in (scene.get("railings") or {}).get("runs", [])
                  if r.get("classification") == "railing"]
    _rail_zone = None
    _pockets = []
    try:
        from shapely.geometry import LineString as _RL
        from shapely.ops import unary_union as _ruu
        _segs = []
        for r in _rail_runs:
            pl = r.get("polyline_ft") or []
            for a, b in zip(pl[0::2], pl[1::2]):
                if math.dist(a, b) > 0.1:
                    _segs.append(_RL([a, b]).buffer(RAIL_T / 2.0, cap_style=2))
            if r.get("pocket_ft"):
                _pockets.append(r["pocket_ft"])
        _rail_zone = _ruu(_segs) if _segs else None
    except Exception:
        _rail_zone = None
    for k, pk in enumerate(_pockets):        # balcony / utility floor
        _add_box(meshes, (pk[0], pk[2], pk[1], pk[3], -0.25, 0),
                 _hexrgba("#e8e4da"), name=f"floor_open_{k}")
    for i, w in enumerate(walls):
        for j, b in enumerate(interval_boxes(w, H, openings)):
            _add_box(meshes, b, _hexrgba("#cfcabd"), name=f"wall_{i}_{j}")
    for i, w in enumerate(walls_poly):
        _cut = None
        if _rail_zone is not None:
            try:
                from shapely.geometry import Polygon as _RP
                _g = _RP(w["outer"], w.get("holes") or [])
                _ov = _g.intersection(_rail_zone)
                if _ov.area > 0.05:
                    _cut = _ov
                    _rest = _g.difference(_rail_zone)
                    if _rest.is_empty or _rest.area < 0.1 * _g.area:
                        w = None            # the polygon WAS the railing
                    elif _rest.geom_type == "Polygon":
                        w = dict(w, outer=list(_rest.exterior.coords)[:-1],
                                 holes=[list(r.coords)[:-1] for r in _rest.interiors])
            except Exception:
                _cut = None
        if w is not None:
            for j, (geom, z0, z1) in enumerate(poly_bands(w, H, openings)):
                _add_poly_prism(meshes, geom, z0, z1, _hexrgba("#cfcabd"),
                                name=f"wall_p{i}_{j}")
        if _cut is not None and not _cut.is_empty:
            _add_poly_prism(meshes, _cut, 0.0, RAIL_FT, _hexrgba("#b9b3a4"),
                            name=f"rail_w{i}")
    if _rail_zone is not None and not _rail_zone.is_empty:
        _add_poly_prism(meshes, _rail_zone, 0.0, RAIL_FT, _hexrgba("#b9b3a4"),
                        name="railing")
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
    for i, c in enumerate(scene.get("columns", [])):
        _add_box(meshes, (c["x"], c["x"] + c["w"], c["y"], c["y"] + c["d"], 0, H),
                 _hexrgba("#9aa0a6"), name=f"column_{i}")
    # A DUCT IS A VOID, AND IT IS NOT A COLUMN (1 Sep 2026, Rahul). Ducts used
    # to be concatenated onto the column list and built as SOLID full-height
    # boxes named `column_i` - so a shaft became structure, and the name hid it
    # from anything reading mesh names. 4 D-5 says a duct is never solid.
    # It is built as a thin SHAFT WALL ring instead: the drawn rectangle's
    # edges, leaving the void open, and named `duct_i` so the viewer and the
    # g-buffer can class it. Currently latent - `scene["ducts"]` is empty on all
    # four corpus sheets, though FLOOR PLAN detects two ducts as void ROOMS.
    for i, c in enumerate(scene.get("ducts", [])):
        x0, y0 = c["x"], c["y"]
        x1, y1 = x0 + c["w"], y0 + c["d"]
        t = min(0.25, c["w"] / 3.0, c["d"] / 3.0)
        for k, b in enumerate(((x0, x1, y0, y0 + t), (x0, x1, y1 - t, y1),
                               (x0, x0 + t, y0, y1), (x1 - t, x1, y0, y1))):
            _add_box(meshes, (b[0], b[1], b[2], b[3], 0, H),
                     _hexrgba("#9aa0a6"), name=f"duct_{i}_{k}")
    # TERRACE over a joined band (Q3, 1 Sep 2026, Rahul). Where two blocks
    # of one building were merged because ink crosses the band between
    # them, that band is a TERRACE on this floor and carries a slab - on
    # neelachala FIRST FLOOR it is the first-floor terrace the design uses
    # to reach its parking count under the FAR limit, so it is structural.
    # The slab is only ever the band we actually merged across; a sheet
    # with no join builds none, which is why nothing else gains one.
    _rg = (scene.get("meta", {}).get("regions") or [{}])[0]
    for i, bf in enumerate((_rg.get("join_evidence") or {})
                           .get("joined_bands_ft") or []):
        if bf and bf[2] > bf[0] and bf[3] > bf[1]:
            _add_box(meshes, (bf[0], bf[2], bf[1], bf[3], -0.25, 0),
                     _hexrgba("#ded9cc"), name=f"terrace_{i}")

    # CHHAJJA — ABOVE THE CUT PLANE (T-1, 7 Sep 2026, Rahul). A sunshade is not
    # cut by the 4 ft section plane, so the plan states only its EXTENT and it
    # must never be built as storey-height material. It is placed at LINTEL
    # LEVEL, matching the door head, as a thin projecting slab of its own drawn
    # depth. neelachala FIRST FLOOR draws 403 items over 158 ft of hatch and
    # built NOTHING until now - not built wrong, not built at all.
    CHHAJJA_T = 0.4                       # slab thickness, ft
    # lintel level: the scene's own door head, so the sunshade sits with the
    # openings it shades rather than at a number chosen here
    _lintel = max((o.get("z") or [0, 0])[1] for o in (scene.get("openings") or [])
                  if o.get("type") == "door") if any(
        o.get("type") == "door" for o in (scene.get("openings") or [])) else 7.0
    for i, c in enumerate(scene.get("chhajja") or []):
        b = c.get("box_ft") or []
        if len(b) < 4 or b[2] <= b[0] or b[3] <= b[1]:
            continue
        _add_box(meshes, (b[0], b[2], b[1], b[3],
                          _lintel, _lintel + CHHAJJA_T),
                 _hexrgba("#cfc9ba"), name=f"chhajja_{i}")

    # STAIRS: actual steps at the DRAWN treads (S-6). A sheet that draws no
    # tread ladder builds NO staircase and says so - a staircase in the wrong
    # place is worse than an absent one, and a room typed `stairs` is not
    # evidence of one (GHATIKIA's is the lift).
    _stair_report = []
    for i, core in enumerate(_stair_cores(
            (scene.get("meta") or {}).get("stair_ladders") or [])):
        steps, why = _stair_steps(core, H)
        _stair_report.append({"flights": len(core), "at_ft": core[0]["box_ft"],
                              "built": bool(steps), "why": why})
        for k, b in enumerate(steps):
            _add_box(meshes, b, _hexrgba("#b8bcc4"), name=f"stair_{i}_{k}")
    for rm in scene.get("rooms", []):
        if rm.get("type") == "stairs" and not any(
                r.get("at_ft") and _overlaps(rm, r["at_ft"]) for r in _stair_report):
            _stair_report.append({"room_sqft": rm.get("area_sqft"), "built": False,
                                  "why": "room typed `stairs`, no drawn tread "
                                         "ladder inside it"})
    try:
        scene.setdefault("meta", {})["stairs_built"] = _stair_report
    except Exception:
        pass
    for i, f in enumerate(scene.get("furniture", [])):
        # never stage furniture into a balcony/utility pocket — a bed was
        # standing in flat-1's utility (20 Aug 2026)
        if any(pk[0] - 0.2 <= f.get("x", 0) <= pk[2] + 0.2
               and pk[1] - 0.2 <= f.get("y", 0) <= pk[3] + 0.2 for pk in _pockets):
            continue
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
    # M-2 ON `meta.glb` (5 Sep 2026, Rahul). Computed HERE because this is the
    # only place the meshes and the scene exist together - one computation, one
    # owner, consumed by the scorecard rather than re-derived there (the
    # `wing_at` / `wing_pick` trap). Carries its own units and axis convention.
    try:
        from model_check import model_check
        scene.setdefault("meta", {})["glb"] = model_check(scene, meshes, H)
    except Exception as _e:
        scene.setdefault("meta", {})["glb"] = {"error": str(_e)[:120]}
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
