"""THE BAND RULE (§12, 21 Aug 2026, Rahul): an empty band splits a sheet only
if NOTHING covers it — and the question is what covers it COLLECTIVELY, not
what individually spans it.

neelachala FIRST FLOOR is one building in two blocks with a 13.1 ft band
between them. No wall line crosses it and no filled path spans it; the
first-floor terrace slab is drawn across it as 19 strokes at exactly 45
degrees, only 2 of which reach both sides. Together they cover it in one
unbroken run. `_wing_groups` used to keep one block and delete the other, so
every number on that sheet described 37% of the footprint.
"""
import os

import numpy as np
import pytest

PLANS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "plans")


def _cover(rows, cols, strokes):
    import cv2
    m = np.zeros((rows, cols), np.uint8)
    for a, b in strokes:
        cv2.line(m, a, b, 255, 2)
    return m


def test_diagonals_bridge_collectively_even_though_none_spans():
    """The whole point: a staircase of 45-degree strokes, no single one of
    which reaches from the top edge to the bottom, still covers the band."""
    from pdf_vector import _band_bridged
    lo = (0, 0, 100, 40)          # block below the band (bbox x0,y0,x1,y1 px)
    hi = (0, 80, 100, 120)        # block above it; band = y 40..80
    diag = [((10 + 12 * k, 30), (10 + 12 * k + 40, 90)) for k in range(6)]
    assert _band_bridged(_cover(120, 100, diag), lo, hi) is True
    assert _band_bridged(_cover(120, 100, []), lo, hi) is False


def test_a_band_nothing_covers_still_splits():
    """The opposite answer from the same test — GHATIKIA's two views."""
    from pdf_vector import _band_bridged
    lf = (0, 0, 40, 100)
    rt = (80, 0, 120, 100)        # band = x 40..80
    # ink INSIDE each block, none of it in the band
    ink = [((5, 5), (35, 95)), ((85, 5), (115, 95))]
    assert _band_bridged(_cover(100, 120, ink), lf, rt) is False


def test_first_floor_keeps_both_blocks():
    """Regression: the discarded block was the LARGER of the two."""
    path = os.path.join(PLANS, "neelachala FIRST FLOOR.pdf")
    if not os.path.exists(path):
        pytest.skip("corpus file not present")
    from pdf_vector import parse
    with open(path, "rb") as f:
        scene = parse(f.read(), None)
    meta = scene["meta"]
    assert meta["wing"]["count"] == 1          # was 2, and one was deleted
    assert meta["plan_depth_ft"] > 150         # both blocks + the band
    assert meta["footprint_sqft"] > 4000       # was 1652 = 37% of the building


# --- THE SPLIT: the band rule's opposite operation (25 Aug 2026) -------------
def test_an_empty_band_splits_and_a_crossed_one_does_not():
    """`_empty_bands` needs a STRONGER signature than "nothing bridges it": a
    real interior corridor has partitions crossing it somewhere along its
    length, while the gutter between two drawings is empty end to end."""
    from pdf_vector import _empty_bands, NORM_PPX
    W = int(30 * NORM_PPX)
    m = np.zeros((int(10 * NORM_PPX), W), np.uint8)
    m[:, :int(12 * NORM_PPX)] = 255                 # left view
    m[:, int(18 * NORM_PPX):] = 255                 # right view; 6 ft gutter
    bands = _empty_bands(m, (0, 0, W, m.shape[0]), 1.0)
    assert [a for a, _lo, _hi in bands] == [0]      # one VERTICAL band
    a, lo, hi = bands[0]
    assert (hi - lo) / NORM_PPX == pytest.approx(6.0, abs=0.2)
    m[int(4 * NORM_PPX):int(5 * NORM_PPX), :] = 255  # one partition crosses it
    assert _empty_bands(m, (0, 0, W, m.shape[0]), 1.0) == []


def test_the_split_is_inert_on_every_single_view_sheet():
    """The failure mode that matters most: a split rule firing on a sheet that
    holds ONE view. Measured on `cover` — FLOOR PLAN, BRICK WORK and neelachala
    FIRST FLOOR have NO interior zero-ink band at all, and only GHATIKIA does
    (6.48 ft). On the WALL MASK, FIRST FLOOR would show a 14.01 ft empty band
    and split back into the two blocks Rahul ruled are one building — the
    terrace hatch's 19 diagonal strokes fill it, and `_segs` is blind to a
    45-degree stroke by construction."""
    from pdf_vector import parse
    for name, wings in (("FLOOR PLAN.pdf", 1), ("BRICK WORK LAYOUT.pdf", 1),
                        ("neelachala FIRST FLOOR.pdf", 1),
                        ("NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf", 2)):
        path = os.path.join(PLANS, name)
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            assert parse(f.read(), None)["meta"]["wing"]["count"] == wings, name
