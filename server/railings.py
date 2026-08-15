"""B-2a — the RAILING TRACER: thin double lines followed as connected runs.

PLAN-READING-RULES §10/B-2a (ruling 14 Aug 2026): a balcony's edge is not
classified per edge. The thin double line is FOLLOWED as a run, turning where
it turns, exactly as a wall is followed. If the run rejoins the building wall
at both ends it is railing on 3 sides; if it only spans the front, 1 side. The
shape comes from the trace, so a balcony END is never detected separately —
it is part of one run. That dissolves the problem that killed every per-edge
rule: a 3.8 ft end is indistinguishable from a plot-boundary stroke on its own,
and identical inside a run.

Dash-dot runs are removed FIRST. Measured on FLOOR PLAN: the plot boundary is
**11 collinear strokes of 6.3-6.7 ft at a constant 3.1 ft pitch**, while every
railing is a **single unbroken stroke** per line. That is a structural property
of how the two things are drawn, not a tuned threshold — and it is the only
test that survived, after length (zero margin at 3.8 ft) and the third-line
test (poisoned by the boundary running 0.5 in alongside) both failed.

Everything here is PURE (lines in feet -> runs in feet).
"""
import math

RAIL_MIN_IN, RAIL_MAX_IN = 0.8, 3.2      # 2-3 in steel; drafting varies
MIN_STROKE_FT = 1.5
JOIN_TOL_FT = 0.75                        # ends of one run meet within this
WALL_TOL_FT = 0.6                         # "meets the building wall"
DASH_MIN_STROKES = 3                      # a dash pattern needs a pattern
DASH_PITCH_CV = 0.25                      # regular gaps = dash-dot, not railing
# Collinearity window for grouping a dash family. MUST be tighter than the
# distance between a railing and a boundary running beside it: on FLOOR PLAN
# flat-1's balcony end sits at y = 0.08 and the plot boundary at y = 0.00, so a
# 0.2 ft window grouped them and the filter deleted the railing with the dashes.
DASH_COLLINEAR_FT = 0.05


def _orient(a, b):
    if abs(b[1] - a[1]) < 0.08:
        return "h"
    if abs(b[0] - a[0]) < 0.08:
        return "v"
    return "d"


def thin_centrelines(lines, min_in=RAIL_MIN_IN, max_in=RAIL_MAX_IN,
                     min_len_ft=MIN_STROKE_FT):
    """[(A, B)] in feet -> centreline strokes of every THIN parallel pair.

    A railing is drawn as two lines a few inches apart; the thing that gets
    traced is the line between them. Pure."""
    out = []
    for group, ax in ((["h"], 1), (["v"], 0)):
        runs = [l for l in lines if _orient(l[0], l[1]) in group]
        runs.sort(key=lambda l: l[0][ax])
        for i in range(len(runs)):
            for j in range(i + 1, len(runs)):
                gap_in = (runs[j][0][ax] - runs[i][0][ax]) * 12.0
                if gap_in > max_in:
                    break
                if gap_in < min_in:
                    continue
                a, b = runs[i], runs[j]
                lo = max(min(a[0][1 - ax], a[1][1 - ax]),
                         min(b[0][1 - ax], b[1][1 - ax]))
                hi = min(max(a[0][1 - ax], a[1][1 - ax]),
                         max(b[0][1 - ax], b[1][1 - ax]))
                if hi - lo < min_len_ft:
                    continue
                mid = (a[0][ax] + b[0][ax]) / 2.0
                P = (lo, mid) if ax == 1 else (mid, lo)
                Q = (hi, mid) if ax == 1 else (mid, hi)
                out.append((P, Q, round(gap_in, 2)))
                break
    return out


def drop_dash_dot(strokes, min_strokes=DASH_MIN_STROKES, cv=DASH_PITCH_CV,
                  collinear_ft=DASH_COLLINEAR_FT):
    """Remove collinear families drawn at a REGULAR pitch — the plot boundary.

    Must run BEFORE tracing: on FLOOR PLAN a boundary stroke sits 0.5 in from
    flat-1's balcony end, so tracing first welds them into a bogus 30.8 ft run
    spanning two different things. Pure."""
    kept, dropped = [], []
    used = set()
    for i, s in enumerate(strokes):
        if i in used:
            continue
        ax = 1 if _orient(s[0], s[1]) == "h" else 0
        perp = s[0][ax]
        fam = [(j, t) for j, t in enumerate(strokes)
               if _orient(t[0], t[1]) == _orient(s[0], s[1])
               and abs(t[0][ax] - perp) < collinear_ft]
        if len(fam) < min_strokes:
            continue
        fam.sort(key=lambda jt: min(jt[1][0][1 - ax], jt[1][1][1 - ax]))
        gaps = []
        for k in range(len(fam) - 1):
            end = max(fam[k][1][0][1 - ax], fam[k][1][1][1 - ax])
            nxt = min(fam[k + 1][1][0][1 - ax], fam[k + 1][1][1][1 - ax])
            gaps.append(nxt - end)
        gaps = [g for g in gaps if g > 0.05]
        if len(gaps) < min_strokes - 1:
            continue
        mean = sum(gaps) / len(gaps)
        var = sum((g - mean) ** 2 for g in gaps) / len(gaps)
        if mean > 0 and (var ** 0.5) / mean <= cv:
            for j, _t in fam:
                used.add(j)
                dropped.append(j)
    kept = [s for i, s in enumerate(strokes) if i not in used]
    return kept, len(dropped)


