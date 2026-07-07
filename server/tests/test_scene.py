"""Tests for Step B scene builder (pure - no GPU/OpenCV/trimesh needed)."""
from scene_builder import scene_from_segments


def test_box_walls_count_and_types():
    segs = [[20, 23, 380, 23], [20, 277, 380, 277],
            [23, 20, 23, 280], [377, 20, 377, 280],
            [200, 40, 200, 260]]           # 4 outer + 1 interior
    s = scene_from_segments(segs, 400, 300, 40.0)
    assert len(s["walls"]) == 5
    assert sum(w["type"] == "external" for w in s["walls"]) == 4
    assert sum(w["type"] == "internal" for w in s["walls"]) == 1
    assert s["meta"]["units"] == "ft"


def test_scale_and_y_flip():
    s = scene_from_segments([[0, 0, 100, 0]], 100, 100, 10.0)  # 0.1 ft/px
    w = s["walls"][0]
    assert w["x0"] == 0.0 and w["x1"] == 10.0        # scaled to feet
    assert w["y0"] > 0                                # top of image -> high y (flipped)


def test_empty_plan():
    s = scene_from_segments([], 100, 100, 40.0)
    assert s["walls"] == [] and s["openings"] == []


# --- Step B2: openings ---
def test_door_opening_on_horizontal_wall():
    s = scene_from_segments([[10, 50, 90, 50]], 100, 100, 10.0,
                            openings=[{"type": "door", "seg": 0, "along": [40, 55]}])
    assert len(s["openings"]) == 1
    o = s["openings"][0]
    assert o["wall"] == "w0" and o["type"] == "door"
    assert o["along"] == [4.0, 5.5]                 # 0.1 ft/px
    assert o["z"][0] == 0 and 6.5 < o["z"][1] < 7.5  # ~2.1 m door head
    assert o["hinge"] == "x0" and o["swing"] == "in"


def test_window_opening_on_vertical_wall_y_flip():
    s = scene_from_segments([[50, 10, 50, 90]], 100, 100, 10.0,
                            openings=[{"type": "window", "seg": 0, "along": [30, 60]}])
    o = s["openings"][0]
    assert o["along"] == [4.0, 7.0]                 # y-flipped and sorted
    assert o["z"][0] > 0                            # window has a sill
    w = s["walls"][0]
    assert w["y0"] <= o["along"][0] and o["along"][1] <= w["y1"]


def test_opening_clamped_and_tiny_dropped():
    s = scene_from_segments([[10, 50, 90, 50]], 100, 100, 10.0,
                            openings=[{"type": "door", "seg": 0, "along": [0, 200]},
                                      {"type": "door", "seg": 0, "along": [40, 40.5]}])
    assert len(s["openings"]) == 1
    o = s["openings"][0]
    w = s["walls"][0]
    assert o["along"] == [w["x0"], w["x1"]]         # clamped to the wall


def test_glb_boxes_skip_the_door_void():
    from scene_to_glb import interval_boxes
    s = scene_from_segments([[10, 50, 90, 50]], 100, 100, 10.0,
                            openings=[{"type": "door", "seg": 0, "along": [40, 55]}])
    H = s["meta"]["wall_height_ft"]
    boxes = interval_boxes(s["walls"][0], H, s["openings"])
    # no solid box may fill the doorway below the door head
    for x0, x1, _, _, z0, z1 in boxes:
        inside = max(x0, 4.0) < min(x1, 5.5)
        assert not (inside and z0 < s["openings"][0]["z"][1])


# --- Step B2: corner snapping ---
def test_corner_walls_meet():
    s = scene_from_segments([[20, 20, 380, 20], [20, 20, 20, 280]], 400, 300, 40.0)
    xw = next(w for w in s["walls"] if w["axis"] == "x")
    yw = next(w for w in s["walls"] if w["axis"] == "y")
    assert xw["x0"] <= yw["x0"]                     # x-wall reaches across y-wall
    assert yw["y1"] >= xw["y1"]                     # y-wall reaches up to x-wall
