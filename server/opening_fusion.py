"""G5 cross-reader opening fusion.

best-of arbitration picks ONE reader's scene and discards the other's doors/
windows entirely. But both readers parse the SAME image at the SAME width, so
they share one feet coordinate frame. This module ADDS to the winner any door/
window the other reader(s) found that (a) isn't already present and (b) sits on
a wall the winner also detected — so a door found by either model survives,
without importing conflicting wall geometry.

Pure functions -> unit-tested. ML path only (needs axis-aligned `walls`; the
vector path has walls_poly and its own opening extraction, so fusion no-ops).
"""


def _centroid(o, walls_by_id):
    """(cx, cy, axis, width_ft) of an opening from its wall + along span, or
    None if the wall is missing. Both readers share the feet frame, so these
    centroids are directly comparable across scenes."""
    w = walls_by_id.get(o.get("wall"))
    al = o.get("along")
    if not w or not al or "axis" not in w or len(al) < 2:
        return None
    a0, a1 = float(al[0]), float(al[1])
    mid, width = (a0 + a1) / 2.0, abs(a1 - a0)
    if w["axis"] == "x":
        return mid, (float(w["y0"]) + float(w["y1"])) / 2.0, "x", width
    return (float(w["x0"]) + float(w["x1"])) / 2.0, mid, "y", width


MIN_OPENING_FT = 0.15


def _find_host_wall(cx, cy, axis, walls, perp_tol=1.0, end_pad=0.5):
    """The NEAREST winner wall of the right orientation whose span contains
    (cx, cy) — nearest so a door doesn't attach to the wrong one of two closely
    spaced parallel walls (double/party walls, wall+railing)."""
    best, best_perp = None, 1e18
    for w in walls:
        if w.get("axis") != axis:
            continue
        if axis == "x":
            perp = (float(w["y0"]) + float(w["y1"])) / 2.0
            if abs(perp - cy) <= perp_tol and abs(perp - cy) < best_perp \
               and float(w["x0"]) - end_pad <= cx <= float(w["x1"]) + end_pad:
                best, best_perp = w, abs(perp - cy)
        else:
            perp = (float(w["x0"]) + float(w["x1"])) / 2.0
            if abs(perp - cx) <= perp_tol and abs(perp - cx) < best_perp \
               and float(w["y0"]) - end_pad <= cy <= float(w["y1"]) + end_pad:
                best, best_perp = w, abs(perp - cx)
    return best


def augment_openings(winner, others, dedup_ft=1.5):
    """Add openings from `others` onto the winner's walls. Returns
    (winner, n_added). Skips openings already present (same type within
    dedup_ft) or with no host wall in the winner."""
    walls = winner.get("walls", []) or []
    if not walls:
        return winner, 0                     # vector path / no axis walls
    w_by_id = {w["id"]: w for w in walls if "id" in w}
    win_ops = winner.get("openings", []) or []
    existing = []                            # (type, cx, cy)
    for o in win_ops:
        c = _centroid(o, w_by_id)
        if c:
            existing.append((o.get("type"), c[0], c[1]))
    added = 0
    for other in others or []:
        o_by_id = {w["id"]: w for w in (other.get("walls", []) or []) if "id" in w}
        for o in other.get("openings", []) or []:
            c = _centroid(o, o_by_id)
            if not c:
                continue
            cx, cy, axis, width = c
            typ = o.get("type")
            if any(t == typ and (ex - cx) ** 2 + (ey - cy) ** 2 < dedup_ft ** 2
                   for t, ex, ey in existing):
                continue                     # already have this opening
            host = _find_host_wall(cx, cy, axis, walls)
            if host is None:
                continue                     # no shared wall to cut -> skip
            half = max(width, 1.0) / 2.0
            if axis == "x":
                lo, hi = cx - half, cx + half
                lo, hi = max(lo, float(host["x0"])), min(hi, float(host["x1"]))
            else:
                lo, hi = cy - half, cy + half
                lo, hi = max(lo, float(host["y0"])), min(hi, float(host["y1"]))
            # CLAMP to the host wall so the door leaf can't protrude past it
            # (the native scene_builder path clamps the same way); drop slivers
            if hi - lo < MIN_OPENING_FT:
                continue
            rec = {"id": f"fused{added}", "type": typ, "wall": host["id"],
                   "along": [round(lo, 3), round(hi, 3)],
                   "z": o.get("z", [0, 7.0]), "fused": True}
            if typ == "door":
                rec["hinge"] = o.get("hinge", "x0")
            win_ops.append(rec)
            existing.append((typ, cx, cy))
            added += 1
    winner["openings"] = win_ops
    return winner, added
