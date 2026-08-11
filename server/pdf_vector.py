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

import furnish

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
WALL_MINLEN_PT = 8.0         # a real wall line is longer than this; below = brick
                             # hatch / outlined text (median can be ~0.2 pt)
WALL_MINKEEP = 8             # need this many long lines to treat a hatch-heavy
                             # layer as walls (else it is genuinely just text)


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
    # Pass 1: proper wall layers (median line is feet-long = real walls).
    short = []
    for name, ds in sorted(by_layer.items()):
        ls = _segs(ds, lambda n: True)
        if not ls:
            continue
        med = statistics.median(math.hypot(x2 - x1, y2 - y1) for x1, y1, x2, y2 in ls)
        if med >= TEXT_MED_MAXLEN_PT:
            segs += ls
        else:
            short.append((name, ls, med))
    have_proper = bool(segs)
    # Pass 2: short-median layers are brick HATCH or outlined text. Recover the
    # LONG lines (real walls) ONLY when there is NO proper wall layer — else those
    # long strokes are hatch/projections/decoys that would over-extend the plan
    # (e.g. FLOOR PLAN has a real 'ar wall' AND a hatch 'wall'; use 'ar wall').
    for name, ls, med in short:
        long_ls = [s for s in ls
                   if math.hypot(s[2] - s[0], s[3] - s[1]) >= WALL_MINLEN_PT]
        if not have_proper and len(long_ls) >= WALL_MINKEEP:
            segs += long_ls
            warnings.append(f"layer '{name}': brick-hatch walls - kept "
                            f"{len(long_ls)} wall lines, dropped "
                            f"{len(ls) - len(long_ls)} hatch/text strokes")
        else:
            dropped.add(name)
            warnings.append(f"layer '{name}' skipped: text-like "
                            f"(median seg {med:.1f} pt, n={len(ls)})")
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


def gap_openings(segs, min_w, max_w, min_flank=1.0,
                 face_tol=0.35, group_tol=1.2, junction_pad=0.4):
    """Detect openings (doorway / window gaps) in axis-aligned wall-face
    segments WITHOUT layer names. Pure geometry, so it is unit-testable:
    `segs` is a list of (x0, y0, x1, y1) and EVERY threshold is in the SAME
    unit (feet in production).

    An opening is a run-to-run gap along one wall line whose width is in
    [min_w, max_w], flanked by wall >= min_flank on both sides, with NO
    perpendicular wall crossing the gap (that crossing = a T/L junction, not a
    doorway). Returns [{'cx','cy','w','orient'}] where orient is 'h' or 'v'
    (the wall's direction) and (cx, cy) is the gap centre.

    This is what lets flattened PDFs (no CAD layers, no door symbols) still
    get doors + sealed rooms: the gaps we fill to make walls continuous ARE
    the openings.
    """
    # bucket every segment as horizontal or vertical by its dominant axis
    H, V = [], []                        # (lo, hi, perp) along-axis intervals
    for x0, y0, x1, y1 in segs:
        if abs(y1 - y0) <= abs(x1 - x0):        # horizontal wall face
            if abs(y1 - y0) <= face_tol:
                H.append((min(x0, x1), max(x0, x1), (y0 + y1) / 2))
        else:                                    # vertical wall face
            if abs(x1 - x0) <= face_tol:
                V.append((min(y0, y1), max(y0, y1), (x0 + x1) / 2))

    def _runs_by_line(lines):
        """Group faces by their perpendicular coord (merging the two faces of
        one wall), then union the along-axis intervals into solid runs."""
        lines = sorted(lines, key=lambda s: s[2])
        groups = []                       # [perp_mean, [intervals]]
        for lo, hi, perp in lines:
            if groups and perp - groups[-1][0] <= group_tol:
                groups[-1][1].append((lo, hi))
                # rolling mean keeps the key near the wall centre-line
                groups[-1][0] = (groups[-1][0] + perp) / 2
            else:
                groups.append([perp, [(lo, hi)]])
        out = []
        for perp, ivs in groups:
            ivs.sort()
            merged = [list(ivs[0])]
            for lo, hi in ivs[1:]:
                if lo <= merged[-1][1] + face_tol:
                    merged[-1][1] = max(merged[-1][1], hi)
                else:
                    merged.append([lo, hi])
            out.append((perp, merged))
        return out

    def _crosses(cross_runs, at_perp, at_along):
        """True if a perpendicular wall run passes through (at_perp, at_along)
        — i.e. a junction sits in this gap, so it is not a doorway."""
        for perp, merged in cross_runs:
            if abs(perp - at_along) <= junction_pad:
                for lo, hi in merged:
                    if lo - junction_pad <= at_perp <= hi + junction_pad:
                        return True
        return False

    h_runs = _runs_by_line(H)
    v_runs = _runs_by_line(V)
    out = []
    for orient, runs, cross in (('h', h_runs, v_runs), ('v', v_runs, h_runs)):
        for perp, merged in runs:
            for i in range(len(merged) - 1):
                a_lo, a_hi = merged[i]
                b_lo, b_hi = merged[i + 1]
                gap = b_lo - a_hi
                if not (min_w <= gap <= max_w):
                    continue
                if (a_hi - a_lo) < min_flank or (b_hi - b_lo) < min_flank:
                    continue
                mid = (a_hi + b_lo) / 2
                if _crosses(cross, perp, mid):
                    continue
                if orient == 'h':
                    out.append({'cx': mid, 'cy': perp, 'w': gap, 'orient': 'h'})
                else:
                    out.append({'cx': perp, 'cy': mid, 'w': gap, 'orient': 'v'})

    # dedup: the two faces of a wall can survive as separate lines and yield
    # the same gap twice — keep one per (centre, orientation)
    ded = []
    for o in out:
        if not any(o['orient'] == p['orient']
                   and abs(o['cx'] - p['cx']) <= min_w
                   and abs(o['cy'] - p['cy']) <= group_tol for p in ded):
            ded.append(o)
    return ded


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


def _wing_room_pockets(m_env, bbox_px, min_room_px):
    """Count enclosed free-space pockets inside a wing's bbox — a cheap 'how
    many rooms does this region hold'. The real FLOOR PLAN wing is full of
    rooms; a dimension-string / section / title block region that got captured
    as a tall thin 'wing' has none. Used to pick the right wing when there's no
    door layer to score by."""
    import cv2
    import numpy as np
    x0, y0, x1, y1 = bbox_px
    sub = m_env[max(0, y0):y1, max(0, x0):x1]
    if sub.size == 0:
        return 0
    free = (sub == 0).astype(np.uint8)
    n, _lab, stt, _c = cv2.connectedComponentsWithStats(free, 4)
    Hs, Ws = sub.shape
    cnt = 0
    for i in range(1, n):
        rx, ry, rw, rh, ra = stt[i]
        if ra < min_room_px:
            continue
        if rx == 0 or ry == 0 or rx + rw >= Ws or ry + rh >= Hs:
            continue                         # touches the wing border = outside
        cnt += 1
    return cnt


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


_DIMPAIR = None


def _room_dim_scale(page, drawings, warnings, pairs=None, wall_segs=None):
    """Scale from room-DIMENSION text like 9'0"X12'0" (a W x H pair written
    inside a room). Very common on Indian/CAD residential plans that carry no
    column layer and no on-line dimension text. For each such label we measure
    the room it sits in (nearest walls in each direction) and vote
    extent_points / stated_feet; the true scale is where the votes cluster.
    Returns pt/ft or None. Scale-free: uses only ratios.

    `pairs` supplies already-read dimension labels (room_dims.dimension_pairs,
    OCR-fed) for sheets whose lettering is outlined and whose live text is
    therefore empty. Without it the live-text reader below is used, exactly as
    before."""
    import re
    import statistics
    import fitz
    global _DIMPAIR
    if _DIMPAIR is None:
        _DIMPAIR = re.compile(r"(\d+)'(\d+)?\"?[xX×](\d+)'(\d+)?\"?")
    mat = page.rotation_matrix
    toks = []                             # (cx, cy, w_ft, h_ft) in points
    if pairs:
        toks = [(p["x"], p["y"], p["w_ft"], p["h_ft"]) for p in pairs
                if 3 <= p["w_ft"] <= 60 and 3 <= p["h_ft"] <= 60]
    else:
        for w in page.get_text("words"):
            m = _DIMPAIR.search((w[4] or "").replace(" ", ""))
            if not m:
                continue
            wf = int(m.group(1)) + int(m.group(2) or 0) / 12.0
            hf = int(m.group(3)) + int(m.group(4) or 0) / 12.0
            if not (3 <= wf <= 60 and 3 <= hf <= 60):
                continue
            r = (fitz.Rect(w[:4]) * mat).normalize()
            toks.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, wf, hf))
    if len(toks) < 2:
        return None

    H, V = [], []                         # H: (y, x0, x1); V: (x, y0, y1)
    if wall_segs:
        # A room's extent must be measured between WALLS. Scanning every drawn
        # line works on a live-text sheet, but on an outlined-lettering sheet
        # the nearest line above a label is a stroke of the label's own
        # letters: FLOOR PLAN.pdf voted 17.97 pt/ft that way against a true
        # ~28. Given the wall faces, use only those.
        for ax, ay, bx, by in wall_segs:
            if abs(ay - by) < 1.5 and abs(ax - bx) > 3:
                H.append(((ay + by) / 2, min(ax, bx), max(ax, bx)))
            elif abs(ax - bx) < 1.5 and abs(ay - by) > 3:
                V.append(((ax + bx) / 2, min(ay, by), max(ay, by)))
    else:
        for d in drawings:
            for it in d["items"]:
                if it[0] != "l":
                    continue
                a, b = it[1], it[2]
                if abs(a.y - b.y) < 1.5 and abs(a.x - b.x) > 3:
                    H.append(((a.y + b.y) / 2, min(a.x, b.x), max(a.x, b.x)))
                elif abs(a.x - b.x) < 1.5 and abs(a.y - b.y) > 3:
                    V.append(((a.x + b.x) / 2, min(a.y, b.y), max(a.y, b.y)))

    votes = []
    for cx, cy, wf, hf in toks:
        above = max((y for y, x0, x1 in H if y < cy and x0 - 2 <= cx <= x1 + 2), default=None)
        below = min((y for y, x0, x1 in H if y > cy and x0 - 2 <= cx <= x1 + 2), default=None)
        left = max((x for x, y0, y1 in V if x < cx and y0 - 2 <= cy <= y1 + 2), default=None)
        right = min((x for x, y0, y1 in V if x > cx and y0 - 2 <= cy <= y1 + 2), default=None)
        vext = (below - above) if (above is not None and below is not None) else None
        hext = (right - left) if (left is not None and right is not None) else None
        # room orientation is unknown (and pages rotate), so try both pairings;
        # correct ppf clusters, wrong ones scatter and get trimmed
        for ext, dim in ((hext, wf), (vext, hf), (hext, hf), (vext, wf)):
            if ext and dim and ext / dim > 2:
                votes.append(ext / dim)
    if len(votes) < 2:
        return None
    med = statistics.median(votes)
    good = [v for v in votes if 0.82 * med <= v <= 1.18 * med]
    if len(good) < 2:
        return None
    ppf = statistics.median(good)
    warnings.append(f"scale from room-dimension text (WxH): {ppf:.2f} pt/ft "
                    f"({len(good)} agreeing votes)")
    return ppf


