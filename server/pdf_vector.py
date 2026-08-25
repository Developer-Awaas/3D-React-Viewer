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
# ONE CONSTANT PER PURPOSE (18 Aug 2026). `DOOR_MIN_FT` was doing FIVE jobs at
# once — a real leaf width, a drawn-gap width, the geometry fallback's gap, a
# sanity bound, and a strip-span floor — and the `- 0.3` slack existed only to
# reconcile the last with the first. Worst instance of the week's pattern
# (the seal served 2, the built-up formula 2, the strip bound 3).
#
# A REAL DOOR LEAF, in the world: what a printed tag or a derived width must
# look like to be a door at all. Indian residential practice, 2'0"-5'6".
DOOR_LEAF_MIN_FT, DOOR_LEAF_MAX_FT = 2.0, 5.5
# THE DRAWN OPENING in the linework: the run-to-run gap between wall faces
# where the drafter stopped the wall. It equals the leaf it holds, so the
# numbers coincide — but it is a measurement of the DRAWING, not of a door,
# and it must be free to move independently.
DRAWN_GAP_MIN_FT, DRAWN_GAP_MAX_FT = 2.0, 5.5
# kept as an alias so nothing outside this file breaks
DOOR_MIN_FT, DOOR_MAX_FT = DOOR_LEAF_MIN_FT, DOOR_LEAF_MAX_FT
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


def _filter_text_layers(drawings, want, warnings, maxlen=None):
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
        ls = _segs(ds, lambda n: True, maxlen=maxlen or BORDER_MAXLEN_PT)
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

# W-3, THE WALL-GAP BAND — ONE DEFINITION (21 Aug 2026, Rahul). Two faces are
# the same wall when they are parallel, this far apart and overlapping along
# the run. Five functions ask that question — `paired_extent`,
# `_paired_indices`, `wall_rects`, `keep_structural_lines` and, since gap faces
# began grouping by measured pair, `gap_openings` — and the band was written
# out at each. It is a SPEC constant (§2 W-3), not a tuning dial, and it is
# expressed in INCHES so it converts per sheet against that sheet's own scale
# rather than living in page units.
WALL_GAP_MIN_IN, WALL_GAP_MAX_IN = 3.0, 18.0


def wall_gap_band(units_per_ft):
    """The W-3 band in whatever unit `units_per_ft` measures (points, px, ft).
    Derived per sheet from its own scale — never a hardcoded span."""
    return ((WALL_GAP_MIN_IN / 12.0) * units_per_ft,
            (WALL_GAP_MAX_IN / 12.0) * units_per_ft)


def paired_extent(segs, ppf, min_in=WALL_GAP_MIN_IN, max_in=WALL_GAP_MAX_IN, min_ovl_ft=2.0):
    """Bounding box of the lines that PAIR into walls — i.e. the building.

    Split out so the extent can be computed from the TRUSTED walls ALONE,
    before any candidate line is considered. Computing it from a set that
    already contains the candidates lets them vouch for themselves: on
    FLOOR PLAN, 13 lines on layer `0` at y -13.0..-7.9 ft (below the building)
    pair with each other, extend the "building", and then pass the position
    gate that was supposed to reject them. Same self-vouching error as
    measuring connectivity against a network containing the tile grid.
    Returns (x0, y0, x1, y1) or None. Pure."""
    paired = _paired_indices(segs, ppf, min_in, max_in, min_ovl_ft)
    if not paired:
        return None
    xs = [v for k in paired for v in (segs[k][0], segs[k][2])]
    ys = [v for k in paired for v in (segs[k][1], segs[k][3])]
    return (min(xs), min(ys), max(xs), max(ys))


def inside_extent(seg, extent, margin):
    """Does a candidate line lie inside the building extent? Pure."""
    if extent is None:
        return True
    bx0, by0, bx1, by1 = extent
    return (bx0 - margin <= min(seg[0], seg[2]) and max(seg[0], seg[2]) <= bx1 + margin
            and by0 - margin <= min(seg[1], seg[3]) and max(seg[1], seg[3]) <= by1 + margin)


def _paired_indices(segs, ppf, min_in=WALL_GAP_MIN_IN, max_in=WALL_GAP_MAX_IN, min_ovl_ft=2.0):
    """Indices of segments that have a parallel partner at wall thickness."""
    lo, hi = (min_in / 12.0) * ppf, (max_in / 12.0) * ppf
    H, V = [], []
    for k, (x0, y0, x1, y1) in enumerate(segs):
        if abs(y1 - y0) < 0.5:
            H.append((k, (y0 + y1) / 2, min(x0, x1), max(x0, x1)))
        elif abs(x1 - x0) < 0.5:
            V.append((k, (x0 + x1) / 2, min(y0, y1), max(y0, y1)))
    paired = set()
    for runs in (H, V):
        runs.sort(key=lambda r: r[1])
        for i in range(len(runs)):
            ki, pi, ai, bi = runs[i]
            for j in range(i + 1, len(runs)):
                kj, pj, aj, bj = runs[j]
                if pj - pi > hi:
                    break
                if pj - pi < lo:
                    continue
                if min(bi, bj) - max(ai, aj) >= min_ovl_ft * ppf:
                    paired.add(ki)
                    paired.add(kj)
    return paired


def _spans_beyond(runs, at, lo, hi, over, tol=0.12):
    """Is there a line collinear with this side that runs well past the box?"""
    for p, a, b in runs:
        if abs(p - at) <= tol and (a < lo - over or b > hi + over):
            return True
    return False


