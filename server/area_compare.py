"""R-8 — read the sheet's OWN printed AREA STATEMENT and compare it with what
we parsed.

Why this exists (PLAN-READING-RULES §0.1 + R-8): where a sheet prints its own
areas, those are GROUND TRUTH. A parsed number that contradicts them is wrong
until proven otherwise, and the comparison is the single strongest accuracy
signal available — stronger than any geometric self-check, because it comes
from the architect.

Both functions here are PURE (no OCR, no I/O, no PDF), so every rule is unit-
tested with synthetic tokens and the test suite never needs tesseract. The
caller (pdf_vector) supplies tokens from whatever text source it has; on real
Indian CAD sheets that is OCR, because the text is outlined line-art and
page.get_text() returns nothing (FLOOR PLAN.pdf: 24 live words, all of them
"PRODUCED BY AN AUTODESK EDUCATIONAL PRODUCT").

Token format (unit-agnostic — points, pixels, feet all work):
    {"text": str, "x0": float, "y0": float, "x1": float, "y1": float}
"""
import re

# a printed area figure: 2-6 digits, optional thousands commas ("3,371")
_NUM_RE = re.compile(r"^([\d][\d,]{1,6})(?:\.\d+)?$")
_FLAT_RE = re.compile(r"^FLAT[-\s]*(\d+)", re.IGNORECASE)

MIN_SQFT, MAX_SQFT = 20.0, 200000.0   # a printed area outside this is not one
_TABLE_ROWS_SPAN = 8                  # accept rows within N row-heights of the
                                      # header — keeps in-plan text ("FLAT-1
                                      # B.U.A- 870 SFT", printed on the drawing
                                      # itself) out of the table


def _val(text):
    """'3,371' -> 3371.0 · '870' -> 870.0 · anything else -> None."""
    m = _NUM_RE.match((text or "").strip())
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return v if MIN_SQFT <= v <= MAX_SQFT else None


def _cx(t):
    return (t["x0"] + t["x1"]) / 2.0


def _cy(t):
    return (t["y0"] + t["y1"]) / 2.0


