"""G1 wall-gap healing: when the OUTER wall has a gap, interior free-space
leaks to the image border and yields 0 rooms (0% efficiency). The footprint
free-mask bridges the gap so interior pockets stay bounded. Pure tests."""
import cv2
import numpy as np

import pdf_vector as P


def _count_pockets(mask):
    """Non-border-touching free components >= a small area."""
    n, lab, stt, _ = cv2.connectedComponentsWithStats(mask, 4)
    H, W = mask.shape
    out = 0
    for i in range(1, n):
        x, y, w, h, a = stt[i]
        if a < 400:
            continue
        if x == 0 or y == 0 or x + w >= W or y + h >= H:
            continue                     # touches border = outside
        out += 1
    return out


def _broken_box_with_partition():
    """A 300x300 building: 8px outer wall with a GAP in the bottom edge, plus a
    vertical interior partition -> two rooms that should be recoverable."""
    m = np.zeros((360, 360), np.uint8)
    m[40:48, 40:320] = 255           # top
    m[40:320, 40:48] = 255           # left
    m[40:320, 312:320] = 255         # right
    m[312:320, 40:170] = 255         # bottom-left ... GAP ...
    m[312:320, 210:320] = 255        # bottom-right (gap 170..210)
    m[40:320, 176:184] = 255         # interior partition
    return m


def test_without_healing_interior_leaks_to_border():
    m = _broken_box_with_partition()
    free = (m == 0).astype(np.uint8)
    assert _count_pockets(free) == 0        # the gap lets it all leak out


def test_footprint_healing_recovers_two_rooms():
    m = _broken_box_with_partition()
    healed = P._footprint_free_mask(m, seal_ft=6.0, norm_ppx=10)
    assert healed is not None
    assert _count_pockets(healed) == 2      # both rooms bounded now


def test_healing_is_noop_shape_on_empty():
    assert P._footprint_free_mask(np.zeros((50, 50), np.uint8), 6.0, norm_ppx=10) is None


def test_sealed_box_unaffected_by_healing():
    """A fully-sealed box already yields its interior pocket; healing must not
    lose it (idempotent-ish)."""
    m = np.zeros((360, 360), np.uint8)
    m[40:48, 40:320] = 255; m[40:320, 40:48] = 255
    m[40:320, 312:320] = 255; m[312:320, 40:320] = 255
    healed = P._footprint_free_mask(m, seal_ft=6.0, norm_ppx=10)
    assert _count_pockets(healed) == 1
