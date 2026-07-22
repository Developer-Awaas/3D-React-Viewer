"""Door/window TEXT-TAG reader — plans that mark openings with schedule tags
(D, D1, D2, D3, SD for doors; W, W1, W2, V for windows/ventilators) instead of
symbols or layers. Very common on Indian residential sheets (the user's Zenith
brick-work decode is the reference).

Pure core (detect_tag_openings) so every rule is unit-tested; pdf_vector calls
it ADDITIVELY: tags only add openings where none was already found nearby, so
existing detection can't get worse.

Default sizes come from the Zenith schedule (typical Indian practice):
  D 3'9" | D1 3'3" | D2 3'0" | D3 2'6" | SD 7'0"  (all lintel 7'0", sill 0)
  W 6'0" | W1 5'0" | W2 4'0" | W3 3'0"  sill 2'6", head 7'0"
  V 2'0"           sill 5'0", head 7'0"
"""
import math
import re

_TAG_RE = re.compile(r"^(SD|D\d?|W\d?|V\d?)$", re.IGNORECASE)

DOOR_W_FT = {"D": 3.75, "D1": 3.25, "D2": 3.0, "D3": 2.5, "D4": 2.5, "SD": 7.0}
WIN_FT = {  # tag -> (width_ft, sill_ft, head_ft)
    "W": (6.0, 2.5, 7.0), "W1": (5.0, 2.5, 7.0), "W2": (4.0, 2.5, 7.0),
    "W3": (3.0, 2.5, 7.0), "V": (2.0, 5.0, 7.0), "V1": (2.0, 5.0, 7.0),
}
DOOR_HEAD_FT = 7.0
_THICK = 0.6          # opening footprint thickness across the wall, ft


def classify_tag(text):
    """Token text -> ('door'|'window', tag) or None. Pure."""
    t = (text or "").strip().upper().rstrip(".")
    if not _TAG_RE.match(t):
        return None
    if t.startswith(("D", "SD")):
        return ("door", t) if t in DOOR_W_FT or t.startswith("D") else None
    return ("window", t)


def _nearest_on_seg(px, py, seg):
    x0, y0, x1, y1 = seg
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 <= 0:
        return None
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    qx, qy = x0 + t * dx, y0 + t * dy
    return math.hypot(px - qx, py - qy), qx, qy, dx, dy


def detect_tag_openings(tokens, wall_segs, existing_centers,
                        max_wall_dist=4.0, dedupe_dist=3.0):
    """tokens: [(x_ft, y_ft, text)] · wall_segs: [(x0,y0,x1,y1)] ft ·
    existing_centers: [(x_ft, y_ft)] of already-detected openings.
    Returns opening dicts {type, tag, footprint[x0,y0,x1,y1], z[lo,hi]} placed on
    the nearest wall. A tag is skipped if an opening already exists within
    dedupe_dist (additive-only guarantee) or no wall is near enough."""
    out = []
    placed = list(existing_centers)
    for px, py, text in tokens:
        cls = classify_tag(text)
        if not cls:
            continue
        kind, tag = cls
        best = None
        for seg in wall_segs:
            hit = _nearest_on_seg(px, py, seg)
            if hit and (best is None or hit[0] < best[0]):
                best = hit
        if best is None or best[0] > max_wall_dist:
            continue
        _, qx, qy, dx, dy = best
        if any(math.hypot(qx - ex, qy - ey) <= dedupe_dist for ex, ey in placed):
            continue
        if kind == "door":
            w = DOOR_W_FT.get(tag, 3.0)
            z = [0.0, DOOR_HEAD_FT]
        else:
            w, sill, head = WIN_FT.get(tag, (4.0, 2.5, 7.0))
            z = [sill, head]
        horiz = abs(dx) >= abs(dy)          # wall runs along X?
        if horiz:
            fp = [qx - w / 2, qy - _THICK / 2, qx + w / 2, qy + _THICK / 2]
        else:
            fp = [qx - _THICK / 2, qy - w / 2, qx + _THICK / 2, qy + w / 2]
        out.append({"type": kind, "tag": tag,
                    "footprint": [round(v, 3) for v in fp],
                    "z": z, "snapped": True, "from_tag": True})
        placed.append((qx, qy))
    return out