def _overall_dims(page, drawings, ppf):
    """GENERAL rule (no per-plan logic): collect VERIFIED overall-dimension
    candidates — a ft-in text token hugging a parallel drawn line whose length
    matches the stated feet at the chosen scale (within 6%). Returns
    (horizontal_vals_ft, vertical_vals_ft).

    Why: the drawn linework extent includes chhajja/balcony PROJECTIONS, so
    plan_width/depth read bigger than the architect's own overall dimension
    (anchor case: neelachala FIRST FLOOR measures 39.98 x 66.9 ft of linework
    but is dimensioned 38'3" x 64'2" — the user-confirmed plot). When such a
    verified dimension exists and the extent only exceeds it a little, the
    architect's number is the truth worth reporting."""
    import re
    import fitz
    if not ppf:
        return [], []
    mat = page.rotation_matrix
    FTIN = re.compile(r"^(\d+)['’]-?(\d+)?[\"”]?$")
    toks = []
    for w in page.get_text("words"):
        m = FTIN.match(w[4].strip())
        if not m:
            continue
        val = int(m.group(1)) + int(m.group(2) or 0) / 12.0
        if 12 <= val <= 400:                  # building-sized only
            r = (fitz.Rect(w[:4]) * mat).normalize()
            toks.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, val))
    if not toks:
        return [], []
    hs, vs = [], []
    for d in drawings:
        for it in d["items"]:
            if it[0] != "l":
                continue
            a, b = it[1], it[2]
            dx, dy = b.x - a.x, b.y - a.y
            L = math.hypot(dx, dy)
            if L < 30 or L > BORDER_MAXLEN_PT:
                continue
            for cx, cy, val in toks:
                if abs(L / val - ppf) > 0.06 * ppf:
                    continue                  # line length must MATCH the text
                t = ((cx - a.x) * dx + (cy - a.y) * dy) / (L * L)
                if not (0.15 < t < 0.85):
                    continue                  # text sits mid-line
                perp = math.hypot(cx - (a.x + t * dx), cy - (a.y + t * dy))
                if perp > 9:
                    continue                  # and hugs it
                (hs if abs(dx) >= abs(dy) else vs).append(val)
    return hs, vs


def _snap_envelope(dim_ft, candidates):
    """Largest verified overall dimension that the drawn extent only exceeds
    by projections (<= 12%) and never undercuts (> 2%). None = keep extent."""
    best = None
    for v in candidates:
        if 0.88 * dim_ft <= v <= 1.02 * dim_ft:
            best = v if best is None else max(best, v)
    return best


FOOTPRINT_MIN_COMP_FRAC = 0.10      # ignore wall specks below 10% of the biggest


def _free_ring_endpoints(seg_px, join_tol, min_gap):
    """Wall ends that meet nothing — the jambs of an opening in the ring.

    A wall end that lands on another wall (corner, T-junction) is joined; one
    that lands on nothing is a JAMB: a balcony face, an entrance, a doorway.
    Pairs closer than `min_gap` (one wall thickness) are skipped, because the
    two faces of a single wall end beside each other and capping that gap
    closes nothing. Returns [(p, q), ...] pixel pairs to bridge. Pure."""
    import numpy as np
    if not seg_px:
        return []
    # The WALL RUN an end belongs to: every segment collinear with it, summed.
    # A wall line is drawn as many short pieces between junctions, so one
    # segment's own length is far too small a bound — the run is the wall.
    runs = {}
    for x0, y0, x1, y1 in seg_px:
        horiz = abs(y1 - y0) <= abs(x1 - x0)
        perp = (y0 + y1) / 2.0 if horiz else (x0 + x1) / 2.0
        key = (horiz, round(perp / max(1e-6, join_tol)))
        runs[key] = runs.get(key, 0.0) + math.hypot(x1 - x0, y1 - y0)

    ends, runlen = [], []
    for x0, y0, x1, y1 in seg_px:
        horiz = abs(y1 - y0) <= abs(x1 - x0)
        perp = (y0 + y1) / 2.0 if horiz else (x0 + x1) / 2.0
        L = runs[(horiz, round(perp / max(1e-6, join_tol)))]
        ends += [(float(x0), float(y0)), (float(x1), float(y1))]
        runlen += [L, L]                 # the wall run this end belongs to
    arr = np.array(ends, dtype=np.float64)
    if len(arr) < 2:
        return []
    d = np.linalg.norm(arr[:, None, :] - arr[None, :, :], axis=2)
    touching = (d <= join_tol).sum(axis=1)          # counts itself
    free = [i for i in range(len(arr)) if touching[i] <= 1]
    pairs, used = [], set()
    cand = sorted(((d[i, j], i, j) for k, i in enumerate(free)
                   for j in free[k + 1:] if d[i, j] >= min_gap))
    for dist, i, j in cand:
        if i in used or j in used:
            continue
        used.add(i)
        used.add(j)
        # A GAP CANNOT BE LONGER THAN THE WALL IT IS A HOLE IN. The bound is
        # the longer of the two walls the gap sits between — so a 42 ft
        # balcony face between two 40 ft+ walls is legitimate on a 95x30 strip,
        # while a 96 ft span between two stubs is the sheet, not an opening.
        pairs.append((arr[i], arr[j], dist, max(runlen[i], runlen[j])))
    return pairs


def _footprint_from_walls(wall_mask, seg_px=None, norm_ppx=NORM_PPX,
                          min_frac=FOOTPRINT_MIN_COMP_FRAC):
    """The building footprint, from the OUTER WALL RING (W-1).

    The old footprint closed the wall mask with a fixed kernel and filled the
    result. That kernel is a guess about the widest opening in the outer wall,
    and no value is right: a 6 ft kernel leaves FLOOR PLAN's balcony faces open
    (footprint 1240 sqft against a real plate of ~1951), while 14 ft closes
    them and simultaneously inflates neelachala FIRST FLOOR past its own plot.

    So bridge the ring instead of dilating it. Each wall COMPONENT is joined to
    the next by a straight line between their two CLOSEST points — a minimum
    spanning tree over the components — so a balcony face is bridged by a line
    exactly as long as that gap happens to be, and nothing else grows. Then the
    largest external contour is the footprint.

    Returns (filled_footprint_mask, bridged_ft, rejected_ft); the mask is None
    when no contour can be formed.
    """
    import cv2
    import numpy as np
    n, lab, stt, _c = cv2.connectedComponentsWithStats(wall_mask, 8)
    if n <= 1:
        return None, [], [], None, []
    areas = [(i, stt[i, cv2.CC_STAT_AREA]) for i in range(1, n)]
    biggest = max(a for _i, a in areas)
    keep = [i for i, a in areas if a >= min_frac * biggest]
    work = np.zeros_like(wall_mask)
    for i in keep:
        work[lab == i] = 255

    # 1) bridge openings WITHIN the ring — jamb to jamb. FLOOR PLAN's walls are
    # a single connected component whose ring is open at the balcony faces, so
    # component-to-component bridging alone never fires there.
    # Jamb bridges are bounded per-gap by the wall run they sit in (see
    # _free_ring_endpoints). COMPONENT bridges join separate wall blobs rather
    # than filling a hole in one wall, so they keep a building-relative bound.
    max_bridge = float(min(wall_mask.shape))
    bridges, rejected, rejected_lines = [], [], []
    thick = max(3, int(0.5 * norm_ppx))
    for pa, pb, dist, bound in _free_ring_endpoints(seg_px or [],
                                                    join_tol=0.35 * norm_ppx,
                                                    min_gap=1.2 * norm_ppx):
        if dist > bound:
            rejected.append(round(dist / norm_ppx, 2))
            rejected_lines.append((pa, pb))       # an OPEN SIDE (B-1)
            continue
        cv2.line(work, (int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])),
                 255, thick)
        bridges.append(round(dist / norm_ppx, 2))

    # 2) boundary points per component (subsampled: only the nearest PAIR matters)
    pts = []
    for i in keep:
        comp = np.zeros_like(wall_mask)
        comp[lab == i] = 255
        cnts, _h = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        p = np.vstack([c.reshape(-1, 2) for c in cnts]) if cnts else np.empty((0, 2))
        if len(p) > 400:
            p = p[:: max(1, len(p) // 400)]
        pts.append(p.astype(np.float64))

    # 3) Prim's MST over components, weight = distance between closest points
    if len(pts) > 1:
        inside, outside = {0}, set(range(1, len(pts)))
        while outside:
            best = None                   # (dist, i, j, pi, pj)
            for i in inside:
                for j in outside:
                    if len(pts[i]) == 0 or len(pts[j]) == 0:
                        continue
                    d = np.linalg.norm(pts[i][:, None, :] - pts[j][None, :, :],
                                       axis=2)
                    k = int(d.argmin())
                    a, b = divmod(k, d.shape[1])
                    if best is None or d[a, b] < best[0]:
                        best = (float(d[a, b]), i, j, pts[i][a], pts[j][b])
            if best is None:
                break
            dist, _i, j, pa, pb = best
            if dist > max_bridge:            # same relative cap as the jambs
                rejected.append(round(dist / norm_ppx, 2))
                rejected_lines.append((pa, pb))
                outside.discard(j)           # leave it a separate component
                continue
            cv2.line(work, (int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])),
                     255, thick)
            bridges.append(round(dist / norm_ppx, 2))
            inside.add(j)
            outside.discard(j)

    cnts, _h = cv2.findContours(work, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None, bridges, rejected, None, rejected_lines
    foot = np.zeros_like(wall_mask)
    cv2.drawContours(foot, [max(cnts, key=cv2.contourArea)], -1, 255, -1)

    # B-1: the spaces behind the REJECTED spans are the open sides — balconies.
    # Closing the ring with those spans too gives footprint + balconies; the
    # difference is the balcony area. The span is drawn ONLY on this scratch
    # mask, never on the wall geometry, so the open face is never built as a
    # wall (B-4).
    foot_ext = None
    if rejected_lines:
        ext = work.copy()
        for pa, pb in rejected_lines:
            cv2.line(ext, (int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])),
                     255, thick)
        ecnts, _eh = cv2.findContours(ext, cv2.RETR_EXTERNAL,
                                      cv2.CHAIN_APPROX_SIMPLE)
        if ecnts:
            foot_ext = np.zeros_like(wall_mask)
            cv2.drawContours(foot_ext, [max(ecnts, key=cv2.contourArea)],
                             -1, 255, -1)
    return foot, bridges, rejected, foot_ext, rejected_lines


