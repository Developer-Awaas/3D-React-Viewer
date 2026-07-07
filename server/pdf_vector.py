"""Step D1 - vector CAD PDFs -> canonical scene.json, read BY LAYER (no AI).

Ported from the drishti reference and hardened against real exports
(FLOOR PLAN.pdf, 2026-07-07):
- layer names vary per exporter -> discover by keyword, case-insensitive
  (walls: 'wall'/'AR Wall'; columns: 'COLUMN'; doors: 'ALL DOOR'; ...)
- pages can be rotated (this one: 270) -> apply page.rotation_matrix
- one sheet can hold several drawings (site compound wall etc.) -> keep only
  structure inside the COLUMN-layer extent (columns exist only in the building)
- doors: cluster the door-layer fragments; each cluster's bbox = one door

Output: polygon walls (`walls_poly`, angled walls OK) + door/window openings
as footprints + columns. FEET, origin bottom-left, z-up. Scale: dominant
column box = 12 in, else PPF env, else the width_ft parameter.
"""
import math
import os

COL_FT = 1.0                 # standard column = 12 in = 1 ft (locked decision)
NORM_PPX = 50.9              # raster px per ft (keeps morphology physical)
BORDER_MAXLEN_PT = 900       # drop page-border / site-boundary mega-lines
WINDOW_SILL_FT = 3.0         # locked: sill 3 ft / head 7 ft
WINDOW_HEAD_FT = 7.0
DOOR_HEAD_FT = 6.89          # ~2.1 m (matches Step B2)
DOOR_MIN_FT, DOOR_MAX_FT = 2.0, 5.5
WALL_HEIGHT_FT = 9.843       # ~3 m
MIN_WALL_AREA_PX = 6000
MIN_HOLE_AREA_PX = 2500
PAD_PX = 10
BBOX_MARGIN = 0.15           # building bbox = column extent + 15%


def _lname(d):
    return (d.get("layer") or "").lower()


def _is_wall_layer(name):
    return "wall" in name and "door" not in name and "boundary" not in name


def _is_window_layer(name):
    return "window" in name or name == "win"


def _is_column_layer(name):
    return "column" in name or name == "col"


def _is_door_layer(name):
    return "door" in name


def _page_drawings(page):
    """get_drawings() with every point/rect mapped through the page rotation."""
    import fitz
    mat = page.rotation_matrix
    out = []
    for d in page.get_drawings():
        items = []
        for it in d["items"]:
            if it[0] == "l":
                items.append(("l", fitz.Point(it[1]) * mat, fitz.Point(it[2]) * mat))
            elif it[0] == "re":
                items.append(("re", (fitz.Rect(it[1]) * mat).normalize()))
            elif it[0] == "qu":
                q = it[1]
                items.append(("qu", [fitz.Point(p) * mat for p in (q.ul, q.ur, q.lr, q.ll)]))
            elif it[0] == "c":
                items.append(("c",) + tuple(fitz.Point(p) * mat for p in it[1:]))
        out.append({"layer": d.get("layer"), "lname": _lname(d),
                    "rect": (fitz.Rect(d["rect"]) * mat).normalize(), "items": items})
    return out


