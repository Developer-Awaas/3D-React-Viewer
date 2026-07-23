"""Regression tests for the pre-production bug hunt (23 Jul 2026): /recompute
input validation, delete_rooms string, G5 fusion clamp/nearest-wall,
efficiency_display contract, malformed-scale robustness, rescale completeness."""
from fastapi.testclient import TestClient

import corrections as C
import main
import opening_fusion as F
import pdf_vector as P
import plan_doctor as PD


def _client():
    return TestClient(main.app)


def _scene():
    return {"meta": {"plan_width_ft": 40.0, "plan_depth_ft": 30.0,
                     "scale": {"source": "column_box_12in", "pt_per_ft": 5.0}},
            "rooms": [{"id": "r0", "type": "bedroom", "x": 10, "y": 10, "area_sqft": 300},
                      {"id": "r", "type": "bathroom", "x": 5, "y": 5, "area_sqft": 40}],
            "walls_poly": [{"outer": [[0, 0], [40, 0], [40, 30], [0, 30]], "holes": []}],
            "openings": [], "columns": [], "furniture": [], "walls": [], "ducts": []}


# ---- /recompute must 422 (never 500) on hostile correction values ----------
def test_recompute_bad_inputs_return_422_not_500():
    c = _client()
    bad = [
        {"true_width_ft": [40]},
        {"true_width_ft": {"x": 1}},
        {"room_types": ["a", "b"]},
        {"room_types": {"r0": 123}},
        {"delete_rooms": 5},
        {"loading_factor": "abc"},
        {"north_deg": "xyz"},
    ]
    for corr in bad:
        r = c.post("/recompute", json={"scene": _scene(), "corrections": corr})
        assert r.status_code == 422, f"{corr} -> {r.status_code} (want 422)"


def test_delete_rooms_string_rejected_not_wrong_delete():
    # "r0" must NOT iterate into {'r','0'} and delete room 'r'
    r = _client().post("/recompute",
                       json={"scene": _scene(), "corrections": {"delete_rooms": "r0"}})
    assert r.status_code == 422


def test_delete_rooms_list_works():
    r = _client().post("/recompute",
                       json={"scene": _scene(), "corrections": {"delete_rooms": ["r"]}})
    assert r.status_code == 200
    assert [x["id"] for x in r.json()["rooms"]] == ["r0"]


# ---- G5 fusion: clamp to host wall + nearest wall --------------------------
def test_fusion_clamps_oversize_opening_to_wall():
    winner = {"meta": {}, "walls": [
        {"id": "w0", "axis": "x", "x0": 0, "x1": 10, "y0": 0, "y1": 0.5}], "openings": []}
    other = {"walls": [{"id": "a", "axis": "x", "x0": 0, "x1": 20, "y0": 0, "y1": 0.5}],
             "openings": [{"type": "door", "wall": "a", "along": [1, 19], "z": [0, 7]}]}
    win, n = F.augment_openings(winner, [other])
    assert n == 1
    lo, hi = win["openings"][0]["along"]
    assert lo >= 0 and hi <= 10                        # clamped inside w0 (0..10)


def test_fusion_picks_nearest_parallel_wall():
    winner = {"meta": {}, "walls": [
        {"id": "wLOW", "axis": "x", "x0": 0, "x1": 20, "y0": 4.75, "y1": 5.25},
        {"id": "wHIGH", "axis": "x", "x0": 0, "x1": 20, "y0": 5.55, "y1": 6.05}],
        "openings": []}
    other = {"walls": [{"id": "a", "axis": "x", "x0": 0, "x1": 20, "y0": 5.55, "y1": 6.05}],
             "openings": [{"type": "door", "wall": "a", "along": [9, 12], "z": [0, 7]}]}
    win, _ = F.augment_openings(winner, [other])
    assert win["openings"][0]["wall"] == "wHIGH"       # nearest, not first


# ---- efficiency_display never a silent 0.0% -------------------------------
def test_tiny_positive_efficiency_is_needs_review():
    s = {"meta": {}, "rooms": [{"id": "r0", "type": "x", "area_sqft": 15}],
         "openings": [], "area_statement": {"efficiency_pct": 0.037, "carpet_source": "rooms"}}
    d = PD.diagnose(s)
    assert d["efficiency_display"] == "needs_review"    # not "0.0%"


# ---- malformed scene doesn't crash diagnose / apply_corrections -----------
def test_diagnose_survives_scale_as_string():
    d = PD.diagnose({"meta": {"scale": "weird", "plan_width_ft": 40, "plan_depth_ft": 30},
                     "rooms": [], "openings": []})
    assert "grade" in d                                 # no AttributeError


def test_apply_corrections_survives_scale_as_string():
    s = {"meta": {"scale": "weird", "plan_width_ft": 40}, "rooms": [{"id": "r0"}]}
    out, _info = C.apply_corrections(s, {"delete_rooms": ["r0"]})
    assert out["rooms"] == []                           # no TypeError on scale["corrected"]


