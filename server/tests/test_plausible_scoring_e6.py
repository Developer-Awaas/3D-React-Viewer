"""E6: plan_health rewards PLAUSIBLE rooms only, capped, so a noisy over-
detecting reader can't win best-of by inventing count."""
import plan_health as ph


def _scene(rooms, doors=4, w=40, d=50):
    return {"meta": {"plan_width_ft": w, "plan_depth_ft": d},
            "rooms": rooms, "openings": [{"type": "door"}] * doors}


def test_tiny_rooms_do_not_count():
    junk = _scene([{"id": "r0", "area_sqft": 3.0}])          # a 3 sqft "room"
    assert ph.plausible_room_count(junk) == 0
    assert "no_rooms" in ph.health_flags(junk)               # junk -> unhealthy


def test_missing_area_counts_as_plausible():
    # vector/legacy rooms without area must behave exactly as before
    s = _scene([{"id": "r0"}, {"id": "r1"}])
    assert ph.plausible_room_count(s) == 2
    assert "no_rooms" not in ph.health_flags(s)


def test_score_caps_room_overdetection():
    real = _scene([{"id": f"r{i}", "area_sqft": 120} for i in range(8)])
    spam = _scene([{"id": f"r{i}", "area_sqft": 120} for i in range(80)])
    # capped: 80 hallucinated rooms can't score arbitrarily higher than 8 real
    assert ph.score_scene(spam) - ph.score_scene(real) <= 2 * ph.ROOM_SCORE_CAP
    assert ph.score_scene(spam) == 2 * ph.ROOM_SCORE_CAP + 4


def test_real_reader_beats_shaft_hallucinator():
    real = _scene([{"id": f"r{i}", "area_sqft": 130} for i in range(5)], doors=6)
    shafts = _scene([{"id": f"r{i}", "area_sqft": 4} for i in range(40)], doors=0)
    assert ph.score_scene(real) > ph.score_scene(shafts)