def _segs(drawings, want, maxlen=BORDER_MAXLEN_PT):
    """Line segments (pt, rotated coords) from layers matching predicate `want`."""
    out = []
    for d in drawings:
        if not want(d["lname"]):
            continue
        for it in d["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                if math.hypot(b.x - a.x, b.y - a.y) <= maxlen:
                    out.append((a.x, a.y, b.x, b.y))
            elif it[0] == "re":
                r = it[1]
                if max(r.width, r.height) <= maxlen:
                    out += [(r.x0, r.y0, r.x1, r.y0), (r.x1, r.y0, r.x1, r.y1),
                            (r.x1, r.y1, r.x0, r.y1), (r.x0, r.y1, r.x0, r.y0)]
            elif it[0] == "qu":
                pts = it[1]
                for i in range(4):
                    a, b = pts[i], pts[(i + 1) % 4]
                    out.append((a.x, a.y, b.x, b.y))
    return out


def is_vector_plan(raw):
    """True if these PDF bytes carry recognizable CAD layers."""
    try:
        import fitz
        page = fitz.open(stream=raw, filetype="pdf")[0]
        names = {_lname(d) for d in page.get_drawings()}
        return any(_is_wall_layer(n) or _is_column_layer(n) or _is_window_layer(n)
                   for n in names)
    except Exception:
        return False


def _column_rects(drawings):
    """Square-ish boxes on column layers (hatch strokes share the box bbox,
    which only reinforces the dominant size)."""
    out = []
    for d in drawings:
        if not _is_column_layer(d["lname"]):
            continue
        r = d["rect"]
        w, h = r.width, r.height
        if 0.6 < (w / (h + 1e-6)) < 1.6 and 4 < max(w, h) < 200:
            out.append(r)
    return out


def _scale_ppf(col_rects, bbox_w_pt, width_ft):
    """Points-per-foot. Priority: dominant column box (=1 ft) > PPF env > width_ft."""
    if col_rects:
        import numpy as np
        sizes = [round(max(r.width, r.height), 1) for r in col_rects]
        vals, cnt = np.unique(sizes, return_counts=True)
        return float(vals[cnt.argmax()]) / COL_FT, "column_box_12in"
    if os.environ.get("PPF"):
        return float(os.environ["PPF"]), "env_ppf"
    if width_ft and bbox_w_pt > 0:
        return bbox_w_pt / width_ft, "assumed_width"
    raise ValueError("no scale: no column layer boxes; pass width_ft or set PPF")


def _cluster_rects(rects, gap=3.0):
    """Union-find rectangles that touch (within `gap` pt) into cluster bboxes."""
    import fitz
    parent = list(range(len(rects)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    grown = [fitz.Rect(r.x0 - gap, r.y0 - gap, r.x1 + gap, r.y1 + gap) for r in rects]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if grown[i].intersects(grown[j]):
                parent[find(i)] = find(j)
    groups = {}
    for i, r in enumerate(rects):
        groups.setdefault(find(i), fitz.Rect(r)).include_rect(r)
    return list(groups.values())


def parse(raw, width_ft=None):
    """Vector PDF bytes -> canonical scene dict. Raises ValueError if unusable."""
    import cv2
    import fitz
    import numpy as np

    page = fitz.open(stream=raw, filetype="pdf")[0]
    drawings = _page_drawings(page)

    struct = _segs(drawings, _is_wall_layer) + _segs(drawings, _is_window_layer)
    if not struct:
        raise ValueError("no segments on wall/window layers - not a layered CAD PDF")
    col_rects = _column_rects(drawings)

    # one sheet may hold several drawings; the building is where the columns are
    if col_rects:
        cx0 = min(r.x0 for r in col_rects); cy0 = min(r.y0 for r in col_rects)
        cx1 = max(r.x1 for r in col_rects); cy1 = max(r.y1 for r in col_rects)
        mx, my = (cx1 - cx0) * BBOX_MARGIN, (cy1 - cy0) * BBOX_MARGIN
        bx0, by0, bx1, by1 = cx0 - mx, cy0 - my, cx1 + mx, cy1 + my

        def inside(s):
            x = (s[0] + s[2]) / 2.0
            y = (s[1] + s[3]) / 2.0
            return bx0 <= x <= bx1 and by0 <= y <= by1
        kept = [s for s in struct if inside(s)]
        if len(kept) >= max(8, 0.2 * len(struct)):   # sanity: don't crop all away
            struct = kept

    xs = [s[0] for s in struct] + [s[2] for s in struct]
    ys = [s[1] for s in struct] + [s[3] for s in struct]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)

    ppf, scale_src = _scale_ppf(col_rects, x1 - x0, width_ft)
    w_ft = (x1 - x0) / ppf
    d_ft = (y1 - y0) / ppf

    # --- normalized raster -> solid wall bands ---
    sc = NORM_PPX / ppf
    W = int((x1 - x0) * sc) + 2 * PAD_PX
    H = int((y1 - y0) * sc) + 2 * PAD_PX
    if W * H > 6000 * 6000:
        raise ValueError(f"plan raster too large ({W}x{H}) - scale looks wrong")

    def tp(x, y):
        return (int((x - x0) * sc) + PAD_PX, int((y - y0) * sc) + PAD_PX)

    m = np.zeros((H, W), np.uint8)
    for ax, ay, bx, by in struct:
        cv2.line(m, tp(ax, ay), tp(bx, by), 255, 2)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
    n, lab, stt, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros_like(m)
    for i in range(1, n):
        if stt[i, cv2.CC_STAT_AREA] > MIN_WALL_AREA_PX:
            keep[lab == i] = 255
    m = keep

    # --- contours -> polygons in FEET (origin bottom-left, y up) ---
    def fx(px):
        return round((px - PAD_PX) / NORM_PPX, 3)

    def fy(py):
        return round(d_ft - (py - PAD_PX) / NORM_PPX, 3)

    def poly_pts(c):
        c = cv2.approxPolyDP(c, 1.2, True).reshape(-1, 2).astype(float)
        return [[fx(px), fy(py)] for px, py in c]

    cnts, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    walls_poly = []
    if hier is not None:
        hier = hier[0]
        for i, c in enumerate(cnts):
            if hier[i][3] != -1 or cv2.contourArea(c) < MIN_WALL_AREA_PX:
                continue
            holes = []
            ch = hier[i][2]
            while ch != -1:
                if cv2.contourArea(cnts[ch]) > MIN_HOLE_AREA_PX:
                    holes.append(poly_pts(cnts[ch]))
                ch = hier[ch][0]
            walls_poly.append({"id": f"wp{len(walls_poly)}",
                               "outer": poly_pts(c), "holes": holes})
    if not walls_poly:
        raise ValueError("wall mask empty after morphology - no wall regions found")

    def ft_rect(r):
        return [round((r.x0 - x0) / ppf, 3), round(d_ft - (r.y1 - y0) / ppf, 3),
                round((r.x1 - x0) / ppf, 3), round(d_ft - (r.y0 - y0) / ppf, 3)]

    openings = []

    # --- windows: rects on window layers, plausible sizes ---
    for d in drawings:
        if not _is_window_layer(d["lname"]):
            continue
        r = d["rect"]
        L = max(r.width, r.height) / ppf
        T = min(r.width, r.height) / ppf
        if 1.5 <= L <= 8.0 and 0.05 <= T <= 1.2:
            openings.append({"id": f"o{len(openings)}", "type": "window",
                             "footprint": ft_rect(r),
                             "z": [WINDOW_SILL_FT, WINDOW_HEAD_FT]})
    has_window_layer = any(_is_window_layer(d["lname"]) for d in drawings)

    # --- doors: cluster door-layer fragments; cluster bbox ~ leaf + swing arc ---
    door_rects = [d["rect"] for d in drawings if _is_door_layer(d["lname"])]
    has_door_layer = bool(door_rects)
    for cl in _cluster_rects(door_rects) if door_rects else []:
        wd = max(cl.width, cl.height) / ppf
        if DOOR_MIN_FT <= wd <= DOOR_MAX_FT:
            openings.append({"id": f"o{len(openings)}", "type": "door",
                             "footprint": ft_rect(cl),
                             "z": [0, DOOR_HEAD_FT]})

    # --- columns (dominant-size boxes only, deduplicated by cluster) ---
    columns = []
    if col_rects:
        dom_candidates = [max(r.width, r.height) for r in col_rects
                          if abs(max(r.width, r.height) - ppf * COL_FT) < 0.6]
        if dom_candidates:
            dom = max(dom_candidates)
            uniq = _cluster_rects([r for r in col_rects
                                   if abs(max(r.width, r.height) - dom) < 0.6], gap=1.0)
            for r in uniq:
                columns.append({"id": f"c{len(columns)}", "kind": "column",
                                "x": round((r.x0 - x0) / ppf, 3),
                                "y": round(d_ft - (r.y1 - y0) / ppf, 3),
                                "w": round(r.width / ppf, 3), "d": round(r.height / ppf, 3)})

    warnings = []
    if scale_src == "column_box_12in":
        warnings.append("scale from dominant column box = 12 in (provisional)")
    else:
        warnings.append("scale is a placeholder until dimension text is readable")
    if not has_window_layer:
        warnings.append("no window layer found - windows not extracted")
    if not has_door_layer:
        warnings.append("no door layer found - doors not extracted")

    return {
        "meta": {
            "source": "vector_pdf_layers",
            "units": "ft",
            "wall_height_ft": WALL_HEIGHT_FT,
            "plan_width_ft": round(w_ft, 3),
            "plan_depth_ft": round(d_ft, 3),
            "scale": {"source": scale_src, "pt_per_ft": round(ppf, 3)},
            "warnings": warnings,
        },
        "wall_types": {},
        "rooms": [],
        "walls": [],                # axis-aligned walls unused on this path
        "walls_poly": walls_poly,   # exact footprints incl. angled walls
        "openings": openings,
        "columns": columns,
        "ducts": [], "furniture": [],
    }