def dedupe_edges(strokes, perp_ft=0.15, overlap_frac=0.8):
    """One physical edge drawn with THREE lines yields two overlapping
    centrelines. On FLOOR PLAN flat-1's balcony end appears at y = 0.08 and
    y = 0.11 — 0.36 in apart, same 3.84 ft span — and would be counted twice,
    turning a 20.66 ft run into 24.48. Same edge, one stroke. Pure."""
    out = []
    for s in strokes:
        ax = 1 if _orient(s[0], s[1]) == "h" else 0
        lo, hi = sorted((s[0][1 - ax], s[1][1 - ax]))
        dup = False
        for t in out:
            if _orient(t[0], t[1]) != _orient(s[0], s[1]):
                continue
            if abs(t[0][ax] - s[0][ax]) > perp_ft:
                continue
            tlo, thi = sorted((t[0][1 - ax], t[1][1 - ax]))
            ov = min(hi, thi) - max(lo, tlo)
            if ov > overlap_frac * min(hi - lo, thi - tlo):
                dup = True
                break
        if not dup:
            out.append(s)
    return out


def _length(s):
    return math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1])


def trace_runs(strokes, join_tol=JOIN_TOL_FT):
    """Connect strokes whose ends meet into RUNS, following turns. Pure."""
    parent = list(range(len(strokes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(strokes)):
        for j in range(i + 1, len(strokes)):
            for P in strokes[i][:2]:
                for Q in strokes[j][:2]:
                    if math.hypot(P[0] - Q[0], P[1] - Q[1]) <= join_tol:
                        parent[find(i)] = find(j)
    runs = {}
    for k, s in enumerate(strokes):
        runs.setdefault(find(k), []).append(s)
    return list(runs.values())


def describe_run(run, wall_lines, join_tol=JOIN_TOL_FT, wall_tol=WALL_TOL_FT):
    """A traced run -> its shape and its verdict. Pure."""
    total = sum(_length(s) for s in run)
    turns = 0
    for i in range(len(run)):
        for j in range(i + 1, len(run)):
            if _orient(run[i][0], run[i][1]) == _orient(run[j][0], run[j][1]):
                continue
            for P in run[i][:2]:
                for Q in run[j][:2]:
                    if math.hypot(P[0] - Q[0], P[1] - Q[1]) <= join_tol:
                        turns += 1
    open_ends = []
    for s in run:
        for P in s[:2]:
            shared = any(math.hypot(P[0] - Q[0], P[1] - Q[1]) <= join_tol
                         for t in run if t is not s for Q in t[:2])
            if not shared:
                open_ends.append(P)

    def on_wall(P):
        for A, B in wall_lines:
            dx, dy = B[0] - A[0], B[1] - A[1]
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((P[0] - A[0]) * dx
                                                       + (P[1] - A[1]) * dy) / L2))
            if math.hypot(P[0] - (A[0] + t * dx), P[1] - (A[1] + t * dy)) <= wall_tol:
                return True
        return False

    anchored = sum(1 for P in open_ends if on_wall(P))
    sides = len(run)
    poly = [[round(p[0], 2), round(p[1], 2)] for s in run for p in s[:2]]
    return {
        "depth_ft": enclosed_depth_ft({"polyline_ft": poly}, wall_lines),
        "pocket_ft": pocket_ft({"polyline_ft": poly}, wall_lines),
        "length_ft": round(total, 2),
        "turns": turns,
        "segments": sides,
        "open_ends": len(open_ends),
        "ends_on_wall": anchored,
        "verdict": ("3-sided" if turns >= 2 and anchored >= 2
                    else "1-sided" if sides == 1
                    else "partial"),
        "polyline_ft": [[round(p[0], 2), round(p[1], 2)]
                        for s in run for p in s[:2]],
    }


def trace(lines, wall_lines, **kw):
    """Full pass: thin pairs -> drop dash-dot -> trace -> describe. Pure."""
    strokes = thin_centrelines(lines)
    strokes, n_dash = drop_dash_dot(strokes)
    strokes = dedupe_edges(strokes)
    runs = [describe_run(r, wall_lines) for r in trace_runs(strokes)]
    runs = [r for r in runs if r["length_ft"] >= 3.0]
    runs.sort(key=lambda r: -r["length_ft"])
    return {"runs": runs, "dash_dot_strokes_dropped": n_dash}