def _footprint_free_mask(wall_mask, seal_ft, norm_ppx=NORM_PPX):
    """G1 wall-gap healing: interior free-space BOUNDED by the building
    footprint. Closes the wall blob (bridges outer-wall gaps up to seal_ft),
    fills its largest outer contour = footprint, then subtracts the walls. Lets
    rooms form even when the outer wall is broken/missing — which otherwise
    leaks interior free-space to the image border and yields 0 rooms (0%
    efficiency). Interior partitions are still subtracted, so real rooms stay
    separate. Pure -> unit-tested. Returns a 0/255 mask or None."""
    import cv2
    import numpy as np
    fk = max(3, int(seal_ft * norm_ppx)) | 1
    blob = cv2.morphologyEx(wall_mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_RECT, (fk, fk)))
    cnts, _h = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    foot = np.zeros_like(wall_mask)
    cv2.drawContours(foot, [max(cnts, key=cv2.contourArea)], -1, 255, -1)
    return cv2.bitwise_and(foot, cv2.bitwise_not(wall_mask))


def _scale_ppf(col_rects, bbox_w_pt, width_ft):
    """Points-per-foot. Priority: dominant column box (=1 ft) > PPF env > width_ft."""
    if col_rects:
        import numpy as np
        sizes = [round(max(r.width, r.height), 1) for r in col_rects]
        vals, cnt = np.unique(sizes, return_counts=True)
        return float(vals[cnt.argmax()]) / COL_FT, "column_box_12in"
    if os.environ.get("PPF"):
        _ppf = float(os.environ["PPF"])
        if _ppf > 0:                      # guard: ppf is a divisor in ~15 places
            return _ppf, "env_ppf"
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


def _classify_furniture(a, b, hint):
    """Name a furniture block from its two side lengths (feet) + a layer hint.
    Pure + unit-tested. hint prefix 'san' -> sanitaryware, 'kit' -> kitchen,
    anything else -> general furniture. Returns a type string the GLB builder
    knows (bed/sofa/cupboard/table/chair/sidetable/commode/basin/counter) or
    None for symbol fragments and whole-room outlines."""
    w, l = (a, b) if a <= b else (b, a)         # short side, long side
    h = (hint or "").lower()
    if h.startswith("san"):
        if not (0.7 <= w <= 2.5 and 1.0 <= l <= 3.0):
            return None
        return "commode" if l >= 1.8 else "basin"
    if h.startswith("kit"):
        if not (0.9 <= w <= 4.0 and 1.5 <= l <= 12.0):
            return None
        return "counter"
    # general furniture
    if w < 0.7 or l > 12.0:
        return None
    if w >= 4.5 and l >= 5.5:
        return "bed"                             # double bed
    if 2.6 <= w <= 3.6 and l >= 6.0:
        return "bed"                             # single bed
    if 2.2 <= w <= 3.2 and 4.5 <= l < 6.5:
        return "sofa"
    if w >= 3.2 and 4.0 <= l <= 6.0:
        return "table"
    if w < 2.0 and l >= 4.0:
        return "cupboard"
    if l / w <= 1.2 and l <= 2.2:
        return "sidetable"
    if w <= 2.4 and l <= 3.0:
        return "chair"
    return None


_FURN_LAYER_KW = ("furn", "sanitar", "kitchen", "fixture", "toilet",
                  "wardrobe", "wc")


def _furn_hint(lname):
    if "sanitar" in lname or "toilet" in lname or "wc" in lname:
        return "san"
    if "kitchen" in lname:
        return "kit"
    return "furn"


def _rect_overlap_frac(a, b):
    """Intersection area / smaller-rect area (0..1)."""
    ix = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    iy = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    inter = ix * iy
    small = min(a.width * a.height, b.width * b.height) or 1.0
    return inter / small


def _furniture_items(drawings, ppf):
    """Extract + classify + dedupe furniture rects from furniture/sanitary/
    kitchen layers. CAD blocks often stack an outline rect on a detail rect of
    the same footprint — keep the larger one only. Returns [(type, fitz.Rect)]."""
    cand = []
    for d in drawings:
        ln = d.get("lname", "")
        if not any(k in ln for k in _FURN_LAYER_KW):
            continue
        r = d.get("rect")
        if r is None:
            continue
        t = _classify_furniture(r.width / ppf, r.height / ppf, _furn_hint(ln))
        if t:
            cand.append((t, r))
    kept = []
    for t, r in sorted(cand, key=lambda tr: -(tr[1].width * tr[1].height)):
        if any(_rect_overlap_frac(r, kr) > 0.6 for _, kr in kept):
            continue
        kept.append((t, r))
    return kept


OCR_TAG_MIN_CONF = 40            # OCR tags below this are noise, not tags
NOMINAL_DOOR_FT = 3.0            # 2'6"-3'6" band centre (Indian residential)
GUESSED_SCALES = ("column_box_12in", "assumed_width", "env_ppf")


def _door_median_ft(openings):
    """Median snapped-door width in feet, or None if < 5 snapped doors."""
    import statistics
    widths = []
    for o in openings:
        if o.get("type") == "door" and o.get("snapped") and o.get("footprint"):
            x0, y0, x1, y1 = o["footprint"]
            widths.append(max(x1 - x0, y1 - y0))
    return statistics.median(widths) if len(widths) >= 5 else None


def _assign_room_labels(rooms, tokens, only_untyped=False):
    """Give each room the label TOKEN nearest its interior point AND inside its
    own free-space component (so a merged region can't steal a neighbour's
    label). tokens: [(feet_x, feet_y, component_label, room_type), ...].
    only_untyped=True skips rooms that already have a type, so a lower-
    confidence source (OCR) fills gaps without overwriting live text.
    Returns how many rooms it newly typed. Pure -> unit-tested."""
    gained = 0
    for r in rooms:
        if only_untyped and r.get("type"):
            continue
        was_typed = bool(r.get("type"))
        best, best_d = None, 1e18
        for tx, ty, lab, rtype in tokens:
            if lab != r.get("_lab"):
                continue
            dd = (tx - r.get("x", 0)) ** 2 + (ty - r.get("y", 0)) ** 2
            if dd < best_d:
                best_d, best = dd, rtype
        if best:
            r["type"] = best
            if not was_typed:
                gained += 1
    return gained


_OCR_NUM_RE = None
OCR_REFINE_MAX = 40          # cap the per-cell re-reads; a table has ~10


def _ocr_refine_numbers(img, tokens, dpi, pad=8.0, scale=4):
    """Re-read every NUMBER on the sheet digits-only, from its own box.

    A whole-page OCR pass reads CAD lettering well enough for words but
    misreads thin digits (on FLOOR PLAN.pdf it returned 935 for 835, 346 for
    246 and 71 for 1900). Cropping each numeric token with a little padding,
    upscaling it and running tesseract in single-line digits-only mode fixes
    every one of those — and an area statement read wrong is worse than none
    at all (R-8 treats these as ground truth). Mutates nothing: returns a new
    token list. A crop that fails to re-read keeps its original text."""
    import re
    global _OCR_NUM_RE
    if _OCR_NUM_RE is None:
        _OCR_NUM_RE = re.compile(r"^[\d][\d,]{1,6}$")
    import pytesseract
    from PIL import Image as _Img
    z = dpi / 72.0
    cfg = "--psm 7 -c tessedit_char_whitelist=0123456789"
    out, done = [], 0
    for t in tokens:
        if done >= OCR_REFINE_MAX or not _OCR_NUM_RE.match(t["text"]):
            out.append(t)
            continue
        try:
            box = (int((t["x0"] - pad) * z), int((t["y0"] - pad) * z),
                   int((t["x1"] + pad) * z), int((t["y1"] + pad) * z))
            c = img.crop(box)
            c = c.resize((c.width * scale, c.height * scale), _Img.LANCZOS)
            fixed = pytesseract.image_to_string(c, config=cfg).strip()
            done += 1
        except Exception:
            fixed = ""
        out.append({**t, "text": fixed} if fixed.isdigit() else t)
    return out


_OCR_DIMISH_RE = None
# Inch marks are deliberately absent from the whitelist: pytesseract shlex-splits
# its config, so a bare `"` breaks it, and _PAIR_RE treats the inch mark as
# optional anyway ("13'6X10'3" parses exactly like `13'6" X 10'3"`).
_OCR_DIM_CFG = '--psm 7 -c tessedit_char_whitelist="0123456789\'Xx"'


