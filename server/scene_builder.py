"""Step B - turn wall centre-line segments into the canonical scene.json.

Output is FEET, origin bottom-left, z-up (see docs/SCENE_SCHEMA.md).
Walls only for now; openings/rooms/furniture come in later steps.
Pure Python (unit-tested) - no torch/cv2 needed here.
"""

DEFAULT_WIDTH_FT = 40.0
WALL_HEIGHT_FT = 9.843        # ~3 m
EXT_THICKNESS_FT = 0.75
INT_THICKNESS_FT = 0.4


def scene_from_segments(segments, width_px, height_px, width_ft=DEFAULT_WIDTH_FT):
    """segments: [[x1,y1,x2,y2], ...] wall centre-lines in PIXELS (origin top-left, y down).
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
    for i, (x1, y1, x2, y2) in enumerate(segments):
        horizontal = abs(x2 - x1) >= abs(y2 - y1)
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

    return {
        "meta": {
            "source": "cubicasa detection",
            "units": "ft",
            "wall_height_ft": WALL_HEIGHT_FT,
            "plan_width_ft": round(width_ft, 3),
            "plan_depth_ft": round(height_px * ft_per_px, 3),
            "scale": {"source": "assumed_width", "assumed_width_ft": width_ft, "ft_per_px": ft_per_px},
            "warnings": ["scale is a placeholder (assumed width) until Step 4",
                         "walls only; openings/rooms not yet extracted"],
        },
        "wall_types": {"external": {"thickness_ft": EXT_THICKNESS_FT},
                       "internal": {"thickness_ft": INT_THICKNESS_FT}},
        "rooms": [], "walls": walls, "openings": [], "columns": [], "ducts": [], "furniture": [],
    }
