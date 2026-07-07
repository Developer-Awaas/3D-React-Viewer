"""Step A - wall vectorizer.

Turns CubiCasa's wall PIXELS into clean wall LINE-SEGMENTS.
Pure geometry in _collapse() (unit-tested); OpenCV only used inside _bands().
Coordinates are in pixels for now - real-world scale is applied in Step 4.
"""


def _collapse(runs, perp_tol, gap_tol, min_len):
    """Merge parallel wall runs and bridge small gaps (doorways stay open).

    runs: list of {"p": perpendicular_pos, "a": start, "b": end}
    Returns merged runs, dropping any shorter than min_len.
    (Ported from the viewer's detect.worker.js collapse logic.)
    """
    runs = sorted(runs, key=lambda r: r["p"])
    clusters = []
    for s in runs:
        if clusters and s["p"] - clusters[-1][-1]["p"] <= perp_tol:
            clusters[-1].append(s)
        else:
            clusters.append([s])

    out = []
    for cl in clusters:
        p = sum(s["p"] for s in cl) / len(cl)
        intervals = sorted(([s["a"], s["b"]] for s in cl), key=lambda x: x[0])
        ca, cb = intervals[0]
        for a, b in intervals[1:]:
            if a <= cb + gap_tol:          # gap small enough -> same wall
                cb = max(cb, b)
            else:                          # real gap (doorway) -> split
                out.append({"p": p, "a": ca, "b": cb})
                ca, cb = a, b
        out.append({"p": p, "a": ca, "b": cb})

    return [r for r in out if r["b"] - r["a"] >= min_len]


def _bands(mask, axis, open_len, close_th):
    """Extract horizontal ('h') or vertical ('v') wall bands from a binary mask
    and return their centre-line runs. Uses OpenCV morphology."""
    import cv2
    if axis == "h":
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (open_len, 1))
        ck = cv2.getStructuringElement(cv2.MORPH_RECT, (1, close_th))
    else:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, open_len))
        ck = cv2.getStructuringElement(cv2.MORPH_RECT, (close_th, 1))

    band = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)     # keep long runs in this orientation
    band = cv2.morphologyEx(band, cv2.MORPH_CLOSE, ck)   # fuse double-line walls
    n, _, stats, _ = cv2.connectedComponentsWithStats(band, connectivity=8)

    runs = []
    for i in range(1, n):
        x = stats[i, cv2.CC_STAT_LEFT]; y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]; h = stats[i, cv2.CC_STAT_HEIGHT]
        if axis == "h":
            runs.append({"p": y + h / 2, "a": x, "b": x + w})
        else:
            runs.append({"p": x + w / 2, "a": y, "b": y + h})
    return runs


def _denoise(mask, min_area):
    """Remove small stray components (dimension arrows, symbols, specks)."""
    import cv2
    import numpy as np
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = np.zeros_like(mask)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            out[labels == i] = 255
    return out


def vectorize_walls(wall_mask):
    """wall_mask: HxW array, non-zero where CubiCasa predicted 'Wall'.
    Returns wall segments as [[x1, y1, x2, y2], ...] in PIXEL coordinates."""
    import numpy as np
    mask = (np.asarray(wall_mask) > 0).astype(np.uint8) * 255
    H, W = mask.shape[:2]
    mask = _denoise(mask, max(40, int(0.0002 * W * H)))   # drop stray specks/blobs

    # thresholds scale with image width so it works on any size
    open_len = max(20, int(0.04 * W))   # min run length to count as a wall
    close_th = max(3, int(0.01 * W))    # fuse the two lines of a double-line wall
    gap_tol = max(6, int(0.03 * W))     # bridge gaps up to ~3% (keeps doorways open)
    min_len = max(15, int(0.05 * W))    # drop tiny fragments
    perp_tol = max(8, int(0.01 * W))    # how close parallel lines must be to merge

    h_runs = _bands(mask, "h", open_len, close_th)
    v_runs = _bands(mask, "v", open_len, close_th)

    segments = []
    for r in _collapse(h_runs, perp_tol, gap_tol, min_len):
        segments.append([r["a"], r["p"], r["b"], r["p"]])   # horizontal wall
    for r in _collapse(v_runs, perp_tol, gap_tol, min_len):
        segments.append([r["p"], r["a"], r["p"], r["b"]])   # vertical wall
    return segments