def _dimension_ish(text):
    """Could this token be part of a printed dimension? Strip digits and the
    marks a dimension is made of; a real dimension leaves nothing behind (or
    one stray letter, e.g. OCR's 8'o" for 8'0"), while a word like 'FLAT-1'
    leaves plenty. Pure."""
    rest = "".join(c for c in (text or "")
                   if not (c.isdigit() or c in "'\"’”°`!|Xx -"))
    return any(c.isdigit() for c in (text or "")) and len(rest) <= 1


def _digits_compatible(a, b):
    """May a re-read replace the original? Only if it fixed PUNCTUATION, not
    digits: one digit string must be a subsequence of the other. The re-read
    legitimately turns 17111" into 17'11 (a dropped stroke) but it also turned
    11'6" into 17'6 — a different room. Subsequence keeps the first and
    rejects the second. Pure."""
    da = "".join(c for c in (a or "") if c.isdigit())
    db = "".join(c for c in (b or "") if c.isdigit())

    def sub(small, big):
        it = iter(big)
        return all(c in it for c in small)

    return sub(da, db) or sub(db, da)


def _ocr_dimension_tokens(page, tokens, dpi=150, pad=8.0, scale=4):
    """A SEPARATE token list with dimension-like tokens re-read at higher
    resolution, digits-and-quotes only.

    Kept separate on purpose: this pass recovers 11°6" -> 11'6 and 8'o" -> 8'0,
    but it also mangles anything it is pointed at that is not a dimension
    ('FLAT-1' -> '1'), and the shared token list feeds the area statement,
    the schedule and the room labels. Never mutate that one."""
    try:
        import pytesseract
        from PIL import Image as _Img
        z = dpi / 72.0
        pix = page.get_pixmap(dpi=dpi)
        img = _Img.frombytes("RGB", (pix.width, pix.height), pix.samples)
    except Exception:
        return tokens
    out, done = [], 0
    for t in tokens:
        if done >= 60 or not _dimension_ish(t["text"]):
            out.append(t)
            continue
        try:
            box = (int((t["x0"] - pad) * z), int((t["y0"] - pad) * z),
                   int((t["x1"] + pad) * z), int((t["y1"] + pad) * z))
            c = img.crop(box)
            c = c.resize((c.width * scale, c.height * scale), _Img.LANCZOS)
            fixed = pytesseract.image_to_string(c, config=_OCR_DIM_CFG).strip()
            done += 1
        except Exception:
            fixed = ""
        keep = fixed and _digits_compatible(t["text"], fixed)
        out.append({**t, "text": fixed} if keep else t)
    return out


def _ocr_page_tokens(page, dpi=150, refine_numbers=False):
    """OCR the rendered page -> [{text, x0, y0, x1, y1, conf}] in POINT
    coordinates of the ROTATED page (the frame tp() works in).

    Indian CAD sheets outline their lettering, so page.get_text() returns
    nothing usable (FLOOR PLAN.pdf: 24 live words, all of them the Autodesk
    educational banner). OCR is therefore the ONLY way to read room labels
    (G2) and the printed area statement (R-8). Optional dependency: any
    failure returns [] and the callers simply skip their feature.
    refine_numbers re-reads digits cell-by-cell (see _ocr_refine_numbers)."""
    out = []
    try:
        import pytesseract
        from PIL import Image as _Img
        zoom = dpi / 72.0
        pix = page.get_pixmap(dpi=dpi)
        img = _Img.frombytes("RGB", (pix.width, pix.height), pix.samples)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        for i, txt in enumerate(data["text"]):
            t = (txt or "").strip()
            if not t:
                continue
            x, y = data["left"][i] / zoom, data["top"][i] / zoom
            w, h = data["width"][i] / zoom, data["height"][i] / zoom
            out.append({"text": t, "x0": x, "y0": y, "x1": x + w, "y1": y + h,
                        "conf": int(data["conf"][i])})
        if refine_numbers and out:
            out = _ocr_refine_numbers(img, out, dpi)
    except Exception:
        return []
    return out


def _door_scale_sanity(openings, warnings):
    """Practical cross-check: snapped doors are real doors (2'0"-4'6" wide in
    Indian residential work). If their median width is far outside that band,
    the SCALE is suspect - warn with the implied correction factor."""
    med = _door_median_ft(openings)
    if med is not None and not (2.1 <= med <= 4.2):
        factor = med / NOMINAL_DOOR_FT
        warnings.append(
            f"SCALE SUSPECT: median snapped-door width {med:.2f} ft "
            f"(expected 2'6\"-3'6\"); sizes may be off ~{factor:.2f}x - "
            f"check the column size or provide width_ft")


def _rescale_scene_ft(scene, k):
    """G3: multiply every FEET coordinate/area in a FINISHED scene dict by k
    (heights and z-ranges are FIXED and never scaled). One uniform pass so no
    field is missed; unit-tested against a scene with every field populated."""
    if not k or abs(k - 1.0) < 1e-6:
        return scene

    def sp(p):
        return [round(p[0] * k, 3), round(p[1] * k, 3)]

    def sv(seq):
        return [round(v * k, 3) for v in seq]

    m = scene.get("meta", {}) or {}
    for key in ("plan_width_ft", "plan_depth_ft"):
        if key in m:
            m[key] = round(m[key] * k, 3)
    wing = m.get("wing") or {}
    if wing.get("bbox_ft"):
        wing["bbox_ft"] = sv(wing["bbox_ft"])
    sc = m.get("scale")
    if isinstance(sc, dict) and sc.get("pt_per_ft"):
        sc["pt_per_ft"] = round(float(sc["pt_per_ft"]) / k, 4)   # stays consistent
    for wt in (scene.get("wall_types") or {}).values():
        if isinstance(wt, dict) and "thickness_ft" in wt:
            wt["thickness_ft"] = round(float(wt["thickness_ft"]) * k, 4)
    for wp in scene.get("walls_poly", []) or []:
        if wp.get("outer"):
            wp["outer"] = [sp(p) for p in wp["outer"]]
        if wp.get("holes"):
            wp["holes"] = [[sp(p) for p in h] for h in wp["holes"]]
    for w in scene.get("walls", []) or []:
        for key in ("x0", "x1", "y0", "y1"):
            if key in w:
                w[key] = round(w[key] * k, 3)
    for o in scene.get("openings", []) or []:
        if o.get("along"):
            o["along"] = sv(o["along"])
        for key in ("footprint", "swing_area"):
            if o.get(key):
                o[key] = sv(o[key])
        # z (height range) is NOT scaled
    for coll in ("columns", "ducts", "furniture"):
        for c in scene.get(coll, []) or []:
            for key in ("x", "y", "w", "d"):
                if key in c:
                    c[key] = round(c[key] * k, 3)
    for r in scene.get("rooms", []) or []:
        for key in ("x", "y"):
            if key in r:
                r[key] = round(r[key] * k, 3)
        if "area_sqft" in r:
            r["area_sqft"] = round(r["area_sqft"] * k * k, 1)   # area ~ k^2
    return scene


def _apply_scale_correction(scene):
    """G3 scale auto-correction. When the scale came from a GUESS (columns=12in
    / assumed width) and the snapped doors say it's confidently off, flag it
    loudly with the exact correction factor. DRISHTI_AUTOSCALE=1 also APPLIES
    the correction (rescales geometry so a nominal 3ft door lands right);
    default is flag-only — on a RERA product we don't silently reshape a
    building on a door-width guess, we tell the user to confirm width_ft."""
    m = scene.get("meta", {}) or {}
    scale = m.get("scale", {}) or {}
    if scale.get("source") not in GUESSED_SCALES:
        return scene
    med = _door_median_ft(scene.get("openings", []) or [])
    if med is None or 2.2 <= med <= 4.0:
        return scene                             # no doors, or doors look right
    oversize = round(med / NOMINAL_DOOR_FT, 3)   # >1 = scene too big
    k = round(NOMINAL_DOOR_FT / med, 4)          # multiply feet by this to fix
    scale["needs_review"] = True
    scale["door_median_ft"] = round(med, 2)
    scale["suggested_factor"] = k
    scale["implied_oversize"] = oversize
    if os.getenv("DRISHTI_AUTOSCALE", "0").lower() in ("1", "true", "yes"):
        _rescale_scene_ft(scene, k)
        scale["source"] = f"{scale.get('source')}+door_corrected"
        scale["pt_per_ft"] = round(float(scale.get("pt_per_ft", 0)) / k, 3)
        m.setdefault("warnings", []).append(
            f"scale auto-corrected x{k:.3f} from door widths "
            f"(median door was {med:.2f} ft)")
    else:
        m.setdefault("warnings", []).append(
            f"SCALE NEEDS REVIEW: doors imply the plan is ~{oversize:.2f}x off "
            f"(median door {med:.2f} ft). Re-upload with the real width, or set "
            "DRISHTI_AUTOSCALE=1, to correct every size.")
    return scene