DEPTH_TOL_FT = 0.25          # measured error against printed: 0.08 and 0.13 ft


def _straight_depth_ft(run, wall_lines, min_ft=1.0, max_ft=12.0):
    """Depth of a ONE-SIDED balcony: railing to the wall behind it.

    A straight run encloses nothing by itself — its bbox short side is 0.00,
    which is why every 0-turn run scored a depth of zero and could never match
    a printed width. The space is between the railing and the building, so the
    depth is the perpendicular distance to the nearest PARALLEL wall that the
    run actually runs alongside (>= half its length of overlap). Pure."""
    pts = run.get("polyline_ft") or []
    if len(pts) < 2:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    horiz = (max(xs) - min(xs)) >= (max(ys) - min(ys))
    ax = 1 if horiz else 0                       # the perpendicular axis
    perp = (min(ys) + max(ys)) / 2 if horiz else (min(xs) + max(xs)) / 2
    lo, hi = (min(xs), max(xs)) if horiz else (min(ys), max(ys))
    need = 0.5 * (hi - lo)
    best = None
    for A, B in wall_lines or []:
        if horiz and abs(B[1] - A[1]) > 0.08:
            continue
        if not horiz and abs(B[0] - A[0]) > 0.08:
            continue
        wp = (A[1] + B[1]) / 2 if horiz else (A[0] + B[0]) / 2
        wlo, whi = sorted((A[1 - ax], B[1 - ax]))
        if min(hi, whi) - max(lo, wlo) < need:
            continue
        d = abs(wp - perp)
        if min_ft <= d <= max_ft and (best is None or d < best[0]):
            best = (d, wp)
    return best                      # (depth_ft, wall's perpendicular coord)


def pocket_ft(run, wall_lines=None):
    """The rectangle a run encloses, in feet: [x0, y0, x1, y1].

    A turning run encloses its own bbox. A ONE-SIDED run encloses nothing by
    itself — the space is the strip between it and the wall behind — so the
    bbox is extended to that wall. Pure."""
    pts = run.get("polyline_ft") or []
    if len(pts) < 2:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if min(x1 - x0, y1 - y0) >= 0.5:
        return [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]
    got = _straight_depth_ft(run, wall_lines)
    if not got:
        return None
    _d, wp = got
    if (x1 - x0) >= (y1 - y0):                      # horizontal run
        y0, y1 = min(y0, wp), max(y1, wp)
    else:
        x0, x1 = min(x0, wp), max(x1, wp)
    return [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]


def enclosed_depth_ft(run, wall_lines=None):
    """The SHORT side of the space a 3-sided run encloses against its wall.

    A balcony is a strip: the sheet prints its WIDTH, and that width is this
    depth. Measured on FLOOR PLAN: 3.92 ft against a printed 4'0", 3.37 ft
    against a printed 3'6". Pure."""
    pts = [p for s in run["polyline_ft"] for p in ((s,) if isinstance(s[0], (int, float)) else s)] \
        if run.get("polyline_ft") else []
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    d = round(min(max(xs) - min(xs), max(ys) - min(ys)), 2)
    if d >= 0.5:                       # a run that turns encloses its own bbox
        return d
    got = _straight_depth_ft(run, wall_lines)    # 1-sided: measure to the wall
    return round(got[0], 2) if got else None


def classify(run, printed_widths_ft, tol=DEPTH_TOL_FT):
    """railing | unclassified. Three tests, all from the DRAWING:

    ends on the building wall (>=2), turns (>=1), and — the one that kills the
    false positive — its enclosed depth must match a width the sheet PRINTS.
    FLOOR PLAN's 12.33 ft run at (25.58, 24.06) passes the first two and
    encloses 4.91 ft, which matches neither printed 4'0" nor 3'6": it is the
    lobby drafting error, not a balcony. Pure."""
    # NO TURN REQUIRED (15 Aug 2026). §10/B-2a defines a ONE-SIDED balcony —
    # railing across the front only — and the code was rejecting the case its
    # own spec describes: 47 of 50 runs on neelachala FIRST FLOOR and 38 of 38
    # on GHATIKIA have zero turns, so those sheets could never report a
    # balcony however good the anchor got. Continuity still matters (it is what
    # makes the run one thing), but the DEPTH test below is what keeps false
    # positives out, and it uses the sheet's own printed widths.
    if run["ends_on_wall"] < 2:
        return "unclassified"
    d = run.get("depth_ft") if run.get("depth_ft") is not None \
        else enclosed_depth_ft(run)
    if d is None or not printed_widths_ft:
        return "unclassified"
    return "railing" if any(abs(d - w) <= tol for w in printed_widths_ft) \
        else "unclassified"
