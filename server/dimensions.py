"""§10.2 — DIMENSION ANCHORS: the fourth instrument (D-7).

A printed dimension is a POINTER (§10.2 D-1..D-3). It is pulled perpendicular
from the edge it measures, and its arrowhead lands on a REAL edge — the inner
face of a wall for an inner-face dimension, the outer line for an external
wall-to-wall one. So the drawing states where its own edges are, and we can
check our parse against that statement instead of against ourselves:

    IF AN ARROW LANDS WHERE NO WALL WAS DETECTED, THE PARSE IS WRONG.

R-8 needs a printed area statement, R-2 needs printed room dimensions, and the
balcony check needs a printed width. This one needs only that the sheet is
dimensioned at all — which is why it reaches BRICK WORK, blind on all three.

Two routes, because sheets differ (measured 15 Aug 2026):
  LAYER  — a `dim`/`dimension` layer exists. Its long lines are the dimension
           lines; the short perpendicular lines touching their ends are the
           EXTENSION lines, and the far end of an extension is the edge (D-2).
           Glyph strokes from dead text share the layer but are an order of
           magnitude shorter, so length alone separates them: FLOOR PLAN
           carries 38 dimension lines among 8,534 glyph strokes.
  TEXT   — no dim layer. A dimension label anchors the nearest long line.

Everything here is PURE (feet in -> anchors in feet out).
"""
import math
import re

EXT_MAX_FT = 1.0             # an extension line is short; a dimension line is not
EXT_MIN_FT = 0.1             # below this it is a glyph stroke, not geometry
TOUCH_FT = 0.4               # extension line meets the dimension line's end
NEAR_TEXT_FT = 6.0           # a label sits beside the line it belongs to
HIT_FT = 0.5                 # "lands on a detected face" — the instrument's bar

_FT_IN = re.compile(r"^(\d{1,3})'-?(\d{1,2})?\"?$")
_METRIC = re.compile(r"^(\d{1,2}\.\d{1,2})$")


def parse_value_ft(text):
    """`12'6"`, `11'-5"`, `3.43` (metres) -> feet. None if it is not a
    dimension. Pure."""
    t = (text or "").strip().upper().replace("’", "'").replace("”", '"')
    m = _FT_IN.match(t)
    if m:
        return round(int(m.group(1)) + (int(m.group(2)) if m.group(2) else 0) / 12.0, 3)
    m = _METRIC.match(t)
    if m:
        return round(float(m.group(1)) * 3.28084, 3)
    return None


def _len(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _horiz(a, b):
    return abs(b[0] - a[0]) > abs(b[1] - a[1])


def dist_to_walls(p, wall_lines):
    """Distance in feet from a point to the nearest wall face, and the face.
    Pure."""
    best, seg = None, None
    for A, B in wall_lines or []:
        dx, dy = B[0] - A[0], B[1] - A[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - A[0]) * dx
                                                   + (p[1] - A[1]) * dy) / L2))
        d = math.hypot(p[0] - (A[0] + t * dx), p[1] - (A[1] + t * dy))
        if best is None or d < best:
            best, seg = d, (A, B)
    return (round(best, 2), seg) if best is not None else (None, None)


def follow_extension(end, a, b, short_lines, touch_ft=TOUCH_FT):
    """D-2: from a dimension line's END, follow the EXTENSION line back to the
    edge and return that edge point.

    The dimension line is offset from the building, so its own endpoint is NOT
    on the edge — the extension line is what reaches it. Returns None when no
    extension is attached, and the caller falls back to the endpoint. Pure."""
    hd = _horiz(a, b)
    for c, d in short_lines or []:
        if _horiz(c, d) == hd:                   # must be PERPENDICULAR
            continue
        dc, dd = _len(c, end), _len(d, end)
        if min(dc, dd) > touch_ft:
            continue
        return d if dc < dd else c               # the FAR end is the edge
    return None


def anchors(dim_lines, short_lines, texts, wall_lines, hit_ft=HIT_FT,
            require_value=True):
    """[(A, B)] dimension lines -> one anchor record each. Pure.

    `texts` is [(value_ft, (x, y))]; the nearest label within NEAR_TEXT_FT of a
    dimension line's midpoint gives its value.

    `require_value` (D-3): a dimension STATES a number, so a candidate line
    carrying none is not a dimension. This is what separates real dimensions
    from TITLE-BLOCK ARTWORK sharing the `dim` layer — measured 16 Aug on
    FLOOR PLAN, where all 29 arrows landing on nothing were the area-statement
    table (8), the sheet frame (8), the ARCHITRAVE logo (12) and one leader
    line, and every one of them is valueless."""
    out = []
    dropped = 0
    for a, b in dim_lines or []:
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        val, vd = None, NEAR_TEXT_FT
        for v, c in texts or []:
            d = math.hypot(mid[0] - c[0], mid[1] - c[1])
            if d < vd:
                val, vd = v, d
        if require_value and val is None:
            dropped += 1                       # sheet furniture, not a dimension
            continue
        rec = {"value_ft": val, "span_ft": round(_len(a, b), 2), "ends": []}
        for end in (a, b):
            pt = follow_extension(end, a, b, short_lines) or end
            d, seg = dist_to_walls(pt, wall_lines)
            rec["ends"].append({
                "at_ft": [round(pt[0], 2), round(pt[1], 2)],
                "via_extension": follow_extension(end, a, b, short_lines) is not None,
                "wall_dist_ft": d,
                "wall_face": [[round(v, 2) for v in seg[0]],
                              [round(v, 2) for v in seg[1]]] if seg else None})
        out.append(rec)
    ends = [e for r in out for e in r["ends"] if e["wall_dist_ft"] is not None]
    hits = sum(1 for e in ends if e["wall_dist_ft"] <= hit_ft)
    return {"anchors": out,
            "summary": {"dimensions": len(out),
                        "candidates": len(dim_lines or []),
                        "dropped_no_value": dropped,
                        "endpoints": len(ends),
                        "within_0_5_ft": hits,
                        "pct_on_a_detected_face": round(100.0 * hits / len(ends), 1)
                        if ends else None,
                        "via_extension_line": sum(1 for e in ends
                                                  if e["via_extension"]),
                        "valued": sum(1 for r in out if r["value_ft"] is not None)}}
