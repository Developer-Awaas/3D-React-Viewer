"""E5: CubiCasa's room-type map -> typed rooms in the ML scene (was discarded).
Pure tests with synthetic maps + scene_builder wiring (no torch/GPU)."""
import numpy as np

import perception
import plan_health
import scene_builder as SB


def _room_map():
    """40x40 label map: a Kitchen block and a Bed Room block (class indices
    from perception.ROOM_CLASSES)."""
    m = np.zeros((40, 40), dtype=int)
    ki = perception.ROOM_CLASSES.index("Kitchen")
    bi = perception.ROOM_CLASSES.index("Bed Room")
    m[2:18, 2:18] = ki           # top-left kitchen
    m[22:38, 22:38] = bi         # bottom-right bedroom
    return m


def test_rooms_from_pred_types_and_positions():
    rooms = perception.rooms_from_pred(_room_map(), min_area_frac=0.0)
    types = sorted(r["type"] for r in rooms)
    assert types == ["bedroom", "kitchen"]
    ki = next(r for r in rooms if r["type"] == "kitchen")
    assert 9 < ki["cx"] < 11 and 9 < ki["cy"] < 11      # centroid ~ (10,10)
    assert ki["area_px"] == 16 * 16


def test_speckle_below_min_area_is_dropped():
    m = np.zeros((100, 100), dtype=int)
    m[0:2, 0:2] = perception.ROOM_CLASSES.index("Kitchen")   # 4 px speck
    assert perception.rooms_from_pred(m) == []               # below min_area


def test_scene_builder_converts_rooms_to_feet():
    rooms_px = [{"type": "kitchen", "cx": 50.0, "cy": 25.0, "area_px": 400}]
    # 100px wide plan declared 20ft -> 0.2 ft/px
    scene = SB.scene_from_segments([[0, 0, 100, 0]], 100, 50, width_ft=20.0,
                                   rooms_px=rooms_px)
    assert len(scene["rooms"]) == 1
    r = scene["rooms"][0]
    assert r["type"] == "kitchen"
    assert r["x"] == 10.0                          # 50 * 0.2
    assert r["y"] == 5.0                           # (50-25) * 0.2, Y-flipped
    assert r["area_sqft"] == 16.0                  # 400 * 0.2^2


def test_scene_builder_no_rooms_keeps_old_behaviour():
    scene = SB.scene_from_segments([[0, 0, 100, 0]], 100, 50, width_ft=20.0)
    assert scene["rooms"] == []
    assert "rooms/furniture not yet extracted" in scene["meta"]["warnings"]


def test_typed_ml_rooms_lift_health_score():
    """The whole point: an ML scene WITH typed rooms scores higher and clears
    the no_rooms flag that used to sink every photo parse."""
    walls_seg = [[0, 0, 100, 0], [0, 0, 0, 50], [100, 0, 100, 50], [0, 50, 100, 50]]
    rooms_px = [{"type": "bedroom", "cx": 50, "cy": 25, "area_px": 3000}]
    with_rooms = SB.scene_from_segments(walls_seg, 100, 50, 60.0,
                                        openings=[], rooms_px=rooms_px)
    without = SB.scene_from_segments(walls_seg, 100, 50, 60.0, openings=[])
    assert "no_rooms" in plan_health.health_flags(without)
    assert "no_rooms" not in plan_health.health_flags(with_rooms)
    assert plan_health.score_scene(with_rooms) > plan_health.score_scene(without)
