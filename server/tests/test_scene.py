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