def parse(raw, width_ft=None, wing="largest", ppf_hint=None, force_geometry=False):
    """Vector PDF bytes -> canonical scene dict. Raises ValueError if unusable.
    wing: "largest" or an int index - which building wing to build when the
    sheet holds several separate blocks (sorted largest first).
    ppf_hint: EXACT pt-per-ft when known (CAD DXF/DWG route: real units) -
    overrides dimension-text and column-box scale guessing.
    force_geometry: ignore wall/window LAYERS and detect walls from raw
    parallel-line geometry over ALL drawings — the retry for sheets whose real
    walls live on unnamed layers ('0', '6') while a named wall layer carries
    only fragments/decoys (the layers-mode result comes out unhealthy)."""
    import cv2
    import fitz
    import numpy as np

    try:                                  # corrupt/empty bytes -> ValueError, not
        page = fitz.open(stream=raw, filetype="pdf")[0]   # a raw PyMuPDF type the
    except Exception as e:                # CAD path / batch_eval would leak as 500
        raise ValueError(f"could not open PDF: {type(e).__name__}: {e}")
    drawings = _page_drawings(page)

    # ONE OCR pass per parse, shared by every text-dependent consumer: the
    # SCALE (dimension text, R-2 room dimensions), room labels (G2), opening
    # tags + schedule (TG-5) and the printed area statement (R-8). Defined up
    # here because scale is decided first and, on a sheet whose lettering is
    # outlined line-art, the scale is exactly what OCR has to rescue.
    # Lazy: nothing renders until the first consumer actually asks.
    _ocr_on = os.getenv("DRISHTI_OCR", "auto").lower() not in ("0", "off", "false")
    _ocr_cache = {}

    def ocr_words():
        if "t" not in _ocr_cache:
            _ocr_cache["t"] = (_ocr_page_tokens(page, refine_numbers=True)
                               if _ocr_on else [])
        return _ocr_cache["t"]

    def live_words():
        """Live PDF text in the same token shape as ocr_words()."""
        if "live" not in _ocr_cache:
            out = []
            for wd in page.get_text("words"):
                r = (fitz.Rect(wd[:4]) * page.rotation_matrix).normalize()
                out.append({"text": wd[4], "x0": r.x0, "y0": r.y0,
                            "x1": r.x1, "y1": r.y1, "conf": 100})
            _ocr_cache["live"] = out
        return _ocr_cache["live"]

    def dim_words():
        """Tokens for reading printed DIMENSIONS only (see
        _ocr_dimension_tokens): digits and feet/inch marks re-read per crop."""
        if "dim" not in _ocr_cache:
            _ocr_cache["dim"] = (
                _ocr_dimension_tokens(page, ocr_words()) if _ocr_on else [])
        return _ocr_cache["dim"]

    def printed_dim_pairs():
        """Printed W x H room dimensions (R-2). Live text first; on an
        outlined-text sheet, the union of the plain OCR pass and the dimension
        re-read (they fail on different labels)."""
        if "pairs" not in _ocr_cache:
            import opening_schedule as _os
            import room_dims as _rd
            src = live_words()
            pairs = _rd.dimension_pairs(src)
            if not pairs and _ocr_on:
                src = ocr_words()
                pairs = _rd.merge_pairs(_rd.dimension_pairs(src),
                                        _rd.dimension_pairs(dim_words()))
            # An opening SCHEDULE's dimension column is full of `3'9" X 7'0"`
            # pairs that are door sizes, not room sizes. Voting a scale off
            # them put BRICK WORK 4.3x out. Exclude the table's own box.
            reg = None
            try:
                reg = _os.schedule_region(src)
            except Exception:
                reg = None
            if reg:
                x0_, y0_, x1_, y1_ = reg
                dropped = [p for p in pairs
                           if x0_ <= p["x"] <= x1_ and y0_ <= p["y"] <= y1_]
                pairs = [p for p in pairs if p not in dropped]
                if dropped:
                    warnings.append(
                        f"{len(dropped)} dimension(s) ignored for scale: they "
                        "are rows of the opening schedule, not room sizes")
            _ocr_cache["pairs"] = pairs
        return _ocr_cache["pairs"]

    warnings = []
    wall_segs, skipped = _filter_text_layers(drawings, _is_wall_layer, warnings)
    win_segs, skipped_w = _filter_text_layers(drawings, _is_window_layer, warnings)
    skipped |= skipped_w
    struct = wall_segs + win_segs
    if force_geometry:
        struct = []          # ignore named wall layers -> geometry branch runs
        warnings.append("force_geometry: named wall layers ignored - detecting "
                        "walls from raw linework across all layers")
    col_rects = _column_rects(drawings)

    # scale from live dimension text beats every other signal
    # (unless the caller KNOWS the scale - CAD files carry real units)
    text_ppf, _tv, dim_keys = _text_scale(page, drawings, warnings)
    if ppf_hint:
        text_ppf = None
    # room-dimension text (9'0"X12'0") — the scale signal on plans with no column
    # layer and no on-line dimensions (very common on internet/CAD plans)
    room_ppf = None
    if not ppf_hint and not text_ppf:
        room_ppf = _room_dim_scale(page, drawings, warnings)
        # §0.1 + R-2: the dimensions the architect PRINTED inside each room are
        # ground truth, and they outrank the column-width assumption (C-6,
        # which is explicitly a weak anchor). On an outlined-text sheet they
        # are invisible to get_text, so read them by OCR rather than falling
        # through to the column guess.
        if room_ppf is None:
            _p = printed_dim_pairs()
            if _p:
                room_ppf = _room_dim_scale(page, drawings, warnings, pairs=_p,
                                           wall_segs=struct)
                # CONSISTENCY (§0.1): the printed dimensions are ground truth,
                # but the ppf we DERIVE from them (voting room extents between
                # walls) is not. Cross-check it against the column-box scale;
                # when the two disagree by more than 2x, our derivation is
                # broken, not the sheet. Keep the old scale and say so, rather
                # than ship a 2.75 ft building.
                if room_ppf and col_rects:
                    import numpy as _np
                    _sz = [round(max(r.width, r.height), 1) for r in col_rects]
                    _v, _c = _np.unique(_sz, return_counts=True)
                    _ref = float(_v[_c.argmax()]) / COL_FT
                    if _ref > 0 and not (0.5 <= room_ppf / _ref <= 2.0):
                        warnings.append(
                            f"printed room dimensions imply {room_ppf:.1f} pt/ft "
                            f"but the column boxes imply {_ref:.1f} — a "
                            f"{room_ppf / _ref:.1f}x disagreement, so the "
                            "room-dimension scale is REJECTED (our reading of "
                            "them is wrong, not the sheet). NEEDS REVIEW.")
                        room_ppf = None
                if room_ppf:
                    warnings.append(
                        f"scale from PRINTED room dimensions read by OCR "
                        f"({len(_p)} label(s)) — outlined lettering on this "
                        "sheet; this outranks the column-width assumption")

    mode = "layers"
    if len(struct) < 30:            # no usable wall layer -> geometry detection
        seed = ppf_hint or text_ppf or room_ppf
        if seed is None and col_rects:
            import numpy as np
            sizes = [round(max(r.width, r.height), 1) for r in col_rects]
            v, c = np.unique(sizes, return_counts=True)
            seed = float(v[c.argmax()]) / COL_FT
        if seed is None and width_ft:
            # last-resort seed: user-supplied plan width vs drawn linework
            # extent (flattened PDFs: no layers, no on-line dim text, no
            # columns - the only signal left is the user's own number).
            xs = [v for d in drawings for v in (d["rect"].x0, d["rect"].x1)]
            if xs and width_ft > 0:
                span = max(xs) - min(xs)
                if span > 0:
                    seed = span / width_ft
                    warnings.append(f"scale seeded from width override: "
                                    f"{seed:.2f} pt/ft (linework span "
                                    f"{span:.0f} pt / {width_ft} ft)")
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
    elif room_ppf:
        ppf, scale_src = room_ppf, "room_dim_text"
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

    def _mask(shape_flag, dil, ero, seal_ft=0.0):
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
        # envelope sealing (wings/rooms mask only): directionally bridge gaps in
        # wall runs BEFORE the area filter, so a fragmented building reconnects
        # into one region that survives instead of being dropped as slivers.
        if seal_ft > 0:
            g = int(seal_ft * NORM_PPX) | 1
            mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, K(cv2.MORPH_RECT, (g, 3)))
            mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, K(cv2.MORPH_RECT, (3, g)))
        if ero:
            mm = cv2.erode(mm, K(cv2.MORPH_RECT, (ero, ero)))
        n, lab, stt, _ = cv2.connectedComponentsWithStats(mm, 8)
        keep = np.zeros_like(mm)
        for i in range(1, n):
            if stt[i, cv2.CC_STAT_AREA] > MIN_WALL_AREA_PX:
                keep[lab == i] = 255
        return keep

    m = _mask("RECT", 9, 5)             # output mask (de-blobbed) -> walls_poly
    m_snap = _mask("ELLIPSE", 13, 0)    # fat mask for door-gap finding only
    # sealed mask used ONLY for wing-grouping + room free-space: bridges wall
    # gaps so a fragmented building is one region and rooms enclose. walls_poly
    # stays from the unsealed `m`, so stairs/open features are never filled.
    _SEAL_FT = float(os.getenv("DRISHTI_SEAL_FT", "4") or 0)
    m_env = _mask("RECT", 9, 5, seal_ft=_SEAL_FT) if _SEAL_FT > 0 else m

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
    wing_groups = _wing_groups(m_env)        # sealed: a fragmented building
    wing_count = len(wing_groups)            # groups as ONE wing, not slivers
    wbox_ft = None
    w_idx = 0
    if wing_count > 1:
        if wing == "largest":
            def _ft_box(wb):
                return ((wb[0] - PAD_PX) / NORM_PPX,
                        d_ft - (wb[3] - PAD_PX) / NORM_PPX,
                        (wb[2] - PAD_PX) / NORM_PPX,
                        d_ft - (wb[1] - PAD_PX) / NORM_PPX)
            # score every wing by (enclosed ROOMS, doors, area). Rooms are the
            # strongest 'this is the floor plan' signal — a section/detail block
            # or a door SCHEDULE (many door symbols, NO rooms) has none, so
            # rooms must outrank doors (a door schedule was out-scoring the real
            # plan on neelachala). Doors break ties when walls are too
            # fragmented for pockets to form; area breaks the final tie.
            _min_room_px = int(28 * NORM_PPX * NORM_PPX)
            scores = []
            for g in wing_groups:
                bx0, by0, bx1, by1 = _ft_box(g[1])
                dsc = sum(1 for cx, cy in door_centers
                          if bx0 - 2 <= cx <= bx1 + 2 and by0 - 2 <= cy <= by1 + 2)
                pockets = _wing_room_pockets(m_env, g[1], _min_room_px)
                scores.append((pockets, dsc, g[2]))
            w_idx = max(range(wing_count), key=lambda i: scores[i])
            if w_idx != 0:
                warnings.append(
                    f"wing auto-pick: wing {w_idx} is the floor plan "
                    f"(rooms={scores[w_idx][0]}, doors={scores[w_idx][1]}) - "
                    "overriding the largest-area wing (a non-plan drawing)")
        elif wing != "largest":
            w_idx = int(wing)
        if not (0 <= w_idx < wing_count):
            raise ValueError(f"wing {w_idx} out of range (sheet has {wing_count})")
        labels, wb, _area = wing_groups[w_idx]
        # crop every mask to the selected wing's bbox (wings are spatially
        # separated, so a box crop cleanly isolates it). m_env drives rooms,
        # m drives walls_poly, m_snap drives door snapping — keep them aligned.
        for _mm in (m, m_snap, m_env):
            _mm[:wb[1], :] = 0
            _mm[wb[3]:, :] = 0
            _mm[:, :wb[0]] = 0
            _mm[:, wb[2]:] = 0
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

    # endpoint-first rescue for DENSE sheets: when both the raster gap-finder
    # and the vector-endpoint fallback miss, look up the nearest true doorway
    # GAP in the wall lines (the unit-tested gap_openings detector, computed
    # once, in mask px) and snap the door onto it. Each gap is used once.
    _gap_state = {"gaps": None, "used": []}

    def _nearest_wall_gap(ccx_px, ccy_px):
        if _gap_state["gaps"] is None:
            seg_px_ = [(*tp(ax, ay), *tp(bx, by)) for ax, ay, bx, by in struct]
            _gap_state["gaps"] = gap_openings(
                seg_px_, DOOR_MIN_FT * NORM_PPX, DOOR_MAX_FT * NORM_PPX,
                min_flank=0.8 * NORM_PPX, face_tol=0.35 * NORM_PPX,
                group_tol=1.2 * NORM_PPX, junction_pad=0.5 * NORM_PPX)
        best, bd = None, (4.0 * NORM_PPX) ** 2      # within 4 ft of the swing
        for g in _gap_state["gaps"]:
            if id(g) in _gap_state["used"]:
                continue
            dd = (g["cx"] - ccx_px) ** 2 + (g["cy"] - ccy_px) ** 2
            if dd < bd:
                bd, best = dd, g
        if best is not None:
            _gap_state["used"].append(id(best))
        return best

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
            continue
        # endpoint-first rescue: nearest true wall gap to the swing box
        g = _nearest_wall_gap(*tp((cl.x0 + cl.x1) / 2, (cl.y0 + cl.y1) / 2))
        if g:
            th = int(0.9 * NORM_PPX)
            if g["orient"] == "h":
                gx0, gx1 = int(g["cx"] - g["w"] / 2), int(g["cx"] + g["w"] / 2)
                gy0, gy1 = int(g["cy"] - th / 2), int(g["cy"] + th / 2)
            else:
                gy0, gy1 = int(g["cy"] - g["w"] / 2), int(g["cy"] + g["w"] / 2)
                gx0, gx1 = int(g["cx"] - th / 2), int(g["cx"] + th / 2)
            gx0, gy0 = max(0, gx0), max(0, gy0)
            for mm in (m, m_snap):      # fill: wall continuous, header cut works
                mm[gy0:gy1, gx0:gx1] = 255
            m[max(0, gy0 - 5):gy1 + 5, max(0, gx0 - 5):gx1 + 5] = 255
            door_hits.append(((gx0, gy0, gx1, gy1), cl))
        else:
            door_hits.append((None, cl))

    # --- geometric doors: flattened PDFs have no door layer and no clean swing
    # symbols, so doors are found as door-width GAPS in the wall lines. Filling
    # each gap makes the wall continuous (so scene_to_glb's header cut works and
    # the room seals); the gap itself is emitted as the door. Pure detection is
    # in gap_openings() (unit-tested). Gated on `not has_door_layer`, so layered
    # CAD plans never enter here and cannot regress. ---
    if not has_door_layer and struct:
        import fitz as _fitz
        seg_px = [(*tp(ax, ay), *tp(bx, by)) for ax, ay, bx, by in struct]
        geo = gap_openings(seg_px,
                           DOOR_MIN_FT * NORM_PPX, DOOR_MAX_FT * NORM_PPX,
                           min_flank=0.8 * NORM_PPX, face_tol=0.35 * NORM_PPX,
                           group_tol=1.2 * NORM_PPX, junction_pad=0.5 * NORM_PPX)
        th = int(0.9 * NORM_PPX)          # fill thickness ~ one wall band
        placed = 0
        for o in geo:
            cx, cy, w = o["cx"], o["cy"], o["w"]
            if o["orient"] == "h":
                gx0, gx1 = int(cx - w / 2), int(cx + w / 2)
                gy0, gy1 = int(cy - th / 2), int(cy + th / 2)
            else:
                gy0, gy1 = int(cy - w / 2), int(cy + w / 2)
                gx0, gx1 = int(cx - th / 2), int(cx + th / 2)
            gx0, gy0 = max(0, gx0), max(0, gy0)
            fcx = (cx - PAD_PX) / NORM_PPX
            fcy = d_ft - (cy - PAD_PX) / NORM_PPX
            if not _in_wing(fcx, fcy):
                continue
            for mm in (m, m_snap):        # seal the doorway, both masks
                mm[gy0:gy1, gx0:gx1] = 255
            px0, py0 = x0 + (gx0 - PAD_PX) / sc, y0 + (gy0 - PAD_PX) / sc
            px1, py1 = x0 + (gx1 - PAD_PX) / sc, y0 + (gy1 - PAD_PX) / sc
            cl = _fitz.Rect(px0, py0, px1, py1).normalize()
            door_hits.append(((gx0, gy0, gx1, gy1), cl))
            placed += 1
        if placed:
            warnings.append(f"{placed} door(s) detected by GEOMETRY (wall-gap "
                            f"rule) - no door layer/symbols on this sheet")

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
    # rooms come from the SEALED mask (bridged wall gaps -> enclosed pockets);
    # walls_poly above stays from the unsealed `m`, so stairs/open features are
    # unaffected in the exported geometry.
    min_room_px = int(28 * NORM_PPX * NORM_PPX)          # >= ~28 sqft
    # A small space that is COMPLETELY ringed by wall is a real room — a lift
    # shaft, a shaft, a WC. FLOOR PLAN's lift is printed 5'x5' = 25 sqft and was
    # being dropped by the 28 sqft floor. Anything this small that is NOT fully
    # wall-enclosed is a sliver between wall faces, so the enclosure test is
    # what keeps noise out (L-4: a lift is an enclosed shaft).
    small_room_px = int(18 * NORM_PPX * NORM_PPX)        # >= ~18 sqft, enclosed
    Hpx, Wpx = m.shape

    def _rooms_from_free(free, drop_border=True):
        """Enclosed free-space components -> (room dicts, label array). Marker =
        most-interior pixel (distance transform). The returned label array MUST
        travel with the rooms: each room's `_lab` indexes into it (room-label
        matching below reads rlab[y, x])."""
        out = []
        ndt = cv2.distanceTransform(free, cv2.DIST_L2, 3)
        ncomp, rlab, rstt, _c = cv2.connectedComponentsWithStats(free, 4)
        for i in range(1, ncomp):
            rx, ry, rw, rh, rarea = rstt[i]
            if rarea < min_room_px:
                if rarea < small_room_px:
                    continue
                comp8 = (rlab == i).astype(np.uint8)
                ring = cv2.dilate(comp8, np.ones((3, 3), np.uint8)) - comp8
                if not np.all(m_env[ring > 0] > 0):
                    continue              # not fully ringed by wall: a sliver
            if drop_border and (rx == 0 or ry == 0
                                or rx + rw >= Wpx or ry + rh >= Hpx):
                continue                                 # touches border = outside
            comp = (rlab == i)
            d = np.where(comp, ndt, 0)
            py_, px_ = np.unravel_index(int(d.argmax()), d.shape)
            out.append({"x": fx(px_), "y": fy(py_),
                        "area_sqft": round(rarea / (NORM_PPX ** 2), 1),
                        "_lab": int(i),
                        "_bbox_ft": (fx(rx), fy(ry + rh), fx(rx + rw), fy(ry))})
        return out, rlab

    # FOOTPRINT BOUNDING (2026-08-11). "Inside the building" is decided by the
    # outer WALL RING (W-1), not by whether a free-space blob happens to touch
    # the raster border. That border test discarded 675 sqft of REAL rooms on
    # FLOOR PLAN.pdf, because the balconies' open faces chain interior ->
    # balcony -> outside. See _footprint_from_walls for why the ring is bridged
    # rather than dilated.
    footprint_sqft = None
    _seg_px = [(*tp(ax, ay), *tp(bx, by)) for ax, ay, bx, by in struct]
    _foot, _bridges, _rejected, _foot_ext, _rej_lines = _footprint_from_walls(
        m_env, seg_px=_seg_px)
    rooms, rlab = [], None
    if _foot is not None:
        footprint_sqft = round(float((_foot > 0).sum()) / (NORM_PPX ** 2), 1)
        rooms, rlab = _rooms_from_free(
            cv2.bitwise_and(_foot, cv2.bitwise_not(m_env)), drop_border=False)
        if rooms:
            warnings.append(
                f"footprint from the outer wall ring: {footprint_sqft:.0f} sqft"
                + (f", {len(_bridges)} opening(s) bridged "
                   f"({', '.join(f'{b:.1f}ft' for b in sorted(_bridges)[-4:])})"
                   if _bridges else "")
                + (f"; {len(_rejected)} span(s) REJECTED as longer than the "
                   f"building's shorter side "
                   f"({', '.join(f'{b:.0f}ft' for b in sorted(_rejected)[-3:])})"
                   if _rejected else ""))
    # B-1 / B-5: a balcony is enclosed on 3 sides and open on 1, so it never
    # forms an enclosed pocket and ring bridging cannot reach it (§0.1). It IS
    # the space between the footprint and the ring closed across its open face.
    # Closed as a SPACE here, reported on its own line, and its open face is
    # never built as a wall — walls_poly comes from `m`, which is untouched.
    if rooms and _foot is not None and _foot_ext is not None:
        _bal_free = cv2.bitwise_and(
            cv2.bitwise_and(_foot_ext, cv2.bitwise_not(m_env)),
            cv2.bitwise_not(_foot))
        # ONE OPEN FACE = ONE BALCONY, and a balcony is a STRIP: bound its depth
        # by the widest balcony width the sheet itself prints ("BALCONY 4' WIDE"),
        # never by a constant (B-5). Everything deeper than that is not balcony —
        # it is interior space (the utility strip) or ground outside, and the two
        # are told apart by how much wall rings them (B-1: enclosed on 3 sides).
        _bal_ft = []
        try:
            import room_dims as _rd2
            _src = live_words() if _rd2.printed_widths(live_words(), "BALCON") \
                else ocr_words()
            _bal_ft = _rd2.printed_widths(_src, "BALCON")
        except Exception:
            _bal_ft = []
        # NOT YET SPLIT PER FACE. Banding the space within the printed balcony
        # width of each rejected span was tried on 11 Aug and REJECTED: the long
        # spurious spans (42 ft, 96 ft) sweep a 4 ft band along the whole south
        # edge, so the "balcony" came out 208.9 sqft of outside ground at
        # (85.9, 5.4) and built-up fell 98.8% -> 96.0%. The band is the wrong
        # primitive; the depth bound belongs on the RESULTING region's short
        # side, and the spurious spans need eliminating first. Kept as one
        # region until that is built — an honest lump beats a confident
        # mis-split. `room_dims.printed_widths` (4'0" / 3'6" here) is ready.
        _bands = _bal_free.copy()
        _bals, _ = _rooms_from_free(_bands, drop_border=False)
        for _b in _bals:
            _b["type"] = "balcony"
            _b["open_side"] = True
            _b["_lab"] = -1              # never matched to a printed room label
        # what is left is too deep to be a balcony
        _rest = cv2.bitwise_and(_bal_free, cv2.bitwise_not(_bands))
        _deep, _ = _rooms_from_free(_rest, drop_border=False)
        _kept_deep = []
        for _d in _deep:
            _d["_lab"] = -1
            _kept_deep.append(_d)         # untyped -> counts as carpet
        if _bals or _kept_deep:
            rooms += _bals + _kept_deep
            warnings.append(
                f"{len(_bals)} balcony(s) ({sum(b['area_sqft'] for b in _bals):.0f} "
                f"sqft, depth bounded by the sheet's own "
                f"{max(_bal_ft) if _bal_ft else 0:.1f} ft balcony width) + "
                f"{len(_kept_deep)} deeper space(s) "
                f"({sum(d['area_sqft'] for d in _kept_deep):.0f} sqft) behind "
                f"{len(_rej_lines)} open face(s)")
    if not rooms:
        rooms, rlab = _rooms_from_free((m_env == 0).astype(np.uint8))
    if not rooms:
        # G1 WALL-GAP HEALING: 0 rooms means the interior free-space leaked to
        # the raster border (broken / missing OUTER wall) or no pocket formed
        # -> 0% efficiency. Cap the free space to the building FOOTPRINT (close
        # the wall blob, fill its largest outer contour) so interior pockets
        # stay bounded even with a gappy outer wall. Fires ONLY on the 0-room
        # failure, so healthy plans can't regress; room-only, so walls_poly and
        # stairs are untouched. GENERAL rule, not per-plan.
        rsf = float(os.getenv("DRISHTI_ROOM_SEAL_FT", "6") or 0)
        inside_free = _footprint_free_mask(m_env, rsf) if rsf > 0 else None
        if inside_free is not None:
            healed, healed_lab = _rooms_from_free(inside_free, drop_border=False)
            if healed:
                rooms, rlab = healed, healed_lab
                warnings.append(
                    f"rooms recovered by footprint sealing ({len(rooms)} "
                    "room(s); the outer wall had gaps on this sheet)")
    rooms.sort(key=lambda r: -r["area_sqft"])
    rooms = rooms[:16]
    for k, r in enumerate(rooms):
        r["id"] = f"r{k}"

    # --- room labels: Indian plans name their rooms ("Bed Room", "C. Bath").
    # Collect every room-name word with its position, then give each room the
    # label token NEAREST its interior point and inside its own component (so a
    # merged region doesn't pick up an unrelated label). Gives room types for
    # staging + render prompts. Poorly-sealed plans stay best-effort. ---
    # 1) LIVE PDF text is authoritative: collect room-name words, assign each
    # room the nearest one inside its own component.
    live_tokens = []                      # (feet_x, feet_y, component_label, type)
    for w in page.get_text("words"):
        rtype = furnish.classify_room_type((w[4] or "").strip())
        if not rtype:
            continue
        rr = (fitz.Rect(w[:4]) * page.rotation_matrix).normalize()
        cxp, cyp = tp((rr.x0 + rr.x1) / 2, (rr.y0 + rr.y1) / 2)
        if 0 <= cyp < Hpx and 0 <= cxp < Wpx:
            live_tokens.append((fx(cxp), fy(cyp), int(rlab[cyp, cxp]), rtype))
    _assign_room_labels(rooms, live_tokens)

    # 2) OCR FILL (G2): many CAD exports OUTLINE their text (letters become line
    # art, invisible to get_text). Run whenever rooms remain UNTYPED — not only
    # when live text found NOTHING — so a plan with a few readable labels still
    # gets the rest via OCR. OCR NEVER overwrites a live label. Pixmap pixels
    # are already in rotated page space, matching tp()'s frame. Optional dep:
    # skipped silently if tesseract absent; DRISHTI_OCR=0 disables.

    untyped = [r for r in rooms if not r.get("type")]
    if untyped and _ocr_on:
        try:
            ocr_tokens = []
            for w in ocr_words():
                t = w["text"]
                if len(t) < 3 or w["conf"] < 40:
                    continue
                rtype = furnish.classify_room_type(t)
                if not rtype:
                    continue
                cxp, cyp = tp((w["x0"] + w["x1"]) / 2, (w["y0"] + w["y1"]) / 2)
                if 0 <= cyp < Hpx and 0 <= cxp < Wpx:
                    ocr_tokens.append((fx(cxp), fy(cyp),
                                       int(rlab[cyp, cxp]), rtype))
            gained = _assign_room_labels(rooms, ocr_tokens, only_untyped=True)
            if gained:
                warnings.append(f"room labels recovered by OCR: {gained} "
                                "(outlined text on this sheet)")
        except Exception:
            pass                          # OCR unavailable/failed -> untyped rooms

    # --- R-2: the sheet PRINTS each room's size ("BEDROOM 13'6" X 10'3"").
    # That is the architect's own statement, so per §0.1 it CHECKS the room we
    # measured. Strictly additive: area_sqft is never touched — the printed
    # figure and the match sit beside it so the two can be compared. ---
    try:
        import room_dims as _rdims
        _pairs = _rdims.dimension_pairs(live_words())
        if not _pairs:
            # the plain OCR pass and the dimension re-read fail on different
            # labels, so read with both and take the union (see merge_pairs)
            _pairs = _rdims.merge_pairs(_rdims.dimension_pairs(ocr_words()),
                                        _rdims.dimension_pairs(dim_words()))
        _located = []
        for _p in _pairs:
            _cxp, _cyp = tp(_p["x"], _p["y"])
            if 0 <= _cyp < Hpx and 0 <= _cxp < Wpx:
                _p["lab"] = int(rlab[_cyp, _cxp])
                _p["fx"], _p["fy"] = fx(_cxp), fy(_cyp)
                _located.append(_p)
        _n = _rdims.attach_printed_dims(rooms, _located)
        if _n:
            _s = _rdims.summary(rooms) or {}
            warnings.append(
                f"printed room dimensions read for {_n} room(s) — median match "
                f"with our measurement {_s.get('median_match_pct')}% "
                f"({_s.get('rooms_off')} room(s) off by more than 20%)")
    except Exception:
        pass                              # R-2 is a check, never a blocker

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
                # door openings are appended AFTER this section - test against
                # the door cluster centres found earlier instead
                near_door = any(abs(dcx - fcx) < 2.5 and abs(dcy - fcy) < 2.5
                                for dcx, dcy in door_centers)
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
    import tag_openings as _tags

    # --- opening TAGS (D/D1/W1/V…), ONE token source for both consumers: the
    # W/V legend just below and the schedule-tag reader further down.
    #
    # LIVE text wins whenever the sheet has any tags in it — that path is the
    # frozen baseline and must not shift. OCR is the fallback for sheets whose
    # lettering is outlined line-art, where live text carries no tags at all
    # (BRICK WORK LAYOUT: 0 live words; FLOOR PLAN: 24, none of them tags).
    # Two guards apply to the OCR path ONLY, because inventing an opening is
    # worse than missing one (WN-4): a confidence floor (FLOOR PLAN's lone
    # 'v' reads at conf 0 — pure noise), and the legend-column filter that
    # keeps a schedule TABLE from being placed as six doors.
    def _is_tag_text(s):
        return (_tags.classify_tag(s) is not None
                or (s or "").strip().upper() in LEGEND)

    def _tag_words():
        """[(cx_pt, cy_pt, text)] for opening tags, + the source name."""
        import fitz as _fitz
        live = []
        for wd in page.get_text("words"):
            if not _is_tag_text(wd[4]):
                continue
            r = (_fitz.Rect(wd[:4]) * page.rotation_matrix).normalize()
            live.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, wd[4]))
        if live:
            return live, "live"
        out, sched_y = [], None
        for w in ocr_words():
            up = w["text"].upper()
            if any(k in up for k in _tags.SCHEDULE_WORDS):
                sched_y = w["y0"] if sched_y is None else min(sched_y, w["y0"])
            if w["conf"] >= OCR_TAG_MIN_CONF and _is_tag_text(w["text"]):
                out.append(((w["x0"] + w["x1"]) / 2, (w["y0"] + w["y1"]) / 2,
                            w["text"]))
        kept = _tags.drop_legend_tags(out, sched_y)
        if kept:
            warnings.append(f"{len(kept)} opening tag(s) read by OCR "
                            f"(outlined lettering; {len(out) - len(kept)} "
                            "schedule-table row(s) excluded)")
        return kept, "ocr"

    tag_words, _tag_src = _tag_words()

    # --- TG-5: the sheet's OWN opening schedule overrides every default size
    # below. Same live-first / OCR-fallback source as the tags. Absent
    # schedule -> `sched` is None and behaviour is exactly as before. ---
    import opening_schedule as _osched
    sched = None
    try:
        _live_all = []
        for wd in page.get_text("words"):
            _rr = (fitz.Rect(wd[:4]) * page.rotation_matrix).normalize()
            _live_all.append({"text": wd[4], "x0": _rr.x0, "y0": _rr.y0,
                              "x1": _rr.x1, "y1": _rr.y1})
        sched = _osched.parse_opening_schedule(_live_all)
        if not sched and (len(_live_all) < 50 or "t" in _ocr_cache):
            sched = _osched.parse_opening_schedule(ocr_words())
        if sched:
            warnings.append(
                "opening schedule read from the sheet — sizes now come from it, "
                "not from defaults: "
                + ", ".join(f"{k} {v['w_ft']:.2f}ft" for k, v in sorted(sched.items())))
    except Exception:
        sched = None

    tags = [((t or "").strip().upper(), cx, cy) for cx, cy, t in tag_words
            if (t or "").strip().upper() in LEGEND]
    tadd = 0
    for t, cx, cy in tags:
        wft, sill, head = _osched.window_size(sched, t, LEGEND[t])  # TG-5
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
        fp = None
        if bbox_px:
            px0, py0, px1, py1 = bbox_px
            cand = [fx(px0), fy(py1), fx(px1), fy(py0)]
            span = max(abs(cand[2] - cand[0]), abs(cand[3] - cand[1]))
            thick = min(abs(cand[2] - cand[0]), abs(cand[3] - cand[1]))
            # VALIDATE the snapped strip: a real door cut is a plausible leaf
            # width AND thin. A fat/oversize strip (>5.5 ft wide or >1.6 ft
            # thick) is a merged WALL, not a door — demote it to an unsnapped
            # swing-box cut so BOQ / the door-scale check don't trust it.
            if DOOR_MIN_FT - 0.3 <= span <= DOOR_MAX_FT + 0.5 and thick <= 1.6:
                fp = cand
        if fp is not None:
            rec["footprint"] = fp
        else:
            rec["footprint"] = ft_rect(cl)       # swing box; snapped=False flags it
            rec["snapped"] = False
            fallback_doors += 1
        openings.append(rec)
    if fallback_doors:
        warnings.append(f"{fallback_doors} door(s): doorway gap not found in the "
                        "wall mask - swing box used as cut (check these doors)")

    # --- schedule-tag openings (D/D1/SD, W/W1/V): many Indian sheets mark
    # openings with TEXT TAGS instead of symbols/layers. Additive-only: a tag
    # adds an opening ONLY where none was detected nearby, so existing
    # detection can never get worse. Sizes from the standard schedule. ---
    tag_toks = []
    for cx_pt, cy_pt, text in tag_words:      # live text, or OCR (see above)
        if _tags.classify_tag(text) is None:
            continue
        txp, typ_ = tp(cx_pt, cy_pt)
        tfx, tfy = fx(txp), fy(typ_)
        if _in_wing(tfx, tfy):
            tag_toks.append((tfx, tfy, text))
    if tag_toks:
        segs_ft = [((ax - x0) / ppf, d_ft - (ay - y0) / ppf,
                    (bx - x0) / ppf, d_ft - (by - y0) / ppf)
                   for ax, ay, bx, by in struct]
        centers = []
        for o in openings:
            fp = o.get("footprint")
            if fp:
                centers.append(((fp[0] + fp[2]) / 2, (fp[1] + fp[3]) / 2))
        added = _tags.detect_tag_openings(tag_toks, segs_ft, centers,
                                          schedule=sched)      # TG-5
        for rec in added:
            rec["id"] = f"o{len(openings)}"
            openings.append(rec)
        if added:
            kinds = sum(1 for r in added if r["type"] == "door")
            warnings.append(f"{len(added)} opening(s) placed from schedule tags "
                            f"({kinds} door, {len(added) - kinds} window/vent)")

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
    if not has_door_layer and not any(o.get("type") == "door" for o in openings):
        warnings.append("no door layer found - doors not extracted")

    _door_scale_sanity(openings, warnings)

    # --- furniture: rects on furniture/sanitary/kitchen layers, classified by
    # size (the GLB builder turns each into a recognizable assembly). Empty on
    # flattened plans with no furniture layer — additive, never blocks. ---
    furniture = []
    for t, r in _furniture_items(drawings, ppf):
        fr = ft_rect(r)
        cx, cy = (fr[0] + fr[2]) / 2, (fr[1] + fr[3]) / 2
        if not _in_wing(cx, cy):
            continue
        furniture.append({"type": t, "x": round(fr[0], 3), "y": round(fr[1], 3),
                          "w": round(fr[2] - fr[0], 3), "d": round(fr[3] - fr[1], 3)})
    n_detected = len(furniture)
    if n_detected:
        warnings.append(f"{n_detected} furniture item(s) placed from layers")

    # --- auto-stage: a typed room with NO drawn furniture inside it gets a few
    # sensible default pieces (bedroom->bed, kitchen->counter...). Conservative:
    # only when the room is empty; nothing for parking/balcony/stairs. ---
    def _has_furniture(bx0, by0, bx1, by1):
        return any(bx0 <= f["x"] + f["w"] / 2 <= bx1 and by0 <= f["y"] + f["d"] / 2 <= by1
                   for f in furniture)

    n_staged = 0
    for r in rooms:
        rtype = r.get("type")
        bb = r.get("_bbox_ft")
        if not rtype or not bb:
            continue
        if not furnish.plausible_area(rtype, r.get("area_sqft")):
            continue                              # mis-typed / merged region
        if _has_furniture(*bb):
            continue                              # room already has drawn furniture
        for f in furnish.stage_room(rtype, *bb):
            if _in_wing(f["x"] + f["w"] / 2, f["y"] + f["d"] / 2):
                furniture.append(f)
                n_staged += 1
    if n_staged:
        warnings.append(f"{n_staged} furniture item(s) auto-staged by room type")

    # room dicts: expose `type`, drop internal helpers
    for r in rooms:
        r.pop("_lab", None)
        r.pop("_bbox_ft", None)

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
        for f in furniture:
            f["x"] = round(f["x"] - sx, 3)
            f["y"] = round(f["y"] - sy, 3)
    else:
        out_w, out_d = w_ft, d_ft

    # --- envelope truth: prefer the architect's VERIFIED overall dimension
    # over the raw linework extent. The extent includes chhajja/balcony
    # projections, inflating the reported plot by a few % (and RERA areas by
    # ~2x that, since area scales with the square). GENERAL rule, corpus-
    # gated: only a ft-in text hugging a line of matching drawn length counts,
    # and only when the extent exceeds it by <= 12% (projection-sized). ---
    env_src = "linework_extent"
    try:
        _hs, _vs = _overall_dims(page, drawings, ppf)
        _sw, _sd = _snap_envelope(out_w, _hs), _snap_envelope(out_d, _vs)
        if _sw or _sd:
            drawn = (out_w, out_d)
            out_w, out_d = (_sw or out_w), (_sd or out_d)
            env_src = "overall_dimension_text"
            warnings.append(
                f"envelope from on-sheet overall dimension: {out_w:.2f} x "
                f"{out_d:.2f} ft (drawn extent {drawn[0]:.2f} x {drawn[1]:.2f} "
                f"ft includes projections)")
    except Exception:
        pass
    # --- R-8 / §0.1: the sheet's OWN printed area statement is ground truth.
    # Read-only and additive: it never touches a parsed number, it is only
    # compared against them (main.py builds the comparison block). Absent
    # table / no OCR -> the key is simply not there. ---
    printed_areas = None
    try:
        import area_compare
        # LIVE text first — it is free and exact where a sheet has it. OCR is
        # the fallback, and only where it is warranted: the sheet's text is
        # unreadable anyway (outlined lettering), or an OCR pass already ran
        # for room labels so it costs nothing extra. A sheet with healthy live
        # text and no table never pays for OCR.
        _live_toks = []
        for _w in page.get_text("words"):
            _r = (fitz.Rect(_w[:4]) * page.rotation_matrix).normalize()
            _live_toks.append({"text": _w[4], "x0": _r.x0, "y0": _r.y0,
                               "x1": _r.x1, "y1": _r.y1, "conf": 100})
        printed_areas = area_compare.parse_area_statement(_live_toks)
        _dead_text = len(_live_toks) < 50
        if not printed_areas and (_dead_text or "t" in _ocr_cache):
            printed_areas = area_compare.parse_area_statement(ocr_words())
        if printed_areas:
            _bits = []
            if printed_areas.get("built_up_total_sqft"):
                _bits.append(f"built-up {printed_areas['built_up_total_sqft']:.0f}")
            if printed_areas.get("carpet_total_sqft"):
                _bits.append(f"carpet {printed_areas['carpet_total_sqft']:.0f}")
            warnings.append("printed AREA STATEMENT read from the sheet"
                            + (f" ({', '.join(_bits)} sqft)" if _bits else ""))
    except Exception:
        printed_areas = None

    _plot_sqft = None
    if printed_areas and printed_areas.get("plot_area_sqft"):
        _plot_sqft = round(float(printed_areas["plot_area_sqft"]), 1)
    elif env_src == "overall_dimension_text":
        _plot_sqft = round(float(out_w) * float(out_d), 1)

    scene = {
        "meta": {
            "source": f"vector_pdf_{mode}",
            "units": "ft",
            "wall_height_ft": WALL_HEIGHT_FT,
            "plan_width_ft": round(out_w, 3),
            "plan_depth_ft": round(out_d, 3),
            "scale": {"source": scale_src, "pt_per_ft": round(ppf, 3),
                      "envelope": env_src},
            # PHYSICS CHECK (§0.1): a building cannot be bigger than its land.
            # plot_sqft is the sheet's own printed plot area, else the verified
            # overall-dimension envelope; None when the sheet states neither,
            # and then the check is skipped rather than guessed.
            "footprint_sqft": footprint_sqft,
            "plot_sqft": _plot_sqft,
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
        "ducts": [], "furniture": furniture,
    }
    if printed_areas:
        scene["printed_areas"] = printed_areas
    # G3: cross-check a GUESSED scale against snapped-door widths; flag (default)
    # or auto-correct (DRISHTI_AUTOSCALE=1). No-op on verified scales.
    return _apply_scale_correction(scene)
