"""R-2 — the room's PRINTED dimensions, read off the sheet and used to check
the room we measured.

PLAN-READING-RULES R-2: "Room name and dimensions are printed inside the room
in most sheets ("bed room 11'-5" X 12'-6""). Read them." Until now we read only
the NAME. The dimension pair is the architect's own statement of that room's
size, so per §0.1 it outranks our measurement: where they disagree, ours is the
number under suspicion.

Additive by contract: this module NEVER changes `area_sqft`. It attaches
`printed_dim_ft`, `printed_area_sqft` and `dim_match_pct` alongside it, so the
measurement and the sheet can be compared instead of one silently replacing
the other.

Pure (tokens in, pairs out) -> unit-tested without tesseract. Token format is
area_compare's: {"text", "x0", "y0", "x1", "y1"}.
"""
import re

from area_compare import text_rows

# "13'6"X10'3"" once the tokens are joined and spaces stripped. Both sides must
# be well-formed: OCR that drops an apostrophe ("13'6"X121"") is unreadable,
# and an unreadable dimension is skipped, never repaired by guesswork.
_PAIR_RE = re.compile(r"(\d{1,2})'(\d{1,2})?\"?[X](\d{1,2})'(\d{1,2})?\"?")

MIN_SIDE_FT, MAX_SIDE_FT = 3.0, 60.0


def _ft(feet, inches):
    """Feet+inches -> feet, or None if the inches are not inches. OCR turns
    `12'1"` into `12'71`, and 71 inches is not a dimension — without this the
    pair reads 17.92 ft and looks perfectly plausible."""
    inch = int(inches or 0)
    if inch > 11:
        return None
    return int(feet) + inch / 12.0


def _chain(tokens, start, max_join):
    """Tokens immediately following `start` on its own line: each must begin
    within ~1.5 glyph-heights of where the previous one ended and share its
    vertical band. Room labels are scattered over the drawing, so adjacency
    has to be LOCAL — grouping by sheet-wide rows chains a room's dimensions
    to unrelated text on the far side of the page.
    ponytail: O(n^2) over a few hundred OCR tokens; fine, revisit if a sheet
    ever carries thousands."""
    h = max(1.0, start["y1"] - start["y0"])
    cy0 = (start["y0"] + start["y1"]) / 2.0
    out = [start]
    while len(out) < max_join:
        last = out[-1]
        nxt = None
        for t in tokens:
            if t is last or t["x0"] < last["x1"] - 0.4 * h:
                continue
            if t["x0"] - last["x1"] > 1.5 * h:
                continue
            if abs((t["y0"] + t["y1"]) / 2.0 - cy0) > 0.8 * h:
                continue
            if nxt is None or t["x0"] < nxt["x0"]:
                nxt = t
        if nxt is None:
            break
        out.append(nxt)
    return out


def dimension_pairs(tokens, max_join=4):
    """Tokens -> [{"w_ft", "h_ft", "x", "y"}], one per printed W x H label.

    OCR splits `13'6" X 10'3"` into three tokens, so each token is joined with
    its local right-hand neighbours before matching. `x`/`y` is the centre of
    the tokens that formed the pair, in the tokens' own units. Pure."""
    toks = sorted(tokens or [], key=lambda t: (t["x0"], t["y0"]))
    out, consumed = [], set()
    for i, t0 in enumerate(toks):
        if i in consumed:
            continue
        chain = _chain(toks, t0, max_join)
        text = ""
        for n, t in enumerate(chain, start=1):
            text += (t["text"] or "")
            m = _PAIR_RE.search(text.upper().replace("×", "X").replace(" ", ""))
            if not m:
                continue
            w, h = _ft(m.group(1), m.group(2)), _ft(m.group(3), m.group(4))
            if w is None or h is None:
                continue
            if not (MIN_SIDE_FT <= w <= MAX_SIDE_FT
                    and MIN_SIDE_FT <= h <= MAX_SIDE_FT):
                continue
            used = chain[:n]
            out.append({"w_ft": round(w, 3), "h_ft": round(h, 3),
                        "x": (min(u["x0"] for u in used)
                              + max(u["x1"] for u in used)) / 2.0,
                        "y": (min(u["y0"] for u in used)
                              + max(u["y1"] for u in used)) / 2.0})
            consumed.update(toks.index(u) for u in used)
            break
    return out


def merge_pairs(*sets, tol=15.0):
    """Union of dimension_pairs() results from several OCR passes.

    The plain pass and the digits-and-quotes re-read fail on DIFFERENT labels
    (on FLOOR PLAN.pdf: 6 only the plain pass reads, 3 only the re-read reads,
    1 both), so the union is strictly better than either. Two pairs at the same
    spot that disagree are BOTH dropped — a conflict between two reads of the
    same label cannot be resolved, and a guess here would poison the check.
    Pure."""
    out = []
    for pairs in sets:
        for p in pairs:
            hit = next((q for q in out
                        if abs(q["x"] - p["x"]) <= tol
                        and abs(q["y"] - p["y"]) <= tol), None)
            if hit is None:
                out.append(dict(p))
            elif (hit["w_ft"], hit["h_ft"]) != (p["w_ft"], p["h_ft"]):
                hit["_conflict"] = True
    return [p for p in out if not p.get("_conflict")]


def match_pct(measured_sqft, printed_sqft):
    """100 = identical, 0 = off by the printed area or worse. Pure."""
    if not printed_sqft:
        return None
    d = abs(float(measured_sqft) - float(printed_sqft)) / float(printed_sqft)
    return round(max(0.0, 100.0 - 100.0 * d), 1)


def attach_printed_dims(rooms, pairs):
    """Give each room the printed dimension label that sits inside it, and
    score our measurement against it.

    `pairs` are dimension_pairs() results carrying an extra "lab" (the room
    component the label falls in) and "fx"/"fy" (position in the rooms' own
    coordinates). A label is used once, by the room it sits in — the nearest
    one wins if a component holds several. area_sqft is NOT touched. Returns
    how many rooms gained a printed dimension. Pure -> unit-tested."""
    used, gained = set(), 0
    for r in rooms:
        best, best_d = None, None
        for k, p in enumerate(pairs):
            if k in used or p.get("lab") != r.get("_lab"):
                continue
            d = (p.get("fx", 0) - r.get("x", 0)) ** 2 \
                + (p.get("fy", 0) - r.get("y", 0)) ** 2
            if best_d is None or d < best_d:
                best_d, best = d, k
        if best is None:
            continue
        used.add(best)
        p = pairs[best]
        printed = round(p["w_ft"] * p["h_ft"], 1)
        r["printed_dim_ft"] = [p["w_ft"], p["h_ft"]]
        r["printed_area_sqft"] = printed
        r["dim_match_pct"] = match_pct(r.get("area_sqft", 0) or 0, printed)
        gained += 1
    return gained


def summary(rooms):
    """Fleet view for the Plan Doctor: how many rooms had a printed dimension
    and how well they matched. None when the sheet printed none. Pure."""
    scored = [r["dim_match_pct"] for r in rooms
              if r.get("dim_match_pct") is not None]
    if not scored:
        return None
    scored.sort()
    return {"rooms_checked": len(scored),
            "median_match_pct": scored[len(scored) // 2],
            "worst_match_pct": scored[0],
            "rooms_off": sum(1 for v in scored if v < 80.0)}
