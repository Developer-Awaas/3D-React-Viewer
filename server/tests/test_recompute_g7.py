"""G7 user corrections: /recompute applies true-width rescale, room-type edits
and phantom-room deletes, then returns fresh area/vastu/boq/diagnosis. Pure
corrections tests + endpoint contract."""
import copy

from fastapi.testclient import TestClient

import corrections as C
import main


def _scene():
    return {
        "meta": {"plan_width_ft": 60.0, "plan_depth_ft": 40.0,
                 "wall_height_ft": 9.84,
                 "scale": {"source": "column_box_12in", "pt_per_ft": 5.0},
                 "warnings": []},
        "walls_poly": [{"outer": [[0, 0], [60, 0], [60, 40], [0, 40]], "holes": []}],
        "rooms": [
            {"id": "r0", "type": "bedroom", "x": 15, "y": 20, "area_sqft": 600},
            {"id": "r1", "type": None, "x": 45, "y": 20, "area_sqft": 500},
            {"id": "r2", "type": "bathroom", "x": 5, "y": 5, "area_sqft": 4},  # phantom
        ],
        "openings": [], "columns": [], "furniture": [], "walls": [], "ducts": [],
    }


# ---- pure corrections -------------------------------------------------------
def test_true_width_rescales_everything():
    s, info = C.apply_corrections(_scene(), {"true_width_ft": 30.0})   # half size
    assert s["meta"]["plan_width_ft"] == 30.0
    assert s["meta"]["plan_depth_ft"] == 20.0
    assert abs(info["scale_factor"] - 0.5) < 1e-6
    assert s["rooms"][0]["area_sqft"] == round(600 * 0.25, 1)          # area ~ k^2
    assert "user_width" in s["meta"]["scale"]["source"]


def test_true_width_clears_g3_flag():
    s = _scene()
    s["meta"]["scale"]["needs_review"] = True
    s["meta"]["scale"]["suggested_factor"] = 0.6
    s2, _ = C.apply_corrections(s, {"true_width_ft": 45.0})
    assert "needs_review" not in s2["meta"]["scale"]                    # human fixed it


def test_room_type_edit_and_clear():
    s, _ = C.apply_corrections(_scene(), {"room_types": {"r1": "kitchen", "r0": ""}})
    by = {r["id"]: r for r in s["rooms"]}
    assert by["r1"]["type"] == "kitchen"
    assert "type" not in by["r0"] or by["r0"].get("type") is None


def test_invalid_room_type_rejected():
    try:
        C.apply_corrections(_scene(), {"room_types": {"r1": "dungeon"}})
        assert False, "should reject"
    except ValueError:
        pass


def test_delete_phantom_room():
    s, info = C.apply_corrections(_scene(), {"delete_rooms": ["r2"]})
    assert [r["id"] for r in s["rooms"]] == ["r0", "r1"]
    assert any("deleted" in a for a in info["applied"])


def test_identity_width_is_noop():
    s, info = C.apply_corrections(_scene(), {"true_width_ft": 60.0})
    assert "scale_factor" not in info                                  # no rescale


# ---- endpoint ---------------------------------------------------------------
def _client():
    return TestClient(main.app)


def test_recompute_endpoint_rescales_and_reanalyzes():
    body = {"scene": _scene(), "corrections": {"true_width_ft": 30.0}}
    r = _client().post("/recompute", json=body)
    assert r.status_code == 200
    out = r.json()
    assert out["meta"]["plan_width_ft"] == 30.0
    assert "area_statement" in out and "diagnosis" in out
    assert out["meta"]["correction_info"]["applied"]


def test_recompute_delete_updates_efficiency():
    base = _client().post("/recompute", json={"scene": _scene(), "corrections": {}}).json()
    fixed = _client().post("/recompute",
                           json={"scene": _scene(),
                                 "corrections": {"delete_rooms": ["r2"]}}).json()
    # dropping the 4-sqft phantom changes carpet -> the statement recomputes
    assert base["area_statement"]["carpet_area"]["sqft"] != \
        fixed["area_statement"]["carpet_area"]["sqft"]


def test_recompute_rejects_bad_body():
    assert _client().post("/recompute", json={"scene": {}}).status_code == 422
    assert _client().post("/recompute",
                          json={"scene": _scene(),
                                "corrections": {"true_width_ft": -5}}).status_code == 422
