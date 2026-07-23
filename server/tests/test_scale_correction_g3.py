"""G3 scale auto-correction: a GUESSED scale cross-checked against snapped-door
widths -> flag (default) or rescale (DRISHTI_AUTOSCALE=1). Pure tests."""
import copy

import pdf_vector as P
import plan_doctor as PD


def _door(w_ft):
    return {"type": "door", "snapped": True, "footprint": [0, 0, w_ft, 0.5]}


def _scene(scale_src, door_ft, n=6):
    return {
        "meta": {"plan_width_ft": 60.0, "plan_depth_ft": 40.0,
                 "scale": {"source": scale_src, "pt_per_ft": 5.0}, "warnings": []},
        "openings": [_door(door_ft) for _ in range(n)],
        "walls_poly": [{"outer": [[0, 0], [60, 0], [60, 40], [0, 40]], "holes": []}],
        "rooms": [{"id": "r0", "x": 30, "y": 20, "area_sqft": 400}],
        "columns": [{"id": "c0", "x": 5, "y": 5, "w": 1, "d": 1}],
        "furniture": [], "walls": [], "ducts": [],
    }


def test_verified_scale_never_flagged():
    s = P._apply_scale_correction(_scene("dimension_text", 4.5))
    assert "needs_review" not in s["meta"]["scale"]        # only guessed scales


def test_good_doors_on_guessed_scale_pass():
    s = P._apply_scale_correction(_scene("column_box_12in", 3.0))
    assert "needs_review" not in s["meta"]["scale"]


def test_oversize_doors_flag_needs_review(monkeypatch):
    monkeypatch.delenv("DRISHTI_AUTOSCALE", raising=False)
    s = P._apply_scale_correction(_scene("column_box_12in", 4.5))   # 1.5x too big
    sc = s["meta"]["scale"]
    assert sc["needs_review"] is True
    assert sc["implied_oversize"] == 1.5
    assert abs(sc["suggested_factor"] - (3.0 / 4.5)) < 1e-3
    # flag-only: geometry unchanged
    assert s["meta"]["plan_width_ft"] == 60.0
    assert any("NEEDS REVIEW" in w for w in s["meta"]["warnings"])


def test_autoscale_applies_correction(monkeypatch):
    monkeypatch.setenv("DRISHTI_AUTOSCALE", "1")
    s = P._apply_scale_correction(_scene("column_box_12in", 4.5))
    sc = s["meta"]["scale"]
    k = 3.0 / 4.5
    assert "door_corrected" in sc["source"]
    assert abs(s["meta"]["plan_width_ft"] - 60.0 * k) < 0.05     # 60 -> 40
    assert abs(s["rooms"][0]["area_sqft"] - 400 * k * k) < 1.0   # area ~ k^2
    assert abs(s["columns"][0]["w"] - 1.0 * k) < 0.01


def test_rescale_scales_every_field():
    s = _scene("column_box_12in", 4.5)
    s["openings"][0]["along"] = [10.0, 13.0]
    s["walls"] = [{"x0": 0, "x1": 10, "y0": 0, "y1": 0.5}]
    before = copy.deepcopy(s)
    P._rescale_scene_ft(s, 0.5)
    assert s["meta"]["plan_width_ft"] == 30.0
    assert s["walls_poly"][0]["outer"][1] == [30.0, 0.0]
    assert s["openings"][0]["along"] == [5.0, 6.5]
    assert s["walls"][0]["x1"] == 5.0
    assert s["rooms"][0]["area_sqft"] == round(400 * 0.25, 1)
    # identity factor is a no-op
    again = P._rescale_scene_ft(copy.deepcopy(before), 1.0)
    assert again["meta"]["plan_width_ft"] == 60.0


def test_doctor_flags_scale_mismatch():
    s = P._apply_scale_correction(_scene("column_box_12in", 4.5))
    d = PD.diagnose(s)
    assert "scale_door_mismatch" in d["learn_tags"]
    assert d["grade"] in ("D", "F")
