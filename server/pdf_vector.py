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
DOOR_HEAD_FT = 7.0           # lintel level 7'0" (Indian practice; matches window head)
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


TEXT_MED_MAXLEN_PT = 5.0     # a layer whose MEDIAN segment is shorter = outlined text


def _filter_text_layers(drawings, want, warnings):
    """Segments from layers matching `want`, minus text-like decoy layers.

    Outlined lettering (e.g. a title block on a layer literally named 'wall',
    seen in real exports) is thousands of sub-point strokes; real wall lines
    are feet long. Any candidate layer whose MEDIAN segment length is under
    TEXT_MED_MAXLEN_PT is dropped whole, with a warning recorded.
    Returns (segments, dropped_layer_names)."""
    import statistics
    by_layer = {}
    for d in drawings:
        if want(d["lname"]):
            by_layer.setdefault(d["lname"], []).append(d)
    segs, dropped = [], set()
    for name, ds in sorted(by_layer.items()):
        ls = _segs(ds, lambda n: True)
        if not ls:
            continue
        med = statistics.median(math.hypot(x2 - x1, y2 - y1) for x1, y1, x2, y2 in ls)
        if med < TEXT_MED_MAXLEN_PT:
            dropped.add(name)
            warnings.append(f"layer '{name}' skipped: text-like "
                            f"(median seg {med:.1f} pt, n={len(ls)})")
        else:
            segs += ls
    return segs, dropped


GEOM_SKIP = ("door", "dim", "text", "furn", "sanitary", "kitchen", "stair",
             "elev", "chhaja", "boundary")   # layers that never carry wall lines


