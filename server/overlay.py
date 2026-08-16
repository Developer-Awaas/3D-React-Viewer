"""PHASE 0 — the WALL OVERLAY instrument: parsed geometry drawn over the
original drawing, in the drawing's own coordinates.

Why it exists: R-8 measures areas and R-2 measures room sizes. Neither can
tell us a wall is in the WRONG PLACE — a wall 2 ft out and a wall missing
entirely can both leave the area statement looking healthy. Every geometry
phase needs to see where the parsed lines actually land, so the instrument
comes before the fix, exactly as R-8 did for the numbers.

Two design rules:
  * A layer with no data yet (railing, plot boundary, setback) is emitted
    EMPTY, never omitted — an absent layer looks like a layer that found
    nothing, and the difference matters.
  * The REJECTED line work is a layer of its own. An overlay that draws only
    what was found cannot show a missing wall; the wall we failed to read is
    by definition in the discard pile.

Everything here is PURE (scene in, coordinates out) so the registration maths
is unit-tested — a mis-registered overlay lies convincingly, which is worse
than no overlay at all.
"""

# colour key, kept next to the geometry so the UI and any exported PNG agree
LAYER_STYLE = {
    "walls":          {"colour": "#22d3ee", "kind": "polygon", "width": 1.5},
    "railing":        {"colour": "#a3e635", "kind": "line", "width": 1.5},
    "columns":        {"colour": "#f97316", "kind": "rect", "width": 1.5},
    "doors":          {"colour": "#22c55e", "kind": "rect", "width": 2.0},
    "windows":        {"colour": "#3b82f6", "kind": "rect", "width": 2.0},
    "rooms":          {"colour": "#e879f9", "kind": "polygon", "width": 1.2},
    "footprint":      {"colour": "#facc15", "kind": "polygon", "width": 2.5},
    # the EXTENDED ring (closed across rejected open faces). Balcony = the area
    # between this and `footprint` — see §0.1 on mask differences.
    "footprint_ext":  {"colour": "#fb923c", "kind": "polygon", "width": 2.0},
    "plot_boundary":  {"colour": "#f43f5e", "kind": "line", "width": 2.0},
    "setback":        {"colour": "#fb7185", "kind": "line", "width": 1.5},
    "rejected":       {"colour": "#94a3b8", "kind": "line", "width": 0.8},
    # §10.2 D-7: where each dimension arrow LANDS, against what we detected.
    # Green = on a detected wall face; amber = near it; RED = the arrow points
    # at nothing we found, which means the parse is wrong THERE (or the
    # extraction followed the wrong line — the picture is what tells them apart).
    "dim_anchor_hit":  {"colour": "#22c55e", "kind": "polygon", "width": 1.5},
    "dim_anchor_near": {"colour": "#f59e0b", "kind": "polygon", "width": 1.5},
    "dim_anchor_miss": {"colour": "#ef4444", "kind": "polygon", "width": 2.5},
    # W-2 MEASUREMENT: every wall pair coloured by its measured gap, so a
    # cluster in the histogram can be LOCATED on the drawing. A histogram says
    # a cluster exists; it cannot say what the cluster is.
    "gap_1_3in":      {"colour": "#f472b6", "kind": "line", "width": 2.0},
    "gap_4_5in":      {"colour": "#38bdf8", "kind": "line", "width": 2.0},
    "gap_9_11in":     {"colour": "#4ade80", "kind": "line", "width": 2.0},
    "gap_12in":       {"colour": "#ef4444", "kind": "line", "width": 2.5},
    "gap_other":      {"colour": "#eab308", "kind": "line", "width": 2.0},
}

GAP_CLASSES = (("gap_1_3in", 0.5, 3.9), ("gap_4_5in", 3.9, 5.9),
               ("gap_9_11in", 8.5, 11.5), ("gap_12in", 11.5, 12.9))


def gap_class(gap_in):
    """Measured gap (inches) -> layer name. Buckets only; no meaning attached
    to them yet — that is what locating them on the drawing is for. Pure."""
    for name, lo, hi in GAP_CLASSES:
        if lo <= gap_in < hi:
            return name
    return "gap_other"

# layers Phase 1+ will fill; emitted empty so their absence is visible
NOT_YET_DETECTED = ("railing", "plot_boundary", "setback")


