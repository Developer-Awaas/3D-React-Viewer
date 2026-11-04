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
import numpy as np
import pytest

from conftest import require_corpus_file


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
    path = require_corpus_file("neelachala FIRST FLOOR.pdf")
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
        path = require_corpus_file(name)
        with open(path, "rb") as f:
            assert parse(f.read(), None)["meta"]["wing"]["count"] == wings, name


# --- SEPARATION MUST NOT DEPEND ON A DISTANCE IN FEET (31 Aug 2026) ----------
def test_regions_separate_on_an_empty_band_not_on_proximity():
    """`gap_ft = 8` is a distance in FEET and feet move with ppf, so GHATIKIA
    used to separate for a DIFFERENT REASON on each parse pass — a zero-ink band
    at ppf 8.80, mere proximity at 7.189. The two passes agreed on TWO REGIONS by
    coincidence, not by agreement. Ink is ink at any scale."""
    path = require_corpus_file("NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf")
    from pdf_vector import parse
    raw = open(path, "rb").read()
    for kw in ({"_refit": False}, {}):                 # pass 1 and pass 2
        m = parse(raw, None, **kw)["meta"]
        rs = m["regions"]
        assert len(rs) == 2
        ev = rs[0]["join_evidence"]
        assert ev["basis"] == "separate: a band with NO INK between them"
        assert ev["separated_by"] == {"empty_band_pairs": 1,
                                      "ink_in_band_pairs": 0}


def test_first_floor_still_one_region_the_terrace_puts_ink_in_the_band():
    """The 22 Aug ruling: FIRST FLOOR's two blocks are ONE building, joined by
    the terrace. If the separator ever splits them, that ruling has been
    silently reversed — the failure mode that matters most."""
    path = require_corpus_file("neelachala FIRST FLOOR.pdf")
    from pdf_vector import parse
    with open(path, "rb") as f:
        m = parse(f.read(), None)["meta"]
    assert len(m["regions"]) == 1
    assert m["regions"][0]["join_evidence"]["basis"].startswith("merged")


def test_a_stray_line_in_the_gutter_does_not_merge_two_drawings():
    """The test is a CLEAN LINE of zero ink across the band, not "no ink at
    all": one stray dimension line lying in a gutter must not weld two plans
    into one."""
    from pdf_vector import _band_ink, NORM_PPX
    W, H = int(30 * NORM_PPX), int(10 * NORM_PPX)
    cover = np.zeros((H, W), np.uint8)
    left = (0, 0, int(12 * NORM_PPX), H)
    right = (int(18 * NORM_PPX), 0, W, H)
    assert _band_ink(cover, left, right) is False        # clean gutter -> apart
    # a stray line over PART of the gutter still leaves a clean run
    cover[int(2 * NORM_PPX):int(2 * NORM_PPX) + 2,
          int(12 * NORM_PPX):int(14 * NORM_PPX)] = 255
    assert _band_ink(cover, left, right) is False        # still apart
    # ink drawn ALL THE WAY ACROSS leaves no clean run: one drawing
    cover[:, int(12 * NORM_PPX):int(18 * NORM_PPX)] = 255
    assert _band_ink(cover, left, right) is True

    # CAVEAT, recorded rather than guarded: a SINGLE line crossing the full
    # width of a gutter also leaves no clean run, so it merges two drawings.
    # That is the ruled test's own semantics - anything drawn across the gutter
    # means the drawings touch - and it is what makes FIRST FLOOR's terrace
    # hatch a join. No sheet in the corpus has such a line in a real gutter.
