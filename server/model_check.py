"""M-2: DOES THE MODEL MATCH THE PARSE? (5 Sep 2026, Rahul)

Every instrument we have measures the PARSE. Nothing measured what is BUILT,
and the two came apart badly: FLOOR PLAN read R-8 96.5 while its slab was 58%
too large, it had no staircase and no ceiling. Right numbers, wrong building.

This is the parser half of the GLB instrument the scorecard specced on 27 Aug.
It compares the built meshes against the scene they were built FROM, so it
needs no ground truth and no human reading an image - it can run on any sheet,
including one where every printed instrument is blind.

Meshes arrive as (name, trimesh) in METRES, Y-up, with plan-y mapped to -Z
(the 18 Aug ruling). Everything below is converted back to FEET and plan
coordinates so a number can be compared with the drawing.
"""
FT = 0.3048
M2_TO_SQFT = 1.0 / (FT * FT)
M3_TO_CUFT = 1.0 / (FT ** 3)


def _plan_bbox(mesh):
    """A mesh's extent in PLAN feet: (x0, y0, x1, y1). Undoes plan-y -> -Z."""
    lo, hi = mesh.bounds
    return (lo[0] / FT, -hi[2] / FT, hi[0] / FT, -lo[2] / FT)


def _family(name):
    out = []
    for ch in str(name):
        if ch.isdigit():
            break
        out.append(ch)
    return "".join(out).rstrip("_") or "?"


