"""TG-5 — read the sheet's OWN door/window SCHEDULE and let it override every
hardcoded default.

PLAN-READING-RULES TG-5: "The number is a size variant defined in the sheet's
opening schedule when one exists — read that schedule first if present; it
overrides all defaults." Our built-in tables are typical Indian sizes; the
sheet's schedule is THIS building's sizes. Where they disagree, the sheet wins
(§0.1).

Reference sheet — BRICK WORK LAYOUT.pdf, "SCHEDULE OF DOOR & WINDOW":

    SL | NAME | DIMENSION | SILL  | LINTEL
     1 | D    | 3'9"x7'0" | 0'0"  | 7'0"
     ...
     7 | W    | 6'0"x4'6" | 2'6"  | 7'0"      <- our default said 4'0", sill 3'0"

Pure (tokens in, sizes out) so every rule is unit-tested without tesseract.
Token format is area_compare's: {"text", "x0", "y0", "x1", "y1"}.
"""
import re

from area_compare import center_x, text_rows

_FTIN_RE = re.compile(r"^(\d+)['’]\s*(\d+)?[\"”]?$")
_TAG_RE = re.compile(r"^(SD|D\d?|W\d?|V\d?)$")

# a schedule row must name a real opening tag and give plausible sizes
MIN_FT, MAX_FT = 0.0, 12.0


def ft_in(text):
    """`3'9"` -> 3.75 · `0'0"` -> 0.0 · anything else -> None. Pure."""
    m = _FTIN_RE.match((text or "").strip())
    if not m:
        return None
    v = int(m.group(1)) + int(m.group(2) or 0) / 12.0
    return v if MIN_FT <= v <= MAX_FT else None


def normalize_tag(text):
    """OCR doubles a single-glyph name on this sheet ('V' -> 'Vv', 'W' -> 'WwW').
    Upper-case, then collapse runs of the same letter — 'W1' keeps its digit.
    Returns a valid tag or None. Pure."""
    t = (text or "").strip().upper().rstrip(".)")
    if not t:
        return None
    out = [t[0]]
    for ch in t[1:]:
        if not (ch.isalpha() and ch == out[-1]):
            out.append(ch)
    t = "".join(out)
    return t if _TAG_RE.match(t) else None


_COL_WORDS = (("name", "NAME"), ("dimension", "DIMENSION"),
              ("sill", "SILL"), ("lintel", "LINTEL"))


def _columns(hdr):
    """Header row -> {column: x-centre}, using each heading's whole cell."""
    starts = []
    for key, word in _COL_WORDS:
        hit = next((t for t in hdr if word in (t["text"] or "").upper()), None)
        if hit is not None:
            starts.append((hit["x0"], key))
    starts.sort()
    out = {}
    for i, (x0, key) in enumerate(starts):
        nxt = starts[i + 1][0] if i + 1 < len(starts) else float("inf")
        cell = [t for t in hdr if x0 <= t["x0"] < nxt]
        if cell:
            out[key] = (min(t["x0"] for t in cell)
                        + max(t["x1"] for t in cell)) / 2.0
    return out


def parse_opening_schedule(tokens):
    """Tokens (whole sheet) -> {tag: {w_ft, h_ft, sill_ft, head_ft}}, or None
    when the sheet carries no schedule. Only fully-read rows are returned —
    a row missing its width is dropped rather than half-guessed. Pure."""
    return _parse(tokens)[0]


def schedule_region(tokens):
    """Bounding box (x0, y0, x1, y1) of the schedule TABLE, or None.

    The table's DIMENSION column is full of `3'9" X 7'0"` pairs that look
    exactly like printed ROOM dimensions but are door and window sizes. Read
    as room sizes they wreck the scale (BRICK WORK LAYOUT.pdf: the six
    schedule rows voted a scale 4.3x too small). Callers reading room
    dimensions must exclude anything inside this box. Pure."""
    return _parse(tokens)[1]


