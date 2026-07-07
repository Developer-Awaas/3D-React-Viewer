"""Step B2 - doors & windows.

Turns CubiCasa's icon detections (Window/Door pixel classes) into wall OPENINGS:
1. boxes_from_mask()  icon class map -> pixel bounding boxes        (OpenCV)
2. attach_openings()  boxes + wall segments -> bridged segments
                      + {type, seg, along} opening records          (pure)

Coordinates are PIXELS throughout (origin top-left, y down) - scene_builder
converts to feet and assigns z-ranges. "Bridging" merges two collinear wall
segments whose gap is covered by a door/window box, so the opening becomes a
real cut in a continuous wall instead of a ragged hole.
"""

WINDOW_IDX = 1   # ICON_CLASSES.index("Window")
DOOR_IDX = 2     # ICON_CLASSES.index("Door")
MIN_OPENING_PX = 2


def default_tol(width_px):
    """How far (px) an opening box may sit from a wall centre-line."""
    return max(8, int(0.02 * width_px))


def boxes_from_mask(icons_pred, min_area=30):
    """icons_pred: HxW int array of icon classes.
    Returns [{"type": "door"|"window", "x0","y0","x1","y1"}, ...] in pixels."""
    import cv2
    import numpy as np
    boxes = []
    arr = np.asarray(icons_pred)
    for idx, typ in ((WINDOW_IDX, "window"), (DOOR_IDX, "door")):
        mask = (arr == idx).astype(np.uint8)
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] < min_area:
                continue
            x = int(stats[i, cv2.CC_STAT_LEFT]); y = int(stats[i, cv2.CC_STAT_TOP])
            w = int(stats[i, cv2.CC_STAT_WIDTH]); h = int(stats[i, cv2.CC_STAT_HEIGHT])
            boxes.append({"type": typ, "x0": x, "y0": y, "x1": x + w, "y1": y + h})
    return boxes


def _norm(segments):
    """[[x1,y1,x2,y2], ...] -> [{"h": bool, "p": perp_pos, "a": start, "b": end}]"""
    recs = []
    for x1, y1, x2, y2 in segments:
        if abs(x2 - x1) >= abs(y2 - y1):
            a, b = sorted((x1, x2))
            recs.append({"h": True, "p": (y1 + y2) / 2.0, "a": a, "b": b})
        else:
            a, b = sorted((y1, y2))
            recs.append({"h": False, "p": (x1 + x2) / 2.0, "a": a, "b": b})
    return recs


def _box_span(box, horiz):
    """Opening box -> (along_start, along_end, perp_centre) for a wall orientation."""
    if horiz:
        return box["x0"], box["x1"], (box["y0"] + box["y1"]) / 2.0
    return box["y0"], box["y1"], (box["x0"] + box["x1"]) / 2.0


def bridge_gaps(recs, boxes, tol):
    """Merge collinear segment pairs whose gap is covered by a detection box."""
    recs = [dict(r) for r in recs]
    merged = True
    while merged:
        merged = False
        for i in range(len(recs)):
            if recs[i] is None:
                continue
            for j in range(len(recs)):
                if i == j or recs[j] is None or recs[i] is None:
                    continue
                A, B = recs[i], recs[j]
                if A["h"] != B["h"] or abs(A["p"] - B["p"]) > tol:
                    continue
                if not (A["b"] < B["a"]):          # need A ... gap ... B
                    continue
                mid_p = (A["p"] + B["p"]) / 2.0
                for box in boxes:
                    ba, bb, bp = _box_span(box, A["h"])
                    if (abs(bp - mid_p) <= tol
                            and ba <= A["b"] + tol and bb >= B["a"] - tol):
                        A["b"] = B["b"]
                        A["p"] = mid_p
                        recs[j] = None
                        merged = True
                        break
    return [r for r in recs if r is not None]


def _merge_overlaps(ops):
    """Merge overlapping openings on the same segment (door wins over window)."""
    out = []
    for op in sorted(ops, key=lambda o: (o["seg"], o["along"][0])):
        prev = out[-1] if out else None
        if prev and prev["seg"] == op["seg"] and op["along"][0] <= prev["along"][1]:
            prev["along"][1] = max(prev["along"][1], op["along"][1])
            if op["type"] == "door":
                prev["type"] = "door"
        else:
            out.append({"type": op["type"], "seg": op["seg"],
                        "along": [op["along"][0], op["along"][1]]})
    return out


def match_openings(recs, boxes, tol):
    """Attach each box to the nearest wall it overlaps. Unmatched boxes drop."""
    ops = []
    for box in boxes:
        best = None
        for k, r in enumerate(recs):
            ba, bb, bp = _box_span(box, r["h"])
            d = abs(bp - r["p"])
            if d > tol:
                continue
            a = max(ba, r["a"]); b = min(bb, r["b"])
            if b - a < MIN_OPENING_PX:
                continue
            if best is None or d < best[0] or (d == best[0] and b - a > best[3] - best[2]):
                best = (d, k, a, b)
        if best is not None:
            _, k, a, b = best
            ops.append({"type": box["type"], "seg": k, "along": [a, b]})
    return _merge_overlaps(ops)


def attach_openings(segments, boxes, tol):
    """Main entry. segments: [[x1,y1,x2,y2],...] px centre-lines; boxes from
    boxes_from_mask(). Returns (segments_out, openings) where openings
    reference segments_out by index: {"type", "seg", "along": [a, b]} (px)."""
    recs = bridge_gaps(_norm(segments), boxes, tol)
    ops = match_openings(recs, boxes, tol)
    segs = [[r["a"], r["p"], r["b"], r["p"]] if r["h"]
            else [r["p"], r["a"], r["p"], r["b"]] for r in recs]
    return segs, ops
