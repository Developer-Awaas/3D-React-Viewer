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
    assert out["super_built_up_area"]["sqft"] == 390.0    # 300 * 1.30
    assert out["wall_and_circulation"]["sqft"] == 100.0   # 300 - 200
    assert out["efficiency_pct"] == round(100 * 200 / 390, 1)


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
    scene = {"rooms": [], "walls_poly": [{"outer": [[0, 0], [10, 0], [10, 10], [0, 10]]}],
             "meta": {}}
    out = A.compute_area_statement(scene)
    assert out["carpet_area"]["sqft"] == 0.0
    assert any("No rooms" in n for n in out["notes"])
    assert out["disclaimer"]
