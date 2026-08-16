"""B-2a railing runs, and the two things that make one a BALCONY.

The classifier's third test is the one that matters: a run's enclosed depth
must match a width the SHEET PRINTS. Measured on FLOOR PLAN — flat-1 encloses
3.92 ft against a printed 4'0", flat-2 3.37 ft against 3'6", and the 12.33 ft
run at (25.58, 24.06) encloses 4.91 ft, which matches neither. That last one
is the lobby drafting error (§0 CONTRADICTS), and before this test it read as
37.3 sqft of balcony.
"""
import os

import numpy as np
import pytest

import pdf_vector
import railings

PLANS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "plans")

FLAT1 = {"ends_on_wall": 2, "turns": 2,
         "polyline_ft": [[-3.92, 0.08], [-3.92, 13.23],
                         [0.0, 13.23], [0.0, 0.08]]}
LOBBY = {"ends_on_wall": 2, "turns": 1,          # the false positive
         "polyline_ft": [[25.58, 19.15], [33.17, 19.15], [33.17, 24.06]]}


class TestDepthAgainstPrinted:
    def test_depth_is_the_short_side(self):
        assert railings.enclosed_depth_ft(FLAT1) == 3.92

    def test_a_depth_that_matches_a_printed_width_is_a_balcony(self):
        assert railings.classify(FLAT1, [4.0, 3.5]) == "railing"

    def test_a_depth_that_matches_nothing_printed_is_not(self):
        """4.91 ft against printed 4'0" and 3'6" — the lobby, not a balcony."""
        assert railings.enclosed_depth_ft(LOBBY) == 4.91
        assert railings.classify(LOBBY, [4.0, 3.5]) == "unclassified"

    def test_no_printed_width_means_no_claim(self):
        """A sheet that prints no balcony width gives nothing to check
        against, so nothing is claimed. BRICK WORK goes 3 runs -> 0 here."""
        assert railings.classify(FLAT1, []) == "unclassified"

    def test_the_first_two_tests_still_apply(self):
        stair = {"ends_on_wall": 0, "turns": 0,
                 "polyline_ft": [[0, 0], [27.3, 0]]}
        assert railings.classify(stair, [4.0]) == "unclassified"


def test_bridge_cap_does_not_move_with_the_canvas():
    """§12: `max_bridge = min(wall_mask.shape)` was a CANVAS-unit constant —
    the same class as BORDER_MAXLEN_PT. The same building padded onto a bigger
    raster must give the same footprint, or the canvas silently sets the
    physics."""
    from test_footprint import _ring
    m, segs = _ring(gap_ft=10.0)
    a, _b, _r, _e, _l = pdf_vector._footprint_from_walls(m, seg_px=segs)
    pad = 400
    big = np.zeros((m.shape[0] + 2 * pad, m.shape[1] + 2 * pad), np.uint8)
    big[pad:pad + m.shape[0], pad:pad + m.shape[1]] = m
    segs_big = [(x0 + pad, y0 + pad, x1 + pad, y1 + pad)
                for x0, y0, x1, y1 in segs]
    c, _b2, _r2, _e2, _l2 = pdf_vector._footprint_from_walls(big, seg_px=segs_big)
    assert (c > 0).sum() == pytest.approx((a > 0).sum(), rel=0.01)


@pytest.mark.skipif(not os.path.exists(os.path.join(PLANS, "FLOOR PLAN.pdf")),
                    reason="confidential corpus not present")
def test_floor_plan_balcony_is_measured_from_its_drawn_edge():
    """The balcony must come from the railing, not from `foot_ext - foot`:
    flat-1 sits at x -3.92..0.00, OUTSIDE the wall extent, and the canvas has
    to reach it before any pocket can exist there."""
    with open(os.path.join(PLANS, "FLOOR PLAN.pdf"), "rb") as f:
        s = pdf_vector.parse(f.read())
    bals = [r for r in s["rooms"] if r.get("type") == "balcony"]
    assert bals, "flat-1's balcony must be found"
    assert any(b["depth_ft"] == pytest.approx(3.92, abs=0.15) for b in bals)
    assert s["meta"]["canvas"]["railing_bound_ft"][0] < -3.5   # canvas reaches it
    # the 4.91 ft run must never be a BALCONY. Since 16 Aug it is admitted as
    # the UTILITY (§10.1 CE-5) — a covered-but-not-enclosed strip on its own
    # line — so the test is that it is not counted as balcony, not that it is
    # absent. It was called a false positive for four reports and is not one.
    assert not any(r.get("depth_ft") == pytest.approx(4.91, abs=0.05)
                   for r in s["rooms"] if r.get("type") == "balcony")
    assert any(r.get("type") == "utility"
               and r.get("depth_ft") == pytest.approx(4.91, abs=0.05)
               for r in s["rooms"])


# --- ONE-SIDED balconies (15 Aug 2026) --------------------------------------
# §10/B-2a always defined a 1-sided balcony — railing across the front only —
# and the classifier was rejecting the case its own spec describes. 47 of 50
# runs on neelachala FIRST FLOOR and 38 of 38 on GHATIKIA have zero turns.
STRAIGHT = {"ends_on_wall": 2, "turns": 0, "polyline_ft": [[0, 0], [9.6, 0]]}
WALL_BEHIND = [((0, 3.37), (9.6, 3.37)), ((0, 40.0), (9.6, 40.0))]


class TestOneSided:
    def test_a_straight_run_measures_depth_to_the_wall_behind_it(self):
        """Its bbox short side is 0.00, so depth has to come from the wall."""
        assert railings.enclosed_depth_ft(STRAIGHT, WALL_BEHIND) == 3.37

    def test_no_wall_behind_means_no_depth_and_no_claim(self):
        assert railings.enclosed_depth_ft(STRAIGHT, []) is None
        assert railings.classify(dict(STRAIGHT, depth_ft=None), [3.5]) \
            == "unclassified"

    def test_a_one_sided_run_at_a_printed_width_is_a_balcony(self):
        assert railings.classify(dict(STRAIGHT, depth_ft=3.37), [3.5]) == "railing"

    def test_a_one_sided_run_at_no_printed_width_is_not(self):
        assert railings.classify(dict(STRAIGHT, depth_ft=3.37), [6.0]) \
            == "unclassified"

    def test_the_pocket_extends_to_the_wall(self):
        """Without the extension the rectangle is degenerate and no area can
        ever form — FIRST FLOOR's two balconies are both this shape."""
        assert railings.pocket_ft(STRAIGHT, WALL_BEHIND) == [0, 0, 9.6, 3.37]

    def test_a_turning_run_still_encloses_its_own_bbox(self):
        assert railings.pocket_ft(FLAT1, WALL_BEHIND) == [-3.92, 0.08, 0.0, 13.23]


def test_printed_widths_reads_a_labelled_dimension_pair():
    """`balcony` over `9'-7" X 3'-6"` — the width is the SHORT side. Only the
    `<ft-in> WIDE` form was read before, so FIRST FLOOR yielded [] on a sheet
    that prints three balcony widths."""
    import room_dims
    toks = [{"text": "balcony", "x0": 100, "y0": 100, "x1": 130, "y1": 105},
            {"text": "9'-7\"", "x0": 100, "y0": 106, "x1": 118, "y1": 111},
            {"text": "X3'-6\"", "x0": 118, "y0": 106, "x1": 140, "y1": 111}]
    assert room_dims.printed_widths(toks, "BALCON") == [3.5]
