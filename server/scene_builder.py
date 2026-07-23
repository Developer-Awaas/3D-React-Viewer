"""Step B - turn wall centre-line segments into the canonical scene.json.

Output is FEET, origin bottom-left, z-up (see docs/SCENE_SCHEMA.md).
Step B2 adds: openings (doors/windows cut into walls) and corner snapping
(wall footprints extended to actually meet at junctions).
Pure Python (unit-tested) - no torch/cv2 needed here.
"""

DEFAULT_WIDTH_FT = 40.0
WALL_HEIGHT_FT = 9.843        # ~3 m
EXT_THICKNESS_FT = 0.75
INT_THICKNESS_FT = 0.4
DOOR_HEAD_FT = 7.0            # lintel level 7'0" (Indian practice)
WINDOW_SILL_FT = 3.0          # sill 3'0" (locked convention)
WINDOW_HEAD_FT = 7.0          # lintel level 7'0" = door head
CORNER_TOL_FT = 1.0           # max gap closed when snapping corners
MIN_OPENING_FT = 0.15


def _snap_corners(walls, tol=CORNER_TOL_FT):
    """Extend wall footprints so perpendicular walls meet at junctions
    (centre-line walls otherwise leave a gap of ~half a thickness)."""
    xw = [w for w in walls if w["axis"] == "x"]
    yw = [w for w in walls if w["axis"] == "y"]
    for a in xw:
        yc = (a["y0"] + a["y1"]) / 2.0
        for b in yw:
            if not (b["y0"] - tol <= yc <= b["y1"] + tol):
                continue                     # b doesn't vertically reach a
            if 0 <= a["x0"] - b["x1"] <= tol or b["x0"] <= a["x0"] <= b["x1"]:
                a["x0"] = min(a["x0"], b["x0"])
            if 0 <= b["x0"] - a["x1"] <= tol or b["x0"] <= a["x1"] <= b["x1"]:
                a["x1"] = max(a["x1"], b["x1"])
    for b in yw:
        xc = (b["x0"] + b["x1"]) / 2.0
        for a in xw:
            if not (a["x0"] - tol <= xc <= a["x1"] + tol):
                continue                     # a doesn't horizontally reach b
            if 0 <= b["y0"] - a["y1"] <= tol or a["y0"] <= b["y0"] <= a["y1"]:
                b["y0"] = min(b["y0"], a["y0"])
            if 0 <= a["y0"] - b["y1"] <= tol or a["y0"] <= b["y1"] <= a["y1"]:
                b["y1"] = max(b["y1"], a["y1"])
    for w in walls:
        for k in ("x0", "x1", "y0", "y1"):
            w[k] = round(w[k], 3)


# G4: nominal footprints (ft) for fixtures placed from CubiCasa icons — the
# drawn symbol size is unreliable, so we stamp a real-world size at the icon
# centroid. (w, d) in feet.
_FURN_SIZE_FT = {
    "commode": (1.5, 2.2),
    "basin": (1.3, 1.0),
    "bathtub": (2.5, 5.0),
    "cupboard": (2.0, 2.0),
}


