"""§10.2 dimension anchors — the fourth instrument (D-7).

The other three instruments need something printed that most sheets do not
carry: an area statement (R-8), room dimensions (R-2), a balcony width (B-5).
This one needs only that the sheet is dimensioned, which is why it is the
first check that reaches BRICK WORK.

No percentage is pinned here. The instrument is new and unruled: pinning its
score before Rahul rules on it would create a ratchet nobody authorised.
"""
import os

import pytest

import dimensions as D
import pdf_vector

PLANS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "plans")


class TestValues:
    def test_feet_inches_both_separators(self):
        assert D.parse_value_ft("12'6\"") == 12.5
        assert D.parse_value_ft("11'-5\"") == pytest.approx(11.417, abs=0.001)

    def test_metres_convert(self):
        assert D.parse_value_ft("3.43") == pytest.approx(11.253, abs=0.001)

    def test_a_word_is_not_a_dimension(self):
        assert D.parse_value_ft("bed room") is None
        assert D.parse_value_ft("") is None


class TestAnchors:
    """A dimension line offset 2 ft from the wall it measures, with extension
    lines running back to that wall."""
    A, B = (0.0, 2.0), (10.0, 2.0)
    SHORT = [((0.0, 2.0), (0.0, 0.0)), ((10.0, 2.0), (10.0, 0.0))]
    WALL = [((0.0, 0.0), (10.0, 0.0))]

    def test_the_extension_line_reaches_the_edge_not_the_dimension_line(self):
        """D-2: the dimension line's own endpoint is NOT on the edge."""
        assert D.follow_extension(self.A, self.A, self.B, self.SHORT) == (0.0, 0.0)

    def test_an_anchor_lands_on_the_wall(self):
        r = D.anchors([(self.A, self.B)], self.SHORT, [(10.0, (5.0, 2.2))], self.WALL)
        e = r["anchors"][0]["ends"][0]
        assert e["wall_dist_ft"] == 0.0 and e["via_extension"]
        assert r["anchors"][0]["value_ft"] == 10.0
        assert r["summary"]["pct_on_a_detected_face"] == 100.0

    def test_without_extensions_the_offset_is_reported_not_hidden(self):
        """No extension line to follow, so the dimension line's own endpoint is
        measured — 2 ft off the wall, and it SAYS 2 ft rather than hiding it."""
        r = D.anchors([(self.A, self.B)], [], [(10.0, (5.0, 2.2))], self.WALL)
        assert r["anchors"][0]["ends"][0]["wall_dist_ft"] == 2.0
        assert r["summary"]["within_0_5_ft"] == 0

    def test_a_valueless_line_is_not_a_dimension(self):
        """D-3, 16 Aug: title-block artwork shares the `dim` layer. All 29 of
        FLOOR PLAN's arrows landing on nothing were the area-statement table,
        the sheet frame, the company logo and a leader line — every one of them
        valueless."""
        r = D.anchors([(self.A, self.B)], self.SHORT, [], self.WALL)
        assert r["summary"]["dimensions"] == 0
        assert r["summary"]["dropped_no_value"] == 1
        assert r["summary"]["candidates"] == 1
        r2 = D.anchors([(self.A, self.B)], self.SHORT, [], self.WALL,
                       require_value=False)
        assert r2["summary"]["dimensions"] == 1

    def test_a_perpendicular_short_line_is_required(self):
        """A short line PARALLEL to the dimension line is a glyph stroke or a
        tick, not an extension line."""
        parallel = [((0.0, 2.0), (0.3, 2.0))]
        assert D.follow_extension(self.A, self.A, self.B, parallel) is None

    def test_no_walls_means_no_claim(self):
        r = D.anchors([(self.A, self.B)], self.SHORT, [], [])
        assert r["summary"]["pct_on_a_detected_face"] is None


@pytest.mark.skipif(not os.path.exists(os.path.join(PLANS, "BRICK WORK LAYOUT.pdf")),
                    reason="confidential corpus not present")
def test_the_instrument_reaches_brick_work():
    """BRICK WORK prints no area statement, no room dimensions and no balcony
    width — R-8, R-2 and B-5 are all silent there. It IS dimensioned."""
    with open(os.path.join(PLANS, "BRICK WORK LAYOUT.pdf"), "rb") as f:
        da = pdf_vector.parse(f.read())["meta"]["dimension_anchors"]
    assert da and da["route"] == "dim_layer"
    assert da["summary"]["dimensions"] >= 20
    assert da["summary"]["endpoints"] == 2 * da["summary"]["dimensions"]


@pytest.mark.skipif(not os.path.exists(os.path.join(PLANS, "FLOOR PLAN.pdf")),
                    reason="confidential corpus not present")
def test_the_instrument_is_additive_only():
    """It must not move a number. FLOOR PLAN's ratchets are the check."""
    with open(os.path.join(PLANS, "FLOOR PLAN.pdf"), "rb") as f:
        s = pdf_vector.parse(f.read())
    assert s["meta"]["dimension_anchors"]["summary"]["dimensions"] > 0
    assert s["meta"]["plan_width_ft"] == pytest.approx(95.2, abs=0.1)
    # 16 since 16 Aug: the utility (§10.1 CE-5) plus two duct voids (§4 D-5).
    # The point of this test is that the DIMENSION instrument moves nothing —
    # it does not, and the room count is pinned here to keep that visible.
    assert len(s["rooms"]) == 16