def _rows(tokens):
    """Group tokens into visual rows by y, left-to-right. Pure."""
    if not tokens:
        return []
    heights = sorted(abs(t["y1"] - t["y0"]) for t in tokens)
    h = heights[len(heights) // 2] or 1.0
    out, cur = [], []
    for t in sorted(tokens, key=_cy):
        if cur and _cy(t) - _cy(cur[-1]) > 0.6 * h:
            out.append(sorted(cur, key=_cx))
            cur = []
        cur.append(t)
    out.append(sorted(cur, key=_cx))
    return out


def _has(row, *words):
    """Row contains every word (substring, case-insensitive)."""
    joined = " ".join((t["text"] or "").upper() for t in row)
    return all(w in joined for w in words)


_COL_WORDS = (("label", "FLAT"), ("built_up", "BUILT"),
              ("carpet", "CARPET"), ("common", "COMMON"))


def _columns(hdr):
    """Header row -> {column: x-centre}. A heading is a PHRASE ("COMMON AREA
    (EACH FLOOR)"), so the centre must come from the whole cell, not from the
    keyword token — otherwise a value sitting under a wide heading is matched
    to the wrong column, or to none."""
    starts = []
    for name, word in _COL_WORDS:
        hit = next((t for t in hdr if word in (t["text"] or "").upper()), None)
        if hit is not None:
            starts.append((hit["x0"], name))
    starts.sort()
    out = {}
    for i, (x0, name) in enumerate(starts):
        nxt = starts[i + 1][0] if i + 1 < len(starts) else float("inf")
        cell = [t for t in hdr if x0 <= t["x0"] < nxt]
        if cell:
            out[name] = (min(t["x0"] for t in cell)
                         + max(t["x1"] for t in cell)) / 2.0
    return out


def parse_area_statement(tokens):
    """Tokens (whole sheet) -> the printed area statement, or None if the sheet
    carries no such table. Pure.

    Returns:
      {"plot_area_sqft", "stilt_area_sqft", "common_area_sqft",
       "flats": [{"name", "built_up_sqft", "carpet_sqft"}],
       "built_up_total_sqft", "carpet_total_sqft"}
    Keys whose figure is not printed are omitted, never guessed.
    """
    rows = _rows(tokens or [])
    if not rows:
        return None
    # the header row defines the columns; without it there is no table
    hdr = hi = None
    for i, row in enumerate(rows):
        if _has(row, "BUILT", "CARPET") or _has(row, "BUILT UP", "CARPET"):
            hdr, hi = row, i
            break
    if hdr is None:
        return None
    cols = _columns(hdr)
    col = {k: cols.get(k) for k in ("built_up", "carpet", "common")}
    if col["built_up"] is None or col["carpet"] is None:
        return None
    heights = sorted(abs(t["y1"] - t["y0"]) for t in tokens)
    rh = heights[len(heights) // 2] or 1.0
    y_lo = _cy(hdr[0]) - _TABLE_ROWS_SPAN * rh * 2
    y_hi = _cy(hdr[0]) + _TABLE_ROWS_SPAN * rh * 2
    # x-span of the table: the header row's own extent, widened left to reach
    # the LABEL column ("FLAT-1 (2-BHK)" starts left of the "FLAT NO.S"
    # heading). Without the left margin the label falls outside the table and
    # the flat rows are never recognised.
    xs = [v for v in col.values() if v is not None]
    x_lo = min([t["x0"] for t in hdr] + xs) - 20 * rh
    x_hi = max([t["x1"] for t in hdr] + xs) + 12 * rh

    def _in_table(t):
        return y_lo <= _cy(t) <= y_hi and x_lo <= _cx(t) <= x_hi

    # a value belongs to the nearest column within HALF the column pitch —
    # derived from the header itself, so it holds at any sheet scale
    _cxs = sorted(v for v in col.values() if v is not None)
    _pitch = min((b - a for a, b in zip(_cxs, _cxs[1:])), default=12.0 * rh)
    _reach = max(0.5 * _pitch, 3.0 * rh)

    def _nearest(t):
        """Which column does this number sit under? None if it sits under none."""
        best, bd = None, _reach
        for name, x in col.items():
            if x is None:
                continue
            if abs(_cx(t) - x) < bd:
                bd, best = abs(_cx(t) - x), name
        return best

    out = {"flats": []}
    for i, row in enumerate(rows):
        cells = [t for t in row if _in_table(t)]
        if not cells:
            continue
        label = " ".join((t["text"] or "").upper() for t in cells)
        nums = [(t, _val(t["text"])) for t in cells]
        nums = [(t, v) for t, v in nums if v is not None]
        if not nums:
            continue
        # plain label rows: PLOT AREA | 3371   ·   STILT FLOOR | 1900
        if "PLOT" in label and "plot_area_sqft" not in out:
            out["plot_area_sqft"] = nums[0][1]
            continue
        # "SILT" too: OCR drops the T on this sheet's STILT FLOOR row
        if ("STILT" in label or "SILT" in label) and "stilt_area_sqft" not in out:
            out["stilt_area_sqft"] = nums[0][1]
            continue
        # flat rows: FLAT-1 (2-BHK) | 870 | 680 | (246)
        m = None
        for t in cells:
            m = _FLAT_RE.match((t["text"] or "").strip())
            if m:
                break
        if m and i != hi:
            flat = {"name": f"FLAT-{m.group(1)}"}
            for t, v in nums:
                c = _nearest(t)
                if c == "built_up":
                    flat.setdefault("built_up_sqft", v)
                elif c == "carpet":
                    flat.setdefault("carpet_sqft", v)
                elif c == "common":
                    out.setdefault("common_area_sqft", v)
            if len(flat) > 1:
                out["flats"].append(flat)
            continue
        # the common-area cell often spans both flat rows, so it lands on a
        # row of its own — pick it up wherever it sits under that column
        if "common_area_sqft" not in out and col["common"] is not None:
            for t, v in nums:
                if _nearest(t) == "common":
                    out["common_area_sqft"] = v
                    break

    bu = [f["built_up_sqft"] for f in out["flats"] if "built_up_sqft" in f]
    cp = [f["carpet_sqft"] for f in out["flats"] if "carpet_sqft" in f]
    if bu:
        out["built_up_total_sqft"] = round(sum(bu), 1)
    if cp:
        out["carpet_total_sqft"] = round(sum(cp), 1)
    if not out["flats"] and "plot_area_sqft" not in out:
        return None                       # header matched but nothing readable
    return out


# a parse within MATCH_PCT of the sheet is confirmed; beyond MISMATCH_PCT the
# parse contradicts the architect and R-8/§0.1 say the parse is wrong
MATCH_PCT = 5.0
MISMATCH_PCT = 15.0


def compare(printed, statement):
    """printed: parse_area_statement() output · statement:
    area_statement.compute_area_statement() output.
    -> comparison block, or None when there is nothing comparable. Pure."""
    if not printed or not statement:
        return None
    pairs = (
        ("built_up", "Built-up", printed.get("built_up_total_sqft"),
         (statement.get("built_up_area") or {}).get("sqft")),
        ("carpet", "Carpet", printed.get("carpet_total_sqft"),
         (statement.get("carpet_area") or {}).get("sqft")),
    )
    rows = []
    for key, label, p, q in pairs:
        if not p or q is None:
            continue
        p, q = float(p), float(q)
        rows.append({
            "figure": key, "label": label,
            "printed_sqft": round(p, 1), "parsed_sqft": round(q, 1),
            "diff_pct": round(100.0 * (q - p) / p, 1),
            "match_pct": round(max(0.0, 100.0 - abs(100.0 * (q - p) / p)), 1),
        })
    if not rows:
        return None
    worst = max(abs(r["diff_pct"]) for r in rows)
    return {
        "rows": rows,
        "printed": printed,
        "worst_diff_pct": worst,
        "verdict": ("match" if worst <= MATCH_PCT
                    else "close" if worst <= MISMATCH_PCT else "mismatch"),
    }
