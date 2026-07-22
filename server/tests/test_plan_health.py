"""Tests for the cascade decision logic — the guarantee that it never picks a
worse reading. Each rule pinned individually."""
import plan_health as ph


def _scene(w=40, d=50, rooms=3, doors=4):
    return {
        "meta": {"plan_width_ft": w, "plan_depth_ft": d},
        "rooms": [{"id": f"r{i}"} for i in range(rooms)],
        "openings": [{"type": "door"} for _ in range(doors)],
    }


def test_healthy_scene_has_no_flags():
    assert ph.health_flags(_scene()) == []
    assert ph.is_healthy(_scene())


def test_flags_catch_bad_readings():
    assert "envelope_tiny" in ph.health_flags(_scene(w=5))
    assert "no_rooms" in ph.health_flags(_scene(rooms=0))
    assert "no_doors" in ph.health_flags(_scene(doors=0))
    assert ph.health_flags(None) == ["no_scene"]
    assert not ph.is_healthy(_scene(rooms=0))


def test_better_scene_prefers_healthy_over_flagged():
    good = _scene(rooms=5, doors=6)              # healthy
    bad = _scene(w=5, rooms=0, doors=0)          # flagged
    assert ph.better_scene(bad, good) is good    # ML(good) beats flagged vector
    assert ph.better_scene(good, bad) is good    # flagged ML never beats healthy vector


def test_ties_and_none_keep_vector():
    v = _scene(rooms=3, doors=4)
    m = _scene(rooms=3, doors=4)                 # equal score
    assert ph.better_scene(v, m) is v            # tie -> vector
    assert ph.better_scene(v, None) is v         # no ML -> vector
    assert ph.better_scene(None, m) is m         # vector failed -> ML


def test_ml_wins_only_when_strictly_better():
    v = _scene(rooms=0, doors=0, w=5)            # flagged, score very low
    m = _scene(rooms=8, doors=9)                 # healthy, high score
    assert ph.better_scene(v, m) is m            # ML rescues a failed vector
