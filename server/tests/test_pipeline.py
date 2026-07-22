"""Tests for the analysis pipeline — the single structured block per plan."""
import pipeline


def _scene(w=40, d=50, rooms=3, typed=2, doors=4, windows=3,
           scale_src="dimension_text"):
    rms = [{"id": f"r{i}", "area_sqft": 120} for i in range(rooms)]
    for i in range(min(typed, rooms)):
        rms[i]["type"] = "bedroom"
    ops = [{"type": "door"} for _ in range(doors)] + \
          [{"type": "window"} for _ in range(windows)]
    return {
        "meta": {"plan_width_ft": w, "plan_depth_ft": d, "reader": "vector",
                 "scale": {"source": scale_src}, "warnings": []},
        "rooms": rms, "openings": ops, "furniture": [1, 2],
        "walls_poly": [{"outer": [[0, 0], [w, 0], [w, d], [0, d]]}],
    }


def test_analyze_extracts_all_fields():
    a = pipeline.analyze(_scene())
    assert a["reader"] == "vector"
    assert a["health"]["ok"] is True
    assert a["needs_review"] is False
    assert a["rooms"]["count"] == 3
    assert a["rooms"]["typed"] == {"bedroom": 2}
    assert a["openings"] == {"doors": 4, "windows": 3}
    assert a["area"]["carpet_sqft"] > 0
    assert 0 <= a["quality_score"] <= 100


def test_healthy_plan_scores_high():
    assert pipeline.analyze(_scene())["quality_score"] >= 80


def test_flagged_plan_scores_low_and_needs_review():
    bad = _scene(w=5, rooms=0, doors=0, scale_src="assumed_width")
    a = pipeline.analyze(bad)
    assert a["needs_review"] is True
    assert a["quality_score"] < 50
    assert "no_rooms" in a["health"]["flags"]


def test_assumed_scale_penalized():
    hi = pipeline.analyze(_scene(scale_src="dimension_text"))["quality_score"]
    lo = pipeline.analyze(_scene(scale_src="assumed_width"))["quality_score"]
    assert lo < hi