def _text_scale(page, drawings, warnings):
    """Scale from LIVE dimension text: each ft-in token that hugs a parallel
    line of matching length votes for pt-per-foot; the dominant vote wins.
    Room labels (no matching line) cannot vote. Returns (ppf, nvotes)|(None,0)."""
    import re
    import statistics
    from collections import Counter
    import fitz
    mat = page.rotation_matrix
    FTIN = re.compile(r"^(\d+)['\u2019]-?(\d+)?[\"\u201d]?$")
    toks = []
    for w in page.get_text("words"):
        m = FTIN.match(w[4].strip())
        if not m:
            continue
        val = int(m.group(1)) + int(m.group(2) or 0) / 12.0
        if 2 <= val <= 100:
            r = (fitz.Rect(w[:4]) * mat).normalize()
            toks.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, val))
    if len(toks) < 4:
        return None, 0, set()
    lines = []
    for d in drawings:
        for it in d["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                dx, dy = b.x - a.x, b.y - a.y
                L = math.hypot(dx, dy)
                if 8 < L < BORDER_MAXLEN_PT:
                    lines.append((a.x, a.y, dx, dy, L))
    votes = []
    dim_keys = set()          # lines with dimension text hugging them = NOT walls
    for cx, cy, val in toks:
        for ax, ay, dx, dy, L in lines:
            t = ((cx - ax) * dx + (cy - ay) * dy) / (L * L)
            if not (0.15 < t < 0.85):
                continue                       # text must sit mid-line
            perp = math.hypot(cx - (ax + t * dx), cy - (ay + t * dy))
            if perp > 9:
                continue                       # and hug it (few pt away)
            dim_keys.add((round(ax, 1), round(ay, 1),
                          round(ax + dx, 1), round(ay + dy, 1)))
            ppf = L / val
            if 2 < ppf < 40:
                votes.append(round(ppf, 1))
    if len(votes) < 8:
        return None, 0, dim_keys
    best = Counter(votes).most_common(1)[0][0]
    close = [v for v in votes if abs(v - best) <= 0.3]
    if len(close) < 8 or len(close) < 0.15 * len(votes):
        return None, 0, dim_keys
    ppf = statistics.median(close)
    warnings.append(f"scale from dimension text: {ppf:.2f} pt/ft "
                    f"({len(close)} agreeing votes)")
    return ppf, len(close), dim_keys


def _geometry_wall_segs(drawings, ppf, warnings, dim_keys=frozenset()):
    """Find walls WITHOUT layer names: two parallel axis-aligned lines
    3-11 in apart overlapping >= 2 ft = a masonry wall. Lines identified as
    dimension lines (text hugging them) never count. Returns the paired
    spans as segments for the normal raster pipeline."""
    H, V = [], []
    for d in drawings:
        if any(k in d["lname"] for k in GEOM_SKIP):
            continue
        for it in d["items"]:
            if it[0] != "l":
                continue
            a, b = it[1], it[2]
            if (round(a.x, 1), round(a.y, 1), round(b.x, 1), round(b.y, 1)) in dim_keys:
                continue
            dx, dy = b.x - a.x, b.y - a.y
            L = math.hypot(dx, dy)
            if L < 6 or L > BORDER_MAXLEN_PT:
                continue
            if abs(dy) < 0.5:
                H.append(((a.y + b.y) / 2, min(a.x, b.x), max(a.x, b.x)))
            elif abs(dx) < 0.5:
                V.append(((a.x + b.x) / 2, min(a.y, b.y), max(a.y, b.y)))
    th_min, th_max = 0.25 * ppf, 0.92 * ppf     # 3..11 inch
    min_ovl = 2.0 * ppf

    def pairs(runs, horiz):
        runs = sorted(runs)
        walls = []                     # (p_mid, a, b, p1, p2)
        for i in range(len(runs)):
            p1, a1, b1 = runs[i]
            for j in range(i + 1, len(runs)):
                p2, a2, b2 = runs[j]
                if p2 - p1 > th_max:
                    break
                if p2 - p1 < th_min:
                    continue
                a, b = max(a1, a2), min(b1, b2)
                if b - a < min_ovl:
                    continue
                # a real masonry wall has EMPTY space between its two faces:
                # if a third line runs between p1 and p2 over (nearly) the
                # whole span, the (p1, p2) pair is a phantom spanning several
                # drawn lines. (Phantoms bridged doorway gaps - lost door
                # snaps - and inflated the envelope ~5%.) Threshold is HIGH
                # on purpose: window/fixture linework drawn inside the wall
                # covers part of the span and must NOT kill the wall.
                blocked = False
                for k in range(i + 1, j):
                    pk, ak, bk = runs[k]
                    if pk - p1 < 0.5 or p2 - pk < 0.5:
                        continue       # collinear duplicate of a face
                    if min(b, bk) - max(a, ak) > 0.75 * (b - a):
                        blocked = True
                        break
                if not blocked:
                    walls.append(((p1 + p2) / 2, a, b, p1, p2))
        walls = _drop_stair_ladders(walls, ppf, warnings, horiz)
        segs = set()                   # faces at their TRUE drawn positions
        for _pm, a, b, p1, p2 in walls:
            for q in (p1, p2):
                segs.add((a, q, b, q) if horiz else (q, a, q, b))
        return sorted(segs)

    segs = pairs(H, True) + pairs(V, False)
    if segs:
        warnings.append(f"walls detected by GEOMETRY (parallel-pair rule): "
                        f"{len(segs)} spans - no usable wall layer on this sheet")
    return segs


def _drop_stair_ladders(walls, ppf, warnings, horiz):
    """Remove staircase treads mis-read as walls. Treads are SHORT strips
    (a stair is <= ~8 ft wide) with near-equal spans, marching at a tight
    regular rhythm (0.35-1.6 ft). No real building stacks 4+ walls a foot
    apart. The OUTERMOST rungs are usually the stair enclosure walls, so
    the chain endpoints are kept.

    v3 (2026-07-14): v2 walked the globally sorted list, so ANY unrelated
    wall interleaved by position broke the chain - it never fired on real
    plans (the corrugated stair blob). Now the ladder is chained over
    short-strip candidates that laterally overlap, wherever they sit."""
    if len(walls) < 5:
        return walls
    cand = sorted((k for k in range(len(walls))
                   if walls[k][2] - walls[k][1] <= 8.0 * ppf),
                  key=lambda k: (walls[k][0], walls[k][1]))
    drop, used = set(), set()
    for s in range(len(cand)):
        if cand[s] in used:
            continue
        chain = [cand[s]]
        for k in cand[s + 1:]:
            if k in used:
                continue
            p0, a0, b0 = walls[chain[-1]][:3]
            p1, a1, b1 = walls[k][:3]
            if p1 - p0 > 1.6 * ppf:
                break                       # rhythm broken: no rung this close
            s0, s1 = b0 - a0, b1 - a1
            if min(s0, s1) < 0.75 * max(s0, s1):
                continue                    # unrelated strip; keep scanning
            if min(b0, b1) - max(a0, a1) < 0.8 * max(s0, s1):
                continue                    # not laterally aligned
            chain.append(k)
        ps = sorted(walls[k][0] for k in chain)
        rungs = 1 + sum(1 for t in range(1, len(ps))
                        if ps[t] - ps[t - 1] >= 0.35 * ppf)
        if rungs >= 4:                      # a stair flight
            used.update(chain)
            lo, hi = ps[0], ps[-1]
            for k in chain:                 # keep outermost = enclosure walls
                if walls[k][0] - lo > 0.2 * ppf and hi - walls[k][0] > 0.2 * ppf:
                    drop.add(k)
    if drop:
        warnings.append(f"stair filter: dropped {len(drop)} "
                        f"{'horizontal' if horiz else 'vertical'} tread-like strips")
        return [w for k, w in enumerate(walls) if k not in drop]
    return walls


def _wing_groups(m, gap_ft=8.0):
    """Split the wall mask into spatially separate building wings.
    Returns [(labels_set, bbox_px, area)] sorted largest first."""
    import cv2
    n, lab, stt, _ = cv2.connectedComponentsWithStats(m, 8)
    comps = [(i, (stt[i, 0], stt[i, 1], stt[i, 0] + stt[i, 2],
                  stt[i, 1] + stt[i, 3]), stt[i, 4]) for i in range(1, n)]
    if not comps:
        return []
    gap = gap_ft * NORM_PPX
    parent = list(range(len(comps)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def near(b1, b2):
        return not (b1[2] + gap < b2[0] or b2[2] + gap < b1[0]
                    or b1[3] + gap < b2[1] or b2[3] + gap < b1[1])

    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            if near(comps[i][1], comps[j][1]):
                parent[find(i)] = find(j)
    members = {}
    for k, (idx, bb, area) in enumerate(comps):
        members.setdefault(find(k), []).append((idx, bb, area))
    groups = []
    for mem in members.values():
        biggest = max(a for _, _, a in mem)
        struct = [(i, bb, a) for i, bb, a in mem if a >= 0.1 * biggest]
        bx0 = min(bb[0] for _, bb, _ in struct)
        by0 = min(bb[1] for _, bb, _ in struct)
        bx1 = max(bb[2] for _, bb, _ in struct)
        by1 = max(bb[3] for _, bb, _ in struct)
        groups.append([set(i for i, _, _ in struct), (bx0, by0, bx1, by1),
                       sum(a for _, _, a in struct)])
    return sorted(groups, key=lambda g: -g[2])


def is_vector_plan(raw):
    """True if these PDF bytes can take the vector path: recognizable CAD
    layers, OR enough raw axis-aligned linework for geometry wall detection
    (scanned/flat PDFs have no vector drawings at all, so they still route
    to the raster/CubiCasa path)."""
    try:
        import fitz
        page = fitz.open(stream=raw, filetype="pdf")[0]
        drawings = page.get_drawings()
        names = {_lname(d) for d in drawings}
        if any(_is_wall_layer(n) or _is_column_layer(n) or _is_window_layer(n)
               for n in names):
            return True
        n_axis = 0
        for d in drawings:
            if any(k in _lname(d) for k in GEOM_SKIP):
                continue
            for it in d["items"]:
                if it[0] == "l":
                    a, b = it[1], it[2]
                    if abs(a.x - b.x) < 0.5 or abs(a.y - b.y) < 0.5:
                        n_axis += 1
        return n_axis >= 60
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


def fitz_rect_intersects(a, b):
    """Axis-aligned bbox intersection test for fitz.Rect (touch counts)."""
    return not (a.x1 < b.x0 or b.x1 < a.x0 or a.y1 < b.y0 or b.y1 < a.y0)


def fitz_rect_overlaps_half(a, b):
    """>= half of the smaller rect's area overlaps the other: near-duplicate
    linework of the SAME window symbol (frame vs shutter strokes)."""
    w = min(a.x1, b.x1) - max(a.x0, b.x0)
    h = min(a.y1, b.y1) - max(a.y0, b.y0)
    if w <= 0 or h <= 0:
        return False
    return w * h >= 0.5 * min(a.width * a.height, b.width * b.height)


def _door_gap_strip(m, box_px, door_w_px):
    """Locate the doorway GAP in the wall mask beside a door swing box.

    CAD wall linework stops at both jambs, so the raster wall mask has a hole
    where the doorway is. Morphologically closing the neighbourhood along each
    axis reveals exactly the missing strip. A candidate strip must be thin like
    a wall (else it's a corridor/parallel-wall fill), door-sized along the wall,
    and touching the swing box. Returns (comp_bool_mask, bbox_px, (offx, offy))
    for the best strip, or None if the wall has no gap there."""
    import cv2
    H, W = m.shape
    x0, y0, x1, y1 = box_px
    pad = int(1.2 * NORM_PPX)                     # reach the wall beside the swing
    X0, Y0 = max(0, x0 - pad), max(0, y0 - pad)
    X1, Y1 = min(W, x1 + pad), min(H, y1 + pad)
    if X1 <= X0 or Y1 <= Y0:
        return None
    roi = m[Y0:Y1, X0:X1]
    k = int(door_w_px) + 6
    touch = int(0.6 * NORM_PPX)     # swing box may sit ~half a wall away from the gap
    best = None                     # (area, strip_mask, union_bbox, offset)
    for kern in ((k, 1), (1, k)):
        closed = cv2.morphologyEx(roi, cv2.MORPH_CLOSE,
                                  cv2.getStructuringElement(cv2.MORPH_RECT, kern))
        added = cv2.bitwise_and(closed, cv2.bitwise_not(roi))
        n, lab, stt, _ = cv2.connectedComponentsWithStats(added, 8)
        # a double-line wall shows the gap as SEVERAL parallel strips - accept
        # every door-sized one in this orientation and use their union.
        strip = None
        area = 0
        ub = None
        for i in range(1, n):
            w = stt[i, cv2.CC_STAT_WIDTH]
            h = stt[i, cv2.CC_STAT_HEIGHT]
            long_, thin = max(w, h), min(w, h)
            if thin > 1.5 * NORM_PPX:             # thicker than any wall
                continue
            if not (0.5 * door_w_px <= long_ <= door_w_px + 0.6 * NORM_PPX):
                continue                          # not door-sized along the wall
            bx = stt[i, cv2.CC_STAT_LEFT] + X0
            by = stt[i, cv2.CC_STAT_TOP] + Y0
            if (bx > x1 + touch or bx + w < x0 - touch
                    or by > y1 + touch or by + h < y0 - touch):
                continue                          # nowhere near the swing box
            comp = (lab == i)
            strip = comp if strip is None else (strip | comp)
            area += stt[i, cv2.CC_STAT_AREA]
            bb = (bx, by, bx + w, by + h)
            ub = bb if ub is None else (min(ub[0], bb[0]), min(ub[1], bb[1]),
                                        max(ub[2], bb[2]), max(ub[3], bb[3]))
        if strip is not None and (best is None or area > best[0]):
            best = (area, strip, ub, (X0, Y0))
    return best[1:] if best else None


def _door_gap_endpoints(struct, cl, ppf, wd_ft=None):
    """Vector fallback for doors the raster gap-finder misses (typically at
    wall JUNCTIONS, where the closing kernel merges the doorway with the
    crossing wall). CAD wall lines STOP at the jambs: two nearly-collinear
    lines whose facing endpoints straddle the swing box with a door-sized
    gap mark the doorway. Returns the strip rect in pt (x0, y0, x1, y1)
    covering the full wall band, or None."""
    if wd_ft:                          # this door's own width, + jamb offset /
        wd_lo = max(DOOR_MIN_FT, wd_ft - 0.7) * ppf        # crossing wall
        wd_hi = min(DOOR_MAX_FT + 1.0, wd_ft + 1.6) * ppf
    else:
        wd_lo, wd_hi = DOOR_MIN_FT * ppf, (DOOR_MAX_FT + 0.6) * ppf
    reach = 1.2 * ppf                  # wall face may sit ~a thickness away
    H, V = [], []
    for ax, ay, bx, by in struct:
        if abs(ay - by) < 0.5:
            H.append(((ay + by) / 2, min(ax, bx), max(ax, bx)))
        elif abs(ax - bx) < 0.5:
            V.append(((ax + bx) / 2, min(ay, by), max(ay, by)))
    best = None                        # (overlap, along0, along1, p_lo, p_hi)
    for runs, horiz in ((H, True), (V, False)):
        if horiz:
            lo, hi, clo, chi = cl.x0, cl.x1, cl.y0, cl.y1
        else:
            lo, hi, clo, chi = cl.y0, cl.y1, cl.x0, cl.x1
        near = [r for r in runs if clo - reach <= r[0] <= chi + reach]
        for p1, a1, b1 in near:
            for p2, a2, b2 in near:
                if abs(p2 - p1) > 0.35 * ppf:
                    continue           # not the same wall face
                gap = a2 - b1          # first line ends, second line starts
                if not (wd_lo <= gap <= wd_hi):
                    continue
                g0, g1 = b1, a2
                ovl = min(g1, hi) - max(g0, lo)
                if ovl < 0.4 * (hi - lo):
                    continue           # gap is not at the swing box
                # genuinely open: no third collinear line crossing the gap
                # (offset wall segments are not a doorway)
                crossed = any(min(g1, bk) - max(g0, ak) > 0.25 * gap
                              for pk, ak, bk in near
                              if abs(pk - (p1 + p2) / 2) < 0.6 * ppf
                              and (pk, ak, bk) not in ((p1, a1, b1), (p2, a2, b2)))
                if crossed:
                    continue
                # wall band = faces terminating at these jambs, within one
                # wall thickness of this face (NOT faces of other walls that
                # happen to sit inside the swing box reach)
                pmid = (p1 + p2) / 2
                band = [p for p, a, b in near
                        if (abs(b - g0) < 0.15 * ppf or abs(a - g1) < 0.15 * ppf)
                        and abs(p - pmid) <= 0.95 * ppf]
                p_lo, p_hi = min(band) - 1.0, max(band) + 1.0
                if p_hi - p_lo > 1.3 * ppf:        # thicker than any wall: clamp
                    p_lo, p_hi = pmid - 0.65 * ppf, pmid + 0.65 * ppf
                if p_hi - p_lo < 0.3 * ppf:        # single face: assume 4in wall
                    mid = (p_lo + p_hi) / 2
                    p_lo, p_hi = mid - 0.17 * ppf, mid + 0.17 * ppf
                if best is None or ovl > best[0]:
                    best = (ovl, g0, g1, p_lo, p_hi, horiz)
    if best is None:
        return None
    _, g0, g1, p_lo, p_hi, horiz = best
    return (g0, p_lo, g1, p_hi) if horiz else (p_lo, g0, p_hi, g1)


def wing_arg(w):
    """Query-param -> parse() wing argument: '2'->2, else 'largest'."""
    try:
        return int(w)
    except (TypeError, ValueError):
        return "largest"


def _door_scale_sanity(openings, warnings):
    """Practical cross-check: snapped doors are real doors (2'0"-4'6" wide in
    Indian residential work). If their median width is far outside that band,
    the SCALE is suspect - warn with the implied correction factor."""
    import statistics
    widths = []
    for o in openings:
        if o.get("type") == "door" and o.get("snapped") and o.get("footprint"):
            x0, y0, x1, y1 = o["footprint"]
            widths.append(max(x1 - x0, y1 - y0))
    if len(widths) < 5:
        return
    med = statistics.median(widths)
    if not (2.1 <= med <= 4.2):
        factor = med / 3.0          # vs a nominal 3'0" door
        warnings.append(
            f"SCALE SUSPECT: median snapped-door width {med:.2f} ft "
            f"(expected 2'6\"-3'6\"); sizes may be off ~{factor:.2f}x - "
            f"check the column size or provide width_ft")


def parse(raw, width_ft=None, wing="largest", ppf_hint=None):
    """Vector PDF bytes -> canonical scene dict. Raises ValueError if unusable.
    wing: "largest" or an int index - which building wing to build when the
    sheet holds several separate blocks (sorted largest first).
    ppf_hint: EXACT pt-per-ft when known (CAD DXF/DWG route: real units) -
    overrides dimension-text and column-box scale guessing."""
    import cv2
    import fitz
    import numpy as np

    page = fitz.open(stream=raw, filetype="pdf")[0]
    drawings = _page_drawings(page)

    warnings = []
    wall_segs, skipped = _filter_text_layers(drawings, _is_wall_layer, warnings)
    win_segs, skipped_w = _filter_text_layers(drawings, _is_window_layer, warnings)
    skipped |= skipped_w
    struct = wall_segs + win_segs
    col_rects = _column_rects(drawings)

    # scale from live dimension text beats every other signal
    # (unless the caller KNOWS the scale - CAD files carry real units)
    text_ppf, _tv, dim_keys = _text_scale(page, drawings, warnings)
    if ppf_hint:
        text_ppf = None

    mode = "layers"
    if len(struct) < 30:            # no usable wall layer -> geometry detection
        seed = ppf_hint or text_ppf
        if seed is None and col_rects:
            import numpy as np
            sizes = [round(max(r.width, r.height), 1) for r in col_rects]
            v, c = np.unique(sizes, return_counts=True)
            seed = float(v[c.argmax()]) / COL_FT
        if seed:
            gsegs = _geometry_wall_segs(drawings, seed, warnings, dim_keys)
            if len(gsegs) >= 8:
                struct = gsegs
                mode = "geometry"
    if not struct:
        raise ValueError("no segments on wall/window layers - not a layered CAD PDF")

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
        else:
            warnings.append("building crop skipped: wall extent disagrees with "
                            "column extent (check for stray drawings on the sheet)")

    xs = [s[0] for s in struct] + [s[2] for s in struct]
    ys = [s[1] for s in struct] + [s[3] for s in struct]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)

    if ppf_hint:
        ppf, scale_src = float(ppf_hint), "cad_units"
    elif text_ppf:
        ppf, scale_src = text_ppf, "dimension_text"
    else:
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

    def _mask(shape_flag, dil, ero):
        """Rasterize struct -> solid wall bands. Two flavours are used:
        - RECT + erode: the OUTPUT mask - square corners (no ellipse blobs),
          net fattening ~+2 px (~0.5 in)/side instead of the old ~1.4 in.
        - ELLIPSE, no erode: the exact pre-de-blob mask, kept ONLY for the
          door-gap finder, which is hyper-sensitive to wall fatness (kernel
          sweeps moved snap counts by half). Gap-finding on the fat mask +
          polygons from the thin mask decouples the two."""
        K = cv2.getStructuringElement
        shp = getattr(cv2, f"MORPH_{shape_flag}")
        mm = np.zeros((H, W), np.uint8)
        for ax, ay, bx, by in struct:
            cv2.line(mm, tp(ax, ay), tp(bx, by), 255, 2)
        mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, K(shp, (9, 9)))
        mm = cv2.dilate(mm, K(shp, (dil, dil)))
        # merge the TWO lines of a double-line wall into one solid band:
        # kernel = max wall thickness (10 in ~ 0.85 ft). Door gaps
        # (>= 2'6" = 127 px) survive.
        wk = int(0.9 * NORM_PPX) | 1
        mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, K(shp, (wk, wk)))
        if ero:
            mm = cv2.erode(mm, K(cv2.MORPH_RECT, (ero, ero)))
        n, lab, stt, _ = cv2.connectedComponentsWithStats(mm, 8)
        keep = np.zeros_like(mm)
        for i in range(1, n):
            if stt[i, cv2.CC_STAT_AREA] > MIN_WALL_AREA_PX:
                keep[lab == i] = 255
        return keep

    m = _mask("RECT", 9, 5)             # output mask (de-blobbed)
    m_snap = _mask("ELLIPSE", 13, 0)    # fat mask for door-gap finding only

    # door clusters are needed BEFORE the wing split: the default wing is the
    # one with the most doors (the largest-area block on a mixed sheet can be
    # a section/detail drawing, not the floor plan)
    door_rects = [d["rect"] for d in drawings if _is_door_layer(d["lname"])]
    has_door_layer = bool(door_rects)
    door_clusters = _cluster_rects(door_rects) if door_rects else []
    door_centers = []                  # ft, full-sheet frame, door-sized only
    for cl in door_clusters:
        wd_ = max(cl.width, cl.height) / ppf
        if DOOR_MIN_FT <= wd_ <= DOOR_MAX_FT:
            door_centers.append((((cl.x0 + cl.x1) / 2 - x0) / ppf,
                                 d_ft - ((cl.y0 + cl.y1) / 2 - y0) / ppf))

    # --- wing split: a sheet can hold several separate building blocks; keep
    # ONE per scene (user directive: no overlapping modules). Coordinates stay
    # in the full-sheet frame; meta reports the wing bbox + count. ---
    wing_groups = _wing_groups(m)
    wing_count = len(wing_groups)
    wbox_ft = None
    w_idx = 0
    if wing_count > 1:
        if wing == "largest" and door_centers:
            def _ft_box(wb):
                return ((wb[0] - PAD_PX) / NORM_PPX,
                        d_ft - (wb[3] - PAD_PX) / NORM_PPX,
                        (wb[2] - PAD_PX) / NORM_PPX,
                        d_ft - (wb[1] - PAD_PX) / NORM_PPX)
            scores = []
            for g in wing_groups:
                bx0, by0, bx1, by1 = _ft_box(g[1])
                scores.append(sum(1 for cx, cy in door_centers
                                  if bx0 - 2 <= cx <= bx1 + 2
                                  and by0 - 2 <= cy <= by1 + 2))
            w_idx = max(range(wing_count),
                        key=lambda i: (scores[i], wing_groups[i][2]))
            if w_idx != 0:
                warnings.append(f"wing auto-pick: wing {w_idx} holds the most "
                                f"doors ({scores[w_idx]}) - overriding the "
                                f"largest-area wing (a non-plan drawing)")
        elif wing != "largest":
            w_idx = int(wing)
        if not (0 <= w_idx < wing_count):
            raise ValueError(f"wing {w_idx} out of range (sheet has {wing_count})")
        labels, wb, _area = wing_groups[w_idx]
        import cv2 as _cv2
        _n, _lab = _cv2.connectedComponents(m, 8)
        m = (np.isin(_lab, list(labels)).astype(np.uint8)) * 255
        m_snap[:wb[1], :] = 0           # crop the fat mask to the same wing
        m_snap[wb[3]:, :] = 0
        m_snap[:, :wb[0]] = 0
        m_snap[:, wb[2]:] = 0
        wx0 = (wb[0] - PAD_PX) / NORM_PPX
        wx1 = (wb[2] - PAD_PX) / NORM_PPX
        wy_top = d_ft - (wb[1] - PAD_PX) / NORM_PPX
        wy_bot = d_ft - (wb[3] - PAD_PX) / NORM_PPX
        wbox_ft = (wx0, wy_bot, wx1, wy_top)
        warnings.append(f"{wing_count} separate wings on this sheet - built wing "
                        f"{w_idx} ({(wx1-wx0):.1f} x {(wy_top-wy_bot):.1f} ft, "
                        f"largest first); request wing=N for the others")

    def _in_wing(cx_ft, cy_ft, pad=1.0):
        return (wbox_ft is None
                or (wbox_ft[0] - pad <= cx_ft <= wbox_ft[2] + pad
                    and wbox_ft[1] - pad <= cy_ft <= wbox_ft[3] + pad))

    # --- doors: snap each swing box onto the doorway GAP in the wall, FILL the
    # gap so the wall is continuous, and remember the strip as the door cut.
    # Without this the doorway is a full-height hole and the door record cuts
    # nothing; with it, scene_to_glb's z-band cut (0..DOOR_HEAD_FT) leaves a
    # proper header/lintel above the door, as built on site. ---
    door_hits = []                     # (strip_bbox_px or None, cluster_rect)
    for cl in door_clusters:
        wd = max(cl.width, cl.height) / ppf
        if not (DOOR_MIN_FT <= wd <= DOOR_MAX_FT):
            continue
        ccx = ((cl.x0 + cl.x1) / 2 - x0) / ppf
        ccy = d_ft - ((cl.y0 + cl.y1) / 2 - y0) / ppf
        if not _in_wing(ccx, ccy, pad=2.0):
            continue
        (ax, ay), (bx, by) = tp(cl.x0, cl.y0), tp(cl.x1, cl.y1)
        hit = _door_gap_strip(m_snap, (ax, ay, bx, by), wd * NORM_PPX)
        if hit:
            comp, bbox_px, (offx, offy) = hit
            for mm in (m, m_snap):      # fill: wall continuous, header cut works
                mm[offy:offy + comp.shape[0], offx:offx + comp.shape[1]][comp] = 255
            # the strip is sized to the FAT mask's jambs; the output mask's
            # walls are eroded ~2 px shorter, leaving hairline slits beside
            # the fill that leak rooms into the outside - overfill m a bit
            gx0, gy0, gx1, gy1 = bbox_px
            m[max(0, gy0 - 5):gy1 + 5, max(0, gx0 - 5):gx1 + 5] = 255
            door_hits.append((bbox_px, cl))
            continue
        # junction doors: the raster trick fails where a crossing wall meets
        # the doorway - fall back to the vector endpoints (jamb-to-jamb gap)
        r = _door_gap_endpoints(struct, cl, ppf, wd)
        if r:
            (sx0, sy0), (sx1, sy1) = tp(r[0], r[1]), tp(r[2], r[3])
            sx0, sx1 = min(sx0, sx1), max(sx0, sx1)
            sy0, sy1 = min(sy0, sy1), max(sy0, sy1)
            for mm in (m, m_snap):      # fill: wall continuous, header cut works
                mm[sy0:sy1, sx0:sx1] = 255
            m[max(0, sy0 - 5):sy1 + 5, max(0, sx0 - 5):sx1 + 5] = 255  # seal slits
            door_hits.append(((sx0, sy0, sx1, sy1), cl))
        else:
            door_hits.append((None, cl))

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

    # --- rooms: enclosed FREE-space components of the wall mask. Doorway
    # strips were filled above, so every room is sealed. Components touching
    # the raster border are the outside world (balconies open to it merge
    # there too - fine for v1). Marker point = the component's most interior
    # pixel (distance transform), NOT the centroid, which lands on a wall in
    # L-shaped rooms. Used by the viewer's walk-inside beacons. ---
    rooms = []
    free = (m == 0).astype(np.uint8)
    ndt = cv2.distanceTransform(free, cv2.DIST_L2, 3)
    ncomp, rlab, rstt, _rcent = cv2.connectedComponentsWithStats(free, 4)
    min_room_px = int(28 * NORM_PPX * NORM_PPX)          # >= ~28 sqft
    Hpx, Wpx = m.shape
    for i in range(1, ncomp):
        rx, ry, rw, rh, rarea = rstt[i]
        if rarea < min_room_px:
            continue
        if rx == 0 or ry == 0 or rx + rw >= Wpx or ry + rh >= Hpx:
            continue                                     # touches border = outside
        comp = (rlab == i)
        d = np.where(comp, ndt, 0)
        py_, px_ = np.unravel_index(int(d.argmax()), d.shape)
        rooms.append({"x": fx(px_), "y": fy(py_),
                      "area_sqft": round(rarea / (NORM_PPX ** 2), 1)})
    rooms.sort(key=lambda r: -r["area_sqft"])
    rooms = rooms[:16]
    for k, r in enumerate(rooms):
        r["id"] = f"r{k}"

    def ft_rect(r):
        return [round((r.x0 - x0) / ppf, 3), round(d_ft - (r.y1 - y0) / ppf, 3),
                round((r.x1 - x0) / ppf, 3), round(d_ft - (r.y0 - y0) / ppf, 3)]

    openings = []

    # --- windows: rects on window layers, plausible sizes ---
    for d in drawings:
        if not _is_window_layer(d["lname"]) or d["lname"] in skipped:
            continue
        r = d["rect"]
        wcx = ((r.x0 + r.x1) / 2 - x0) / ppf
        wcy = d_ft - ((r.y0 + r.y1) / 2 - y0) / ppf
        if not _in_wing(wcx, wcy):
            continue
        L = max(r.width, r.height) / ppf
        T = min(r.width, r.height) / ppf
        if 1.5 <= L <= 8.0 and 0.05 <= T <= 1.2:
            openings.append({"id": f"o{len(openings)}", "type": "window",
                             "footprint": ft_rect(r),
                             "z": [WINDOW_SILL_FT, WINDOW_HEAD_FT]})
    has_window_layer = any(_is_window_layer(d["lname"]) and d["lname"] not in skipped
                           for d in drawings)

    # --- windows PLAN B: symbols embedded in the WALL layer (no window layer).
    # Window-sized rects sitting on the wall mask, away from doors, are window
    # symbols. Cut = the rect itself -> a punched hole with jambs, sill 3',
    # head 7' (real construction, not a half-fallen wall). ---
    if not openings or all(o["type"] == "door" for o in openings):
        def _on_wall(r):
            """Centre of rect r sits on (or within ~0.35 ft of) the wall mask.
            A single-pixel test missed hollow/thin walls - use a patch."""
            (ax, ay), (bx, by) = tp(r.x0, r.y0), tp(r.x1, r.y1)
            cxp, cyp = (ax + bx) // 2, (ay + by) // 2
            R = int(0.35 * NORM_PPX)
            y0_, y1_ = max(0, cyp - R), min(m.shape[0], cyp + R + 1)
            x0_, x1_ = max(0, cxp - R), min(m.shape[1], cxp + R + 1)
            return y1_ > y0_ and x1_ > x0_ and bool(m[y0_:y1_, x0_:x1_].any())

        # per-rect evaluation FIRST (the old cluster-then-test merged
        # adjacent windows into >8 ft super-rects and rejected them: on
        # FLOOR PLAN only 1 of ~45 candidates survived)
        accepted = []
        for d in drawings:
            if not _is_wall_layer(d["lname"]) or d["lname"] in skipped:
                continue
            r = d["rect"]
            L = max(r.width, r.height) / ppf
            T = min(r.width, r.height) / ppf
            if 1.5 <= L <= 8.0 and 0.05 <= T <= 1.2 and _on_wall(r):
                accepted.append(r)
        added = 0
        for cl in (_cluster_rects(accepted, gap=1.0) if accepted else []):
            L = max(cl.width, cl.height) / ppf
            if 1.5 <= L <= 8.0:
                group = [cl]           # duplicates of ONE window: use the bbox
            else:                      # adjacent windows fused: keep members,
                group = []             # dropping near-duplicates
                members = sorted((r for r in accepted
                                  if fitz_rect_intersects(r, cl)),
                                 key=lambda r: -(r.width * r.height))
                for r in members:
                    if all(not fitz_rect_overlaps_half(r, g) for g in group):
                        group.append(r)
            for r in group:
                if not (1.5 <= max(r.width, r.height) / ppf <= 8.0):
                    continue
                fp = ft_rect(r)
                fcx, fcy = (fp[0] + fp[2]) / 2, (fp[1] + fp[3]) / 2
                if not _in_wing(fcx, fcy):
                    continue
                near_door = any(o["type"] == "door"
                                and abs((o["footprint"][0]+o["footprint"][2])/2 - fcx) < 2.5
                                and abs((o["footprint"][1]+o["footprint"][3])/2 - fcy) < 2.5
                                for o in openings)
                if near_door:
                    continue
                openings.append({"id": f"o{len(openings)}", "type": "window",
                                 "footprint": fp, "z": [WINDOW_SILL_FT, WINDOW_HEAD_FT]})
                added += 1
        if added:
            has_window_layer = True
            warnings.append(f"{added} window(s) extracted from wall-layer symbols")

    # --- windows PLAN C: W/V text TAGS + the user's opening legend. The tag
    # marks the window on the wall; the legend gives its true width. ---
    LEGEND = {"W1": (5.0, 3.0, 7.0), "W2": (4.0, 3.0, 7.0), "W3": (3.0, 3.5, 6.5),
              "W": (4.0, 3.0, 7.0), "V": (2.0, 5.5, 7.0), "V1": (2.0, 5.5, 7.0)}
    import re as _re
    tags = []
    for wd in page.get_text("words"):
        t = wd[4].strip().upper()
        if t in LEGEND:
            import fitz as _fitz
            r = (_fitz.Rect(wd[:4]) * page.rotation_matrix).normalize()
            tags.append((t, (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))
    tadd = 0
    for t, cx, cy in tags:
        wft, sill, head = LEGEND[t]
        pxc = tp(cx, cy)
        if not (0 <= pxc[1] < m.shape[0] and 0 <= pxc[0] < m.shape[1]):
            continue
        # find the wall near the tag; orientation from local mask. Try a tight
        # 2.5 ft radius first (right wall), widen to 4 ft only if empty (tags
        # sit up to ~3.8 ft off the wall now that walls are true-position).
        patch = None
        for R_ft in (2.5, 4.0):
            R = int(R_ft * NORM_PPX)
            y0_, y1_ = max(0, pxc[1]-R), min(m.shape[0], pxc[1]+R)
            x0_, x1_ = max(0, pxc[0]-R), min(m.shape[1], pxc[0]+R)
            patch = m[y0_:y1_, x0_:x1_]
            if patch.any():
                break
        if patch is None or not patch.any():
            continue
        import numpy as _np
        ys, xs2 = _np.nonzero(patch)
        wy = (ys.mean() + y0_)
        wx = (xs2.mean() + x0_)
        horiz = (xs2.max() - xs2.min()) >= (ys.max() - ys.min())
        fcx = (wx - PAD_PX) / NORM_PPX
        fcy = d_ft - (wy - PAD_PX) / NORM_PPX
        if not _in_wing(fcx, fcy):
            continue
        if horiz:
            fp = [round(fcx - wft/2, 3), round(fcy - 0.6, 3),
                  round(fcx + wft/2, 3), round(fcy + 0.6, 3)]
        else:
            fp = [round(fcx - 0.6, 3), round(fcy - wft/2, 3),
                  round(fcx + 0.6, 3), round(fcy + wft/2, 3)]
        openings.append({"id": f"o{len(openings)}", "type": "window", "tag": t,
                         "footprint": fp, "z": [sill, head]})
        tadd += 1
    if tadd:
        has_window_layer = True
        warnings.append(f"{tadd} window(s)/ventilator(s) placed from W/V text tags + legend")

    # --- doors: footprint = the doorway strip ON the wall (found above, so the
    # z-band cut applies and a header remains); swing_area = the leaf+arc box,
    # kept for the viewer (door placement / swing animation later). ---
    fallback_doors = 0
    for bbox_px, cl in door_hits:
        rec = {"id": f"o{len(openings)}", "type": "door",
               "z": [0, DOOR_HEAD_FT], "swing_area": ft_rect(cl),
               "snapped": bool(bbox_px)}
        if bbox_px:
            px0, py0, px1, py1 = bbox_px
            rec["footprint"] = [fx(px0), fy(py1), fx(px1), fy(py0)]
        else:
            rec["footprint"] = ft_rect(cl)       # swing box; snapped=False flags it
            fallback_doors += 1
        openings.append(rec)
    if fallback_doors:
        warnings.append(f"{fallback_doors} door(s): doorway gap not found in the "
                        "wall mask - swing box used as cut (check these doors)")

    # --- columns (dominant-size boxes only, deduplicated by cluster) ---
    columns = []
    if col_rects:
        if scale_src == "cad_units":
            # real units known - accept any plausible column size (9x9..24x24 in)
            dom_candidates = [max(r.width, r.height) for r in col_rects
                              if 0.5 * ppf <= max(r.width, r.height) <= 2.2 * ppf]
        else:
            dom_candidates = [max(r.width, r.height) for r in col_rects
                              if abs(max(r.width, r.height) - ppf * COL_FT) < 0.6]
        if dom_candidates:
            dom = max(dom_candidates)
            uniq = _cluster_rects([r for r in col_rects
                                   if abs(max(r.width, r.height) - dom) < 0.6], gap=1.0)
            for r in uniq:
                _cx = ((r.x0 + r.x1) / 2 - x0) / ppf
                _cy = d_ft - ((r.y0 + r.y1) / 2 - y0) / ppf
                if not _in_wing(_cx, _cy):
                    continue
                columns.append({"id": f"c{len(columns)}", "kind": "column",
                                "x": round((r.x0 - x0) / ppf, 3),
                                "y": round(d_ft - (r.y1 - y0) / ppf, 3),
                                "w": round(r.width / ppf, 3), "d": round(r.height / ppf, 3)})

    if scale_src == "column_box_12in":
        warnings.append("scale from dominant column box = 12 in (provisional)")
    elif scale_src not in ("dimension_text", "cad_units"):
        warnings.append("scale is a placeholder until dimension text is readable")
    if not has_window_layer:
        warnings.append("no window layer found - windows not extracted")
    if not has_door_layer:
        warnings.append("no door layer found - doors not extracted")

    _door_scale_sanity(openings, warnings)

    if wbox_ft is not None:
        out_w = float(wbox_ft[2] - wbox_ft[0])
        out_d = float(wbox_ft[3] - wbox_ft[1])
        sx, sy = float(wbox_ft[0]), float(wbox_ft[1])

        def _shift_pt(p):
            return [round(p[0] - sx, 3), round(p[1] - sy, 3)]

        for w in walls_poly:
            w["outer"] = [_shift_pt(p) for p in w["outer"]]
            w["holes"] = [[_shift_pt(p) for p in h] for h in (w["holes"] or [])]
        for o in openings:
            for key in ("footprint", "swing_area"):
                if o.get(key):
                    fp = o[key]
                    o[key] = [round(fp[0] - sx, 3), round(fp[1] - sy, 3),
                              round(fp[2] - sx, 3), round(fp[3] - sy, 3)]
        for c in columns:
            c["x"] = round(c["x"] - sx, 3)
            c["y"] = round(c["y"] - sy, 3)
        for r in rooms:
            r["x"] = round(r["x"] - sx, 3)
            r["y"] = round(r["y"] - sy, 3)
    else:
        out_w, out_d = w_ft, d_ft
    return {
        "meta": {
            "source": f"vector_pdf_{mode}",
            "units": "ft",
            "wall_height_ft": WALL_HEIGHT_FT,
            "plan_width_ft": round(out_w, 3),
            "plan_depth_ft": round(out_d, 3),
            "scale": {"source": scale_src, "pt_per_ft": round(ppf, 3)},
            "wing": {"count": wing_count, "index": w_idx,
                     "bbox_ft": [round(v, 3) for v in wbox_ft] if wbox_ft else None},
            "warnings": warnings,
        },
        "wall_types": {},
        "rooms": rooms,             # walk-inside beacons: most-interior point per room
        "walls": [],                # axis-aligned walls unused on this path
        "walls_poly": walls_poly,   # exact footprints incl. angled walls
        "openings": openings,
        "columns": columns,
        "ducts": [], "furniture": [],
    }
