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


# --- ONE CONSTANT PER PURPOSE (18 Aug 2026) ----------------------------------
# `DOOR_MIN_FT` was doing five jobs: a real leaf width, the drawn-gap width in
# gap_openings, the same in the geometry fallback, a sanity bound, and a
# strip-span floor — with a `- 0.3` slack that existed only to reconcile the
# last with the first. The four doors that stopped snapping sat 0.09-0.21 ft
# under that floor because the floor was a compromise between unlike things.
def test_leaf_and_drawn_gap_are_separate_constants():
    import pdf_vector
    assert pdf_vector.DOOR_LEAF_MIN_FT and pdf_vector.DRAWN_GAP_MIN_FT
    # they may coincide in VALUE — a drawn opening holds the leaf it carries —
    # but they must be free to move independently
    assert "DOOR_LEAF_MIN_FT" in dir(pdf_vector)
    assert "DRAWN_GAP_MIN_FT" in dir(pdf_vector)


def test_the_strip_has_no_lower_span_bound():
    """A strip is a property of the ROI close, not a doorway: doors that snap
    correctly show 0.00-0.18 ft of opening on their wall line and still produce
    2.24-3.05 ft strips. A floor borrowed from a door width compared two
    unlike objects, so there is no floor — deliberately."""
    import inspect
    import pdf_vector
    src = inspect.getsource(pdf_vector.parse)
    assert "DOOR_MIN_FT - 0.3" not in src
    assert "span <= DOOR_LEAF_MAX_FT + 0.5 and thick <= 1.6" in src


# --- doors_placed_sound (19 Aug 2026) ----------------------------------------
# The judge for door PLACEMENT, not door COUNT. `snapped` went 8 -> 12 on a
# change that made placement worse, because a count cannot see a cut in the
# wrong place. A cut is SOUND when its width matches the DRAWN leaf cluster it
# belongs to — the strip the ROI close reveals is a different object and cuts
# sized from it removed about half of each doorway.
import pytest
import pdf_vector
from conftest import require_corpus_file


def test_floor_plan_door_placement_ratchet():
    with open(require_corpus_file("FLOOR PLAN.pdf"), "rb") as f:
        d = pdf_vector.parse(f.read())["meta"]["doors_placed_sound"]
    assert d["doors"] == 16 and d["drawn_leaves"] == 12
    # authorised floor is 6 (the value before the cut took its width from the
    # drawn leaf); the fix took it to 11, and it may only rise
    assert d["sound"] >= 6, d


def test_symbol_grouping_by_radius():
    """A symbol may be SPLIT ACROSS PATHS — FLOOR PLAN keeps every leaf in a
    different path from its arc. The geometry groups them: the leaf IS the
    radius of its quarter circle (measured: equal to 0.01 ft on all 12)."""
    import math
    import pdf_vector
    leaf = [((0.0, 0.0), (3.0, 0.0))]
    arc = [((3 * math.cos(a), 3 * math.sin(a)),
            (3 * math.cos(a + 0.05), 3 * math.sin(a + 0.05)))
           for a in [i * 0.05 for i in range(1, 30)]]
    got = pdf_vector.group_door_symbols([leaf, arc])
    assert len(got) == 1 and got[0][0] == leaf[0]
    sw = pdf_vector.door_swing(got[0])
    assert sw and sw["hinge"] == [0.0, 0.0] and sw["leaf_ft"] == 3.0


def test_a_lone_arc_groups_with_nothing():
    """No leaf of matching radius -> no symbol, and no guess."""
    import math
    import pdf_vector
    arc = [((5 * math.cos(a), 5 * math.sin(a)),
            (5 * math.cos(a + 0.05), 5 * math.sin(a + 0.05)))
           for a in [i * 0.05 for i in range(1, 30)]]
    assert pdf_vector.group_door_symbols([[((0.0, 0.0), (2.0, 0.0))], arc]) == []