def model_check(scene, meshes, wall_height_ft=9.843):
    """(scene, [(name, mesh)]) -> M-2 report. Pure apart from mesh geometry."""
    import collections
    from shapely.geometry import Polygon, box

    meta = scene.get("meta", {}) or {}
    fp_ft = scene.get("footprint_ft") or []
    fp = Polygon(fp_ft).buffer(0) if len(fp_ft) >= 3 else None
    fp_sqft = float(meta.get("footprint_sqft") or (fp.area if fp else 0.0))

    fam = collections.Counter(_family(n) for n, _ in meshes)
    floor = [m for n, m in meshes if _family(n) in ("floor", "floor_open", "terrace")]
    built_floor = sum(abs(m.area_faces.sum()) for m in floor) / 2.0 * M2_TO_SQFT \
        if floor else 0.0
    # a slab is a thin prism: its plan area is half its surface area
    vol = sum(abs(m.volume) for _, m in meshes) * M3_TO_CUFT

    outside = []
    tot_area = out_area = 0.0
    if fp is not None:
        for n, m in meshes:
            if _family(n) in ("floor", "terrace"):
                continue                       # the slab IS the footprint
            b = box(*_plan_bbox(m))
            if b.area <= 0:
                continue
            frac = 1.0 - (b.intersection(fp).area / b.area)
            tot_area += b.area
            out_area += b.area * frac
            if frac > 0.5:
                outside.append({"mesh": n, "outside_pct": round(100 * frac, 1),
                                "at_ft": [round(v, 1) for v in _plan_bbox(m)]})

    # SCENE ELEMENT -> MESH FAMILY. A count on each side; a zero on either is
    # the finding (an element built as nothing, or a mesh from nothing).
    doors = [o for o in (scene.get("openings") or [])
             if o.get("type") == "door" and not o.get("unverified")]
    expect = {
        "walls_poly": (len(scene.get("walls_poly") or []), fam.get("wall_p", 0)),
        "doors": (len(doors), fam.get("door", 0)),
        "columns": (len(scene.get("columns") or []), fam.get("column", 0)),
        "ducts": (len(scene.get("ducts") or [])
                  + sum(1 for r in (scene.get("rooms") or [])
                        if r.get("type") == "duct"), fam.get("duct", 0)),
        "railings": (len(scene.get("railings") or []), fam.get("railing", 0)),
        "furniture": (len(scene.get("furniture") or []),
                      sum(v for k, v in fam.items() if k.startswith("furn"))),
        "stairs_rooms": (sum(1 for r in (scene.get("rooms") or [])
                             if r.get("type") == "stairs"), fam.get("stair", 0)),
    }
    unbuilt = {k: v for k, v in expect.items() if v[0] and not v[1]}
    orphan = {k: v for k, v in expect.items() if v[1] and not v[0]}

    # ORIENTATION, on a feature the drawing places asymmetrically: each door's
    # PLAN position against its own mesh's plan position. A mirror or a swapped
    # axis shows here as a large, systematic error; nothing else does.
    errs, pairs_xy = [], []
    # PAIR BY INDEX, NOT BY NEAREST. `scene_to_glb` names each leaf `door_{i}`
    # from the same filtered opening list, so the index IS the identity - and
    # nearest-matching is worse than useless here: it finds a mesh beside every
    # cut whatever the model does, which made the slope read ~1.0 on all eight
    # sheets and on a deliberately stretched fixture. A metric that cannot come
    # out wrong is not a metric.
    dm = {}
    for n, m in meshes:
        if _family(n) != "door":
            continue
        tail = "".join(c for c in str(n)[5:] if c.isdigit() or c == "_").split("_")
        try:
            dm[int(tail[0])] = m
        except (ValueError, IndexError):
            pass
    # SAME INDEX SPACE as the builder: `scene_to_glb` filters only unverified
    # openings and then enumerates, so windows occupy indices too. Indexing the
    # door-only list instead paired door 3 with mesh 3 of a different list and
    # reported a 17 ft median error on FLOOR PLAN - a pairing artefact, caught
    # because a 17 ft error on a 95 ft plan is not a defect anyone could have
    # missed in the viewer.
    for _i, o in enumerate([q for q in (scene.get("openings") or [])
                            if not q.get("unverified")]):
        if o.get("type") != "door":
            continue
        # a door carries no x/y; its `footprint` is the CUT rectangle in plan
        f = o.get("footprint") or o.get("swing_area")
        if not f or len(f) < 4 or _i not in dm:
            continue
        ox, oy = (f[0] + f[2]) / 2.0, (f[1] + f[3]) / 2.0
        b = _plan_bbox(dm[_i])
        errs.append(round(((((b[0] + b[2]) / 2 - ox) ** 2
                            + ((b[1] + b[3]) / 2 - oy) ** 2) ** 0.5), 2))
        pairs_xy.append(((b[1] + b[3]) / 2.0, oy))
    errs.sort()
    # THE OFFSET ALONE IS NOT A DEFECT AND MUST NOT BE READ AS ONE: a door mesh
    # is the LEAF swung open, so its bbox centre sits about half a leaf from
    # the cut it belongs to - which is exactly the ~1.5 ft seen on every sheet.
    #
    # The SLOPE of mesh-y on cut-y is the axis check: 1.0 means plan-y maps to
    # the model one-for-one, and a value away from 1 is a SCALE or unit error
    # in that axis. IT CANNOT SEE A GLOBAL MIRROR, and saying so matters: the
    # meshes are matched to cuts by NEAREST, so a mirrored model still finds a
    # mesh beside every cut. That is the same blind spot §12 records for
    # 18 Aug - "no geometry axis was negated, which is why a coordinate check
    # could not see it"; only a render caught it.
    slope = None
    if len(pairs_xy) >= 3:
        my = sum(p[0] for p in pairs_xy) / len(pairs_xy)
        mx = sum(p[1] for p in pairs_xy) / len(pairs_xy)
        den = sum((p[1] - mx) ** 2 for p in pairs_xy)
        if den > 1e-9:
            slope = round(sum((p[0] - my) * (p[1] - mx) for p in pairs_xy) / den, 3)

    # WALL VOLUME RATIO: built wall prisms against `walls_poly` x storey. Below
    # 1.0 is CORRECT - openings cut material out - so this reads 0.78-0.98
    # across the corpus, not the 1.75-2.11 a double-built wall would give.
    wall_ratio = None
    try:
        from shapely.ops import unary_union
        wp = unary_union([Polygon(w["outer"], w.get("holes") or []).buffer(0)
                          for w in (scene.get("walls_poly") or [])])
        wv = sum(abs(m.volume) for n, m in meshes
                 if _family(n).startswith("wall")) * M3_TO_CUFT
        if wp.area > 0 and wall_height_ft:
            wall_ratio = round(wv / (wp.area * wall_height_ft), 3)
    except Exception:
        pass
    # MISSING: of the element kinds the scene actually carries, how many build
    # NOTHING. A share, so it is comparable across sheets of different size.
    present = [k for k, v in expect.items() if v[0]]
    missing_pct = round(100.0 * len(unbuilt) / len(present), 1) if present else None
    # SEG-UNCLASSIFIED: mesh area whose family maps to no gbuffer class. The
    # list mirrors `src/three/gbuffer.ts`; a family missing there paints as
    # `other` and corrupts the render conditioning maps (fixed 1 Sep).
    known = ("wall", "floor", "door", "window", "glass", "column", "duct",
             "railing", "rail", "stair", "terrace", "furn")
    seg_a = seg_bad = 0.0
    for n, m in meshes:
        f = _family(n)
        a = abs(m.area) or 0.0
        seg_a += a
        if not any(f.startswith(k) for k in known):
            seg_bad += a
    seg_pct = round(100.0 * seg_bad / seg_a, 1) if seg_a else None

    return {
        # UNITS AND AXIS, STATED IN THE FIELD (5 Sep 2026, Rahul): the scorecard
        # lost a measurement comparing metres against feet, and a number without
        # its frame is what cost it.
        "units": {"length": "ft", "area": "sqft", "volume": "cuft",
                  "angle": "deg", "pct": "percent 0-100"},
        "axis": ("scene/plan feet: +x EAST, +y NORTH, origin at the built "
                 "wing after the crop shift. The GLB itself is METRES and "
                 "Y-up with plan-y mapped to -Z; every number here is "
                 "converted back to plan feet before it is reported."),
        "built_floor_sqft": round(built_floor, 1),
        "footprint_sqft": round(fp_sqft, 1),
        "floor_vs_footprint_pct": round(100 * built_floor / fp_sqft, 1) if fp_sqft else None,
        "built_volume_cuft": round(vol, 1),
        "expected_volume_cuft": round(fp_sqft * wall_height_ft, 1),
        "volume_vs_expected_pct": round(100 * vol / (fp_sqft * wall_height_ft), 1)
        if fp_sqft else None,
        "meshes": len(meshes),
        "meshes_outside_footprint": len(outside),
        "outside_examples": outside[:3],
        "element_vs_mesh": expect,
        "built_as_nothing": unbuilt,
        "mesh_from_nothing": orphan,
        # OFFSET is expected (~half a leaf); SLOPE is the orientation test
        "door_plan_error_ft": {"n": len(errs),
                               "median": errs[len(errs) // 2] if errs else None,
                               "max": errs[-1] if errs else None,
                               "note": "a door mesh is the leaf swung open, so "
                                       "~half a leaf of offset is expected"},
        "placement_slope_y": slope,
        # THE FIVE THE SCORECARD CONSUMES - one computation, one owner
        "outside_footprint_pct": round(100.0 * out_area / tot_area, 1) if tot_area else None,
        "wall_volume_ratio": wall_ratio,
        "orphan_meshes": sum(v[1] for v in orphan.values()),
        "missing_pct": missing_pct,
        "seg_unclassified_pct": seg_pct,
    }