def _parse(tokens):
    """-> (schedule dict or None, table bbox or None)."""
    rows = text_rows(tokens or [])
    if not rows:
        return None, None
    hdr = hi = None
    for i, row in enumerate(rows):
        up = " ".join((t["text"] or "").upper() for t in row)
        if "NAME" in up and ("DIMENSION" in up or "SILL" in up
                             or "LINTEL" in up):
            hdr, hi = row, i
            break
    if hdr is None:
        return None, None
    col = _columns(hdr)
    if "name" not in col or "dimension" not in col:
        return None, None
    cxs = sorted(col.values())
    pitch = min((b - a for a, b in zip(cxs, cxs[1:])), default=60.0)
    reach = 0.6 * pitch

    def _cell(row, key):
        x = col.get(key)
        if x is None:
            return []
        return [t for t in row if abs(center_x(t) - x) <= reach]

    out, used_rows = {}, [hdr]
    for row in rows[hi + 1:]:
        name = next((normalize_tag(t["text"]) for t in _cell(row, "name")
                     if normalize_tag(t["text"])), None)
        if not name or name in out:
            continue
        # "3'9" X 7'0"" — the X separates width from height. Read the sides
        # POSITIONALLY: if the width is unreadable, the height must never slide
        # into its place (that would report a 4'6" window as 4'6" WIDE). A row
        # we cannot read whole is dropped, never half-guessed.
        cell = _cell(row, "dimension")
        seps = [t for t in cell if (t["text"] or "").strip().upper() in ("X", "×")]
        vals = [(center_x(t), ft_in(t["text"])) for t in cell]
        vals = [(cx, v) for cx, v in vals if v is not None]
        if seps:
            xmid = center_x(seps[0])
            left = [v for cx, v in vals if cx < xmid]
            right = [v for cx, v in vals if cx > xmid]
            if not left or left[0] <= 0:
                continue                   # width missing: drop the row
            rec = {"w_ft": left[0]}
            if right and right[0] > 0:
                rec["h_ft"] = right[0]
        elif len(vals) == 1 and vals[0][1] > 0:
            rec = {"w_ft": vals[0][1]}     # width-only schedule, no separator
        else:
            continue
        sill = [v for v in (ft_in(t["text"]) for t in _cell(row, "sill"))
                if v is not None]
        head = [v for v in (ft_in(t["text"]) for t in _cell(row, "lintel"))
                if v is not None]
        if sill:
            rec["sill_ft"] = sill[0]
        if head and head[0] > 0:
            rec["head_ft"] = head[0]
        # sill + height is the stronger pair when a lintel column is absent
        if "head_ft" not in rec and "h_ft" in rec:
            rec["head_ft"] = rec.get("sill_ft", 0.0) + rec["h_ft"]
        out[name] = rec
        used_rows.append(row)
    if not out:
        return None, None
    # The table's own box: its COLUMNS horizontally (rows come from sheet-wide
    # clustering, so their x-extent would swallow half the drawing) and header
    # top to last data row vertically.
    flat = [t for row in used_rows for t in row
            if min(col.values()) - pitch <= center_x(t) <= max(col.values()) + pitch]
    if not flat:
        return out, None
    region = (min(t["x0"] for t in flat), min(t["y0"] for t in flat),
              max(t["x1"] for t in flat), max(t["y1"] for t in flat))
    return out, region


def window_size(schedule, tag, default):
    """(width_ft, sill_ft, head_ft) for a window/ventilator tag: the sheet's
    schedule if it lists the tag, else `default`. Pure."""
    rec = (schedule or {}).get((tag or "").upper())
    if not rec:
        return default
    w, sill, head = default
    return (rec.get("w_ft", w), rec.get("sill_ft", sill),
            rec.get("head_ft", head))


def door_width(schedule, tag, default):
    """Door leaf width for a tag: the sheet's schedule, else `default`. Pure."""
    rec = (schedule or {}).get((tag or "").upper())
    return rec.get("w_ft", default) if rec else default
