"""Tests for Vastu analysis — zones and verdicts pinned individually."""
import vastu


def test_zones_on_a_square_plan():
    w = d = 100
    assert vastu.zone_of(50, 95, w, d) == "N"
    assert vastu.zone_of(95, 95, w, d) == "NE"
    assert vastu.zone_of(95, 50, w, d) == "E"
    assert vastu.zone_of(95, 5, w, d) == "SE"
    assert vastu.zone_of(50, 5, w, d) == "S"
    assert vastu.zone_of(5, 5, w, d) == "SW"
    assert vastu.zone_of(5, 50, w, d) == "W"
    assert vastu.zone_of(5, 95, w, d) == "NW"
    assert vastu.zone_of(50, 50, w, d) == "CENTER"


def test_north_rotation():
    # with North pointing to the RIGHT edge (north_deg=90), the right edge is N
    assert vastu.zone_of(95, 50, 100, 100, north_deg=90) in ("N",)


def _scene(rooms):
    return {"meta": {"plan_width_ft": 100, "plan_depth_ft": 100}, "rooms": rooms}


def test_kitchen_se_is_ideal_ne_is_avoid():
    good = vastu.analyze(_scene([{"id": "r0", "type": "kitchen", "x": 95, "y": 5}]))
    bad = vastu.analyze(_scene([{"id": "r0", "type": "kitchen", "x": 95, "y": 95}]))
    assert good["verdicts"][0]["verdict"] == "ideal"
    assert bad["verdicts"][0]["verdict"] == "avoid"
    assert "advice" in bad["verdicts"][0]
    assert good["score"] > bad["score"]


def test_bedroom_sw_ideal():
    r = vastu.analyze(_scene([{"id": "r0", "type": "bedroom", "x": 5, "y": 5}]))
    assert r["verdicts"][0]["verdict"] == "ideal"


def test_bathroom_in_center_is_avoid():
    r = vastu.analyze(_scene([{"id": "r0", "type": "bathroom", "x": 50, "y": 50}]))
    assert r["verdicts"][0]["verdict"] == "avoid"


def test_untyped_and_neutral_rooms_not_scored():
    r = vastu.analyze(_scene([{"id": "r0", "x": 5, "y": 5},
                              {"id": "r1", "type": "parking", "x": 95, "y": 5}]))
    assert r["rooms_scored"] == 0 and r["score"] is None
    assert r["disclaimer"]