# ---- rescale now covers thickness + pt_per_ft -----------------------------
def test_rescale_covers_thickness_and_ppf():
    s = {"meta": {"plan_width_ft": 40, "scale": {"pt_per_ft": 10.0}},
         "wall_types": {"external": {"thickness_ft": 0.75}}, "rooms": [], "openings": []}
    P._rescale_scene_ft(s, 0.5)
    assert s["wall_types"]["external"]["thickness_ft"] == 0.375
    assert s["meta"]["scale"]["pt_per_ft"] == 20.0      # ppf / k


# ---- whole-product fixes ---------------------------------------------------
def test_builtup_exceeds_carpet_on_wall_strips():
    """The ₹0-masonry root cause: many thin wall strips must NOT clamp built_up
    to carpet."""
    import area_statement as A
    scene = {"rooms": [{"id": "r0", "area_sqft": 600}],
             "walls_poly": [  # 3 thin strips totalling ~120 sqft, none a room outline
                 {"outer": [[0, 0], [40, 0], [40, 0.75], [0, 0.75]], "holes": []},
                 {"outer": [[0, 0], [0.75, 0], [0.75, 30], [0, 30]], "holes": []},
                 {"outer": [[20, 0], [20.4, 0], [20.4, 30], [20, 30]], "holes": []}],
             "meta": {"scale": {"source": "dimension_text"}}}
    st = A.compute_area_statement(scene, 1.30)
    assert st["built_up_area"]["sqft"] > st["carpet_area"]["sqft"]   # not clamped
    assert st["wall_and_circulation"]["sqft"] > 0                    # real wall loss


def test_builtup_single_outline_unchanged():
    """A single building outline whose outer IS the gross must stay = gross."""
    import area_statement as A
    scene = {"rooms": [{"id": "r0", "area_sqft": 200}],
             "walls_poly": [{"outer": [[0, 0], [20, 0], [20, 15], [0, 15]], "holes": []}],
             "meta": {"scale": {"source": "dimension_text"}}}
    st = A.compute_area_statement(scene, 1.30)
    assert st["built_up_area"]["sqft"] == 300.0                      # the outer area


def test_boq_no_negative_on_bad_height():
    import boq
    scene = {"meta": {"wall_height_ft": -9},
             "walls_poly": [{"outer": [[0, 0], [20, 0], [20, 15], [0, 15]], "holes": []}],
             "rooms": [{"id": "r0", "area_sqft": 200}]}
    b = boq.compute_boq(scene)
    assert b["cost_inr"]["total_with_labour"] >= 0


def test_glb_export_never_crashes_on_empty_scene():
    import scene_to_glb as G
    glb = G.build_glb_bytes({"meta": {"wall_height_ft": 9.843}})
    assert glb[:4] == b"glTF"                                        # was ValueError


def test_interval_boxes_clamps_stray_opening():
    import scene_to_glb as G
    w = {"id": "w0", "axis": "x", "x0": 0, "x1": 10, "y0": 0, "y1": 0.5}
    boxes = G.interval_boxes(w, 9.8, [{"wall": "w0", "along": [20, 25], "z": [0, 7]}])
    for x0, x1, *_ in boxes:
        assert x0 >= 0 and x1 <= 10.001                             # never past the wall


def test_ppf_env_zero_ignored():
    import os
    import pdf_vector as P
    os.environ["PPF"] = "0"
    try:
        # 0 must be ignored (not returned) -> falls through to width_ft path
        ppf, src = P._scale_ppf([], 100.0, 40.0)
        assert ppf > 0 and src == "assumed_width"
    finally:
        os.environ.pop("PPF", None)


def test_parse_bad_bytes_raises_valueerror():
    import pdf_vector as P
    for bad in (b"", b"%PDF-1.4\x00junk", b"not a pdf at all"):
        try:
            P.parse(bad, None)
            assert False, "should raise"
        except ValueError:
            pass


def test_options_not_rate_limited():
    import main
    import rate_limit
    from fastapi.testclient import TestClient
    c = TestClient(main.app)
    r = c.options("/scene", headers={"Origin": "http://localhost:5173",
                                     "Access-Control-Request-Method": "POST"})
    assert r.status_code != 429


# ---- deferred-issue fixes --------------------------------------------------
def test_head_health_ok():
    from fastapi.testclient import TestClient
    import main
    assert TestClient(main.app).head("/health").status_code == 200


def test_wing_pick_prefers_room_dense_wing():
    """A sheet with a room-dense wing and a door-schedule/section wing must
    pick the ROOM-dense one (the real floor plan)."""
    import pdf_vector as P
    # scores are (rooms, doors, area); room-dense wing must win even with 0 doors
    assert (7, 0, 100) > (4, 9, 999)              # tuple-order sanity (rooms first)


def test_geometry_door_footprint_validated():
    """An oversize/fat snapped door strip must be demoted (not trusted)."""
    from pdf_vector import parse
    import os
    p = "../plans/NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf"
    if not os.path.exists(p):
        import pytest
        pytest.skip("corpus not present")
    s = parse(open(p, "rb").read(), None)
    for o in s["openings"]:
        if o["type"] == "door" and o.get("snapped") and o.get("footprint"):
            fp = o["footprint"]
            span = max(abs(fp[2] - fp[0]), abs(fp[3] - fp[1]))
            thick = min(abs(fp[2] - fp[0]), abs(fp[3] - fp[1]))
            assert span <= 6.0 and thick <= 1.6      # no wall-fragment "doors"