def test_door_cut_and_hinge_come_from_the_drawn_symbol():
    """20 Aug 2026. `_add_door_leaf` used to discard the measured hinge POINT
    and keep only which jamb was nearer, because the cut itself was centred on
    the door STRIP: 6 of 12 FLOOR PLAN cuts sat 0.46-1.99 ft along the wall
    from the door the drafter drew. Measured first that this was misplaced
    CUTS, not mis-associated symbols — 12 symbols, 12 openings, 1:1, none
    shared, every drawn opening overlapping its own cut.

    Now hinge -> the arc end lying along the wall IS the doorway (the strip
    keeps only orientation and perpendicular position), and the cut is the
    wall's own measured thickness deep instead of the ROI close's 1.06-1.55 ft
    against a 0.83 ft wall. Result: every hinge lands ON a jamb, and
    doors_placed_sound went 11/12 -> 12/12."""
    from pdf_vector import parse
    from conftest import require_corpus_file
    f = require_corpus_file("FLOOR PLAN.pdf")
    with open(f, "rb") as fh:
        sc = parse(fh.read())
    doors = [o for o in sc["openings"] if o["type"] == "door"]
    assert len(doors) == 16                    # 12 symbols + 4 leafless gaps
    for o in [d for d in doors if d.get("hinge")]:
        x0, y0, x1, y1 = o["footprint"]
        runx = (x1 - x0) >= (y1 - y0)
        k = 0 if runx else 1
        a, b = sorted((o["footprint"][k], o["footprint"][k + 2]))
        assert min(abs(o["hinge"][k] - a), abs(o["hinge"][k] - b)) <= 0.05, o
        # the cut is the wall, not the strip: 0.83 ft on this sheet
        assert abs(min(x1 - x0, y1 - y0) - 0.83) <= 0.02, o
    assert sc["meta"]["doors_placed_sound"]["sound"] == 16


def test_leaf_swings_to_the_side_the_drawn_arc_sweeps():
    """The rotation sign cannot come from `opens_toward`: that is measured
    against the drawn LEAF, and the drafter draws it shut on some doors and
    open on others, so FLOOR PLAN's two `right` doors needed OPPOSITE signs.
    `opens_ccw` is the cross product of the symbol's shut and open arc ends,
    in plan — unambiguous. 3 of 12 leaves swung the wrong way before it."""
    import math
    import numpy as np
    from pdf_vector import parse
    from conftest import require_corpus_file
    import scene_to_glb
    f = require_corpus_file("FLOOR PLAN.pdf")
    with open(f, "rb") as fh:
        sc = parse(fh.read())
    _s, meshes = scene_to_glb._build_scene(sc)
    leaves = {n: m for n, m in meshes if n.startswith("door_")}
    doors = [o for o in sc["openings"] if o["type"] == "door"]
    for i, o in enumerate(doors, 1):
        m = leaves.get(f"door_{i}")
        if m is None or not o.get("hinge"):
            continue
        hx, hy = o["hinge"]
        P = np.column_stack([m.vertices[:, 0] / 0.3048, -m.vertices[:, 2] / 0.3048])
        tip = P[np.argmax(np.hypot(P[:, 0] - hx, P[:, 1] - hy))]
        sa = o["swing_area"]
        d = math.degrees(math.atan2(tip[1] - hy, tip[0] - hx)) - math.degrees(
            math.atan2((sa[1] + sa[3]) / 2 - hy, (sa[0] + sa[2]) / 2 - hx))
        assert abs((d + 180) % 360 - 180) <= 45, (i, o)


def test_the_doors_wall_line_comes_from_the_hinge_not_the_strip():
    """20 Aug 2026, DR-3. The perpendicular position was the last thing still
    taken from the door STRIP, and a strip can land on the wrong wall: 6 of 12
    FLOOR PLAN cuts sat off their symbol's wall line — five by 0.49-0.68 ft
    (half a wall) and flat-1's bedroom entry by 3.32 ft, a different wall
    entirely, which is what read as a door in the wrong position."""
    from pdf_vector import parse
    from conftest import require_corpus_file
    f = require_corpus_file("FLOOR PLAN.pdf")
    with open(f, "rb") as fh:
        sc = parse(fh.read())
    # gap openings carry no hinge — they have no drawn symbol at all
    for o in [d for d in sc["openings"] if d["type"] == "door" and d.get("hinge")]:
        x0, y0, x1, y1 = o["footprint"]
        j = 1 if (x1 - x0) >= (y1 - y0) else 0          # the ACROSS-wall axis
        centre = (o["footprint"][j] + o["footprint"][j + 2]) / 2
        assert abs(o["hinge"][j] - centre) <= 0.05, o


