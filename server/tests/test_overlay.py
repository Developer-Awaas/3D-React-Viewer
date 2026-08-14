"""PHASE 0 — the wall-overlay instrument.

The registration maths gets the most attention here: a mis-registered overlay
lies convincingly, which is worse than having no overlay at all. Everything is
pure, so none of this needs a PDF or tesseract.
"""
import os

import pytest

import overlay

PLANS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "plans")

# FLOOR PLAN.pdf's real registration, as the parser reports it
REG = {"x0_pt": 460.28, "y0_pt": 854.0, "ppf": 28.468, "d_ft": 29.7892,
       "shift_ft": [0.0, 0.0], "rotation": 270,
       "page_w_pt": 3456.0, "page_h_pt": 2592.0}


class TestRegistration:
    def test_origin_maps_to_the_bottom_left_of_the_linework(self):
        f = overlay.page_transform(REG, dpi=72)
        assert f(0, 0) == [pytest.approx(460.3, abs=0.2),
                           pytest.approx(1702.0, abs=1.0)]   # y0 + d_ft*ppf

    def test_y_axis_flips(self):
        """Scene feet run bottom-up; page pixels run top-down."""
        f = overlay.page_transform(REG, dpi=72)
        assert f(0, 10)[1] < f(0, 0)[1]

    def test_dpi_scales_linearly(self):
        # coordinates are rounded to 0.1 px to keep the payload small, so the
        # tolerance is that quantisation, not floating point
        a = overlay.page_transform(REG, dpi=72)(10, 10)
        b = overlay.page_transform(REG, dpi=144)(10, 10)
        assert b[0] == pytest.approx(a[0] * 2, abs=0.25)
        assert b[1] == pytest.approx(a[1] * 2, abs=0.25)

    def test_one_foot_is_ppf_points(self):
        f = overlay.page_transform(REG, dpi=72)
        assert f(1, 0)[0] - f(0, 0)[0] == pytest.approx(REG["ppf"], abs=0.15)

    def test_wing_shift_is_applied(self):
        """A wing-cropped scene has its origin moved; the overlay must put it
        back or every shape lands offset by the crop."""
        shifted = dict(REG, shift_ft=[10.0, 5.0])
        assert (overlay.page_transform(shifted, dpi=72)(0, 0)[0]
                == pytest.approx(overlay.page_transform(REG, dpi=72)(10, 0)[0],
                                 abs=0.05))


class TestLayers:
    SCENE = {
        "meta": {"page_registration": REG,
                 "wall_line_thicknesses": {"histogram_in": {"5": 19},
                                           "count": 79, "median_in": 10.02},
                 "rejected_summary": {"text": 718}},
        "walls_poly": [{"outer": [[0, 0], [10, 0], [10, 10], [0, 10]],
                        "holes": [[[1, 1], [9, 1], [9, 9], [1, 9]]]}],
        "columns": [{"x": 2.0, "y": 2.0, "w": 1.0, "d": 1.0}],
        "openings": [{"type": "door", "footprint": [3, 0, 6, 0.75]},
                     {"type": "window", "footprint": [7, 0, 9, 0.75]}],
        "rooms": [{"id": "r0", "polygon_ft": [[1, 1], [9, 1], [9, 9], [1, 9]]}],
        "footprint_ft": [[0, 0], [10, 0], [10, 10], [0, 10]],
        "rejected_lines_ft": [[0, 0, 5, 5]],
    }

    def test_every_layer_is_present_even_when_empty(self):
        """A layer that is MISSING looks like a layer that found nothing. The
        difference — 'no detector yet' vs 'detector found none' — is the whole
        point of the instrument, so Phase 1's layers ship empty, not absent."""
        layers = overlay.build_layers(self.SCENE)
        assert set(layers) == set(overlay.LAYER_STYLE)
        for name in overlay.NOT_YET_DETECTED:
            assert layers[name] == []

    def test_shapes_are_counted_per_layer(self):
        out = overlay.build_overlay(self.SCENE)
        assert out["counts"]["walls"] == 2          # outer + hole
        assert out["counts"]["columns"] == 1
        assert out["counts"]["doors"] == 1
        assert out["counts"]["windows"] == 1
        assert out["counts"]["rooms"] == 1
        assert out["counts"]["footprint"] == 1
        assert out["counts"]["rejected"] == 1

    def test_the_discard_pile_is_a_layer(self):
        """An overlay that draws only what was FOUND cannot show a missing
        wall — the wall we failed to read is in the discard pile."""
        assert "rejected" in overlay.LAYER_STYLE
        assert overlay.build_layers(self.SCENE)["rejected"]

    def test_a_column_becomes_a_closed_quad(self):
        (quad,) = overlay.build_layers(self.SCENE)["columns"]
        assert len(quad) == 4

    def test_no_registration_means_no_overlay(self):
        assert overlay.build_layers({"meta": {}}) is None
        assert overlay.build_overlay({"meta": {}}) is None

    def test_measurements_ride_along(self):
        out = overlay.build_overlay(self.SCENE)
        assert out["wall_line_thicknesses"]["median_in"] == 10.02
        assert out["rejected_summary"]["text"] == 718


@pytest.mark.skipif(not os.path.exists(os.path.join(PLANS, "FLOOR PLAN.pdf")),
                    reason="confidential corpus not present")
def test_floor_plan_geometry_lands_inside_the_page():
    """End to end: every drawn shape must fall within the rendered page. A
    registration error big enough to matter puts shapes off-sheet."""
    import pdf_vector
    with open(os.path.join(PLANS, "FLOOR PLAN.pdf"), "rb") as f:
        scene = pdf_vector.parse(f.read())
    reg = scene["meta"]["page_registration"]
    assert reg and reg["ppf"] > 0
    dpi = 110.0
    out = overlay.build_overlay(scene, dpi)
    w = reg["page_w_pt"] * dpi / 72.0
    h = reg["page_h_pt"] * dpi / 72.0
    pts = [p for name in ("walls", "columns", "doors", "windows", "rooms",
                          "footprint")
           for shape in out["layers"][name] for p in shape]
    assert pts, "the overlay must have geometry to draw"
    assert all(-2 <= p[0] <= w + 2 and -2 <= p[1] <= h + 2 for p in pts)


# --- REGISTRATION ASSERTION (14 Aug 2026) -----------------------------------
# The overlay is our only GEOMETRIC instrument, and nothing tested that it kept
# pointing at the same place. Without this, a parser change that shifts the
# linework origin would move every drawn shape, and the overlay would go on
# looking plausible while quietly lying — we would read a registration drift as
# a geometry move. Anchor: FLOOR PLAN's south wall east jamb, the feature the
# whole lobby investigation turned on.
@pytest.mark.skipif(not os.path.exists(os.path.join(PLANS, "FLOOR PLAN.pdf")),
                    reason="confidential corpus not present")
def test_registration_anchor_does_not_drift():
    import pdf_vector
    with open(os.path.join(PLANS, "FLOOR PLAN.pdf"), "rb") as f:
        reg = pdf_vector.parse(f.read())["meta"]["page_registration"]
    px, py = overlay.page_transform(reg, 110.0)(41.24, 0.0)
    # measured 14 Aug 2026; a real geometry change may move this, but it must
    # be an EXPLAINED move, never a silent one
    assert px == pytest.approx(2497.2, abs=2.0)
    assert py == pytest.approx(2600.3, abs=2.0)
