"""Tests for Step B2 - door/window openings (pure logic + one cv2 test)."""
from openings import (attach_openings, bridge_gaps, match_openings,
                      _norm, boxes_from_mask)


def _door(x0, y0, x1, y1):
    return {"type": "door", "x0": x0, "y0": y0, "x1": x1, "y1": y1}


def _window(x0, y0, x1, y1):
    return {"type": "window", "x0": x0, "y0": y0, "x1": x1, "y1": y1}


# --- boxes_from_mask (needs numpy + OpenCV; runs in CI like test_walls) ---
def test_boxes_from_mask_finds_door_and_window():
    import numpy as np
    m = np.zeros((100, 200), dtype=int)
    m[40:50, 20:50] = 2      # door blob
    m[40:48, 120:160] = 1    # window blob
    boxes = boxes_from_mask(m, min_area=30)
    types = sorted(b["type"] for b in boxes)
    assert types == ["door", "window"]
    d = next(b for b in boxes if b["type"] == "door")
    assert (d["x0"], d["y0"], d["x1"], d["y1"]) == (20, 40, 50, 50)


def test_boxes_from_mask_drops_tiny_specks():
    import numpy as np
    m = np.zeros((100, 100), dtype=int)
    m[10:12, 10:12] = 2      # 4 px - noise
    assert boxes_from_mask(m, min_area=30) == []


# --- matching ---
def test_door_attaches_to_horizontal_wall():
    segs = [[10, 50, 90, 50]]
    _, ops = attach_openings(segs, [_door(40, 44, 55, 56)], tol=10)
    assert len(ops) == 1
    assert ops[0]["type"] == "door" and ops[0]["seg"] == 0
    assert ops[0]["along"] == [40, 55]


def test_window_attaches_to_vertical_wall():
    segs = [[50, 10, 50, 90]]                      # vertical wall at x=50
    _, ops = attach_openings(segs, [_window(44, 30, 56, 60)], tol=10)
    assert len(ops) == 1
    assert ops[0]["seg"] == 0 and ops[0]["along"] == [30, 60]


def test_far_box_is_dropped():
    segs = [[10, 50, 90, 50]]
    _, ops = attach_openings(segs, [_door(40, 80, 55, 95)], tol=10)   # 37 px away
    assert ops == []


def test_opening_clamped_to_wall_extent():
    segs = [[10, 50, 60, 50]]
    _, ops = attach_openings(segs, [_door(50, 44, 80, 56)], tol=10)   # sticks out
    assert ops[0]["along"] == [50, 60]


def test_nearest_wall_wins():
    segs = [[10, 50, 90, 50], [10, 58, 90, 58]]
    _, ops = attach_openings(segs, [_door(40, 46, 55, 53)], tol=10)   # centre y=49.5
    assert len(ops) == 1 and ops[0]["seg"] == 0


def test_overlapping_openings_merge_door_wins():
    segs = [[10, 50, 200, 50]]
    boxes = [_window(40, 45, 70, 55), _door(60, 45, 100, 55)]
    _, ops = attach_openings(segs, boxes, tol=10)
    assert len(ops) == 1
    assert ops[0]["type"] == "door" and ops[0]["along"] == [40, 100]


# --- bridging: a door detection spanning a gap fuses the two wall pieces ---
def test_door_bridges_gap_between_collinear_walls():
    segs = [[10, 50, 40, 50], [60, 50, 100, 50]]   # doorway gap 40..60
    boxes = [_door(38, 45, 62, 55)]
    out_segs, ops = attach_openings(segs, boxes, tol=10)
    assert len(out_segs) == 1                      # merged into ONE wall
    assert out_segs[0][0] == 10 and out_segs[0][2] == 100
    assert len(ops) == 1 and ops[0]["along"] == [38, 62]


def test_no_bridge_without_covering_box():
    segs = [[10, 50, 40, 50], [60, 50, 100, 50]]
    out_segs, ops = attach_openings(segs, [_door(70, 45, 90, 55)], tol=10)
    assert len(out_segs) == 2                      # gap stays open
    assert len(ops) == 1 and ops[0]["seg"] == 1


def test_bridge_only_same_orientation():
    segs = [[10, 50, 40, 50], [50, 60, 50, 100]]   # horizontal + vertical
    out_segs, _ = attach_openings(segs, [_door(38, 45, 62, 65)], tol=10)
    assert len(out_segs) == 2


def test_empty_inputs():
    assert attach_openings([], [], tol=10) == ([], [])
    segs, ops = attach_openings([[0, 5, 50, 5]], [], tol=10)
    assert len(segs) == 1 and ops == []
