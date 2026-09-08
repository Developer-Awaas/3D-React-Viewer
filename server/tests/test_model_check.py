"""M-2: does the MODEL match the parse? Every other instrument measures the
parse; FLOOR PLAN read R-8 96.5 with a slab 58% too large and no staircase."""
import numpy as np
import trimesh

from model_check import model_check, _plan_bbox

FT = 0.3048


def _box(x0, y0, x1, y1, z0=0.0, z1=1.0):
    """A box given in PLAN feet, built the way scene_to_glb builds one."""
    m = trimesh.creation.box(extents=((x1 - x0) * FT, (z1 - z0) * FT, (y1 - y0) * FT))
    m.apply_translation(((x0 + x1) / 2 * FT, (z0 + z1) / 2 * FT, -(y0 + y1) / 2 * FT))
    return m


def test_plan_bbox_undoes_the_plan_y_to_minus_z_mapping():
    assert np.allclose(_plan_bbox(_box(2, 5, 6, 11)), (2, 5, 6, 11))


def test_it_sees_an_element_built_as_nothing():
    scene = {"meta": {"footprint_sqft": 100.0},
             "footprint_ft": [[0, 0], [10, 0], [10, 10], [0, 10]],
             "rooms": [{"type": "stairs"}], "columns": [{"x": 1}], "openings": []}
    r = model_check(scene, [("floor_0", _box(0, 0, 10, 10, -0.25, 0))])
    assert "stairs_rooms" in r["built_as_nothing"]
    assert "columns" in r["built_as_nothing"]


def test_it_sees_a_mesh_outside_the_footprint():
    scene = {"meta": {"footprint_sqft": 100.0},
             "footprint_ft": [[0, 0], [10, 0], [10, 10], [0, 10]],
             "rooms": [], "openings": []}
    r = model_check(scene, [("wall_p0", _box(20, 20, 22, 22))])
    assert r["meshes_outside_footprint"] == 1
    assert r["outside_examples"][0]["outside_pct"] == 100.0


def test_placement_slope_reads_one_and_catches_an_axis_SCALE_error():
    """The offset cannot see anything - a door mesh is the leaf swung open, so
    ~half a leaf of offset is expected. The slope catches a y-axis scale error.

    It CANNOT see a global mirror, and the test says so: meshes are matched to
    cuts by NEAREST, so a mirrored model still finds a mesh beside every cut.
    Same blind spot §12 records for 18 Aug - only a render caught that one."""
    fp = [[0, 0], [40, 0], [40, 60], [0, 60]]
    ys = (2, 12, 22, 32)
    doors = [{"type": "door", "footprint": [5, y, 6, y + 1]} for y in ys]
    base = {"meta": {"footprint_sqft": 2400.0}, "footprint_ft": fp,
            "rooms": [], "openings": doors}
    ok = [(f"door_{i}", _box(5, y, 6, y + 1)) for i, y in enumerate(ys)]
    assert abs(model_check(base, ok)["placement_slope_y"] - 1.0) < 0.05
    stretched = [(f"door_{i}", _box(5, 1.5 * y, 6, 1.5 * y + 1)) for i, y in enumerate(ys)]
    assert model_check(base, stretched)["placement_slope_y"] > 1.3


def test_the_five_scorecard_fields_carry_their_units_and_axis():
    """A number without its frame is what cost the scorecard a measurement:
    it compared metres against feet. The frame ships WITH the numbers."""
    scene = {"meta": {"footprint_sqft": 100.0},
             "footprint_ft": [[0, 0], [10, 0], [10, 10], [0, 10]],
             "rooms": [], "openings": [], "walls_poly": []}
    r = model_check(scene, [("floor_0", _box(0, 0, 10, 10, -0.25, 0))])
    for k in ("outside_footprint_pct", "wall_volume_ratio", "orphan_meshes",
              "missing_pct", "seg_unclassified_pct", "units", "axis"):
        assert k in r, k
    assert r["units"]["length"] == "ft"
    assert "METRES" in r["axis"] and "-Z" in r["axis"]


def test_seg_unclassified_sees_a_family_the_gbuffer_does_not_know():
    scene = {"meta": {"footprint_sqft": 100.0},
             "footprint_ft": [[0, 0], [10, 0], [10, 10], [0, 10]],
             "rooms": [], "openings": [], "walls_poly": []}
    known = model_check(scene, [("wall_p0", _box(1, 1, 2, 2))])
    assert known["seg_unclassified_pct"] == 0.0
    unknown = model_check(scene, [("gizmo_0", _box(1, 1, 2, 2))])
    assert unknown["seg_unclassified_pct"] == 100.0
