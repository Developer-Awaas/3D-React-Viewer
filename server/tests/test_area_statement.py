"""Tests for the RERA-style area statement (pure geometry). Hand-computed
expected values so the math is pinned."""
import area_statement as A


def test_polygon_area_rectangle():
    # 10 x 20 ft rectangle -> 200 sqft
    assert A.polygon_area([[0, 0], [10, 0], [10, 20], [0, 20]]) == 200.0


def test_polygon_area_degenerate():
    assert A.polygon_area([[0, 0], [1, 1]]) == 0.0        # <3 points


def test_carpet_is_sum_of_rooms():
    scene = {
        "rooms": [{"id": "r0", "area_sqft": 120.0}, {"id": "r1", "area_sqft": 80.0}],
        "walls_poly": [{"outer": [[0, 0], [20, 0], [20, 15], [0, 15]]}],  # 300 sqft
        "meta": {"scale": {"source": "dimension_text"}},
    }
    out = A.compute_area_statement(scene, loading_factor=1.30)
    assert out["carpet_area"]["sqft"] == 200.0            # 120 + 80
    assert out["built_up_area"]["sqft"] == 300.0          # gross footprint
    # market convention: super = CARPET x loading (200 * 1.30 = 260), floored
    # at built-up (300). Old built_up * loading double-counted wall footprint.
    assert out["super_built_up_area"]["sqft"] == 300.0    # max(260, 300)
    assert out["wall_and_circulation"]["sqft"] == 100.0   # 300 - 200
    assert out["efficiency_pct"] == round(100 * 200 / 300, 1)


def test_super_builtup_is_carpet_based():
    # carpet 800, built-up 900, loading 1.30 -> super = 800*1.30 = 1040 (NOT
    # 900*1.30 = 1170) and efficiency ~76.9% (not ~68%) — the buyer-facing fix
    scene = {
        "rooms": [{"id": "r0", "area_sqft": 800.0}],
        "walls_poly": [{"outer": [[0, 0], [30, 0], [30, 30], [0, 30]]}],  # 900
        "meta": {"scale": {"source": "dimension_text"}},
    }
    out = A.compute_area_statement(scene, loading_factor=1.30)
    assert out["super_built_up_area"]["sqft"] == 1040.0
    assert out["efficiency_pct"] == round(100 * 800 / 1040, 1)
    assert any("carpet x loading" in n for n in out["notes"])


def test_super_builtup_never_below_builtup():
    # small loading on a wall-heavy plan: super floors at built-up
    scene = {
        "rooms": [{"id": "r0", "area_sqft": 100.0}],
        "walls_poly": [{"outer": [[0, 0], [20, 0], [20, 10], [0, 10]]}],  # 200
        "meta": {"scale": {"source": "dimension_text"}},
    }
    out = A.compute_area_statement(scene, loading_factor=1.05)
    assert out["super_built_up_area"]["sqft"] == 200.0    # max(105, 200)


def test_sqm_conversion():
    scene = {"rooms": [{"id": "r0", "area_sqft": 100.0}], "walls_poly": [], "meta": {}}
    out = A.compute_area_statement(scene)
    assert out["carpet_area"]["sqm"] == round(100 * A.SQFT_TO_SQM, 2)  # ~9.29


def test_builtup_falls_back_to_envelope():
    # no walls_poly -> use plan_width * plan_depth
    scene = {"rooms": [{"id": "r0", "area_sqft": 150.0}], "walls_poly": [],
             "meta": {"plan_width_ft": 20, "plan_depth_ft": 30}}
    out = A.compute_area_statement(scene)
    assert out["built_up_area"]["sqft"] == 600.0          # 20 * 30


def test_builtup_never_below_carpet():
    scene = {"rooms": [{"id": "r0", "area_sqft": 500.0}],
             "walls_poly": [{"outer": [[0, 0], [10, 0], [10, 10], [0, 10]]}],  # 100
             "meta": {}}
    out = A.compute_area_statement(scene)
    assert out["built_up_area"]["sqft"] >= out["carpet_area"]["sqft"]


def test_no_rooms_notes_and_zero_carpet():
    # no rooms AND no wall-interior holes -> genuinely 0, with the old note
    scene = {"rooms": [], "walls_poly": [{"outer": [[0, 0], [10, 0], [10, 10], [0, 10]]}],
             "meta": {}}
    out = A.compute_area_statement(scene)
    assert out["carpet_area"]["sqft"] == 0.0
    assert out["carpet_source"] == "none"
    assert any("No rooms" in n for n in out["notes"])
    assert out["disclaimer"]


def test_no_rooms_falls_back_to_wall_interior():
    # 20x15 outer ring with a 16x11 interior hole: carpet should come from the
    # hole (176 sqft) instead of showing a misleading 0.
    scene = {
        "rooms": [],
        "walls_poly": [{
            "outer": [[0, 0], [20, 0], [20, 15], [0, 15]],                 # 300
            "holes": [[[2, 2], [18, 2], [18, 13], [2, 13]]],               # 176
        }],
        "meta": {},
    }
    out = A.compute_area_statement(scene, loading_factor=1.30)
    assert out["carpet_area"]["sqft"] == 176.0
    assert out["carpet_source"] == "wall_interior"
    assert out["built_up_area"]["sqft"] == 300.0
    assert out["efficiency_pct"] > 0
    assert any("estimated from the enclosed area" in n for n in out["notes"])


def test_rooms_present_ignores_fallback():
    # detected rooms win — the fallback must never override real room areas
    scene = {
        "rooms": [{"id": "r0", "area_sqft": 90.0}],
        "walls_poly": [{"outer": [[0, 0], [20, 0], [20, 15], [0, 15]],
                        "holes": [[[2, 2], [18, 2], [18, 13], [2, 13]]]}],
        "meta": {},
    }
    out = A.compute_area_statement(scene)
    assert out["carpet_area"]["sqft"] == 90.0
    assert out["carpet_source"] == "rooms"