def page_transform(reg, dpi=110.0):
    """Registration: scene FEET (origin bottom-left) -> page PIXELS.

    The parser works in points of the ROTATED page, which is the space
    `page.get_pixmap()` renders, so the only extra step is points -> pixels.
    Returns f(x_ft, y_ft) -> [px, py]. Pure."""
    k = float(dpi) / 72.0
    x0 = float(reg["x0_pt"])
    y0 = float(reg["y0_pt"])
    ppf = float(reg["ppf"])
    d_ft = float(reg["d_ft"])
    sx, sy = (list(reg.get("shift_ft") or [0.0, 0.0]) + [0.0, 0.0])[:2]

    def f(x_ft, y_ft):
        px = (x0 + (float(x_ft) + sx) * ppf) * k
        py = (y0 + (d_ft - (float(y_ft) + sy)) * ppf) * k
        return [round(px, 1), round(py, 1)]

    return f


def _rect(f, r):
    """[x0, y0, x1, y1] in feet -> polygon in page pixels (y flips, so the
    corners are re-ordered rather than assumed)."""
    x0, y0, x1, y1 = [float(v) for v in r]
    return [f(x0, y0), f(x1, y0), f(x1, y1), f(x0, y1)]


def build_layers(scene, dpi=110.0):
    """Scene -> {layer: [shapes]} in page pixels, plus the style key. Pure.

    Every layer in LAYER_STYLE is present in the result, empty or not."""
    scene = scene or {}
    meta = scene.get("meta") or {}
    reg = meta.get("page_registration")
    if not reg:
        return None
    f = page_transform(reg, dpi)
    out = {k: [] for k in LAYER_STYLE}

    for wp in scene.get("walls_poly") or []:
        if wp.get("outer"):
            out["walls"].append([f(p[0], p[1]) for p in wp["outer"]])
        for hole in wp.get("holes") or []:
            out["walls"].append([f(p[0], p[1]) for p in hole])

    for c in scene.get("columns") or []:
        out["columns"].append(_rect(f, [c["x"], c["y"],
                                        c["x"] + c["w"], c["y"] + c["d"]]))

    for o in scene.get("openings") or []:
        fp = o.get("footprint")
        if not fp:
            continue
        key = "doors" if o.get("type") == "door" else "windows"
        out[key].append(_rect(f, fp))

    for r in scene.get("rooms") or []:
        poly = r.get("polygon_ft")
        if poly:
            out["rooms"].append([f(p[0], p[1]) for p in poly])

    if scene.get("footprint_ft"):
        out["footprint"].append([f(p[0], p[1]) for p in scene["footprint_ft"]])
    if scene.get("footprint_ext_ft"):
        out["footprint_ext"].append([f(p[0], p[1])
                                     for p in scene["footprint_ext_ft"]])

    da = (meta.get("dimension_anchors") or {}).get("anchors") or []
    for a in da:
        for e in a["ends"]:
            d = e.get("wall_dist_ft")
            if d is None:
                continue
            k = ("dim_anchor_hit" if d <= 0.5
                 else "dim_anchor_near" if d <= 5.0 else "dim_anchor_miss")
            cx, cy = f(e["at_ft"][0], e["at_ft"][1])
            r = 5 if k == "dim_anchor_miss" else 4
            out[k].append([[cx - r, cy - r], [cx + r, cy - r],
                           [cx + r, cy + r], [cx - r, cy + r]])

    for seg in scene.get("rejected_lines_ft") or []:
        out["rejected"].append([f(seg[0], seg[1]), f(seg[2], seg[3])])

    return out


def build_overlay(scene, dpi=110.0):
    """Full instrument payload: layers + style + counts + what is not yet
    detected. Pure; the caller supplies the rendered page image."""
    layers = build_layers(scene, dpi)
    if layers is None:
        return None
    meta = (scene or {}).get("meta") or {}
    return {
        "dpi": float(dpi),
        "layers": layers,
        "style": LAYER_STYLE,
        "counts": {k: len(v) for k, v in layers.items()},
        "not_yet_detected": list(NOT_YET_DETECTED),
        "wall_line_thicknesses": meta.get("wall_line_thicknesses"),
        "rejected_summary": meta.get("rejected_summary"),
        "registration": meta.get("page_registration"),
    }
