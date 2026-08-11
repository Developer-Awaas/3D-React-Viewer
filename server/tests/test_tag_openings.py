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


# --- schedule/legend column filter (Stage A: OCR-read tags) -----------------
# A sheet's real tags sit at their openings, scattered. A SCHEDULE table lists
# the same names stacked in one column — placing those would invent openings in
# the title block. BRICK WORK LAYOUT.pdf: D/D1/D2/D3/SD/W1 stacked at x=216,
# under a "SCHEDULE OF DOOR & WINDOW" heading at y=2730.
SCHED_COL = [(216, 2838, "D"), (216, 2872, "D1"), (216, 2906, "D2"),
             (216, 2941, "D3"), (216, 2975, "SD"), (219, 3077, "W1")]
REAL_TAGS = [(1716, 461, "D3"), (956, 696, "D1"), (1397, 1232, "D"),
             (1398, 2158, "D1"), (1226, 2345, "SD")]


def test_legend_column_is_dropped():
    kept = T.drop_legend_tags(REAL_TAGS + SCHED_COL, schedule_y=2730)
    assert kept == REAL_TAGS


def test_real_tags_are_never_dropped():
    """The tightest real alignment on the corpus is two tags (x=1397/1398);
    a stack must be at least 4 deep to count as a legend column."""
    kept = T.drop_legend_tags(REAL_TAGS, schedule_y=400)
    assert kept == REAL_TAGS


def test_no_schedule_keyword_drops_nothing():
    """Conservative: without a schedule heading on the sheet, keep everything."""
    assert T.drop_legend_tags(REAL_TAGS + SCHED_COL) == REAL_TAGS + SCHED_COL


def test_tags_above_the_schedule_heading_are_kept():
    kept = T.drop_legend_tags(SCHED_COL + [(216, 200, "D1")], schedule_y=2730)
    assert kept == [(216, 200, "D1")]