def test_gap_grouping_is_order_independent():
    """20 Aug 2026. `_runs_by_line` grouped wall faces against a ROLLING MEAN
    and moved the key halfway toward each new member, so groups chained without
    limit (7 FLOOR PLAN faces spanning 2.92 ft merged under a 1.2 ft tolerance)
    and the key landed wherever the walk stopped. That made the result
    ORDER-DEPENDENT: the same faces keyed 18.70 ft read bottom-up and 16.73 ft
    read top-down, which is why the geometric finder put a doorway 2.4 ft off
    its own wall in raster space (y down) while feet-space probes looked fine.
    Nothing else consumes it — walls and rooms come from the mask contours."""
    from pdf_vector import gap_openings
    # one wall line at perp 10/11, a 3 ft doorway in it, plus faces marching
    # up from 8.0 that the old rolling mean would have chained through
    segs = []
    for perp in (8.0, 8.6, 9.2, 10.0, 11.0):
        segs.append((0.0, perp, 6.0, perp))
        segs.append((9.0, perp, 16.0, perp))
    up = gap_openings(segs, 2.0, 5.5, min_flank=0.8, face_tol=0.35,
                      group_tol=1.2, junction_pad=0.5)
    down = gap_openings([(a, -b, c, -d) for a, b, c, d in segs], 2.0, 5.5,
                        min_flank=0.8, face_tol=0.35, group_tol=1.2,
                        junction_pad=0.5)
    assert up and down
    assert len(up) == len(down)
    for a, b in zip(sorted(up, key=lambda g: abs(g["cy"])),
                    sorted(down, key=lambda g: abs(g["cy"]))):
        assert abs(a["cx"] - b["cx"]) < 1e-6
        assert abs(abs(a["cy"]) - abs(b["cy"])) < 1e-6, (a, b)
        # and the key is the group's own centre, not wherever the walk ended
        assert 8.0 <= abs(a["cy"]) <= 11.0


def test_gap_faces_group_by_MEASURED_PAIR_so_one_doorway_is_one_opening():
    """20 Aug 2026, Rahul. Sixth instance of a TOLERANCE DECIDING CONSTRUCTION.
    Clustering wall faces in 1-D failed twice: keyed on a rolling mean it was
    order-dependent (a doorway landed 2.4 ft off its wall), and bounded by the
    group's extent it SPLIT a wall whose faces sat at 7.06 and 7.89, emitting
    one lobby doorway TWICE — once per face.

    A wall line is not a cluster, it is a measured PAIR: parallel, W-3 apart
    (3-18 in), overlapping along the run — the same test `wall_rects` uses. One
    pair is one wall, so one gap in it is ONE opening, structurally rather than
    by widening a dedup tolerance. Collinear segments are merged into a face
    first, or a wall broken at every doorway would pair segment-by-segment and
    the gaps between them could never be seen."""
    from pdf_vector import gap_openings
    # one wall: faces 0.42 apart, each broken by the same 3 ft doorway
    segs = [(0.0, 7.06, 5.0, 7.06), (8.0, 7.06, 16.0, 7.06),
            (0.0, 7.48, 5.0, 7.48), (8.0, 7.48, 16.0, 7.48)]
    got = gap_openings(segs, 2.0, 5.5, min_flank=0.8, face_tol=0.35,
                       group_tol=1.2, junction_pad=0.5,
                       pair_min=0.25, pair_max=1.5)
    assert len(got) == 1, got                      # ONE doorway, not one per face
    assert abs(got[0]["cx"] - 6.5) < 0.01
    assert abs(got[0]["cy"] - 7.27) < 0.01         # the wall centre-line
    assert abs(got[0]["w"] - 3.0) < 0.01
    # without a pair band the old clustering still runs, for callers with no scale
    assert gap_openings(segs, 2.0, 5.5, min_flank=0.8, face_tol=0.35,
                        group_tol=1.2, junction_pad=0.5)