def _grid_index(runs, cell):
    """Bucket segments into grid cells so bridging is not O(n^2). BRICK WORK
    has 4,960 wall segments and the naive pass generated 620,275 candidate
    pairs (17 Aug)."""
    idx = {}
    for k, (a0, a1, p) in enumerate(runs):
        for c in range(int(a0 // cell), int(a1 // cell) + 1):
            idx.setdefault((c, int(p // cell)), []).append(k)
    return idx


def weld_bridges(segs, max_gap, along_cos=0.7):
    """PASS 1 — FRAGMENT WELD: join wall pieces that are near each other,
    regardless of alignment, but ONLY ALONG A WALL RUN.

    §12 (17 Aug 2026): the 4 ft morphological close did two jobs at once —
    welding disconnected fragments into a building (which fragmented sheets
    need to enclose at all) and filling the gap between any two walls 4 ft
    apart (which destroys every narrow room). Separating them is the fix.

    The discriminator is DIRECTION, not distance: a weld runs ALONG at least
    one of the two walls it joins. Two parallel walls facing each other across
    a room have their ends 4 ft apart too, but the line between them runs
    PERPENDICULAR to both — that is not a weld, it is the room. Pure."""
    out = []
    for horiz in (True, False):
        runs = []
        for x0, y0, x1, y1 in segs:
            if horiz and abs(y1 - y0) <= abs(x1 - x0):
                runs.append((min(x0, x1), max(x0, x1), (y0 + y1) / 2.0))
            elif not horiz and abs(x1 - x0) < abs(y1 - y0):
                runs.append((min(y0, y1), max(y0, y1), (x0 + x1) / 2.0))
        idx = _grid_index(runs, max(max_gap, 1.0))
        seen = set()
        for k, (a0, a1, p) in enumerate(runs):
            for c in range(int(a0 // max_gap) - 1, int(a1 // max_gap) + 2):
                for dq in (-1, 0, 1):
                    for j in idx.get((c, int(p // max_gap) + dq), ()):
                        if j <= k or (k, j) in seen:
                            continue
                        seen.add((k, j))
                        b0, b1, q = runs[j]
                        # gap ALONG the run, offset ACROSS it
                        gap = max(b0 - a1, a0 - b1)
                        off = abs(q - p)
                        if gap <= 0 or gap > max_gap or off > max_gap:
                            continue
                        # the weld must run ALONG the walls, not across them
                        if gap / math.hypot(gap, off) < along_cos:
                            continue
                        if b0 > a1:
                            pt, qt = (a1, p), (b0, q)
                        else:
                            pt, qt = (a0, p), (b1, q)
                        out.append((pt, qt) if horiz else ((pt[1], pt[0]),
                                                           (qt[1], qt[0])))
    return out


def dedupe_segments(segs, ppf, min_ft=0.02):
    """Drop DEGENERATE and DUPLICATE wall segments. Pure.

    §12 (17 Aug 2026): BRICK WORK carries **4,960 wall-layer segments of which
    4,335 are ZERO-LENGTH points** and 858 more are exact duplicates — pattern
    and hatch artefacts of the CAD export. They cannot be walls (a segment
    shorter than 0.02 ft has no direction), they carry no information, and they
    made every pairwise wall pass quadratic in noise: the weld/break scan
    generated 686,000 candidate pairs there against 90 on FLOOR PLAN. A grid
    index hides that; removing the noise fixes it."""
    lim = min_ft * ppf
    out, seen = [], set()
    for g in segs:
        if math.hypot(g[2] - g[0], g[3] - g[1]) < lim:
            continue                      # a point, not a wall
        k = (round(min(g[0], g[2]), 1), round(min(g[1], g[3]), 1),
             round(max(g[0], g[2]), 1), round(max(g[1], g[3]), 1))
        if k in seen:
            continue                      # the same line drawn twice
        seen.add(k)
        out.append(g)
    return out


def collinear_bridges(segs, max_gap, tol):
    """Gaps that are a BREAK IN ONE WALL RUN, as (p, q) point pairs.

    §12 (17 Aug 2026): the old envelope seal was a blanket morphological close
    at 4 ft, which bridges any gap of that size — including the gap BETWEEN TWO
    PARALLEL WALLS, which is a room. It filled FLOOR PLAN's C.TOILET solid
    (interior 3.9 ft) while A.TOILET beside it (4.5 ft) survived, and swallowed
    102.5 sqft in all, the passage included.

    The criterion, not the size, was wrong. A gap closes only when the wall
    CONTINUES across it — two collinear ends of the same run, which is a
    doorway or a drafting break. Two walls facing each other along the gap are
    the sides of a space and must never be joined. No threshold decides this;
    the geometry does. Pure."""
    H, V = [], []
    for x0, y0, x1, y1 in segs:
        if abs(y1 - y0) <= tol:
            H.append((min(x0, x1), max(x0, x1), (y0 + y1) / 2.0))
        elif abs(x1 - x0) <= tol:
            V.append((min(y0, y1), max(y0, y1), (x0 + x1) / 2.0))
    out = []
    for runs, horiz in ((H, True), (V, False)):
        runs.sort(key=lambda r: (r[2], r[0]))
        for i, (a0, a1, p) in enumerate(runs):
            for b0, b1, q in runs[i + 1:]:
                if q - p > tol:
                    break                      # sorted by the perpendicular
                gap = b0 - a1
                if 0 < gap <= max_gap:
                    out.append(((a1, p), (b0, q)) if horiz
                               else ((p, a1), (q, b0)))
    return out


def open_side_regions(m_env, norm_ppx, pad_x, pad_y, d_ft, min_sqft=40.0,
                      backed=0.60, leaky=0.35, wall_ft=None):
    """§0.2 CONTRADICTS: free regions ENCLOSED ON THREE SIDES that leak through
    ONE undrawn edge.

    On an upper floor a space has a roof and a floor, so it must be closed. A
    region that fails to enclose on exactly one side is a DRAFTING ERROR, not
    an outside region — and today the border test silently discards it. FLOOR
    PLAN's entire common area (189.9 sqft of lobby + staircase) is thrown away
    this way because its south edge is drawn 2 in wide on `ar furniture`.

    The three-sides test is what keeps the real outside out: the 985.5 sqft
    outside component and the 122.7 sqft balcony strip are backed on ONE side,
    not three. Returns flags; changes nothing. Pure (mask in, dicts out).
    """
    import cv2
    import numpy as np
    free = (m_env == 0).astype(np.uint8)
    n, lab, stt, _c = cv2.connectedComponentsWithStats(free, 4)
    Hpx, Wpx = m_env.shape
    out = []
    for i in range(1, n):
        x, y, w, h, area = stt[i]
        if area / (norm_ppx ** 2) < min_sqft:
            continue
        if not (x == 0 or y == 0 or x + w >= Wpx or y + h >= Hpx):
            continue                       # already enclosed: not our case
        comp = (lab == i)
        cov = {}
        for side in ("N", "S", "E", "W"):
            hits = tot = 0
            if side in ("N", "S"):
                for cx in range(x, x + w, 3):
                    col = np.nonzero(comp[:, cx])[0]
                    if not len(col):
                        continue
                    edge = col.min() if side == "N" else col.max()
                    step = -1 if side == "N" else 1
                    probe = edge + step * 3
                    tot += 1
                    if 0 <= probe < Hpx and m_env[probe, cx] > 0:
                        hits += 1
            else:
                for cy in range(y, y + h, 3):
                    row = np.nonzero(comp[cy, :])[0]
                    if not len(row):
                        continue
                    edge = row.min() if side == "W" else row.max()
                    step = -1 if side == "W" else 1
                    probe = edge + step * 3
                    tot += 1
                    if 0 <= probe < Wpx and m_env[cy, probe] > 0:
                        hits += 1
            cov[side] = (hits / tot) if tot else 0.0
        open_side = min(cov, key=lambda k: cov[k])
        others = [v for k, v in cov.items() if k != open_side]
        if cov[open_side] > leaky or min(others) < backed:
            continue                       # not "three sides and one hole"
        sealed = m_env.copy()
        # close it with the sheet's OWN measured external wall thickness, never
        # a constant: the confirmed edge is a real wall and must be as thick as
        # this building's walls are (§0.1 - measured, not assumed)
        t = max(3, int((wall_ft or 0.83) * norm_ppx))
        if open_side == "S":
            cv2.line(sealed, (x, y + h), (x + w, y + h), 255, t)
        elif open_side == "N":
            cv2.line(sealed, (x, y), (x + w, y), 255, t)
        elif open_side == "E":
            cv2.line(sealed, (x + w, y), (x + w, y + h), 255, t)
        else:
            cv2.line(sealed, (x, y), (x, y + h), 255, t)
        n2, lab2, stt2, _c2 = cv2.connectedComponentsWithStats(
            (sealed == 0).astype(np.uint8), 4)
        py_, px_ = np.nonzero(comp)
        j = lab2[int(py_.mean()), int(px_.mean())]
        closed_sqft = (stt2[j, cv2.CC_STAT_AREA] / (norm_ppx ** 2)) if j > 0 else 0.0
        out.append({
            "open_side": {"N": "north", "S": "south",
                          "E": "east", "W": "west"}[open_side],
            "area_as_drawn_sqft": round(float(area) / (norm_ppx ** 2), 1),
            "area_if_closed_sqft": round(float(closed_sqft), 1),
            "side_backed_pct": {k: round(100 * v, 1) for k, v in cov.items()},
            "bbox_ft": [round(float(x - pad_x) / norm_ppx, 1),
                        round(float(d_ft) - float(y + h - pad_y) / norm_ppx, 1),
                        round(float(x + w - pad_x) / norm_ppx, 1),
                        round(float(d_ft) - float(y - pad_y) / norm_ppx, 1)],
            "wall_ft": round(float(wall_ft), 2) if wall_ft else None,
            "question": "This space appears open on one side. On an upper floor "
                        "that is not possible (§0.2) - is there a wall here?"})
    return out


def enclosed_boxes(segs, min_sqft=2.0, max_sqft=18.0, max_side_ft=6.0, tol=0.12,
                   max_overhang_ft=0.5, wall_ft=None):
    """Small CLOSED rectangles drawn in the wall linework, in feet.

    §4 D-5: a duct is a wall-ringed VOID of 2-18 sqft. It cannot be found as
    free space in the raster — measured 16 Aug, FLOOR PLAN's ducts are 1.00 ft
    across and the wall-merge closing kernel is 0.88 ft, so the interior is
    filled solid and no free-space component exists at ANY area floor. It has
    to be read from the rectangle the drafter actually drew.

    A duct is drawn as its OWN rectangle: its four sides begin and end at the
    box. A WALL BODY also closes into a rectangle wherever two cross-walls
    slice it — the two faces of the wall plus the two crossings — and that is
    the noise this must not admit (a 40x20 double-line box yields a bogus
    0.8 x 4 ft "duct" without the test). The difference is OVERHANG: a wall's
    faces run on past the box, a duct's sides do not.

    Returns [(x0, y0, x1, y1)] of boxes whose four sides are all present and
    none of which overhangs. Pure -> unit-tested."""
    H, V = [], []
    for x0, y0, x1, y1 in segs:
        if abs(y1 - y0) <= tol and abs(x1 - x0) > tol:
            H.append((min(y0, y1), min(x0, x1), max(x0, x1)))
        elif abs(x1 - x0) <= tol and abs(y1 - y0) > tol:
            V.append((min(x0, x1), min(y0, y1), max(y0, y1)))
    H.sort()
    V.sort()
    out = []
    for i, (ya, xa0, xa1) in enumerate(H):
        for yb, xb0, xb1 in H[i + 1:]:
            h = yb - ya
            if h <= tol:
                continue
            if h > max_side_ft:
                break                      # sorted: no later pair is closer
            lo, hi = max(xa0, xb0), min(xa1, xb1)
            if hi - lo <= tol:
                continue
            for j, (xv, ya0, ya1) in enumerate(V):
                if xv < lo - tol or xv > hi + tol:
                    continue
                if ya0 > ya + tol or ya1 < yb - tol:
                    continue               # left side must span the box
                for xw, yb0, yb1 in V[j + 1:]:
                    w = xw - xv
                    if w <= tol:
                        continue
                    if w > max_side_ft:
                        break
                    if xw > hi + tol or yb0 > ya + tol or yb1 < yb - tol:
                        continue
                    a = w * h
                    # (1) a WALL BODY between two cross-walls closes into a
                    # rectangle; its faces run on past the box, a duct's sides
                    # do not.
                    if max(xv - xa0, xa1 - xw, xv - xb0, xb1 - xw,
                           ya - ya0, ya1 - yb, ya - yb0, yb1 - yb) \
                            > max_overhang_ft:
                        continue
                    # (2) a DOOR OPENING drawn as its own rectangle inside the
                    # wall band has no overhang either — the 40x20 test fixture
                    # draws exactly that (4.0 x 0.8 ft). But it is as narrow as
                    # the WALL, because it IS the wall's thickness. A duct is
                    # not: FLOOR PLAN's are 1.00 ft against 0.83 ft walls.
                    if wall_ft and abs(min(w, h) - wall_ft) <= 0.10 * wall_ft:
                        continue
                    if min_sqft <= a <= max_sqft:
                        out.append((round(xv, 2), round(ya, 2),
                                    round(xw, 2), round(yb, 2)))
    # keep the SMALLEST box at each spot: a duct inside a shaft wall would
    # otherwise be reported twice, once per enclosing rectangle
    out.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    kept = []
    for b in out:
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        if not any(k[0] <= cx <= k[2] and k[1] <= cy <= k[3] for k in kept):
            kept.append(b)
    return kept


def _wall_thickness_ft(drawings, ppf):
    """This sheet's own wall thickness: the median measured pair gap. Used
    wherever a tolerance is really "one wall" — never a constant (§0.1)."""
    gaps = sorted(g["gap_in"] / 12.0 for g in (wall_gap_pairs(drawings, ppf) or []))
    return gaps[len(gaps) // 2] if gaps else None


def group_door_symbols(paths, tol_ft=0.35, cv=0.25, min_leaf=1.2):
    """Assemble each door symbol from its ARC polyline and its LEAF.

    §12 (19 Aug 2026): a symbol may be SPLIT ACROSS DRAWING PATHS — FLOOR PLAN
    keeps every leaf in a different path from its arc, so neither path
    membership nor a bounding box can group them (every door box caught the
    same 25 lines). The geometry does it instead: **the leaf IS the radius** of
    its quarter circle, and the leaf's hinge end is the arc's centre. Measured
    on all 12 doors, leaf length equals arc radius to 0.01 ft with a radius CV
    of 0.000-0.001 — an exact match, not a tolerance.

    `paths` is [[(a, b), ...]] in feet, one list per drawing path. Returns
    [[leaf, *arc_segments]] ready for door_swing(). Pure -> unit-tested."""
    arcs, lines = [], []
    for ss in paths or []:
        if not ss:
            continue
        longest = max(math.dist(a, b) for a, b in ss)
        if len(ss) > 5 and longest < 0.6:
            arcs.append(ss)
        else:
            lines += [(a, b) for a, b in ss if math.dist(a, b) >= min_leaf]
    # ROUTE: this decides ARC vs LEAF once per drawing path, so a count is the
    # honest report — a flag would hide a sheet where it fires 200 times and
    # one where it fires twice.
    _ROUTE["door_symbol_paths"] = {"arc": len(arcs), "line": len(paths or []) - len(arcs),
                                   "leaf_segs_kept": len(lines)}
    out = []
    for arc in arcs:
        pts = [p for a, b in arc for p in (a, b)]
        best = None
        for a, b in lines:
            ln = math.dist(a, b)
            for h in (a, b):
                rr = [math.dist(h, p) for p in pts]
                mean = sum(rr) / len(rr)
                if mean <= 0:
                    continue
                spread = (sum((r - mean) ** 2 for r in rr) / len(rr)) ** 0.5 / mean
                if abs(mean - ln) <= tol_ft and spread <= cv \
                        and (best is None or spread < best[0]):
                    best = (spread, (a, b))
        if best:
            out.append([best[1]] + list(arc))
    return out


def door_swing(segs, tol=0.25):
    """DR-3: read a door's LEAF, HINGE and SWING SIDE from its drawn symbol.

    The symbol is a straight leaf plus a quarter-circle arc centred on the
    hinge, drawn as a polyline (measured 19 Aug 2026: FLOOR PLAN's door layer
    carries 300 line items and NO curve items). Two facts fall out of that
    geometry: the arc's CENTRE is the hinge, and the side the arc sweeps to is
    the room the door opens into.

    Until now `hinge` appeared nowhere in the parser and every leaf defaulted to
    +60 degrees in the GLB, i.e. right by chance about half the time.

    Returns {leaf_ft, hinge, tip, opens_toward} or None when the arc is absent
    or ambiguous — never a guess. Pure -> unit-tested."""
    if not segs:
        return None
    leaf = max(segs, key=lambda t: math.dist(t[0], t[1]))
    ln = math.dist(leaf[0], leaf[1])
    if ln < 1.2:
        return None
    pts = [p for a, b in segs for p in (a, b)
           if math.dist(p, leaf[0]) > 0.05 and math.dist(p, leaf[1]) > 0.05]
    if len(pts) < 4:
        return None
    best = None
    for h in (leaf[0], leaf[1]):
        rr = [math.dist(h, p) for p in pts]
        mean = sum(rr) / len(rr)
        if mean <= 0:
            continue
        cv = (sum((r - mean) ** 2 for r in rr) / len(rr)) ** 0.5 / mean
        if best is None or cv < best[0]:
            best = (cv, h, mean)
    if best is None or best[0] > tol:
        return None                      # not a clean arc: report nothing
    cv, hinge, radius = best
    tip = leaf[1] if hinge == leaf[0] else leaf[0]
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    dx, dy = tip[0] - hinge[0], tip[1] - hinge[1]
    side = dx * (cy - hinge[1]) - dy * (cx - hinge[0])   # cross product
    # the CLOSED leaf position: the arc end opposite the drawn (open) tip. The
    # symbol draws the leaf perpendicular to its wall and the arc back to the
    # shut position, so hinge->closed IS the doorway, along the wall run.
    closed = max(pts, key=lambda p: math.dist(p, tip))
    return {"leaf_ft": round(ln, 2), "hinge": [round(hinge[0], 2), round(hinge[1], 2)],
            "tip": [round(tip[0], 2), round(tip[1], 2)],
            "closed": [round(closed[0], 2), round(closed[1], 2)],
            "opens_toward": "left" if side > 0 else "right",
            "arc_fit_cv": round(cv, 3)}


def wall_rects(segs, ppf, min_in=WALL_GAP_MIN_IN, max_in=WALL_GAP_MAX_IN, min_ovl_ft=None):
    """Walls as RECTANGLES: the material BETWEEN each measured pair of faces.

    Rahul's ruling, 17 Aug 2026: a wall is ALWAYS two drawn lines, and the wall
    is what lies between them — its thickness is the MEASURED gap, not a
    painted band. The old raster dilated each line into a band, which is why
    room accuracy improved to R-2 99.5% the moment dilation was removed: the
    faces were being fattened inward over the rooms.

    Returns (rects, unpaired) in the segments' own units. Each rect is
    (x0, y0, x1, y1) covering exactly the overlap of its two faces. Pure.

    THE OVERLAP FLOOR IS DERIVED, NOT 2.0 FT (20 Aug 2026). `min_ovl_ft = 2.0`
    was serving two purposes — "long enough to be a wall" and, silently,
    "solid or two fins": a run under it could never pair, so BOTH of its faces
    fell through to the unpaired fallback and were buffered separately at the
    sheet's MEDIAN wall. That built a short wall end as two fat plates with a
    step between them (FLOOR PLAN: 7 of them, runs 0.47-1.90 ft, plates 0.83 ft
    thick where the wall measures 0.41-0.42, protruding up to 1.75 ft). Fifth
    instance of a constant serving several purposes.

    THE FLOOR IS DERIVED FROM THE DRAWING: a wall run is at least as long as
    the wall is THICK, and the thickness is the pair's own measured gap. No
    page units, no assumed minimum, and it scales with the sheet. Passing
    `min_ovl_ft` restores a fixed floor for callers that want one.

    Shipped 20 Aug 2026 on Rahul's ruling. FLOOR PLAN pairs 48 -> 60, unpaired
    51 -> 33, all 7 fin ends become single rectangles at their measured
    0.42 ft, outline points 96 -> 82; BRICK WORK pairs 39 -> 126, short steps
    361 -> 162, M-1 1.06 -> 1.13, doors 11 -> 12. Its one cost is 2.6 sqft of
    FLOOR PLAN footprint (1799.4 -> 1796.8, R-8 96.7 -> 96.6) and that is the
    artefact going away, not coverage: those 7 ends were painted at TWICE
    their drawn thickness. R-8's pin re-derived to 96.6 with that evidence."""
    lo, hi = (min_in / 12.0) * ppf, (max_in / 12.0) * ppf
    H, V = [], []
    for k, (x0, y0, x1, y1) in enumerate(segs):
        if abs(y1 - y0) < 0.5:
            H.append((k, (y0 + y1) / 2, min(x0, x1), max(x0, x1)))
        elif abs(x1 - x0) < 0.5:
            V.append((k, (x0 + x1) / 2, min(y0, y1), max(y0, y1)))
    rects, paired = [], set()
    for runs, horiz in ((H, True), (V, False)):
        runs.sort(key=lambda r: r[1])
        for i in range(len(runs)):
            ki, pi, ai, bi = runs[i]
            for j in range(i + 1, len(runs)):
                kj, pj, aj, bj = runs[j]
                if pj - pi > hi:
                    break
                if pj - pi < lo:
                    continue
                s0, s1 = max(ai, aj), min(bi, bj)
                _floor = (min_ovl_ft * ppf) if min_ovl_ft is not None else (pj - pi)
                if s1 - s0 < _floor:
                    continue
                rects.append((s0, pi, s1, pj) if horiz else (pi, s0, pj, s1))
                paired.add(ki)
                paired.add(kj)
    return rects, [g for k, g in enumerate(segs) if k not in paired]


def keep_structural_lines(segs, ppf, min_in=WALL_GAP_MIN_IN, max_in=WALL_GAP_MAX_IN, min_ovl_ft=2.0):
    """Drop page borders and site boundaries by WHAT THE LINE IS, not by how
    long it is (§1's actual intent).

    A wall line has a parallel partner one wall thickness away (W-1, W-3:
    3-18 in). A page border, a title-block rule and a site boundary do not.
    That is the discriminator; length is only a backstop for UNPAIRED lines,
    and it is derived from the extent of the paired ones — never from points.

    This replaces `BORDER_MAXLEN_PT = 900`, a page-unit constant that meant
    31.6 ft on FLOOR PLAN (where it silently deleted the 54 ft south external
    wall, and with it the whole south side of the building), 17 ft on
    BRICK WORK and 158 ft on FIRST FLOOR — the same threshold meaning four
    different things. Pure -> unit-tested."""
    if not segs:
        return segs, {"paired": 0, "unpaired_kept": 0, "dropped": 0}
    lo, hi = (min_in / 12.0) * ppf, (max_in / 12.0) * ppf
    H, V, other = [], [], []
    for k, (x0, y0, x1, y1) in enumerate(segs):
        if abs(y1 - y0) < 0.5:
            H.append((k, (y0 + y1) / 2, min(x0, x1), max(x0, x1)))
        elif abs(x1 - x0) < 0.5:
            V.append((k, (x0 + x1) / 2, min(y0, y1), max(y0, y1)))
        else:
            other.append(k)
    paired = set()
    for runs in (H, V):
        runs.sort(key=lambda r: r[1])
        for i in range(len(runs)):
            ki, pi, ai, bi = runs[i]
            for j in range(i + 1, len(runs)):
                kj, pj, aj, bj = runs[j]
                if pj - pi > hi:
                    break
                if pj - pi < lo:
                    continue
                if min(bi, bj) - max(ai, aj) >= min_ovl_ft * ppf:
                    paired.add(ki)
                    paired.add(kj)
    if not paired:                       # nothing pairs: keep everything
        return segs, {"paired": 0, "unpaired_kept": len(segs), "dropped": 0}
    # The PAIRED lines are the building. An unpaired line is kept only if it
    # lies inside their extent: a site boundary or page border reaches outside
    # it by definition, whatever its length. BRICK WORK's site boundary is a
    # 39 ft DIAGONAL on a layer called 'wall' — shorter than the building, so
    # no length rule can catch it, but it runs clean outside the paired box.
    xs = [v for k in paired for v in (segs[k][0], segs[k][2])]
    ys = [v for k in paired for v in (segs[k][1], segs[k][3])]
    bx0, by0, bx1, by1 = min(xs), min(ys), max(xs), max(ys)
    m = 0.02 * max(bx1 - bx0, by1 - by0)        # 2% of the building, not points
    out, kept_unpaired = [], 0
    for k, s in enumerate(segs):
        if k in paired:
            out.append(s)
            continue
        if (bx0 - m <= min(s[0], s[2]) and max(s[0], s[2]) <= bx1 + m
                and by0 - m <= min(s[1], s[3]) and max(s[1], s[3]) <= by1 + m):
            out.append(s)
            kept_unpaired += 1
    return out, {"paired": len(paired), "unpaired_kept": kept_unpaired,
                 "dropped": len(segs) - len(out)}


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
                 face_tol=0.35, group_tol=1.2, junction_pad=0.4,
                 pair_min=None, pair_max=None):
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
        """Group faces into WALL LINES, then union each line's along-axis
        intervals into solid runs.

        GROUPED BY MEASURED PAIR (20 Aug 2026, Rahul) when `pair_min`/
        `pair_max` are given. A wall line is not a 1-D cluster of faces at some
        tolerance — it is the two faces of ONE wall, a measured pair, and
        `wall_rects` identifies those by exactly this test: parallel, W-3 apart
        (3-18 in), overlapping along the run. One pair is one wall, so one
        doorway in it yields ONE opening, structurally.

        Sixth instance of a TOLERANCE DECIDING CONSTRUCTION, after the 4 ft
        seal, the built-up formula, the door-strip span bound, `DOOR_MIN_FT`
        and `min_ovl_ft`. It failed twice here in two different ways. Keyed on
        a ROLLING MEAN it was ORDER-DEPENDENT — the same 7 FLOOR PLAN faces
        keyed 18.70 ft read bottom-up (feet, y up) and 16.73 ft read top-down
        (raster px, y down), which put the kitchen doorway 2.4 ft off its own
        wall. Bounded by the group's EXTENT instead, it SPLIT the lobby wall:
        its faces at 7.06 and 7.89 fell either side of a chain that had begun
        at 6.30, so one doorway was emitted twice, once per face.

        With no pair band supplied the extent-bounded clustering is kept, so
        callers with no scale still work."""
        lines = sorted(lines, key=lambda s: s[2])
        groups = []                       # [perp_a, [intervals], perp_b]
        if pair_min is not None and pair_max is not None:
            # collinear segments first: one drawn FACE is many segments broken
            # at every doorway and junction, and pairing them one by one would
            # split a wall into as many "lines" as it has segments — the gap
            # between two of them could then never be seen. `face_tol` here
            # means "the same drawn line" (drafting precision), not "the same
            # wall" — that is what the measured pair below decides.
            faces = []                    # [perp, [intervals]]
            for lo, hi, perp in lines:
                if faces and perp - faces[-1][0] <= face_tol:
                    faces[-1][1].append((lo, hi))
                else:
                    faces.append([perp, [(lo, hi)]])
            lines = [(min(lo for lo, _h in ivs), max(hi for _l, hi in ivs), perp)
                     for perp, ivs in faces]
            spans = {i: faces[i][1] for i in range(len(faces))}
            used = [False] * len(lines)
            for i, (lo, hi, perp) in enumerate(lines):
                if used[i]:
                    continue
                mate = None
                for j in range(i + 1, len(lines)):
                    if used[j]:
                        continue
                    d = lines[j][2] - perp
                    if d > pair_max:
                        break
                    if d < pair_min:
                        continue
                    if min(hi, lines[j][1]) - max(lo, lines[j][0]) <= 0:
                        continue          # parallel, but not the same wall
                    mate = j
                    break
                used[i] = True
                if mate is None:          # a face with no partner is its own line
                    groups.append([perp, list(spans[i]), perp])
                else:
                    used[mate] = True
                    groups.append([perp, list(spans[i]) + list(spans[mate]),
                                   lines[mate][2]])
            groups.sort(key=lambda g: (g[0] + g[2]) / 2.0)
        else:
            for lo, hi, perp in lines:
                if groups and perp - groups[-1][0] <= group_tol:
                    groups[-1][1].append((lo, hi))
                    groups[-1][2] = perp
                else:
                    groups.append([perp, [(lo, hi)], perp])
        out = []
        for first, ivs, last in groups:
            perp = (first + last) / 2.0
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
    # ROUTE: this fires only on the geometry branch (its one caller is
    # `_geometry_wall_segs`), and under 5 walls it returns untouched — a
    # staircase drawn as 4 treads is silently never de-duped.
    _ROUTE["stair_ladder_dedupe"] = (
        f"ran ({len(walls)} walls)" if len(walls) >= 5
        else f"SKIPPED: {len(walls)} walls < 5")
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


EMPTY_BAND_MIN_FT = 1.0      # noise floor only: the SIGNATURE is emptiness
#                              across the full extent, not the band's width.
#                              Measured 25 Aug — the only band in the corpus
#                              that qualifies is GHATIKIA's 6.48 ft gutter.


def _empty_bands(cover, bbox, min_ft, norm_ppx=NORM_PPX):
    """Interior bands of a group where `cover` holds ZERO INK across the
    group's FULL perpendicular extent (25 Aug 2026, Rahul).

    The band rule of 22 Aug can only MERGE. This is its opposite, and it needs
    a STRONGER signature than "nothing bridges it": a real interior corridor has
    partitions crossing it somewhere along its length, while the gutter between
    two drawings on one sheet is empty end to end. So the test is not "is this
    band unbridged" but "is this band EMPTY, over the whole extent".

    It must run on `cover` — every drawn primitive at any angle — not on the
    wall mask. Measured 25 Aug: on the WALL MASK neelachala FIRST FLOOR shows a
    14.01 ft empty horizontal band and would be split back into the two blocks
    Rahul ruled are one building. On `cover` that band carries the terrace
    hatch's 19 diagonal strokes and is not empty at all. The wall reader is
    blind to a 45-degree stroke by construction (`_segs` keeps only H and V).

    Returns [(axis, lo_px, hi_px)] with axis 0 = a VERTICAL band (splits in x),
    1 = HORIZONTAL. Pure -> unit-tested.
    """
    import numpy as np
    if cover is None:
        return []
    x0, y0, x1, y1 = bbox
    sub = cover[max(0, y0):y1, max(0, x0):x1]
    if sub.size == 0:
        return []
    out = []
    for axis in (0, 1):
        ink = sub.any(axis=axis)          # axis=0 -> one flag per COLUMN
        i, n = 0, len(ink)
        while i < n:
            if ink[i]:
                i += 1
                continue
            j = i
            while j < n and not ink[j]:
                j += 1
            # INTERIOR only: a run touching either end is the margin, not a gutter
            if i > 0 and j < n and (j - i) / norm_ppx >= min_ft:
                base = x0 if axis == 0 else y0
                out.append((axis, base + i, base + j))
            i = j
    return out


def _band_bridged(cover, b1, b2):
    """THE BAND RULE (§12, 21 Aug 2026, Rahul): an empty band splits a sheet
    only if NOTHING covers it — and the question is what covers it
    COLLECTIVELY, not what individually spans it.

    neelachala FIRST FLOOR's two blocks are separated by a 13.1 ft band that no
    wall line crosses and no filled path spans, yet the first-floor terrace
    slab is drawn across it as 19 strokes at EXACTLY 45 degrees: only 2 of them
    reach from one side to the other (a diagonal enters and leaves at different
    y), while together they cover 100% of the band in ONE unbroken run. So the
    test is connectivity, not spanning: is there a single connected component of
    drawn material touching both edges of the band?

    `cover` is painted from every drawn primitive, because `_segs` buckets a
    line as horizontal or vertical and is blind to a diagonal by construction.
    """
    import cv2
    import numpy as np
    if cover is None:
        return False
    if b1[3] <= b2[1] or b2[3] <= b1[1]:                 # one above the other
        lo, hi = (b1, b2) if b1[3] <= b2[1] else (b2, b1)
        crop = cover[lo[3]:hi[1], max(lo[0], hi[0]):min(lo[2], hi[2])]
    elif b1[2] <= b2[0] or b2[2] <= b1[0]:               # side by side
        lf, rt = (b1, b2) if b1[2] <= b2[0] else (b2, b1)
        crop = cover[max(lf[1], rt[1]):min(lf[3], rt[3]), lf[2]:rt[0]].T
    else:
        return False                    # bboxes overlap on both axes: no band
    if crop.shape[0] < 3 or crop.shape[1] < 1:
        return False
    _n, lab = cv2.connectedComponents(np.ascontiguousarray(crop), 8)
    return bool(set(lab[0][lab[0] > 0]) & set(lab[-1][lab[-1] > 0]))


def _wing_groups(m, gap_ft=8.0, cover=None):
    """Split the wall mask into spatially separate building wings.
    Returns [(labels_set, bbox_px, area)] sorted largest first.

    Two blocks of ONE building can sit further apart than `gap_ft` and still be
    one building — the slab bridges them. `cover`, when given, applies the band
    rule to the groups this leaves, and merges any pair whose separating band is
    bridged by drawn material (`_band_bridged`)."""
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
    # BAND RULE pass — merge groups the slab joins. Done on GROUPS, not on the
    # raw components: the ruling is about BLOCKS, and there are only a handful
    # of groups, so the O(n^2) connectivity test costs nothing.
    if cover is not None and len(groups) > 1:
        merged = True
        while merged and len(groups) > 1:
            merged = False
            for i in range(len(groups)):
                for j in range(i + 1, len(groups)):
                    if not _band_bridged(cover, groups[i][1], groups[j][1]):
                        continue
                    a, b = groups[i], groups[j]
                    groups[i] = [a[0] | b[0],
                                 (min(a[1][0], b[1][0]), min(a[1][1], b[1][1]),
                                  max(a[1][2], b[1][2]), max(a[1][3], b[1][3])),
                                 a[2] + b[2]]
                    groups.pop(j)
                    merged = True
                    break
                if merged:
                    break
    # SPLIT PASS — the opposite operation to the merge above (25 Aug 2026,
    # Rahul). GHATIKIA draws TWO VIEWS on one sheet (FIRST FLOOR left, TYPICAL
    # FLOOR right) and they union into ONE group at the 8 ft proximity stage,
    # so `_band_bridged` never even sees them. A group is divided when its
    # interior holds a band with ZERO ink across its full perpendicular extent.
    # Measured on `cover`, min 1 ft: GHATIKIA one vertical band of 6.48 ft;
    # FLOOR PLAN, BRICK WORK and FIRST FLOOR NONE — the rule is inert on every
    # single-view sheet in the corpus, which is the failure mode that matters.
    if cover is not None:
        cbb = {i: bb for i, bb, _a in comps}
        out = []
        for labs, bb, area in groups:
            bands = _empty_bands(cover, bb, EMPTY_BAND_MIN_FT)
            if not bands:
                out.append([labs, bb, area])
                continue
            axis, lo, hi = max(bands, key=lambda b: b[2] - b[1])
            side = {0: [], 1: []}
            for i in labs:
                c = cbb.get(i)
                if c is None:
                    continue
                mid = (c[0] + c[2]) / 2.0 if axis == 0 else (c[1] + c[3]) / 2.0
                side[0 if mid < lo else 1].append(i)
            if not (side[0] and side[1]):
                out.append([labs, bb, area])       # nothing either side: keep
                continue
            for part in (side[0], side[1]):
                bxs = [cbb[i] for i in part]
                out.append([set(part),
                            (min(b[0] for b in bxs), min(b[1] for b in bxs),
                             max(b[2] for b in bxs), max(b[3] for b in bxs)),
                            sum(a for i, _b, a in comps if i in part)])
        groups = out
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


SEAL_DEFAULT_FT = 4.0        # only when the sheet states nothing: see below


def derived_seal_ft(leaf_widths_ft, schedule_widths_ft=None,
                    default_ft=SEAL_DEFAULT_FT, min_n=5):
    """The seal's job is to close a DOORWAY, so its size is the sheet's own
    widest ordinary opening — not a constant (24 Aug 2026, Rahul).

    Order, and it is a §0.1 order: DRAWN LEAVES first (p90, so one freak
    sliding door does not set it), then the PRINTED OPENING SCHEDULE where a
    sheet draws too few leaves to give a p90 — a printed schedule is drawn data
    and outranks any default. NEVER our own cut widths: those come out of the
    mask this seal produces, so deriving from them is circular.

    A sheet with neither is UNDERIVED: it keeps `default_ft` and SAYS SO, so a
    silent default can never masquerade as a measurement.

    Returns (seal_ft, source). Pure -> unit-tested.
    """
    def p90(a):
        a = sorted(x for x in (a or []) if x and x > 0)
        return (round(a[int(0.9 * (len(a) - 1))], 2), len(a)) if a else (None, 0)
    w, n = p90(leaf_widths_ft)
    if n >= min_n:
        return w, f"p90 of {n} drawn leaves"
    sw, sn = p90(schedule_widths_ft)
    if sn:
        return sw, f"p90 of {sn} printed schedule widths ({n} drawn leaves < {min_n})"
    return default_ft, (f"UNDERIVED: {n} drawn leaves and no printed schedule "
                        f"— keeping the {default_ft} ft default")


def door_position_checks(openings, footprint_poly=None, tol_ft=0.35):
    """B — `doors_placed_sound` extended from WIDTH to POSITION (25 Aug 2026).

    The existing rule scores a cut against the width of its drawn leaf, and a
    cut can match that width perfectly while sitting on the wrong wall. Three
    position questions, each answerable from data the opening already carries:

      hinge_on_cut        — is the leaf's measured HINGE on its own cut
                            opening? It can fail and it did: 6 of 12 before the
                            20 Aug fix, 12 of 12 after, and nothing pinned it.
      leaf_inside_plan    — is any part of the leaf outside the building
                            footprint?

    A THIRD CHECK WAS WRITTEN AND DROPPED: "does the leaf lie in the quadrant
    the drawn arc sweeps". `swing_area` is COMPUTED FROM the arc and `hinge` /
    `tip` ARE the arc's two ends, so the test asks whether the arc's endpoints
    lie in the arc's own bounding box. It read 12/12 and it cannot read
    anything else. A check that cannot fail is not a check — testing the BUILT
    leaf against the drawn quadrant needs the leaf the GLB builder makes, which
    does not exist at this layer.

    ROUTE: all three need the drawn ARC (`hinge`, `tip`, `swing_area`), which
    only the door-symbol path produces. A sheet whose `meta.route
    .door_symbol_paths.arc` is 0 reaches NONE of them, and its doors are
    reported as `not_scorable` rather than as passes — an absent branch is not
    a green result. Pure -> unit-tested.
    """
    def _inside(poly, pt):
        if not poly:
            return True                      # no footprint -> not a failure
        x, y = pt
        hit = False
        for i in range(len(poly)):
            (x0, y0), (x1, y1) = poly[i - 1], poly[i]
            if (y0 > y) != (y1 > y):
                if x < x0 + (y - y0) * (x1 - x0) / ((y1 - y0) or 1e-12):
                    hit = not hit
        return hit

    res = {"hinge_on_cut": 0, "leaf_inside_plan": 0,
           "scored": 0, "not_scorable": 0, "outside_plan": []}
    for o in openings or []:
        if o.get("type") != "door":
            continue
        h, t, fp = o.get("hinge"), o.get("tip"), o.get("footprint")
        if not (h and t and fp):
            res["not_scorable"] += 1         # no arc on this sheet's route
            continue
        res["scored"] += 1
        x0, y0, x1, y1 = min(fp[0], fp[2]), min(fp[1], fp[3]), max(fp[0], fp[2]), max(fp[1], fp[3])
        dx = max(x0 - h[0], 0.0, h[0] - x1)
        dy = max(y0 - h[1], 0.0, h[1] - y1)
        if math.hypot(dx, dy) <= tol_ft:
            res["hinge_on_cut"] += 1
        mid = ((h[0] + t[0]) / 2.0, (h[1] + t[1]) / 2.0)
        if all(_inside(footprint_poly, p) for p in (h, t, mid)):
            res["leaf_inside_plan"] += 1
        else:
            res["outside_plan"].append(o.get("id"))
    return res


def _closest_pair(a, b, chunk=512):
    """Exact closest pair of points between two sets, in bounded memory.

    The whole matrix is what the old code built, and it is what forced the
    400-point decimation: two 6,700-point components would need a 6700x6700
    float64 matrix. Chunking the rows gives the same answer at 512 rows at a
    time, so the cap is not needed. Pure. Returns (dist, point_in_a, point_in_b).
    """
    import numpy as np
    best = None
    for s in range(0, len(a), chunk):
        blk = a[s:s + chunk]
        d = np.linalg.norm(blk[:, None, :] - b[None, :, :], axis=2)
        k = int(d.argmin())
        i, j = divmod(k, d.shape[1])
        if best is None or d[i, j] < best[0]:
            best = (float(d[i, j]), blk[i], b[j])
    return best


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
    # The cap is the building's SHORTER SIDE in feet, not the raster's shorter
    # side in pixels. `min(wall_mask.shape)` was a CANVAS-unit constant — the
    # same class as BORDER_MAXLEN_PT — and would have moved the footprint
    # silently the moment the canvas grew in the short axis (§12).
    _ys, _xs = np.nonzero(wall_mask)
    max_bridge = (float(min(_xs.max() - _xs.min(), _ys.max() - _ys.min()))
                  if len(_xs) else float(min(wall_mask.shape)))
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

    # 2) boundary points per component. THE 400-POINT DECIMATION IS GONE
    # (22 Aug 2026, Rahul). It read "subsampled: only the nearest PAIR matters"
    # — but these points are exactly what DECIDES the nearest pair, so keeping
    # every Nth one moves the bridge to whichever sampled point happened to
    # survive, and the bridge LENGTH then decides accept-or-reject against
    # `max_bridge`. Every sheet in the corpus was over the cap: FLOOR PLAN
    # 1491, GHATIKIA 2101, BRICK WORK 4159, FIRST FLOOR 6719 points in a single
    # component — 3.7x to 16.8x. Same family as `rooms[:16]`: an absolute cap
    # on a parsed quantity, invisible to every metric downstream of it.
    pts = []
    for i in keep:
        comp = np.zeros_like(wall_mask)
        comp[lab == i] = 255
        cnts, _h = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        p = np.vstack([c.reshape(-1, 2) for c in cnts]) if cnts else np.empty((0, 2))
        pts.append(p.astype(np.float64))

    # 3) Prim's MST over components, weight = distance between closest points
    if len(pts) > 1:
        inside, outside = {0}, set(range(1, len(pts)))
        _cp = {}          # (i, j) -> closest pair, computed once per component
        while outside:
            best = None                   # (dist, i, j, pi, pj)
            for i in inside:
                for j in outside:
                    if len(pts[i]) == 0 or len(pts[j]) == 0:
                        continue
                    cp = _cp.get((i, j))
                    if cp is None:
                        cp = _cp[(i, j)] = _closest_pair(pts[i], pts[j])
                    if best is None or cp[0] < best[0]:
                        best = (cp[0], i, j, cp[1], cp[2])
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


def wall_gap_pairs(drawings, ppf, max_in=24.0, min_ovl_ft=1.5):
    """Every parallel line PAIR with its measured gap AND its position.

    The histogram says a cluster exists; it cannot say what the cluster IS.
    This returns the same pairs with geometry attached — the centre line over
    the overlap, in page POINTS — so a cluster can be located on the drawing
    (outer envelope? at a column? one wall run?) before anything is classified.
    Measurement only: nothing in the parser reads it. Pure."""
    H, V = [], []
    skip = tuple(GEOM_SKIP) + ("column",)
    for d in drawings:
        if any(k in d["lname"] for k in skip):
            continue
        for it in d["items"]:
            if it[0] != "l":
                continue
            a, b = it[1], it[2]
            L = math.hypot(b.x - a.x, b.y - a.y)
            if L < min_ovl_ft * ppf or L > BORDER_MAXLEN_PT:
                continue
            if abs(a.y - b.y) < 0.5:
                H.append(((a.y + b.y) / 2, min(a.x, b.x), max(a.x, b.x)))
            elif abs(a.x - b.x) < 0.5:
                V.append(((a.x + b.x) / 2, min(a.y, b.y), max(a.y, b.y)))
    out = []
    lim = (max_in / 12.0) * ppf
    for runs, horiz in ((H, True), (V, False)):
        runs.sort()
        for i in range(len(runs)):
            p1, a1, b1 = runs[i]
            for j in range(i + 1, len(runs)):
                p2, a2, b2 = runs[j]
                if p2 - p1 > lim:
                    break
                if p2 - p1 <= 0.01:
                    continue
                lo, hi = max(a1, a2), min(b1, b2)
                if hi - lo < min_ovl_ft * ppf:
                    continue
                mid = (p1 + p2) / 2.0
                seg = (lo, mid, hi, mid) if horiz else (mid, lo, mid, hi)
                out.append({"gap_in": round((p2 - p1) / ppf * 12.0, 2),
                            "seg_pt": [round(v, 2) for v in seg],
                            "orient": "h" if horiz else "v"})
                break
    return out


def wall_gap_distribution(drawings, ppf, max_in=24.0, min_ovl_ft=1.5):
    """MEASUREMENT ONLY (W-2): the gap of every parallel line pair on the
    sheet, in inches, as a histogram.

    Deliberately UNFILTERED — no 3-18 in sanity band — because the point is to
    see the real clusters, including the thin railing/chhajja lines that the
    band would hide. Nothing in the parser reads this; it exists so the wall
    classification can be designed against measured reality instead of the
    10 in / 5 in assumption in the rules. Pure -> unit-tested."""
    H, V = [], []
    # COLUMNS ARE NOT WALL PAIRS. A column box's two sides are parallel lines a
    # column-width apart, so the column layer contributed the largest cluster in
    # the first measurement (24 pairs at 12 in on FLOOR PLAN — larger than
    # either real wall cluster) and would have been inherited by the wall
    # classification. Excluded here only; GEOM_SKIP is left alone because the
    # parser's geometry path reads it and must not change.
    skip = tuple(GEOM_SKIP) + ("column",)
    for d in drawings:
        if any(k in d["lname"] for k in skip):
            continue
        for it in d["items"]:
            if it[0] != "l":
                continue
            a, b = it[1], it[2]
            L = math.hypot(b.x - a.x, b.y - a.y)
            if L < min_ovl_ft * ppf or L > BORDER_MAXLEN_PT:
                continue
            if abs(a.y - b.y) < 0.5:
                H.append(((a.y + b.y) / 2, min(a.x, b.x), max(a.x, b.x)))
            elif abs(a.x - b.x) < 0.5:
                V.append(((a.x + b.x) / 2, min(a.y, b.y), max(a.y, b.y)))
    hist, gaps = {}, []
    lim = (max_in / 12.0) * ppf
    for runs in (H, V):
        runs.sort()
        for i in range(len(runs)):
            p1, a1, b1 = runs[i]
            for j in range(i + 1, len(runs)):
                p2, a2, b2 = runs[j]
                if p2 - p1 > lim:
                    break
                if p2 - p1 <= 0.01:
                    continue
                if min(b1, b2) - max(a1, a2) < min_ovl_ft * ppf:
                    continue
                inches = (p2 - p1) / ppf * 12.0
                gaps.append(round(inches, 2))
                hist[int(inches)] = hist.get(int(inches), 0) + 1
                break            # nearest partner only: one gap per line
    return {"histogram_in": dict(sorted(hist.items())),
            "count": len(gaps),
            "median_in": round(sorted(gaps)[len(gaps) // 2], 2) if gaps else None}


def rejected_lines_ft(raw, reg, max_keep=2500):
    """The discard pile in SCENE FEET, derived from the PDF on demand.

    Deliberately not stored in the scene: 2,500 segments is ~200 KB on every
    /scene response and every logged parse, for something only the overlay
    looks at. Needs just the page drawings (no OCR, no raster), so it is cheap
    to recompute where it is actually used."""
    import fitz
    page = fitz.open(stream=raw, filetype="pdf")[0]
    drawings = _page_drawings(page)
    _segs, skipped = _filter_text_layers(drawings, _is_wall_layer, [])
    _w2, skipped_w = _filter_text_layers(drawings, _is_window_layer, [])
    skipped |= skipped_w
    rj, summary = _rejected_linework(drawings, skipped, max_keep=max_keep)
    x0, y0 = float(reg["x0_pt"]), float(reg["y0_pt"])
    ppf, d_ft = float(reg["ppf"]), float(reg["d_ft"])
    sx, sy = (list(reg.get("shift_ft") or [0.0, 0.0]) + [0.0, 0.0])[:2]
    out = [[round((ax - x0) / ppf - sx, 2), round(d_ft - (ay - y0) / ppf - sy, 2),
            round((bx - x0) / ppf - sx, 2), round(d_ft - (by - y0) / ppf - sy, 2)]
           for ax, ay, bx, by in rj]
    return out, summary


def _rejected_linework(drawings, skipped, max_keep=2500, min_len_pt=6.0):
    """The DISCARD PILE: line work the parser did not use as structure.

    An overlay that draws only what was found cannot show a MISSING wall —
    the wall we failed to read is, by definition, in here. Longest first,
    because a missed wall is long and hatch noise is short. Returns
    ([(x0, y0, x1, y1)], {layer: dropped_count})."""
    out, per_layer = [], {}
    for d in drawings:
        name = d["lname"]
        used = ((_is_wall_layer(name) or _is_window_layer(name))
                and name not in skipped)
        if used:
            continue
        for it in d["items"]:
            if it[0] != "l":
                continue
            a, b = it[1], it[2]
            L = math.hypot(b.x - a.x, b.y - a.y)
            if L < min_len_pt or L > BORDER_MAXLEN_PT:
                continue
            out.append((L, a.x, a.y, b.x, b.y))
            per_layer[name] = per_layer.get(name, 0) + 1
    out.sort(key=lambda s: -s[0])
    return [s[1:] for s in out[:max_keep]], per_layer


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


def _door_gap_strip(m, box_px, door_w_px, wall_ft=None, dil_px=6.0):
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
            # "thicker than any wall" — DERIVED from this sheet's own wall
            # (17 Aug 2026), not the 1.5 ft constant chosen when walls were a
            # 0.20 ft smear. Two walls thick is not a wall. On FLOOR PLAN the
            # gap strip is the wall (0.83) plus the door mask's dilation
            # (0.26 each side) = 1.35 ft, which sat just under the old 1.5 and
            # tipped over it as soon as walls carried their real thickness.
            # DERIVATION ATTEMPTED TWICE AND REVERTED (17 Aug 2026). This
            # constant looks like the same smear-era value as min_flank /
            # face_tol / group_tol, but it is NOT measuring a wall: it bounds
            # the strip the CLOSING reveals, which is a function of the wall,
            # the door mask's dilation and the closing kernel together.
            #   `thin > 2 x W`        -> BRICK WORK snapped 11 -> 3, FIRST
            #                            FLOOR 8 -> 5 (W = 0.25 / 0.42 ft)
            #   `thin > W + 2 x dil`  -> FLOOR PLAN 8 -> 6, BRICK WORK 3
            # Both are worse than the constant on every sheet. Left alone and
            # reported rather than tuned; the strip geometry needs measuring
            # before it can be derived (§12).
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
        wd_lo = max(DOOR_LEAF_MIN_FT, wd_ft - 0.7) * ppf   # (1) a real leaf
        wd_hi = min(DOOR_MAX_FT + 1.0, wd_ft + 1.6) * ppf
    else:
        wd_lo, wd_hi = DOOR_LEAF_MIN_FT * ppf, (DOOR_LEAF_MAX_FT + 0.6) * ppf
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
    # ROUTE: under 5 snapped doors this returns None and every caller falls
    # back to NOMINAL_DOOR_FT — a different scale source, recorded nowhere.
    _ROUTE["door_median"] = (f"median of {len(widths)} snapped doors"
                             if len(widths) >= 5
                             else f"NONE: only {len(widths)} snapped doors < 5")
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


_DEBUG_MASKS = {}          # instrument only: set DRISHTI_DEBUG_MASK=1

# ROUTE FINGERPRINT (22 Aug 2026, Rahul). Nine absolute FLOORS switch which
# code path runs, and a floor is worse than a cap: a cap deletes data, a floor
# reroutes the whole parse, so every number downstream then describes a
# DIFFERENT ALGORITHM and a run diff can only say "these numbers moved". Six of
# the nine are already visible in output we emit (meta.source, meta.scale.
# source, the OCR and anchor warnings, meta.wing, built_up_branch.fired). These
# three left NO TRACE. Purely additive: nothing here is read back by the parser.
# ponytail: module-level like _DEBUG_MASKS, so not thread-safe across concurrent
# parse() calls; make it a threaded parameter if parse ever runs in parallel.
_ROUTE = {}


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
    # ROUTE FINGERPRINT for THIS parse (additive; read by nothing here). Seeded
    # so the shape is CONSTANT across sheets: for a run diff, "this key is
    # missing" and "this key changed" are different findings, and a branch that
    # was never reached is itself a route fact worth stating.
    _ROUTE.clear()
    _ROUTE.update({"stair_ladder_dedupe": "not reached",
                   "door_median": "not reached",
                   "door_symbol_paths": "not reached",
                   "seal": "not reached"})
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

    def printed_open_widths():
        """The widths the sheet prints for OPEN-EDGED strips, by kind:
        [("balcony", 4.0), ("utility", 4.5), ...].

        A balcony is not the only covered-but-not-enclosed strip a sheet
        dimensions — FLOOR PLAN also prints `UTILITY 4'6" WIDE`, and §10.1 CE-5
        rules the utility balcony-TYPE, not a room. The kind travels with the
        width so the admitted space can be reported on the right line."""
        out = []
        try:
            import room_dims as _rdw
            for kind, key in (("balcony", "BALCON"), ("utility", "UTI")):
                src = live_words() if _rdw.printed_widths(live_words(), key) \
                    else ocr_words()
                out += [(kind, w) for w in _rdw.printed_widths(src, key)]
        except Exception:
            return []
        return out

    def printed_balcony_widths():
        return [w for _k, w in printed_open_widths()]

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
    # NO page-unit length cap here: a "mega-line" is decided by whether it has
    # a parallel partner at wall thickness (keep_structural_lines), because 900
    # pt meant 31.6 ft on this sheet and deleted its 54 ft south wall.
    _NOCAP = 10 ** 9
    wall_segs, skipped = _filter_text_layers(drawings, _is_wall_layer, warnings,
                                             maxlen=_NOCAP)
    win_segs, skipped_w = _filter_text_layers(drawings, _is_window_layer,
                                              warnings, maxlen=_NOCAP)
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

    # STRUCTURAL TEST (replaces the page-unit length cap): a line survives if
    # it has a parallel partner at wall thickness, or if it is no longer than
    # the paired extent. Runs once the scale is known, then the extent is
    # recomputed from what survived.
    # --- SIGNATURE UNION (17 Aug 2026): the W-1/W-3 pairing reader runs
    # ALONGSIDE the named layers, not only as a fallback. `DRISHTI_SIG_UNION`:
    # off | on (all signature spans) | nocol (excluding column-layer faces).
    # A column box's two faces are 10 in apart and pass the wall-pair test, so
    # the reader reads them as wall — 20 of FLOOR PLAN's 50 new spans. Columns
    # are detected separately and are NOT walls.
    _sig_mode = os.getenv("DRISHTI_SIG_UNION", "off")
    if _sig_mode != "off" and struct and mode != "geometry":
        _src = drawings if _sig_mode == "on" else [
            d for d in drawings if "column" not in (d["lname"] or "")]
        _sig = _geometry_wall_segs(_src, ppf, [], dim_keys)
        _have = {tuple(round(v, 1) for v in
                       (min(g[0], g[2]), min(g[1], g[3]),
                        max(g[0], g[2]), max(g[1], g[3]))) for g in struct}
        _add = [g for g in _sig
                if tuple(round(v, 1) for v in
                         (min(g[0], g[2]), min(g[1], g[3]),
                          max(g[0], g[2]), max(g[1], g[3]))) not in _have]
        if _add:
            struct = struct + _add
            warnings.append(
                "SIGNATURE UNION (%s): %d wall-signature span(s) admitted "
                "alongside the named layers" % (_sig_mode, len(_add)))

    _n_raw = len(struct)
    struct = dedupe_segments(struct, ppf)
    if len(struct) < _n_raw:
        warnings.append(
            "%d of %d wall segment(s) dropped as degenerate or duplicate "
            "(zero-length pattern artefacts of the CAD export)"
            % (_n_raw - len(struct), _n_raw))
    struct, _keep_info = keep_structural_lines(struct, ppf)
    if _keep_info["dropped"]:
        warnings.append(
            f"{_keep_info['dropped']} unpaired mega-line(s) dropped as page "
            f"border / site boundary ({_keep_info['paired']} wall lines have a "
            "parallel partner at wall thickness and are kept at any length)")
        xs = [s_[0] for s_ in struct] + [s_[2] for s_ in struct]
        ys = [s_[1] for s_ in struct] + [s_[3] for s_ in struct]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        w_ft = (x1 - x0) / ppf
        d_ft = (y1 - y0) / ppf

    # --- PHASE 1 (17 Aug 2026): ADMIT `ar stairs`, ONE VARIABLE --------------
    # Layer names lie (§12, 12 Aug): FLOOR PLAN's lobby north wall is drawn on
    # `ar stairs`. Attempt 6 (16 Aug) admitted it correctly and was judged by
    # an instrument that PUNISHED the fix — built-up was `floor_inside +
    # wall_material`, and wall_material collapses when the ring closes, so
    # R-8 fell to 78.4. Built-up is now the plate from the wall ring (branch
    # c, 17 Aug), which rises as walls are read. This is attempt 7.
    #
    # The gate is computed from the TRUSTED walls ALONE, BEFORE any candidate
    # is seen — a set containing the candidates lets them vouch for themselves
    # (§12, 14 Aug). Candidates must also PAIR at wall thickness: a lone line
    # inside the building is not a wall.
    # Layer `0` is the big one — 782 ft of wall-signature pairs on GHATIKIA and
    # 1,230 ft on neelachala FIRST FLOOR, sheets whose NAMED layers carry
    # essentially nothing (§12, 12 Aug). It is matched EXACTLY: "0" as a
    # substring would match `ar-10`, `column0` and every other layer.
    # LAYER `0` ADMITTED AND REVERTED (17 Aug 2026, attempt 8). On FLOOR PLAN
    # — the only sheet that can judge it — layer `0` contributes NOTHING: of
    # 112 candidates only the same 10 `ar stairs` lines survive, and 101 are
    # rejected outside the trusted extent (the gate correctly throws out its 13
    # lines at y -13.0..-7.9, below the building). On the sheets where it
    # matters it is destructive: neelachala FIRST FLOOR's footprint went
    # 1664.3 -> 3819.6 sqft = **102% OF ITS OWN PLOT**, a §0.1 physics
    # violation, with R-2 96.8 -> 95.9; GHATIKIA lost 485 sqft of carpet
    # (1711.3 -> 1226.0) and R-2 58.6 -> 54.2. Layer `0` carries real wall AND
    # everything else the drafter left unnamed, and the pairing test cannot
    # tell them apart. See §12.
    _ADMIT_SUB = ("ar stairs",)
    _ADMIT_EXACT = ()
    _cand = dedupe_segments(
        [g for g in _segs(drawings,
                          lambda n: n in _ADMIT_EXACT
                          or any(k in n for k in _ADMIT_SUB))
         if g not in struct], ppf)
    if _cand:
        _ext = paired_extent(struct, ppf)
        _margin = 0.02 * max(_ext[2] - _ext[0], _ext[3] - _ext[1]) if _ext else 0.0
        _inside = [g for g in _cand if inside_extent(g, _ext, _margin)]
        _paired = _paired_indices(struct + _inside, ppf)
        _keep = [g for k, g in enumerate(struct + _inside)
                 if k >= len(struct) and k in _paired]
        if _keep:
            struct = struct + _keep
            warnings.append(
                "PHASE 1: %d of %d candidate line(s) (`ar stairs`, `0`) admitted as wall "
                "(inside the trusted extent AND paired at wall thickness); "
                "%d rejected outside it" % (len(_keep), len(_cand),
                                            len(_cand) - len(_inside)))

    # --- CANVAS EXTENSION (14 Aug 2026) -------------------------------------
    # The raster used to be exactly the WALL extent, so anything drawn outside
    # it was off-canvas and could never be measured: FLOOR PLAN's flat-1
    # balcony sits at x -4.0..0.0 ft, west of the linework origin, and no
    # pocket can form for a region that is not in the image. That is why
    # `foot_ext - foot` was never measuring a balcony (§12).
    # The bound comes from the traced RAILING RUNS and nothing else - never
    # the page, never the plot. The plot boundary is dash-dot and is removed
    # by the tracer before any run exists, so it cannot enlarge the canvas.
    _canvas_ext, _rail_runs_raw, _pw0 = None, [], []
    try:
        assert os.getenv("DRISHTI_CANVAS_EXT", "1") != "0"
        import railings as _rail0
        _rf = lambda X, Y: ((X - x0) / ppf, (Y - y0) / ppf)   # translation only
        _ln0 = [(_rf(it[1].x, it[1].y), _rf(it[2].x, it[2].y))
                for d in drawings for it in d["items"] if it[0] == "l"
                and math.hypot(it[2].x - it[1].x, it[2].y - it[1].y) / ppf >= 0.8]
        _wl0 = [(_rf(g[0], g[1]), _rf(g[2], g[3])) for g in struct]
        _runs0 = _rail0.trace(_ln0, _wl0)["runs"]
        _rail_runs_raw = _runs0
        _pw0 = printed_balcony_widths()
        _pts0 = [q for r in _runs0
                 if _rail0.classify(r, _pw0) == "railing"
                 for q in r["polyline_ft"]]
        if _pts0:
            _canvas_ext = (round(min(q[0] for q in _pts0), 2),
                           round(min(q[1] for q in _pts0), 2),
                           round(max(q[0] for q in _pts0), 2),
                           round(max(q[1] for q in _pts0), 2))
    except Exception:
        _canvas_ext = None

    # --- §10.2 DIMENSION ANCHORS (15 Aug 2026) — the FOURTH INSTRUMENT (D-7).
    # An arrow that lands where no wall was detected proves the parse wrong.
    # Additive: nothing downstream reads this, so no number can move. Two
    # routes, because sheets differ — a `dim`/`dimension` LAYER where one
    # exists (its long lines are the dimension lines, the short perpendicular
    # ones touching their ends are the extension lines that reach the edge),
    # otherwise the sheet's own dimension TEXT anchoring the nearest long line.
    _dim_anchors = None
    try:
        import dimensions as _dim
        _dl = [(_rf(it[1].x, it[1].y), _rf(it[2].x, it[2].y))
               for d in drawings if "dim" in (d["lname"] or "")
               for it in d["items"] if it[0] == "l"]
        _texts = []
        for _t in (live_words() or []) + (ocr_words() or []):
            _v = _dim.parse_value_ft(_t.get("text"))
            if _v:
                _texts.append((_v, _rf((_t["x0"] + _t["x1"]) / 2.0,
                                       (_t["y0"] + _t["y1"]) / 2.0)))
        _long = [(a, b) for a, b in _dl if _dim._len(a, b) >= 1.0]
        _short = [(a, b) for a, b in _dl
                  if _dim.EXT_MIN_FT <= _dim._len(a, b) < _dim.EXT_MAX_FT]
        _route = "dim_layer"
        if len(_long) < 3:                      # no dim layer: text route
            _route = "text"
            _all = [(_rf(it[1].x, it[1].y), _rf(it[2].x, it[2].y))
                    for d in drawings for it in d["items"] if it[0] == "l"]
            _all = [(a, b) for a, b in _all if _dim._len(a, b) >= 1.0]
            _long, _short, _seen = [], [], set()
            for _v, _c in _texts:
                _near = [(a, b) for a, b in _all
                         if min(_dim._len(a, _c), _dim._len(b, _c))
                         <= _dim.NEAR_TEXT_FT]
                if not _near:
                    continue
                _best = min(_near, key=lambda ab: min(_dim._len(ab[0], _c),
                                                      _dim._len(ab[1], _c)))
                _k = (round(_best[0][0], 2), round(_best[0][1], 2),
                      round(_best[1][0], 2), round(_best[1][1], 2))
                if _k not in _seen:
                    _seen.add(_k)
                    _long.append(_best)
        _wl_ft = [(_rf(g[0], g[1]), _rf(g[2], g[3])) for g in struct]
        if _long:
            _dim_anchors = _dim.anchors(_long, _short, _texts, _wl_ft)
            _dim_anchors["route"] = _route
            _sm = _dim_anchors["summary"]
            warnings.append(
                "dimension anchors (§10.2 instrument, %s route): %d dimension(s), "
                "%d/%d endpoint(s) land within 0.5 ft of a detected wall face "
                "(%.0f%%) — an arrow landing where no wall was detected means "
                "the parse is wrong, not the drawing"
                % (_route, _sm["dimensions"], _sm["within_0_5_ft"],
                   _sm["endpoints"], _sm["pct_on_a_detected_face"] or 0))
    except Exception:
        _dim_anchors = None

    # --- normalized raster -> solid wall bands ---
    sc = NORM_PPX / ppf
    # asymmetric pads: the FRAME is unchanged (x0/y0/d_ft and every ft value
    # derived from them stay put) - only the canvas around it grows, so a
    # feature outside the wall extent lands at a negative or over-length foot
    # coordinate, which is exactly what it is.
    pad_x = pad_y = pad_r = pad_b = PAD_PX
    if _canvas_ext:
        pad_x += max(0, int(-_canvas_ext[0] * NORM_PPX) + 1)
        pad_y += max(0, int(-_canvas_ext[1] * NORM_PPX) + 1)
        pad_r += max(0, int((_canvas_ext[2] - (x1 - x0) / ppf) * NORM_PPX) + 1)
        pad_b += max(0, int((_canvas_ext[3] - (y1 - y0) / ppf) * NORM_PPX) + 1)
    W = int((x1 - x0) * sc) + pad_x + pad_r
    H = int((y1 - y0) * sc) + pad_y + pad_b
    if W * H > 6000 * 6000:
        raise ValueError(f"plan raster too large ({W}x{H}) - scale looks wrong")

    def tp(x, y):
        return (int((x - x0) * sc) + pad_x, int((y - y0) * sc) + pad_y)

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
        # PAIR-BUILT WALLS (17 Aug 2026, Rahul): paint the MATERIAL BETWEEN each
        # measured pair of faces, at its own measured thickness — never a band
        # dilated out of a line. Dilating the faces inward over the rooms is
        # what cost room accuracy: R-2 went 97.0 -> 99.5 the moment dilation
        # was ablated. An UNPAIRED survivor has no measured thickness, so it
        # takes this sheet's MEDIAN measured wall (derived per sheet, never a
        # constant); on FLOOR PLAN they are 7% of wall length, on neelachala
        # FIRST FLOOR 0%, on BRICK WORK 49%.
        _abl = os.getenv("DRISHTI_ABLATE", "")
        mm = np.zeros((H, W), np.uint8)
        if os.getenv("DRISHTI_PAINT", "pairs") == "lines":   # measurement hook
            for ax, ay, bx, by in struct:
                cv2.line(mm, tp(ax, ay), tp(bx, by), 255, 2)
            _rects, _unp = [], []
        else:
            _rects, _unp = wall_rects(struct, ppf)
        for _rx0, _ry0, _rx1, _ry1 in _rects:
            _p, _q = tp(_rx0, _ry0), tp(_rx1, _ry1)
            cv2.rectangle(mm, (min(_p[0], _q[0]), min(_p[1], _q[1])),
                          (max(_p[0], _q[0]), max(_p[1], _q[1])), 255, -1)
        _med = (sorted(abs(r[3] - r[1]) if abs(r[2] - r[0]) > abs(r[3] - r[1])
                       else abs(r[2] - r[0]) for r in _rects)[len(_rects) // 2]
                if _rects else 0.5 * ppf)
        _upx = max(2, int(_med * sc))
        for ax, ay, bx, by in _unp:
            cv2.line(mm, tp(ax, ay), tp(bx, by), 255, _upx)
        mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, K(shp, (9, 9)))
        # DILATE is now only a JUNCTION CONNECTOR: pair-painting already fills
        # the wall body, so this exists solely to close the pixel-scale gaps
        # where two pair-rectangles meet at a corner. Its value is DERIVED by
        # sweep (DRISHTI_DILATE), not assumed.
        _dil = int(os.getenv("DRISHTI_DILATE", dil) or dil)
        if _abl != "dil" and _dil > 1:
            mm = cv2.dilate(mm, K(shp, (_dil, _dil)))
        # merge the TWO lines of a double-line wall into one solid band:
        # kernel = max wall thickness (10 in ~ 0.85 ft). Door gaps
        # (>= 2'6" = 127 px) survive.
        if os.getenv("DRISHTI_CLOSE45", "off") == "on":      # measurement hook
            _wk = int(0.9 * NORM_PPX) | 1
            mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, K(shp, (_wk, _wk)))
        # the 0.88 ft closing kernel that used to merge the two faces of a
        # wall is REMOVED (17 Aug 2026): ablation showed it changed FLOOR PLAN
        # by nothing and the other sheets by under 4 sqft, and pair-painting
        # fills the wall body directly, so there is nothing left for it to
        # merge. A step we reasoned about for a week did nothing (§12).
        # envelope sealing (wings/rooms mask only): directionally bridge gaps in
        # wall runs BEFORE the area filter, so a fragmented building reconnects
        # into one region that survives instead of being dropped as slivers.
        # TWO PASSES BUILT AND MEASURED, DEFAULT LEFT ON `blanket` (17 Aug
        # 2026). The separation is correct in principle and works on a cleanly
        # drawn sheet — FLOOR PLAN gains C.TOILET and the passage, carpet
        # 1203.5 -> 1301.5, R-8 87.2 -> 92.2 — but it CANNOT rescue a
        # fragmented one, and the reason is not the weld's aim. On neelachala
        # FIRST FLOOR the blanket close adds 493.9 sqft of "wall" that the
        # passes do not, and **35% of it is more than 1.5 ft wide, up to 8.4
        # ft**: it is not welding a wall network, it is SUBSTITUTING for one.
        # That sheet's 11 rooms exist because the close FILLS SPACE, so
        # separating welding from space-destruction necessarily loses them
        # (514 welds fire there and it still collapses to 2 rooms).
        # `DRISHTI_SEAL_MODE=passes` selects the separated version.
        if seal_ft > 0 and os.getenv("DRISHTI_SEAL_MODE", "blanket") == "blanket":
            g = int(seal_ft * NORM_PPX) | 1
            mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, K(cv2.MORPH_RECT, (g, 3)))
            mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, K(cv2.MORPH_RECT, (3, g)))
        elif seal_ft > 0:
            # TWO PASSES, SEPARATED (17 Aug 2026). One kernel was doing two
            # jobs and fixing either half broke the other (§12).
            #   pass 1 WELD  — join fragments ALONG a wall run (any alignment)
            #   pass 2 BREAK — close doorways and drafting breaks (collinear)
            # Neither may cross open space, which is what destroyed C.TOILET.
            _seg_px = [(*tp(a_, b_), *tp(c_, d_)) for a_, b_, c_, d_ in struct]
            _thick = max(3, int(0.5 * NORM_PPX))
            for _p, _q in (weld_bridges(_seg_px, seal_ft * NORM_PPX)
                           + collinear_bridges(_seg_px, seal_ft * NORM_PPX,
                                               0.35 * NORM_PPX)):
                cv2.line(mm, (int(_p[0]), int(_p[1])), (int(_q[0]), int(_q[1])),
                         255, _thick)
        if False:
            # COLLINEAR SEAL TRIED AND REVERTED (17 Aug 2026). Replacing this
            # blanket close with `collinear_bridges` is RIGHT on FLOOR PLAN —
            # C.TOILET and the passage come back, carpet +110.3, R-8 87.2 ->
            # 92.5 — and CATASTROPHIC on the fragmented sheets: neelachala
            # FIRST FLOOR went 11 rooms -> 2 and R-2 96.8 -> 0.0, GHATIKIA
            # 14 -> 2. Their wall fragments are NOT collinear (the geometry
            # reader's paired spans are short and offset), so the gaps that
            # keep those sheets enclosed are not breaks in a run and nothing
            # bridges them. The criterion is right; it needs a companion for
            # offset fragments before it can replace this. See §12.
            g = int(seal_ft * NORM_PPX) | 1
            mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, K(cv2.MORPH_RECT, (g, 3)))
            mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, K(cv2.MORPH_RECT, (3, g)))
        if ero and _abl != "ero":
            mm = cv2.erode(mm, K(cv2.MORPH_RECT, (ero, ero)))
        n, lab, stt, _ = cv2.connectedComponentsWithStats(mm, 8)
        keep = np.zeros_like(mm)
        for i in range(1, n):
            if stt[i, cv2.CC_STAT_AREA] > MIN_WALL_AREA_PX:
                keep[lab == i] = 255
        return keep

    # DILATE 9 -> 5 (17 Aug 2026), DERIVED BY SWEEP, not assumed. With
    # pair-painting the wall body is already filled, so dilation only has to
    # close pixel-scale gaps where two pair-rectangles meet at a corner.
    # Swept 3/5/7/9 on both instrumented sheets: at 3 neelachala FIRST FLOOR
    # collapses (11 rooms -> 7, R-2 96.8 -> 93.7, sample 8 -> 5); 5 is the
    # smallest value that holds it, and it reads BETTER than 9 on both sheets
    # (FLOOR PLAN R-2 96.6 -> 98.0, FIRST FLOOR 97.2 -> 98.4).
    m = _mask("RECT", 5, 5)             # output mask (de-blobbed) -> walls_poly
    # the door-gap finder wants a FAT wall band. With pair-painted walls the
    # band already carries its true thickness, so the extra dilation it used to
    # need is smaller — swept, not assumed (DRISHTI_SNAP_DIL).
    m_snap = _mask("ELLIPSE", int(os.getenv("DRISHTI_SNAP_DIL", 13)), 0)
    # sealed mask used ONLY for wing-grouping + room free-space: bridges wall
    # gaps so a fragmented building is one region and rooms enclose. walls_poly
    # stays from the unsealed `m`, so stairs/open features are never filled.
    # THE SEAL IS DERIVED FROM THE DRAWING (24 Aug 2026, Rahul), not a
    # constant. Inputs must be seal-INDEPENDENT or the derivation is circular:
    # drawn door-layer leaves come straight from the linework, and the printed
    # opening schedule is text. Our own cut widths are NOT usable — they come
    # out of the very mask this seal produces.
    _leaf_w = []
    try:
        _lf = []
        for _d in drawings:
            if not _is_door_layer(_d["lname"]):
                continue
            _r = _d["rect"]
            _w = max(abs(_r.x1 - _r.x0), abs(_r.y1 - _r.y0)) / ppf
            if _w >= 1.5:                     # below this it is arc linework
                _lf.append(((_r.x0 + _r.x1) / 2 / ppf,
                            (_r.y0 + _r.y1) / 2 / ppf, _w))
        _g = []                               # one leaf per door symbol
        for _q in _lf:
            for _grp in _g:
                if math.hypot(_q[0] - _grp[0][0], _q[1] - _grp[0][1]) < 3.0:
                    _grp.append(_q)
                    break
            else:
                _g.append([_q])
        _leaf_w = [max(_q[2] for _q in _grp) for _grp in _g]
    except Exception:
        _leaf_w = []
    _sched_w = []
    try:                                      # TG-5, live text then OCR
        import opening_schedule as _os5
        _stoks = [{"text": _w[4], "x0": _w[0], "y0": _w[1],
                   "x1": _w[2], "y1": _w[3]} for _w in page.get_text("words")]
        _sc = _os5.parse_opening_schedule(_stoks)
        if not _sc:
            _sc = _os5.parse_opening_schedule(ocr_words())
        _sched_w = _os5.door_widths_ft(_sc)     # DOORS ONLY — a window is not
        #                                         a doorway and cannot size one
    except Exception:
        _sched_w = []
    # BUILT, MEASURED AND NOT WIRED (24 Aug 2026). Deriving the seal from the
    # sheet's own openings DISPROVED ITSELF the moment it ran on real data:
    # FLOOR PLAN R-2 98.0 -> 94.6, GHATIKIA 14 rooms -> 1, FIRST FLOOR 19 -> 10
    # with R-2 96.9 -> 57.1. Reason, and it is the 17 Aug finding measured from
    # the other side: the drawn leaves are 2.2-3.1 ft on every sheet, so a
    # leaf-derived seal serves only the BREAK CLOSE job and abandons the
    # FRAGMENT WELD job that the 4.0 ft kernel is silently also doing. The gap
    # between this number and 4.0 IS the weld, and it is now visible per sheet.
    # Reported, never applied: `_SEAL_FT` is unchanged.
    # THE SEAL SPLIT, SHIPPED (24 Aug 2026, Rahul). One kernel was doing two
    # jobs, and 17 Aug named the second one wrongly. The two jobs are:
    #   BREAK CLOSE     — doorways and drafting breaks. Sized from the sheet's
    #                     own drawn leaves (2.2-3.1 ft on every sheet here).
    #                     THAT is what this kernel is for, and all it is for.
    #   OUTER-RING CLOSURE — envelope gaps. ALREADY BUILT and better derived:
    #                     `_footprint_from_walls` bridges the ring jamb-to-jamb
    #                     with a RELATIVE bound (each bridge no longer than the
    #                     wall run it sits in), and rooms already come from
    #                     `_foot AND NOT m_env`, so the envelope never depended
    #                     on this kernel — it only looked as if it did.
    # Measured 24 Aug: going 3.1 -> 4.0 ft moves FLOOR PLAN's outside free space
    # by TWO sqft (its envelope is already closed) while costing it 111 sqft of
    # interior. The headroom above a doorway was buying nothing there and
    # eating rooms.
    # THE SPLIT WAS BUILT AND IT FAILED ITS OWN PREDICTION (24 Aug 2026).
    # Predicted before building: FLOOR PLAN recovers the 111 sqft the headroom
    # eats, and the fragmented sheets keep enclosure because the ring bridger
    # closes the envelope explicitly. THE SECOND HALF IS FALSE, and the reason
    # is one line of plumbing: `_footprint_from_walls` is fed `m_env` — the
    # SEALED mask — so the ring is DOWNSTREAM of the seal, not independent of
    # it. Shrink the seal and the ring's own input gets gappier, its relative
    # `max_bridge` rejects the wider spans, and the footprint itself collapses:
    # GHATIKIA 2647.7 -> 2034.2 sqft and 14 rooms -> 1; FIRST FLOOR 4472.1 ->
    # 4079.7 and 19 rooms -> 10, rooms_checked 16 -> 9.
    # FLOOR PLAN's half held only in part: carpet DID rise 1191.1 -> 1328.1,
    # but R-2 fell 98.0 -> 94.6 — the recovered space is rooms growing past
    # their printed dimensions, not rooms coming back.
    # Reverted under standing rule 6. The split is still right; it cannot be
    # made by moving this number while the ring eats its output.
    _seal_derived, _seal_src = derived_seal_ft(_leaf_w, _sched_w)
    _SEAL_FT = float(os.getenv("DRISHTI_SEAL_FT", "4") or 0)
    _ROUTE["seal"] = {"applied_ft": _SEAL_FT, "derived_ft": _seal_derived,
                      "derived_from": _seal_src,
                      "status": "REPORTED, NOT APPLIED",
                      "break_close_headroom_ft": (round(_SEAL_FT - _seal_derived, 2)
                                                  if _seal_derived else None)}
    m_env = _mask("RECT", 5, 5, seal_ft=_SEAL_FT) if _SEAL_FT > 0 else m

    # door clusters are needed BEFORE the wing split: the default wing is the
    # one with the most doors (the largest-area block on a mixed sheet can be
    # a section/detail drawing, not the floor plan)
    door_rects = [d["rect"] for d in drawings if _is_door_layer(d["lname"])]
    has_door_layer = bool(door_rects)
    door_clusters = _cluster_rects(door_rects) if door_rects else []
    door_centers = []                  # ft, full-sheet frame, door-sized only
    for cl in door_clusters:
        wd_ = max(cl.width, cl.height) / ppf
        if DOOR_LEAF_MIN_FT <= wd_ <= DOOR_LEAF_MAX_FT:   # (4) sanity: a real leaf
            door_centers.append((((cl.x0 + cl.x1) / 2 - x0) / ppf,
                                 d_ft - ((cl.y0 + cl.y1) / 2 - y0) / ppf))

    # --- wing split: a sheet can hold several separate building blocks; keep
    # ONE per scene (user directive: no overlapping modules). Coordinates stay
    # in the full-sheet frame; meta reports the wing bbox + count. ---
    # COVER mask for the band rule: every drawn primitive on a non-annotation
    # layer, at any angle. The terrace hatch that joins neelachala FIRST
    # FLOOR's two blocks is 19 strokes at exactly 45 degrees, and the wall
    # reader drops anything that is not horizontal or vertical, so it needs a
    # raster of its own. Measured 21 Aug: all-layers, non-text and layer-`0`
    # input sets give the SAME answer there (bridged, 100% of rows), and the
    # other three sheets resolve to a single wing before the test is reached.
    _cover = np.zeros((H, W), np.uint8)
    for _d in drawings:
        if any(k in _d["lname"] for k in GEOM_SKIP):
            continue
        for _it in _d["items"]:
            if _it[0] == "l":
                cv2.line(_cover, tp(_it[1].x, _it[1].y),
                         tp(_it[2].x, _it[2].y), 255, 2)
            elif _it[0] == "re":
                _r = _it[1]
                cv2.rectangle(_cover, tp(_r.x0, _r.y0), tp(_r.x1, _r.y1), 255, 2)
            elif _it[0] == "qu":
                cv2.polylines(_cover, [np.array([tp(_q.x, _q.y) for _q in _it[1]],
                                                np.int32)], True, 255, 2)
    wing_groups = _wing_groups(m_env, cover=_cover)   # sealed: a fragmented
    wing_count = len(wing_groups)            # building groups as ONE wing
    wbox_ft = None
    w_idx = 0
    if wing_count > 1:
        if wing == "largest":
            def _ft_box(wb):
                return ((wb[0] - pad_x) / NORM_PPX,
                        d_ft - (wb[3] - pad_y) / NORM_PPX,
                        (wb[2] - pad_x) / NORM_PPX,
                        d_ft - (wb[1] - pad_y) / NORM_PPX)
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
        wx0 = (wb[0] - pad_x) / NORM_PPX
        wx1 = (wb[2] - pad_x) / NORM_PPX
        wy_top = d_ft - (wb[1] - pad_y) / NORM_PPX
        wy_bot = d_ft - (wb[3] - pad_y) / NORM_PPX
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
    _pair_band = wall_gap_band(NORM_PPX)     # W-3, in raster px
    _gap_state = {"gaps": None, "used": []}

    def _nearest_wall_gap(ccx_px, ccy_px):
        if _gap_state["gaps"] is None:
            seg_px_ = [(*tp(ax, ay), *tp(bx, by)) for ax, ay, bx, by in struct]
            # TOLERANCES RE-DERIVED FROM THE SHEET'S OWN WALL THICKNESS
            # (17 Aug 2026). 0.8 / 0.35 / 1.2 ft were fixed values chosen
            # against a 0.20 ft SMEARED band; walls are now painted at their
            # measured thickness, so each tolerance is measuring a different
            # object. Derived, not swept to a target:
            #   group_tol = W   — its stated job is to MERGE THE TWO FACES OF
            #                     ONE WALL, so it is exactly one wall thick
            #   min_flank = W   — a jamb is at least as long as the wall is
            #                     thick, or it is not a jamb
            #   face_tol  = W/2 — "still the same face": past half a wall you
            #                     are at the other face
            _W = _wall_thickness_ft(drawings, ppf) or 0.83
            _gap_state["gaps"] = gap_openings(
                seg_px_, DRAWN_GAP_MIN_FT * NORM_PPX, DRAWN_GAP_MAX_FT * NORM_PPX,
                min_flank=_W * NORM_PPX, face_tol=0.5 * _W * NORM_PPX,
                group_tol=_W * NORM_PPX, junction_pad=0.5 * NORM_PPX,
                pair_min=_pair_band[0], pair_max=_pair_band[1])
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
        if not (DOOR_LEAF_MIN_FT <= wd <= DOOR_LEAF_MAX_FT):   # (4) sanity
            continue
        ccx = ((cl.x0 + cl.x1) / 2 - x0) / ppf
        ccy = d_ft - ((cl.y0 + cl.y1) / 2 - y0) / ppf
        if not _in_wing(ccx, ccy, pad=2.0):
            continue
        (ax, ay), (bx, by) = tp(cl.x0, cl.y0), tp(cl.x1, cl.y1)
        hit = _door_gap_strip(m_snap, (ax, ay, bx, by), wd * NORM_PPX,
                              wall_ft=_wall_thickness_ft(drawings, ppf),
                              dil_px=int(os.getenv("DRISHTI_SNAP_DIL", 13)) / 2.0)
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
    # PER-LOCATION GATING (shipped 21 Aug 2026, Rahul).
    # FLOOR PLAN reads 16 doors — the 12 symbols plus FOUR gaps, every one
    # verified against the drawn faces either side, none a duplicate, and all
    # 16 SOUND (12 leafed, 4 leafless):
    #   KITCHEN   18.00-21.98 at y 18.95, between drawn faces 18.73 / 19.15
    #   BALCONY   y 9.90-12.91 at x 0.41, between drawn faces 0.00 / 0.83
    #   LOBBY     28.41-31.41 at y 7.50, between drawn faces 7.06 / 7.89
    #   FLAT-2    66.60-71.65 at y 13.72, between drawn faces 13.68 / 14.09
    # Two of those were not known to be there: the LOBBY doorway and FLAT-2's
    # BALCONY opening. The sheet was expected to gain 2 and had 4.
    #
        # The gate was `not
    # has_door_layer`: one door layer anywhere on the sheet switched the whole
    # geometric finder off. FLOOR PLAN is the case — it draws NO leaf for the
    # KITCHEN or the BALCONY (measured 19 Aug), so the symbol path has nothing
    # to read at either, while the gap path sees both and had its output
    # discarded. A feature present in two code paths and reachable through
    # neither. A gap is now admitted only where the door layer is SILENT at
    # that location, so a sheet with symbols keeps every one of them.
    _gap_ft = {}
    if struct:
        import fitz as _fitz
        _sym_ft = [((c.x0 + c.x1) / 2.0 - x0, d_ft - ((c.y0 + c.y1) / 2.0 - y0) / ppf)
                   for _b, c in door_hits]
        _sym_ft = [(a / ppf, b) for a, b in _sym_ft]
        seg_px = [(*tp(ax, ay), *tp(bx, by)) for ax, ay, bx, by in struct]
        geo = gap_openings(seg_px,
                           DRAWN_GAP_MIN_FT * NORM_PPX, DRAWN_GAP_MAX_FT * NORM_PPX,
                           min_flank=0.8 * NORM_PPX, face_tol=0.35 * NORM_PPX,
                           group_tol=1.2 * NORM_PPX, junction_pad=0.5 * NORM_PPX,
                           pair_min=_pair_band[0],    # W-3: the same band
                           pair_max=_pair_band[1])    # `wall_rects` pairs on
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
            fcx = (cx - pad_x) / NORM_PPX
            fcy = d_ft - (cy - pad_y) / NORM_PPX
            if not _in_wing(fcx, fcy):
                continue
            # IS THE DOOR LAYER SILENT HERE? a symbol-derived door within a
            # leaf's reach is this same doorway seen from the linework, not a
            # second one. Per-LOCATION: a sheet with symbols keeps every one.
            if any(math.dist((fcx, fcy), _p) < DOOR_LEAF_MAX_FT for _p in _sym_ft):
                continue
            for mm in (m, m_snap):        # seal the doorway, both masks
                mm[gy0:gy1, gx0:gx1] = 255
            px0, py0 = x0 + (gx0 - pad_x) / sc, y0 + (gy0 - pad_y) / sc
            px1, py1 = x0 + (gx1 - pad_x) / sc, y0 + (gy1 - pad_y) / sc
            cl = _fitz.Rect(px0, py0, px1, py1).normalize()
            door_hits.append(((gx0, gy0, gx1, gy1), cl))
            _gap_ft[(gx0, gy0, gx1, gy1)] = (round(fcx, 3), round(fcy, 3),
                                             round(w / NORM_PPX, 3))
            placed += 1
        if placed:
            warnings.append(f"{placed} door(s) detected by GEOMETRY (wall-gap "
                            f"rule) - the door layer is silent at those spots")

    # --- contours -> polygons in FEET (origin bottom-left, y up) ---
    def fx(px):
        return round((px - pad_x) / NORM_PPX, 3)

    def fy(py):
        return round(d_ft - (py - pad_y) / NORM_PPX, 3)

    def poly_pts(c):
        c = cv2.approxPolyDP(c, 1.2, True).reshape(-1, 2).astype(float)
        return [[fx(px), fy(py)] for px, py in c]

    # --- WALLS FROM PAIR RECTANGLES: BUILT 19 Aug 2026 AND REVERTED ---------
    # The idea is right — the traced polygon carries the morphology's rounding
    # around each punched door hole and extrudes it as a lumpy mass in the wall
    # run (five x-values spanning 1.57 ft where a 0.42 ft wall has two faces).
    # The RECTANGLES are clean: 48 of them, 202.1 sqft summed, 198.9 union,
    # only 3.3 sqft (2%) of overlap.
    #
    # What broke was the CORNER CLOSURE. `wall_rects` clips each rectangle to
    # the overlap of its two faces, leaving a wall-thickness square open at
    # every junction, and the closure extended a rectangle to the NEIGHBOUR'S
    # FAR BOUND instead of by one wall thickness — so a rectangle meeting a
    # long perpendicular wall grew across the plan. Net wall material came out
    # **997.1 sqft against the rectangles' own 198.9**, the union swallowed the
    # room voids, and the 3D read as stacked sheets. Every numeric ratchet
    # still passed, which is why nothing caught it.
    #
    # Next attempt: extend by ONE WALL THICKNESS, never to a neighbour's bound,
    # and assert net material ~= the rectangles' union before returning.
    walls_poly = []
    # --- WALLS FROM THE MEASURED PAIR RECTANGLES (19 Aug 2026, 3rd attempt) --
    # Tracing walls_poly out of the raster inherits the morphology's rounding
    # around each punched door hole and extrudes it as a lumpy mass in the wall
    # run. `_mask()` has painted pair rectangles since 17 Aug; this makes the
    # OTHER code path read the same object — one object, one code path.
    #
    # THE CORNER CLOSURE is what broke attempt 1: `wall_rects` clips each
    # rectangle to the overlap of its two faces, leaving a wall-thickness
    # square OPEN at every junction, and attempt 1 closed it by extending to
    # the NEIGHBOUR'S FAR BOUND — so a rectangle meeting a long perpendicular
    # wall grew across the plan (997 sqft of material against 199 measured, a
    # GLB of plan-wide stacked sheets, and every numeric ratchet still green).
    # Here a rectangle is extended along its own run by exactly ONE WALL
    # THICKNESS, its own short side, and only where another wall actually
    # sits — bounded by construction. M-1 now watches the result.
    try:
        from shapely.geometry import box as _sbox
        from shapely.geometry import LineString as _LS
        from shapely.ops import unary_union as _uu
        _pr, _pu = wall_rects(struct, ppf)
        _tof = lambda X, Y: ((X - x0) / ppf, d_ft - (Y - y0) / ppf)
        _shapes = []
        for _a, _b, _c, _e in _pr:
            _p1, _q1 = _tof(_a, _b), _tof(_c, _e)
            _shapes.append(_sbox(min(_p1[0], _q1[0]), min(_p1[1], _q1[1]),
                                 max(_p1[0], _q1[0]), max(_p1[1], _q1[1])))
        # an unpaired survivor has no measured thickness -> this sheet's MEDIAN
        # PAIR RECTANGLE, which is the rule `_mask()` uses. Attempt 2 used
        # `_wall_thickness_ft` here instead and so painted a different wall
        # from the mask on the sheet where it matters (BRICK WORK, 54%
        # unpaired) — the same "different input, different measurement" error
        # as the 1.92-vs-1.26 M-1 reading.
        _mth = (sorted(min(abs(r[2] - r[0]), abs(r[3] - r[1])) for r in _pr)[len(_pr) // 2]
                / ppf) if _pr else 0.5
        for _a, _b, _c, _e in _pu:
            _p1, _q1 = _tof(_a, _b), _tof(_c, _e)
            if math.dist(_p1, _q1) > 0.01:
                _shapes.append(_LS([_p1, _q1]).buffer(_mth / 2.0, cap_style=2,
                                                      join_style=2))
        # CLOSURE APPLIES TO PAIR RECTANGLES ONLY. The open junction square is
        # created by `wall_rects` clipping a rectangle to the overlap of its
        # two faces; an unpaired survivor is buffered at full length and was
        # never clipped, so it has no such gap to close. Extending them too
        # (attempts 2-3) added 60% of extra material on BRICK WORK, where 54%
        # of the wall length is unpaired, against 9% on FLOOR PLAN.
        _npair = len(_pr)
        _bb = [g.bounds for g in _shapes]
        _grown = []
        for _i, _g in enumerate(_shapes):
            if _i >= _npair:
                _grown.append(_g)
                continue
            _a0, _b0, _a1, _b1 = _bb[_i]
            _w, _h = _a1 - _a0, _b1 - _b0
            _t = min(_w, _h)                      # this wall's own thickness
            if _t <= 0 or _t >= max(_w, _h):
                _grown.append(_g)
                continue
            _x0e, _y0e, _x1e, _y1e = _a0, _b0, _a1, _b1
            for _j, _o in enumerate(_bb):
                if _j == _i:
                    continue
                if _w >= _h:                       # runs in x: extend in x
                    if not (_o[1] <= _b1 + _t and _o[3] >= _b0 - _t):
                        continue
                    if _a0 - _t <= _o[2] <= _a0 + _t:
                        _x0e = min(_x0e, _a0 - _t)
                    if _a1 - _t <= _o[0] <= _a1 + _t:
                        _x1e = max(_x1e, _a1 + _t)
                else:                              # runs in y
                    if not (_o[0] <= _a1 + _t and _o[2] >= _a0 - _t):
                        continue
                    if _b0 - _t <= _o[3] <= _b0 + _t:
                        _y0e = min(_y0e, _b0 - _t)
                    if _b1 - _t <= _o[1] <= _b1 + _t:
                        _y1e = max(_y1e, _b1 + _t)
            _grown.append(_sbox(_x0e, _y0e, _x1e, _y1e))
        _shapes = _grown
        if wbox_ft is not None:            # keep only the built wing
            _wg = _sbox(*wbox_ft)
            _shapes = [g for g in (h.intersection(_wg) for h in _shapes)
                       if not g.is_empty and g.area > 0]
        _u = _uu(_shapes) if _shapes else None
        _parts = ([] if _u is None else
                  ([_u] if _u.geom_type == "Polygon" else list(_u.geoms)))
        for _g in _parts:
            if _g.geom_type != "Polygon" or _g.area < 0.5:
                continue
            _g = _g.simplify(0.01, preserve_topology=True)
            walls_poly.append({
                "id": f"wp{len(walls_poly)}",
                "outer": [[round(px, 3), round(py, 3)]
                          for px, py in _g.exterior.coords[:-1]],
                "holes": [[[round(px, 3), round(py, 3)] for px, py in r.coords[:-1]]
                          for r in _g.interiors]})
    except Exception:
        walls_poly = []
    _wall_src_rects = bool(walls_poly)
    cnts, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if walls_poly:
        cnts, hier = [], None          # rectangles won; skip the traced path
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
    # §4 D-5: the small-space floor was lowered to 2 sqft here on 16 Aug to
    # catch ducts and REVERTED the same day. Two reasons, both measured: a duct
    # interior is 1.00 ft across against a 0.88 ft wall-merge kernel, so it
    # fills solid and NO area floor can reach it; and at 2 sqft the gate
    # admitted a 3.2 sqft wall-ringed pocket in the plain 40x20 test fixture.
    # Ducts are read from the DRAWN rectangle instead (`enclosed_boxes`).
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
            _void = False
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
            # the room's real OUTLINE, not just its bbox: an L-shaped room's
            # bbox covers space that is not the room, and a wall overlay drawn
            # from bboxes cannot tell a real error from a bbox artefact
            _c, _hh = cv2.findContours(comp.astype(np.uint8), cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
            poly = []
            if _c:
                big = max(_c, key=cv2.contourArea)
                pts = cv2.approxPolyDP(big, 1.5, True).reshape(-1, 2)
                poly = [[fx(int(p[0])), fy(int(p[1]))] for p in pts]
            out.append({"x": fx(px_), "y": fy(py_),
                        # a void has NO floor and is never solid structure in
                        # 3D; it is common area, never carpet (§4 D-5)
                        **({"type": "duct", "void": True} if _void else {}),
                        "area_sqft": round(rarea / (NORM_PPX ** 2), 1),
                        "polygon_ft": poly,
                        "_lab": int(i),
                        "_bbox_ft": (fx(rx), fy(ry + rh), fx(rx + rw), fy(ry))})
        return out, rlab

    # FOOTPRINT BOUNDING (2026-08-11). "Inside the building" is decided by the
    # outer WALL RING (W-1), not by whether a free-space blob happens to touch
    # the raster border. That border test discarded 675 sqft of REAL rooms on
    # FLOOR PLAN.pdf, because the balconies' open faces chain interior ->
    # balcony -> outside. See _footprint_from_walls for why the ring is bridged
    # rather than dilated.
    footprint_sqft, footprint_poly = None, []
    _seg_px = [(*tp(ax, ay), *tp(bx, by)) for ax, ay, bx, by in struct]
    _foot, _bridges, _rejected, _foot_ext, _rej_lines = _footprint_from_walls(
        m_env, seg_px=_seg_px)
    footprint_ext_poly = []
    if _foot is not None:                     # outline, for the wall overlay
        _fc, _fh = cv2.findContours(_foot, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
        if _fc:
            _fp = cv2.approxPolyDP(max(_fc, key=cv2.contourArea), 2.0, True)
            footprint_poly = [[fx(int(p[0][0])), fy(int(p[0][1]))] for p in _fp]
    # INSTRUMENT (measurement only): the EXTENDED ring — the ring closed across
    # the rejected open faces. Balcony area is currently `ext MINUS foot`, so
    # seeing both contours is the only way to see what that subtraction really
    # measures (PLAN-READING-RULES §0.1: a mask difference is not a measurement).
    if _foot_ext is not None:
        _ec, _eh = cv2.findContours(_foot_ext, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
        if _ec:
            _ep = cv2.approxPolyDP(max(_ec, key=cv2.contourArea), 2.0, True)
            footprint_ext_poly = [[fx(int(q[0][0])), fy(int(q[0][1]))] for q in _ep]
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
    # B-1 / B-4 / B-5: THE BALCONY IS MEASURED FROM ITS DRAWN EDGE (§0.1).
    #
    # It used to be `foot_ext - foot` — a difference between two masks, which
    # measures where the ring bridging reached, not where the balcony is. That
    # was proved an ARTEFACT on 14 Aug: flat-1's balcony sits at x -3.92..0.00,
    # west of the linework origin, so it was off-canvas entirely and the 42.7
    # sqft it reported could not have been that balcony (§12).
    #
    # Now: each railing run classified `railing` (ends on wall, turns, and a
    # depth matching a width the SHEET PRINTS) is closed back against the wall
    # and filled. Wall pixels are subtracted so thickness is never counted as
    # floor. The run is drawn on this scratch mask ONLY — walls_poly comes from
    # `m` and is untouched, so the open face is still never built as a wall.
    if rooms and _rail_runs_raw:
        _bals = []
        _kinds0 = printed_open_widths()
        for _r in _rail_runs_raw:
            if _rail0.classify(_r, _pw0) != "railing":
                continue
            _kind, _mw = _rail0.matched_kind(_r, _kinds0)
            # the POCKET the run encloses (railings.pocket_ft): a 3-sided run
            # encloses its own bbox; a 1-sided run encloses the strip between
            # it and the wall behind, which is nothing at all without that
            # extension — FIRST FLOOR's two balconies are both 1-sided.
            _pk = _r.get("pocket_ft")
            if not _pk:
                continue
            _bm = np.zeros_like(m_env)
            cv2.rectangle(_bm, (int(_pk[0] * NORM_PPX) + pad_x,
                                int(_pk[1] * NORM_PPX) + pad_y),
                          (int(_pk[2] * NORM_PPX) + pad_x,
                           int(_pk[3] * NORM_PPX) + pad_y), 255, -1)
            # subtract the UNSEALED wall mask: `m_env` is sealed with a 4 ft
            # kernel, which fills a 3.37 ft balcony solid and loses it entirely
            # (flat-2 measured 0 sqft against a printed 3'6"). The seal is a
            # gap-bridging artefact, not wall.
            _bm = cv2.bitwise_and(_bm, cv2.bitwise_not(m))
            # never count space already counted as a room (no double count)
            for _rm in rooms:
                if _rm.get("_lab", -1) > 0:
                    _bm[rlab == _rm["_lab"]] = 0
            _a = int((_bm > 0).sum())
            if _a < small_room_px:
                continue
            _c2, _h2 = cv2.findContours(_bm, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
            _big = max(_c2, key=cv2.contourArea)
            _poly = [[fx(int(q[0][0])), fy(int(q[0][1]))]
                     for q in cv2.approxPolyDP(_big, 1.5, True)]
            _mx, _my = np.nonzero(_bm)
            _bals.append({"x": fx(int(_my.mean())), "y": fy(int(_mx.mean())),
                          "area_sqft": round(_a / (NORM_PPX ** 2), 1),
                          "polygon_ft": _poly, "_lab": -1,
                          "type": _kind or "balcony", "open_side": True,
                          "printed_width_ft": _mw,
                          "depth_ft": _r["depth_ft"] if "depth_ft" in _r
                          else _rail0.enclosed_depth_ft(_r),
                          "_bbox_ft": (fx(_my.min()), fy(_mx.max()),
                                       fx(_my.max()), fy(_mx.min()))})
        if _bals:
            rooms += _bals
            warnings.append(
                "%d open-edged space(s) measured from the DRAWN edge "
                "(%.1f sqft; depths %s ft against the sheet's printed %s ft)"
                % (len(_bals), sum(b["area_sqft"] for b in _bals),
                   ", ".join("%.2f" % b["depth_ft"] for b in _bals),
                   ", ".join("%.2f" % w for w in _pw0)))
    # §0.2 CONTRADICTS: flag spaces that fail to enclose on ONE side. Emitted
    # only — it must not change a number until Rahul has seen what it flags.
    try:
        # the ENVELOPE thickness (W-2: 9-11 in is the outer wall on this
        # corpus, 4-5 in are partitions), measured from this sheet's own pairs
        _env_gaps = [g["gap_in"] / 12.0 for g in (wall_gap_pairs(drawings, ppf) or [])
                     if 8.0 <= g["gap_in"] <= 14.0]
        _env_ft = (sorted(_env_gaps)[len(_env_gaps) // 2] if _env_gaps else None)
        _open_sides = open_side_regions(m_env, NORM_PPX, pad_x, pad_y, d_ft,
                                        wall_ft=_env_ft)
    except Exception:
        _open_sides = []
    if _open_sides:
        warnings.append(
            "§0.2 CONTRADICTS: %d space(s) enclosed on three sides but open on "
            "one - %s. On an upper floor that is not possible; the DRAWING is "
            "wrong. ASK the user to confirm the missing edge (nothing is "
            "auto-closed, nothing counted)"
            % (len(_open_sides),
               "; ".join("%.1f sqft open to the %s (would be %.1f sqft closed)"
                         % (r["area_as_drawn_sqft"], r["open_side"],
                            r["area_if_closed_sqft"]) for r in _open_sides)))

    if os.getenv("DRISHTI_DEBUG_MASK"):
        _DEBUG_MASKS.clear()
        _DEBUG_MASKS.update({"m_env": m_env.copy(), "m": m.copy(),
                             "m_snap": m_snap.copy(),
                             "pad_x": pad_x, "pad_y": pad_y,
                             "norm_ppx": NORM_PPX, "d_ft": d_ft})

    # --- §4 D-5 DUCTS (16 Aug 2026): wall-ringed VOIDS, 2-18 sqft ------------
    # Read from the DRAWN rectangle, not from raster free space: a duct is
    # narrower (1.00 ft on FLOOR PLAN) than the wall-merge kernel (0.88 ft plus
    # dilation), so its interior is filled solid and no area floor can reach
    # it. Ducts are COMMON AREA, never carpet, and carry `void` so nothing
    # builds them as solid structure or gives them a floor.
    if rooms:
        # same frame as fx()/fy() above: raw feet, the wing shift is applied
        # to every room later, so applying it here would double-count it
        _seg_ft = [((g[0] - x0) / ppf, d_ft - (g[1] - y0) / ppf,
                    (g[2] - x0) / ppf, d_ft - (g[3] - y0) / ppf)
                   for g in struct]
        # the sheet's own wall thickness, so a rectangle as narrow as a wall
        # can be recognised as wall rather than void (measured, not assumed)
        _gaps = [g["gap_in"] / 12.0 for g in (wall_gap_pairs(drawings, ppf) or [])]
        if not _gaps:
            # fall back to the structural pairing itself: the same 3-18 in test
            # that decides what a wall IS (wall_gap_pairs excludes columns and
            # can come back empty on a sparse sheet, e.g. the test fixture)
            _H, _V = [], []
            for _a, _b, _c, _d in _seg_ft:
                if abs(_d - _b) <= 0.12:
                    _H.append(((_b + _d) / 2, min(_a, _c), max(_a, _c)))
                elif abs(_c - _a) <= 0.12:
                    _V.append(((_a + _c) / 2, min(_b, _d), max(_b, _d)))
            for _runs in (_H, _V):
                _runs.sort()
                for _i in range(len(_runs) - 1):
                    for _j in range(_i + 1, len(_runs)):
                        _g = _runs[_j][0] - _runs[_i][0]
                        if _g > 1.5:
                            break
                        if _g >= 0.25 and min(_runs[_i][2], _runs[_j][2]) \
                                - max(_runs[_i][1], _runs[_j][1]) >= 2.0:
                            _gaps.append(_g)
                            break
        _wall_ft = (sorted(_gaps)[len(_gaps) // 2] if _gaps else None)
        _ducts = []
        for _b in enclosed_boxes(_seg_ft, wall_ft=_wall_ft):
            _cx, _cy = (_b[0] + _b[2]) / 2.0, (_b[1] + _b[3]) / 2.0
            # A duct INSIDE a larger room is still a duct (17 Aug 2026): a
            # void is not a room and containment must not suppress it. The
            # only real risk is double-counting, so the test is whether the
            # duct's own interior is already FREE space claimed by a room —
            # it is not, because a wall-ringed void reads as solid in m_env.
            _px_, _py_ = int(_cx * NORM_PPX) + pad_x, int((d_ft - _cy) * NORM_PPX) + pad_y
            if 0 <= _py_ < m_env.shape[0] and 0 <= _px_ < m_env.shape[1] \
                    and m_env[_py_, _px_] == 0:
                continue                       # free space: a room already has it
            _ducts.append({"x": round(_cx, 2), "y": round(_cy, 2),
                           "type": "duct", "void": True, "_lab": -1,
                           "area_sqft": round((_b[2] - _b[0]) * (_b[3] - _b[1]), 1),
                           "polygon_ft": [[_b[0], _b[1]], [_b[2], _b[1]],
                                          [_b[2], _b[3]], [_b[0], _b[3]]],
                           "_bbox_ft": (_b[0], _b[1], _b[2], _b[3])})
        if _ducts:
            rooms += _ducts
            warnings.append(
                "%d duct/shaft void(s) read from the drawn rectangle (%s sqft) "
                "- common area, never carpet, never solid in 3D (§4 D-5)"
                % (len(_ducts), ", ".join("%.1f" % d["area_sqft"] for d in _ducts)))

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
    # THE 16-ROOM CAP IS GONE (22 Aug 2026, Rahul). It was an absolute count
    # sized for a one-plate sheet, applied to a sheet that now holds five flats
    # on two blocks: neelachala FIRST FLOOR finds NINETEEN rooms and the cap
    # deleted the three smallest — 34.0, 33.5 and 29.1 sqft — of which the
    # first two are its two BALCONIES. That is why B-5 read 0.0 there while the
    # sheet prints `balcony 9'-7" X 4'-0"` twice. Same family as
    # BORDER_MAXLEN_PT: a constant that is not derived from the drawing will
    # one day meet a drawing it was not sized for, and it fails SILENTLY
    # because the survivors all look reasonable.
    # Rooms are already bounded by a DERIVED floor — `_min_room_px`, the
    # sheet's own minimum room area — so the cap was a second, blunter filter
    # on the same thing. FLOOR PLAN finds exactly 16 and is unchanged.
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
        fcx = (wx - pad_x) / NORM_PPX
        fcy = d_ft - (wy - pad_y) / NORM_PPX
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
    # DR-3 (19 Aug 2026): read hinge + swing from the DRAWN ARC, per cluster.
    def _dft(px, py):                     # same frame ft_rect() uses here
        return ((px - x0) / ppf, d_ft - (py - y0) / ppf)
    # ONE DRAWING PATH = ONE DOOR SYMBOL (measured 19 Aug: FLOOR PLAN's door
    # layer has exactly 12 paths carrying more than 5 items, and 12 doors). A
    # bbox filter cannot separate them — every door box caught the same 25
    # lines — but the drafter already grouped each leaf with its own arc.
    _raw_paths = [[(_dft(it[1].x, it[1].y), _dft(it[2].x, it[2].y))
                   for it in _d["items"] if it[0] == "l"]
                  for _d in drawings if _is_door_layer(_d["lname"])]
    _door_paths = []
    for _sym in group_door_symbols(_raw_paths):
        _cx = sum((a[0] + b[0]) / 2 for a, b in _sym) / len(_sym)
        _cy = sum((a[1] + b[1]) / 2 for a, b in _sym) / len(_sym)
        _door_paths.append(((_cx, _cy), _sym))
    fallback_doors = 0
    _swing_read = 0
    for bbox_px, cl in door_hits:
        _box = ft_rect(cl)
        _bc = ((_box[0] + _box[2]) / 2.0, (_box[1] + _box[3]) / 2.0)
        _sw = None
        if _door_paths:
            _c, _ss = min(_door_paths,
                          key=lambda t: math.hypot(t[0][0] - _bc[0], t[0][1] - _bc[1]))
            if math.hypot(_c[0] - _bc[0], _c[1] - _bc[1]) <= 4.0:
                _sw = door_swing(_ss)
        rec = {"id": f"o{len(openings)}", "type": "door",
               "z": [0, DOOR_HEAD_FT], "swing_area": ft_rect(cl),
               "snapped": bool(bbox_px)}
        if bbox_px is not None and tuple(bbox_px) in _gap_ft:
            # a GAP opening: no drawn leaf anywhere, so `doors_placed_sound`
            # scores it against the drawn GAP instead (leafless branch)
            rec["gap_ft"] = list(_gap_ft[tuple(bbox_px)])
        if _sw:
            _swing_read += 1
            rec["hinge"] = _sw["hinge"]
            rec["opens_toward"] = _sw["opens_toward"]
            rec["leaf_ft"] = _sw["leaf_ft"]
            rec["closed"] = _sw["closed"]
            rec["tip"] = _sw["tip"]
        fp = None
        if bbox_px:
            px0, py0, px1, py1 = bbox_px
            cand = [fx(px0), fy(py1), fx(px1), fy(py0)]
            # STEP 1 (19 Aug 2026): the cut spans the DRAWN LEAF, not the strip.
            # The strip is a property of the ROI close and came out 1.5-1.7 ft
            # against leaves of 2.2-3.2 ft, so each cut removed about half its
            # doorway and left the rest standing — the "thick wall covering the
            # door" at four separate locations. Position and orientation still
            # come from the strip (that is what it is good for); only the WIDTH
            # comes from the door the drafter drew. Same class as DOOR_MIN_FT:
            # anything sized from the strip is sized from the wrong object.
            # the LEAF alone when the arc could be read (the swing box includes
            # the arc and over-cuts by up to 0.6 ft); the box only as fallback
            _bx = ft_rect(cl)
            _lw = rec.get("leaf_ft") or max(_bx[2] - _bx[0], _bx[3] - _bx[1])
            if DOOR_LEAF_MIN_FT <= _lw <= DOOR_LEAF_MAX_FT:
                _rx = (cand[2] - cand[0]) >= (cand[3] - cand[1])   # runs along x?
                # POSITION FROM THE DRAWN SYMBOL TOO (20 Aug 2026). Centring the
                # leaf width on the STRIP left 6 of 12 FLOOR PLAN cuts shifted
                # 0.46-1.99 ft along their wall from the door the drafter drew
                # (measured: 12 symbols, 12 openings, 1:1, none shared, every
                # drawn opening overlapping its cut — misplaced cuts, not
                # mis-associated symbols). The leaf was then hinged at OUR jamb
                # instead of the drawn one, which pierced 5 leaves with wall
                # material and swung 3 to the side the arc does not sweep.
                # hinge -> closed IS the doorway; the strip keeps only what it
                # is good for, the wall's ORIENTATION and its perpendicular
                # position.
                # The symbol's two arc ends are the leaf SHUT (lying in the
                # wall) and the leaf OPEN (perpendicular to it); which of
                # `tip`/`closed` is which varies by symbol, so pick the one
                # that runs ALONG this wall rather than assuming.
                _hg, _k = rec.get("hinge"), (0 if _rx else 1)
                _end = None
                for _e in (rec.get("closed"), rec.get("tip")):
                    if (_e and abs(abs(_hg[_k] - _e[_k]) - _lw) <= 0.35
                            and abs(_hg[1 - _k] - _e[1 - _k]) <= 0.35):
                        _end = _e
                        break
                if _hg and _end:
                    _a, _b = sorted((_hg[_k], _end[_k]))
                    # SWING SENSE IN PLAN (20 Aug 2026). `opens_toward` is
                    # measured against the DRAWN LEAF, and the drafter draws
                    # that leaf shut on some doors and open on others — so its
                    # left/right is not a fixed frame and cannot set a rotation
                    # sign. The two arc ends give it unambiguously: the leaf
                    # rotates from the SHUT end (the one along this wall, above)
                    # toward the OPEN end. Sign = the cross product of the two.
                    _op = (rec.get("tip") if _end is rec.get("closed")
                           else rec.get("closed"))
                    if _op:
                        _sd = (_end[0] - _hg[0], _end[1] - _hg[1])
                        _od = (_op[0] - _hg[0], _op[1] - _hg[1])
                        rec["opens_ccw"] = bool(_sd[0] * _od[1] - _sd[1] * _od[0] > 0)
                else:                      # no readable arc: centre on the strip
                    _c = (cand[_k] + cand[_k + 2]) / 2.0
                    _a, _b = _c - _lw / 2.0, _c + _lw / 2.0
                cand = ([_a, cand[1], _b, cand[3]] if _rx
                        else [cand[0], _a, cand[2], _b])
            # CUT DEPTH = THE WALL'S OWN MEASURED THICKNESS (20 Aug 2026). The
            # strip's perpendicular span is the ROI close's, not the wall's:
            # 1.06-1.55 ft against a measured 0.83 ft wall (1.3-1.9x), which
            # centred every leaf in a band up to 0.36 ft off the wall's own
            # centre plane. Same class as STEP 1 — sized from the wrong object.
            _wt = _wall_thickness_ft(drawings, ppf)
            if _wt:
                _rx2 = (cand[2] - cand[0]) >= (cand[3] - cand[1])
                _j = 1 if _rx2 else 0
                # PERPENDICULAR POSITION FROM THE HINGE TOO (20 Aug 2026, DR-3).
                # It was the last thing still taken from the strip, and the
                # strip can land on the wrong wall: 6 of 12 FLOOR PLAN cuts sat
                # off their symbol's wall line — five by 0.49-0.68 ft (half a
                # wall, harmless) and flat-1's bedroom entry by 3.32 ft, a
                # different wall entirely. The drawn hinge sits ON the doorway,
                # so it fixes the wall line as well as the jamb; the strip is
                # trusted only for ORIENTATION now.
                _hg2 = rec.get("hinge")
                _pc = (_hg2[_j] if _hg2 else (cand[_j] + cand[_j + 2]) / 2.0)
                cand[_j], cand[_j + 2] = _pc - _wt / 2.0, _pc + _wt / 2.0
            span = max(abs(cand[2] - cand[0]), abs(cand[3] - cand[1]))
            thick = min(abs(cand[2] - cand[0]), abs(cand[3] - cand[1]))
            # VALIDATE the snapped strip: a real door cut is a plausible leaf
            # width AND thin. A fat/oversize strip (>5.5 ft wide or >1.6 ft
            # thick) is a merged WALL, not a door — demote it to an unsnapped
            # swing-box cut so BOQ / the door-scale check don't trust it.
            # (5) THE STRIP HAS NO LOWER BOUND, and that is the finding, not
            # an omission. Measured 18 Aug: a strip is a property of the ROI
            # CLOSE, not of the doorway — three doors that snap correctly show
            # 0.00-0.18 ft of opening on their wall line and still produce
            # 2.24-3.05 ft strips, while the four that failed produced
            # 1.49-1.61 ft strips at real openings of 2.06-3.46 ft. A floor
            # borrowed from a door width was comparing two unlike objects, and
            # the old `- 0.3` was slack papering over exactly that. What still
            # makes a strip valid is that it is THIN (a door cut, not a merged
            # wall) and not absurdly long.
            if span <= DOOR_LEAF_MAX_FT + 0.5 and thick <= 1.6:
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
        # C-4: the acceptance band is 8-48 INCHES on the SHORT side (C-6: the
        # 12 in assumption is about the short side, since that is the dimension
        # the reference bands constrain). Everything here is derived from ppf.
        #
        # It used to be `abs(max(w, h) - ppf * 1ft) < 0.6` — a tolerance of 0.6
        # POINTS, which only ever worked while ppf happened to equal the column
        # box. When the scale moved on 11 Aug (23.80 -> 28.47 pt/ft) the boxes
        # stopped matching and FLOOR PLAN went 26 columns -> 0, silently,
        # because nothing reported columns. Any tolerance in page units must be
        # derived from scale (§12, 12 Aug).
        # C-4's floor is 8 in, applied with a 10% margin because OUR SCALE
        # itself carries a known open question (C-6: the 12 in assumption is
        # pinned to the long side, still unfixed). GHATIKIA's columns measure
        # 7.0-8.4 in short side at its current ppf; a hard 8 in floor cuts one
        # real cluster in half, which is a measurement artefact, not a rule.
        lo, hi = 0.9 * (8.0 / 12.0) * ppf, (48.0 / 12.0) * ppf
        band = [r for r in col_rects if lo <= min(r.width, r.height) <= hi]
        if band:
            # dominant short side, to a proportional (not fixed) tolerance
            tol = max(0.15 * ppf, 0.5)          # ~1.8 in at any scale
            sides = sorted(min(r.width, r.height) for r in band)
            dom = sides[len(sides) // 2]        # median: robust to stray boxes
            uniq = _cluster_rects([r for r in band
                                   if abs(min(r.width, r.height) - dom) <= tol],
                                  gap=1.0)
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
            if r.get("polygon_ft"):
                r["polygon_ft"] = [[round(p[0] - sx, 3), round(p[1] - sy, 3)]
                                   for p in r["polygon_ft"]]
        for f in furniture:
            f["x"] = round(f["x"] - sx, 3)
            f["y"] = round(f["y"] - sy, 3)
    else:
        out_w, out_d = w_ft, d_ft
        sx = sy = 0.0

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

    # --- INSTRUMENT data (Phase 0). Measurement only: the wall-gap
    # distribution and the discard pile. Guarded so an instrument can never
    # break a parse. ---
    _gap_dist, _rej_summary = None, {}
    try:
        _gap_dist = wall_gap_distribution(drawings, ppf)
        _rj, _rej_summary = _rejected_linework(drawings, skipped)
    except Exception:
        _gap_dist, _rej_summary = None, {}

    # --- B-2a RAILING TRACER (additive instrument, 14 Aug 2026). Thin double
    # lines followed as connected RUNS; dash-dot families (the plot boundary)
    # removed first. Emitted for inspection ONLY — nothing downstream reads it,
    # so no area, room or ring number can move. Runs that fail the railing test
    # are still emitted, TAGGED, so the consumer can never assume every run is
    # a balcony: on FLOOR PLAN one run is stair linework and another is the
    # 15.2 ft line across the lobby entrance, which is the drafting error
    # itself (§0 CONTRADICTS). ---
    _railings = None
    try:
        import railings as _rail
        _ftp = lambda X, Y: ((X - x0) / ppf - sx, d_ft - (Y - y0) / ppf - sy)
        _lines = [(_ftp(it[1].x, it[1].y), _ftp(it[2].x, it[2].y))
                  for d in drawings for it in d["items"]
                  if it[0] == "l"
                  and math.hypot(it[2].x - it[1].x, it[2].y - it[1].y) / ppf >= 0.8]
        _wl = [(_ftp(g[0], g[1]), _ftp(g[2], g[3])) for g in struct]
        _railings = _rail.trace(_lines, _wl)
        _pw = printed_balcony_widths()
        _railings["printed_widths_ft"] = _pw
        for _r in _railings["runs"]:
            # depth_ft already comes from describe_run, WITH the wall lines —
            # recomputing it here without them returns None for every straight
            # (1-sided) run and silently unclassifies all of them.
            _r["classification"] = _rail.classify(_r, _pw)
        _n = sum(1 for _r in _railings["runs"] if _r["classification"] == "railing")
        if _railings["runs"]:
            warnings.append(
                f"railing tracer: {len(_railings['runs'])} thin-line run(s), "
                f"{_n} classified as railing, "
                f"{_railings['dash_dot_strokes_dropped']} dash-dot stroke(s) "
                "dropped as plot boundary (instrument only — feeds nothing)")
    except Exception:
        _railings = None

    # THE PLOT MUST COME FROM THE DRAWING OR THE USER — NEVER FROM THE
    # BUILDING (21 Aug 2026, Rahul). The old fallback took `out_w * out_d`
    # whenever the envelope came from overall-dimension text, i.e. the
    # BUILDING'S OWN BOUNDING BOX, and `footprint <= plot` — our only physics
    # check — was then comparing the building to itself. It can only fail that
    # way if the footprint exceeds its own extent. neelachala FIRST FLOOR read
    # a "plot" of 2454.4 sqft, which is exactly its 38.2 x 64.2 ft envelope and
    # exactly the BOTTOM BLOCK's printed 64'-2" x 38'-3": with both blocks kept
    # the pair would read 182% of a plot that was never a plot, failing a
    # CORRECT build. Rahul's real figure for that site is 11,500 sqft (39%).
    # Same class as measuring wall connectivity against a network that contains
    # the tile grid: the instrument's reference was the thing under test.
    #
    # Where the sheet states no plot, plot is UNKNOWN and the check is BLIND —
    # said out loud on `meta.plot_source`, never quietly passed. A user can
    # supply it (`corrections.plot_area_sqft`).
    _plot_sqft, _plot_src = None, "unknown"
    if printed_areas and printed_areas.get("plot_area_sqft"):
        _plot_sqft = round(float(printed_areas["plot_area_sqft"]), 1)
        _plot_src = "printed_area_statement"

    # §12 (19 Aug 2026): a cut must span the DRAWN LEAF, not the strip the ROI
    # close happens to reveal. Six of twelve cuts came out 1.5-1.7 ft against
    # leaves of 2.2-3.2 ft — each cutting half its doorway and leaving the rest
    # standing, which IS the "thick wall covering the door".
    # §0.2 ASK (19 Aug 2026): a REAL-WORLD CLASH — a column standing inside a
    # doorway. Rahul's ruling: report the CLEAR WIDTH left after obstructions,
    # not the overlap, because that is what decides whether a person fits. C-7
    # says the column is where the drawing puts it, so either the drawing
    # clashes or the door is elsewhere — both need the user. Never corrected.
    _blocked = []
    try:
        for _o in openings:
            if _o.get("type") != "door" or not _o.get("footprint"):
                continue
            _f = _o["footprint"]
            _rx = (_f[2] - _f[0]) >= (_f[3] - _f[1])
            _w = max(_f[2] - _f[0], _f[3] - _f[1])
            _eaten = 0.0
            for _c in columns:
                if _c["x"] > _f[2] or _c["x"] + _c["w"] < _f[0] \
                        or _c["y"] > _f[3] or _c["y"] + _c["d"] < _f[1]:
                    continue
                _eaten += (min(_c["x"] + _c["w"], _f[2]) - max(_c["x"], _f[0])) if _rx \
                    else (min(_c["y"] + _c["d"], _f[3]) - max(_c["y"], _f[1]))
            _clear = _w - _eaten
            if _eaten > 0 and _clear < DOOR_LEAF_MIN_FT:
                _blocked.append({
                    "at_ft": [round((_f[0] + _f[2]) / 2, 2), round((_f[1] + _f[3]) / 2, 2)],
                    "opening_ft": round(_w, 2), "obstructed_ft": round(_eaten, 2),
                    "clear_ft": round(_clear, 2), "clear_in": round(_clear * 12, 1),
                    "question": "A column obstructs this doorway, leaving %.0f in "
                                "clear. Is the column or the door misplaced?"
                                % (_clear * 12)})
    except Exception:
        _blocked = []
    if _blocked:
        warnings.append(
            "§0.2 ASK: %d doorway(s) obstructed by a column - %s. Nobody walks "
            "through that; the drawing clashes or the door is elsewhere. NOT "
            "corrected" % (len(_blocked),
                           "; ".join("%.0f in clear at (%.1f, %.1f)"
                                     % (b["clear_in"], b["at_ft"][0], b["at_ft"][1])
                                     for b in _blocked)))

    # WALL FACE QUALITY (19 Aug 2026): a wall face is straight between its
    # endpoints, so a clean polygon has almost no SHORT steps. Contour-traced
    # walls carried 195 of them on FLOOR PLAN, 92 within 3 ft of a doorway —
    # the staircase left by morphology around each punched door hole, which
    # extruded into a lumpy mass in the wall run. Pinned so it cannot return.
    _wall_quality = None
    try:
        _short = 0
        for _w in walls_poly:
            _o = _w["outer"]
            for _i in range(len(_o)):
                if math.dist(_o[_i - 1], _o[_i]) < 0.35:
                    _short += 1
        _wall_quality = {"polygons": len(walls_poly),
                         "short_step_vertices": _short,
                         "max_outline_points": max((len(w["outer"]) for w in walls_poly),
                                                   default=0),
                         "source": ("pair_rectangles" if _wall_src_rects else "traced_mask")}
        # --- M-1, WALL MATERIAL CROSS-CHECK (19 Aug 2026, Rahul) -----------
        # The model's own material against an INDEPENDENTLY MEASURED drawing
        # quantity: the union of the pair rectangles, each painted between two
        # measured wall faces. Built because the pair-rectangle walls_poly of
        # 19 Aug shipped a GLB of plan-wide stacked sheets carrying 997.1 sqft
        # of material against the rectangles' own 198.9 (5.01x) and EVERY
        # numeric ratchet passed — R-8, R-2, carpet, rooms, doors, footprint
        # and the golden all measure the 2D parse, none measures the model.
        # The traced path reads ~1.9x legitimately: morphology's seal and the
        # unpaired survivors paint beyond the measured faces. Ceiling 2.5.
        from shapely.geometry import Polygon as _Pg
        from shapely.geometry import box as _bx1
        from shapely.ops import unary_union as _uu1
        _rc, _un = wall_rects(struct, ppf)
        _to = lambda X, Y: ((X - x0) / ppf, d_ft - (Y - y0) / ppf)
        _rb = []
        for _a, _b, _c, _e in _rc:
            _p1, _q1 = _to(_a, _b), _to(_c, _e)
            _rb.append(_bx1(min(_p1[0], _q1[0]), min(_p1[1], _q1[1]),
                            max(_p1[0], _q1[0]), max(_p1[1], _q1[1])))
        # DENOMINATOR CORRECTED (19 Aug 2026, Rahul): the pair rectangles UNION
        # the UNPAIRED SURVIVORS at this sheet's own median wall — exactly what
        # `_mask()` paints, so numerator and denominator describe the same
        # object. With pairs alone, BRICK WORK read 3.02 for no fault of the
        # model: 54% of its wall length is unpaired, and every square foot of
        # it was in the numerator and absent from the denominator. Same class
        # as R-8's flats-only basis — comparing two different objects.
        from shapely.geometry import LineString as _LS1
        _mt = (sorted(min(abs(r[2] - r[0]), abs(r[3] - r[1])) for r in _rc)[len(_rc) // 2]
               / ppf) if _rc else 0.5
        for _a, _b, _c, _e in _un:
            _p1, _q1 = _to(_a, _b), _to(_c, _e)
            if math.dist(_p1, _q1) > 0.01:
                _rb.append(_LS1([_p1, _q1]).buffer(_mt / 2.0, cap_style=2,
                                                   join_style=2))
        if wbox_ft is not None:      # walls_poly is cropped to the built wing,
            _wgb = _bx1(*wbox_ft)    # so the denominator must be too
            _rb = [g for g in (r.intersection(_wgb) for r in _rb) if not g.is_empty]
        _meas = _uu1(_rb).area if _rb else 0.0
        _net = 0.0
        for _w in walls_poly:
            _net += _Pg(_w["outer"]).area - sum(_Pg(_h).area for _h in _w["holes"])
        _wall_quality.update({
            "material_sqft": round(_net, 1),
            "measured_pair_sqft": round(_meas, 1),
            "material_ratio": round(_net / _meas, 2) if _meas > 0 else None,
            "material_ratio_max": 2.5})
    except Exception:
        _wall_quality = None

    _doors_sound = None
    try:
        _lf = []
        for _d in drawings:
            if not _is_door_layer(_d["lname"]):
                continue
            _r = _d["rect"]
            _a = ((_r.x0 - x0) / ppf - sx, d_ft - (_r.y0 - y0) / ppf - sy)
            _b = ((_r.x1 - x0) / ppf - sx, d_ft - (_r.y1 - y0) / ppf - sy)
            _w = max(abs(_b[0] - _a[0]), abs(_b[1] - _a[1]))
            if _w >= 1.5:
                _lf.append(((_a[0] + _b[0]) / 2, (_a[1] + _b[1]) / 2, _w))
        _grp = []
        for _p in _lf:
            for _g in _grp:
                if math.hypot(_p[0] - _g[0][0], _p[1] - _g[0][1]) < 3.0:
                    _g.append(_p)
                    break
            else:
                _grp.append([_p])
        _drawn = [(sum(q[0] for q in g) / len(g), sum(q[1] for q in g) / len(g),
                   max(q[2] for q in g)) for g in _grp]
        _tol, _ok, _n, _leafless = 0.35, 0, 0, 0
        for _o in openings:
            if _o.get("type") != "door" or not _o.get("footprint"):
                continue
            _f = _o["footprint"]
            _cx, _cy = (_f[0] + _f[2]) / 2, (_f[1] + _f[3]) / 2
            _cw = max(_f[2] - _f[0], _f[3] - _f[1])
            _n += 1
            if _o.get("gap_ft") is not None:
                # LEAFLESS BRANCH (20 Aug 2026, Rahul). A gap opening has no
                # drawn leaf, so width scoring cannot apply — it would score
                # every one of them unsound and hide a real placement fault
                # behind a metric that simply cannot see it. Score it on what a
                # gap opening DOES have: the cut sits on the drawn gap, it is
                # the gap's own width, and it lies inside the plan.
                _g = _o["gap_ft"]
                if (math.dist((_cx, _cy), (_g[0], _g[1])) <= _tol
                        and abs(_cw - _g[2]) <= _tol
                        and 0.0 <= _cx <= out_w and 0.0 <= _cy <= out_d):
                    _ok += 1
                _leafless += 1
                continue
            if not _drawn:
                _n -= 1
                continue
            _m = min(_drawn, key=lambda t: math.hypot(t[0] - _cx, t[1] - _cy))
            if abs(_cw - _m[2]) <= _tol:
                _ok += 1
        # footprint_poly is still in the UNSHIFTED frame here (the sx/sy
        # re-origin is applied to `scene["footprint_ft"]` later), while the
        # openings above are already shifted — so shift it to match.
        _fpoly = [[p[0] - sx, p[1] - sy] for p in (footprint_poly or [])]
        _pos = door_position_checks(openings, _fpoly, _tol)
        _doors_sound = {"doors": _n, "sound": _ok, "tol_ft": _tol,
                        "position": _pos,
                        "drawn_leaves": len(_drawn), "leafless": _leafless,
                        "rule": "a cut with a DRAWN LEAF is sound when its width "
                                "matches that leaf; a GAP opening has no leaf, so "
                                "it is sound when the cut sits on the drawn gap, "
                                "at the gap's own width, inside the plan"}
    except Exception:
        _doors_sound = None

    if _dim_anchors:
        # the anchors were measured before the wing shift was known, in the raw
        # frame ((X-x0)/ppf, (Y-y0)/ppf). Put them in SCENE feet so the overlay
        # and every consumer share one coordinate system.
        for _a in _dim_anchors["anchors"]:
            for _e in _a["ends"]:
                _e["at_ft"] = [round(_e["at_ft"][0] - sx, 2),
                               round(d_ft - _e["at_ft"][1] - sy, 2)]
                if _e.get("wall_face"):
                    _e["wall_face"] = [[round(q[0] - sx, 2),
                                        round(d_ft - q[1] - sy, 2)]
                                       for q in _e["wall_face"]]
        _dim_anchors["frame"] = "scene_ft"

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
            # canvas instrument: the wall extent, the railing-derived bound
            # that grew it, and the resulting raster (px). Reporting only.
            "doors_placed_sound": _doors_sound,
            # WHICH CODE PATH RAN (22 Aug 2026). Three absolute FLOORS switch
            # branches with no trace in any output, so two similar drawings can
            # be parsed by different code and a run diff can only say "these
            # numbers moved". Read by nothing in the parser.
            "route": dict(_ROUTE),
            "wall_face_quality": _wall_quality,
            "dimension_anchors": _dim_anchors,
            "open_side_regions": _open_sides,
            "blocked_openings": _blocked,
            "canvas": {"wall_extent_ft": [0.0, 0.0, round(w_ft, 2), round(d_ft, 2)],
                       "railing_bound_ft": list(_canvas_ext) if _canvas_ext else None,
                       "raster_px": [W, H],
                       "pads_px": [pad_x, pad_y, pad_r, pad_b]},
            "plot_sqft": _plot_sqft,
            # where the plot came from, or "unknown" — the physics check is
            # BLIND when unknown and says so rather than passing (21 Aug 2026)
            "plot_source": _plot_src,
            # REGISTRATION for the wall overlay (instrument, Phase 0): how to
            # put a scene coordinate (FEET, origin bottom-left) back onto the
            # rendered page. page_px = (x0_pt + (X_ft + shift) * ppf) * dpi/72,
            # y measured down from the top: (y0_pt + (d_ft - (Y_ft + shift)) *
            # ppf). Points are in ROTATED page space, which is what
            # page.get_pixmap() renders. Nothing in the parser reads this.
            "page_registration": {
                "x0_pt": round(float(x0), 3), "y0_pt": round(float(y0), 3),
                "ppf": round(float(ppf), 4), "d_ft": round(float(d_ft), 4),
                "shift_ft": [round(float(sx), 3), round(float(sy), 3)],
                "rotation": int(getattr(page, "rotation", 0) or 0),
                "page_w_pt": round(float(page.rect.width), 2),
                "page_h_pt": round(float(page.rect.height), 2),
            },
            # W-2 MEASUREMENT (not used by the parser): the real distribution
            # of parallel-line gaps on this sheet, so wall classification can
            # be designed against measured clusters, not the 10"/5" assumption
            "wall_line_thicknesses": _gap_dist,
            "rejected_summary": _rej_summary,
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
    # NB: the discard pile itself is NOT put in the scene — 2,500 segments is
    # ~200 KB on every /scene response and every Supabase log. /overlay derives
    # it from the PDF on demand (rejected_lines_ft), which is where it is used.
    if footprint_poly:
        scene["footprint_ft"] = [[round(p[0] - sx, 3), round(p[1] - sy, 3)]
                                 for p in footprint_poly]
    if _railings:
        scene["railings"] = _railings
    if footprint_ext_poly:
        scene["footprint_ext_ft"] = [[round(p[0] - sx, 3), round(p[1] - sy, 3)]
                                     for p in footprint_ext_poly]
    # G3: cross-check a GUESSED scale against snapped-door widths; flag (default)
    # or auto-correct (DRISHTI_AUTOSCALE=1). No-op on verified scales.
    return _apply_scale_correction(scene)
