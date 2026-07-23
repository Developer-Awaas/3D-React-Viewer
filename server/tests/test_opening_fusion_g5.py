"""G5 cross-reader opening fusion: a door/window found by the LOSING reader is
added onto the winner's walls (deduped), so openings seen by either model
survive. Pure tests."""
import opening_fusion as F


def _winner():
    """4-wall box; winner found only ONE door (on the south wall w0)."""
    return {
        "meta": {}, "walls": [
            {"id": "w0", "axis": "x", "x0": 0, "x1": 20, "y0": 0, "y1": 0.5},
            {"id": "w1", "axis": "x", "x0": 0, "x1": 20, "y0": 15, "y1": 15.5},
            {"id": "w2", "axis": "y", "x0": 0, "x1": 0.5, "y0": 0, "y1": 15},
            {"id": "w3", "axis": "y", "x0": 19.5, "x1": 20, "y0": 0, "y1": 15},
        ],
        "openings": [{"id": "o0", "type": "door", "wall": "w0",
                      "along": [8, 11], "z": [0, 7]}],
    }


def _other_with_extra_door_and_window():
    """Same building; this reader found the SAME south door (dup) PLUS a north
    door (w1) and an east window (w3) the winner missed."""
    return {
        "walls": [
            {"id": "a0", "axis": "x", "x0": 0, "x1": 20, "y0": 0, "y1": 0.5},
            {"id": "a1", "axis": "x", "x0": 0, "x1": 20, "y0": 15, "y1": 15.5},
            {"id": "a3", "axis": "y", "x0": 19.5, "x1": 20, "y0": 0, "y1": 15},
        ],
        "openings": [
            {"id": "b0", "type": "door", "wall": "a0", "along": [8.2, 11.2], "z": [0, 7]},   # dup
            {"id": "b1", "type": "door", "wall": "a1", "along": [9, 12], "z": [0, 7]},        # NEW
            {"id": "b2", "type": "window", "wall": "a3", "along": [6, 9], "z": [3, 7]},        # NEW
        ],
    }


def test_fusion_adds_missing_openings_and_dedups():
    win, n = F.augment_openings(_winner(), [_other_with_extra_door_and_window()])
    assert n == 2                                     # north door + east window, not the dup
    fused = [o for o in win["openings"] if o.get("fused")]
    assert {o["type"] for o in fused} == {"door", "window"}
    # the new north door landed on the winner's north wall w1
    nd = next(o for o in fused if o["type"] == "door")
    assert nd["wall"] == "w1"


def test_no_host_wall_is_skipped():
    win = _winner()
    other = {"walls": [{"id": "x", "axis": "x", "x0": 0, "x1": 5, "y0": 99, "y1": 99.5}],
             "openings": [{"id": "z", "type": "door", "wall": "x", "along": [1, 4], "z": [0, 7]}]}
    _w, n = F.augment_openings(win, [other])
    assert n == 0                                     # wall at y=99 matches no winner wall


def test_vector_scene_no_axis_walls_is_noop():
    win = {"meta": {}, "walls": [], "walls_poly": [{"outer": []}], "openings": []}
    _w, n = F.augment_openings(win, [_other_with_extra_door_and_window()])
    assert n == 0


def test_fused_door_has_hinge_for_leaf():
    win, _ = F.augment_openings(_winner(), [_other_with_extra_door_and_window()])
    nd = next(o for o in win["openings"] if o.get("fused") and o["type"] == "door")
    assert "hinge" in nd                              # so scene_to_glb builds a leaf
