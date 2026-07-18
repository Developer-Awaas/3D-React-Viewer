"""The bundled demo building (public/sample.glb) is a PRODUCT - pin it.

tools/make_sample_plan.py generates a synthetic 2BHK CAD PDF and runs it
through the real engine. These tests regenerate it in memory and pin every
stat the demo shows, so a parser change that degrades the first thing every
visitor sees fails CI immediately.
"""
import os
import sys

import pytest

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)


@pytest.fixture(scope="module")
def sample_scene():
    from make_sample_plan import build_pdf
    from pdf_vector import parse
    return parse(build_pdf(), None)


def test_sample_envelope_and_scale(sample_scene):
    m = sample_scene["meta"]
    assert m["plan_width_ft"] == pytest.approx(40.5, abs=0.6)
    assert m["plan_depth_ft"] == pytest.approx(28.5, abs=0.6)
    assert m["scale"]["source"] == "column_box_12in"
    assert m["wing"]["count"] == 1


def test_sample_all_doors_snap(sample_scene):
    doors = [o for o in sample_scene["openings"] if o["type"] == "door"]
    assert len(doors) == 6
    assert all(o.get("snapped") for o in doors), \
        "every demo door must snap (headers/lintels depend on it)"


def test_sample_windows(sample_scene):
    wins = [o for o in sample_scene["openings"] if o["type"] == "window"]
    assert len(wins) == 6
    for o in wins:
        assert o["z"] == [3.0, 7.0]    # sill 3', head 7'


def test_sample_rooms_for_walk_inside(sample_scene):
    """Every enclosed space becomes a walk-inside beacon: the 2BHK must
    yield its main rooms, and no beacon may sit inside a wall."""
    from shapely.geometry import Point, Polygon
    rooms = sample_scene["rooms"]
    assert len(rooms) >= 4                       # living, beds, kitchen, bath…
    walls = [Polygon(w["outer"], w.get("holes") or None).buffer(0)
             for w in sample_scene["walls_poly"]]
    m = sample_scene["meta"]
    areas = [r["area_sqft"] for r in rooms]
    assert areas == sorted(areas, reverse=True)  # biggest room first
    for r in rooms:
        assert 0 <= r["x"] <= m["plan_width_ft"]
        assert 0 <= r["y"] <= m["plan_depth_ft"]
        p = Point(r["x"], r["y"])
        assert all(not w.contains(p) for w in walls), \
            f"beacon {r['id']} sits inside a wall"
        assert r["area_sqft"] >= 28


def test_single_room_box_yields_one_room():
    from pdf_vector import parse
    import test_pdf_vector as fixtures
    s = parse(fixtures._make_pdf())          # plain 40x20 double-line box
    assert len(s["rooms"]) == 1
    r = s["rooms"][0]
    assert 5 < r["x"] < 35 and 3 < r["y"] < 17


def test_sample_glb_parts(sample_scene, tmp_path):
    import trimesh
    from scene_to_glb import build_glb
    out = tmp_path / "sample.glb"
    build_glb(sample_scene, str(out))
    names = set(trimesh.load(str(out)).geometry.keys())
    assert "floor" in names
    assert any(n.startswith("wall") for n in names)
    assert sum(1 for n in names if n.startswith("glass_")) == 6
    assert any(n.startswith("column_") for n in names)
