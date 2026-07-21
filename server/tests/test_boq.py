"""Tests for the BOQ estimator — hand-computed quantities on a simple scene."""
import boq

# carpet 200 (two rooms 100+100), built-up 300 -> wall footprint 100 sqft
SCENE = {
    "meta": {"plan_width_ft": 20, "plan_depth_ft": 15, "wall_height_ft": 10.0,
             "scale": {"source": "dimension_text"}},
    "rooms": [{"id": "r0", "area_sqft": 100.0}, {"id": "r1", "area_sqft": 100.0}],
    "walls_poly": [{"outer": [[0, 0], [20, 0], [20, 15], [0, 15]]}],  # 300 sqft
}


def test_quantities_hand_computed():
    out = boq.compute_boq(SCENE)
    q = out["quantities"]
    assert q["wall_footprint_sqft"] == 100.0          # 300 - 200
    assert q["wall_volume_cuft"] == 1000.0            # 100 x 10ft height
    assert q["bricks_pcs"] == 12500                   # 1000 x 12.5
    assert q["wall_length_ft"] == 200.0               # 100 / 0.5
    assert q["plaster_area_sqft"] == 4000.0           # 2 x 200 x 10
    assert q["flooring_sqft"] == 200.0                # carpet


def test_costs_positive_and_labour_factor_applied():
    out = boq.compute_boq(SCENE)
    c = out["cost_inr"]
    assert c["material"] > 0
    assert c["total_with_labour"] == int(round(c["material"] * 1.35))


def test_rate_override():
    out = boq.compute_boq(SCENE, rates={"labour_factor": 1.0, "brick_pc": 10.0})
    assert out["cost_inr"]["total_with_labour"] == out["cost_inr"]["material"]
    assert out["cost_inr"]["rates_used"]["brick_pc"] == 10.0


def test_empty_scene_degrades_to_zero():
    out = boq.compute_boq({"meta": {}, "rooms": [], "walls_poly": []})
    assert out["quantities"]["bricks_pcs"] == 0
    assert out["disclaimer"]
