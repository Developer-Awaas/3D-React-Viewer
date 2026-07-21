"""Tests for the door/window tag reader — each rule pinned individually."""
import tag_openings as T

WALLS = [(0, 0, 30, 0), (0, 0, 0, 20)]      # one horizontal + one vertical wall


def test_classify_tags():
    assert T.classify_tag("D1") == ("door", "D1")
    assert T.classify_tag("sd") == ("door", "SD")
    assert T.classify_tag("W1") == ("window", "W1")
    assert T.classify_tag("V") == ("window", "V")
    assert T.classify_tag("D2.") == ("door", "D2")
    assert T.classify_tag("BED") is None
    assert T.classify_tag("12'") is None
    assert T.classify_tag("") is None


def test_door_tag_snaps_to_nearest_wall_with_schedule_width():
    ops = T.detect_tag_openings([(10, 1.0, "D2")], WALLS, [])
    assert len(ops) == 1
    o = ops[0]
    assert o["type"] == "door" and o["tag"] == "D2"
    x0, y0, x1, y1 = o["footprint"]
    assert (x1 - x0) == 3.0                  # D2 = 3'0" along the horizontal wall
    assert o["z"] == [0.0, T.DOOR_HEAD_FT]


def test_window_tag_gets_sill_and_head():
    ops = T.detect_tag_openings([(1.0, 10, "V")], WALLS, [])
    assert len(ops) == 1
    o = ops[0]
    assert o["type"] == "window" and o["z"] == [5.0, 7.0]   # ventilator sill 5'
    x0, y0, x1, y1 = o["footprint"]
    assert (y1 - y0) == 2.0                  # V = 2' along the vertical wall


def test_tag_far_from_any_wall_is_ignored():
    assert T.detect_tag_openings([(15, 15, "D1")], WALLS, []) == []


def test_dedupe_against_existing_openings():
    # an opening already detected at (10, 0) -> the D2 tag there adds nothing
    ops = T.detect_tag_openings([(10, 1.0, "D2")], WALLS, [(10, 0)])
    assert ops == []


def test_two_tags_do_not_stack_on_same_spot():
    ops = T.detect_tag_openings([(10, 1.0, "D2"), (10.5, 1.2, "D2")], WALLS, [])
    assert len(ops) == 1                      # second dedupes against the first
