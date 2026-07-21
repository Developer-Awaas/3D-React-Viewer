"""Tests for geometric door/opening detection on flattened PDFs (no CAD layers).

Two layers of testing:
- gap_openings(): a pure function over wall-face segments — every case has a
  hand-computed expected answer (units are arbitrary; feet used here).
- parse() on a real flattened plan fixture — the end-to-end regression pin.
"""
import os

import pytest

from pdf_vector import gap_openings, parse

MIN_W, MAX_W = 2.0, 5.5          # door width band, feet
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "plan_20x45_flat.pdf")


# ---------- pure function: gap_openings ----------

def test_single_horizontal_doorway():
    """One horizontal wall broken by a 3 ft gap -> one door at the gap centre."""
    segs = [(0, 0, 5, 0), (8, 0, 15, 0)]          # gap x=5..8 (3 ft)
    ops = gap_openings(segs, MIN_W, MAX_W, min_flank=1.0)
    assert len(ops) == 1
    o = ops[0]
    assert o["orient"] == "h"
    assert o["w"] == pytest.approx(3.0)
    assert o["cx"] == pytest.approx(6.5)
    assert o["cy"] == pytest.approx(0.0)


def test_single_vertical_doorway():
    """Same, on a vertical wall -> orient 'v'."""
    segs = [(0, 0, 0, 5), (0, 8, 0, 15)]          # gap y=5..8 (3 ft)
    ops = gap_openings(segs, MIN_W, MAX_W, min_flank=1.0)
    assert len(ops) == 1
    assert ops[0]["orient"] == "v"
    assert ops[0]["cy"] == pytest.approx(6.5)
    assert ops[0]["cx"] == pytest.approx(0.0)


def test_gap_too_narrow_is_not_a_door():
    """A 1 ft gap (< MIN_W) is not a doorway."""
    segs = [(0, 0, 5, 0), (6, 0, 15, 0)]          # gap 1 ft
    assert gap_openings(segs, MIN_W, MAX_W, min_flank=1.0) == []


def test_gap_too_wide_is_not_a_door():
    """A 7 ft gap (> MAX_W) is an open span, not a doorway."""
    segs = [(0, 0, 5, 0), (12, 0, 20, 0)]         # gap 7 ft
    assert gap_openings(segs, MIN_W, MAX_W, min_flank=1.0) == []


def test_junction_is_not_a_door():
    """A perpendicular wall crossing the gap is a T/L junction, not a door."""
    segs = [
        (0, 0, 5, 0), (8, 0, 15, 0),              # horizontal wall w/ 3 ft gap
        (6.5, 0, 6.5, 6),                          # vertical wall through the gap
    ]
    ops = gap_openings(segs, MIN_W, MAX_W, min_flank=1.0)
    # only the vertical wall has no gap; the horizontal gap is filtered
    assert all(not (o["orient"] == "h") for o in ops)


def test_short_flank_is_rejected():
    """A stub shorter than min_flank on one side is not a wall -> no door."""
    segs = [(0, 0, 0.5, 0), (3, 0, 15, 0)]        # left flank only 0.5 ft
    assert gap_openings(segs, MIN_W, MAX_W, min_flank=1.0) == []


def test_double_line_wall_deduped():
    """Both faces of one wall carry the same gap -> report the door once."""
    segs = [
        (0, 0.0, 5, 0.0), (8, 0.0, 15, 0.0),      # inner face
        (0, 0.5, 5, 0.5), (8, 0.5, 15, 0.5),      # outer face (0.5 ft thick)
    ]
    ops = gap_openings(segs, MIN_W, MAX_W, min_flank=1.0)
    assert len(ops) == 1


def test_two_separate_doors_on_one_line():
    """Two real gaps in a long wall -> two doors."""
    segs = [(0, 0, 5, 0), (8, 0, 13, 0), (16, 0, 24, 0)]   # gaps 5..8 and 13..16
    ops = gap_openings(segs, MIN_W, MAX_W, min_flank=1.0)
    assert len(ops) == 2
    assert sorted(round(o["cx"], 1) for o in ops) == [6.5, 14.5]


# ---------- end-to-end regression on a real flattened plan ----------

@pytest.mark.skipif(not os.path.exists(FIXTURE), reason="fixture PDF absent")
def test_flat_plan_gets_geometric_doors_and_rooms():
    """The 20x45 flattened plan (no layers) must parse to the right envelope
    AND recover doors + rooms geometrically. Pins current behaviour so a future
    change can't silently zero them out again."""
    raw = open(FIXTURE, "rb").read()
    scene = parse(raw, width_ft=20)
    assert scene["meta"]["plan_width_ft"] == pytest.approx(20.0, abs=0.5)
    assert scene["meta"]["plan_depth_ft"] == pytest.approx(45.0, abs=1.0)
    doors = [o for o in scene["openings"] if o["type"] == "door"]
    assert len(doors) >= 3           # geometric doors recovered (was 0)
    # envelope sealing bridges fragmented walls -> more rooms enclose (was 2)
    assert len(scene["rooms"]) >= 4