def scene_from_segments(segments, width_px, height_px, width_ft=DEFAULT_WIDTH_FT,
                        openings=None, rooms_px=None, furniture_px=None):
    """segments: [[x1,y1,x2,y2], ...] wall centre-lines in PIXELS (origin top-left, y down).
    openings: optional [{"type": "door"|"window", "seg": <segment index>,
    "along": [a, b] px}, ...] from openings.attach_openings().
    rooms_px: optional typed room regions in PIXELS (E5, from
    perception.rooms_from_pred): [{"type","cx","cy","area_px"}, ...]. Converted
    to feet rooms so the ML path ships typed, furnishable, Vastu-scorable rooms.
    Returns a canonical scene.json dict (feet, origin bottom-left, z up)."""
    ft_per_px = (width_ft / width_px) if width_px else 1.0

    xs = [c for s in segments for c in (s[0], s[2])]
    ys = [c for s in segments for c in (s[1], s[3])]
    minx, maxx = (min(xs), max(xs)) if xs else (0, 0)
    miny, maxy = (min(ys), max(ys)) if ys else (0, 0)
    edge_tol = 0.06 * max(width_px, height_px, 1)   # "near the outer boundary" = external

    def fx(px):
        return round(px * ft_per_px, 3)

    def fy(py):
        return round((height_px - py) * ft_per_px, 3)   # flip Y (top-left -> bottom-left)

    walls = []
    horiz = []                                  # per segment: is it an axis-x wall?
    for i, (x1, y1, x2, y2) in enumerate(segments):
        horizontal = abs(x2 - x1) >= abs(y2 - y1)
        horiz.append(horizontal)
        if horizontal:
            p = (y1 + y2) / 2.0
            a, b = sorted((x1, x2))
            external = abs(p - miny) <= edge_tol or abs(p - maxy) <= edge_tol
            th = EXT_THICKNESS_FT if external else INT_THICKNESS_FT
            cy = fy(p)
            walls.append({"id": f"w{i}", "axis": "x",
                          "x0": fx(a), "x1": fx(b),
                          "y0": round(cy - th / 2, 3), "y1": round(cy + th / 2, 3),
                          "type": "external" if external else "internal"})
        else:
            p = (x1 + x2) / 2.0
            a, b = sorted((y1, y2))
            external = abs(p - minx) <= edge_tol or abs(p - maxx) <= edge_tol
            th = EXT_THICKNESS_FT if external else INT_THICKNESS_FT
            cx = fx(p)
            ya, yb = sorted((fy(a), fy(b)))
            walls.append({"id": f"w{i}", "axis": "y",
                          "x0": round(cx - th / 2, 3), "x1": round(cx + th / 2, 3),
                          "y0": ya, "y1": yb,
                          "type": "external" if external else "internal"})

    _snap_corners(walls)

    H = WALL_HEIGHT_FT
    out_openings = []
    for op in (openings or []):
        k = op["seg"]
        if not (0 <= k < len(walls)):
            continue
        w = walls[k]
        a_px, b_px = op["along"]
        if horiz[k]:
            lo, hi = sorted((fx(a_px), fx(b_px)))
            lo, hi = max(lo, w["x0"]), min(hi, w["x1"])
        else:
            lo, hi = sorted((fy(a_px), fy(b_px)))    # y-flip reverses the interval
            lo, hi = max(lo, w["y0"]), min(hi, w["y1"])
        if hi - lo < MIN_OPENING_FT:
            continue
        rec = {"id": f"o{len(out_openings)}", "type": op["type"], "wall": w["id"],
               "along": [round(lo, 3), round(hi, 3)]}
        if op["type"] == "door":
            rec["z"] = [0, round(min(DOOR_HEAD_FT, H), 3)]
            rec["hinge"] = "x0"
            rec["swing"] = "in"
        else:
            rec["z"] = [round(min(WINDOW_SILL_FT, H / 2), 3),
                        round(min(WINDOW_HEAD_FT, H), 3)]
        out_openings.append(rec)

    # E5: typed rooms from the ML room-type map (px -> ft, same Y-flip as walls)
    rooms = []
    for i, r in enumerate(rooms_px or []):
        cx, cy = float(r.get("cx", 0)), float(r.get("cy", 0))
        area_px = float(r.get("area_px", 0) or 0)
        rooms.append({
            "id": f"r{i}",
            "type": r.get("type"),
            "x": fx(cx),
            "y": fy(cy),
            "area_sqft": round(area_px * ft_per_px * ft_per_px, 1),
        })
    rooms.sort(key=lambda r: -r["area_sqft"])

    # G4: fixture furniture from CubiCasa icons — a nominal real-world footprint
    # centred on each icon (px -> ft, same Y-flip as walls/rooms).
    furniture = []
    for f in (furniture_px or []):
        w_ft, d_ft = _FURN_SIZE_FT.get(f.get("type"), (1.5, 1.5))
        cx, cy = float(f.get("cx", 0)), float(f.get("cy", 0))
        cx_ft, cy_ft = cx * ft_per_px, (height_px - cy) * ft_per_px
        furniture.append({
            "type": f["type"],
            "x": round(cx_ft - w_ft / 2, 3),
            "y": round(cy_ft - d_ft / 2, 3),
            "w": w_ft, "d": d_ft, "staged": True,
        })

    warnings = ["scale is a placeholder (assumed width) until Step 4"]
    if not rooms:
        warnings.append("rooms/furniture not yet extracted")
    return {
        "meta": {
            "source": "cubicasa detection",
            "units": "ft",
            "wall_height_ft": WALL_HEIGHT_FT,
            "plan_width_ft": round(width_ft, 3),
            "plan_depth_ft": round(height_px * ft_per_px, 3),
            "scale": {"source": "assumed_width", "assumed_width_ft": width_ft, "ft_per_px": ft_per_px},
            "warnings": warnings,
        },
        "wall_types": {"external": {"thickness_ft": EXT_THICKNESS_FT},
                       "internal": {"thickness_ft": INT_THICKNESS_FT}},
        "rooms": rooms, "walls": walls, "openings": out_openings,
        "columns": [], "ducts": [], "furniture": furniture,
    }
