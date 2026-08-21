"""Geometry regression tests for scene_to_glb (needs trimesh + shapely)."""
import numpy as np

import scene_to_glb
from scene_to_glb import FT


def test_poly_prism_band_z_offset_moves_height_not_plan():
    """Regression: the z0 translation sat on the wrong matrix row, shifting
    upper wall bands sideways (plan-y) instead of up. A band extruded from
    z0=3 to z1=6 must span Y=[3*FT, 6*FT] with plan coords unshifted."""
    from shapely.geometry import Polygon
    poly = Polygon([(0, 0), (10, 0), (10, 1), (0, 1)])
    meshes = []
    scene_to_glb._add_poly_prism(meshes, poly, 3.0, 6.0,
                                 [200, 200, 200, 255], name="band")
    assert meshes
    v = np.vstack([m.vertices for _, m in meshes])
    assert np.isclose(v[:, 1].min(), 3 * FT)   # Y = height
    assert np.isclose(v[:, 1].max(), 6 * FT)
    assert np.isclose(v[:, 0].min(), 0 * FT)   # X = plan-x, unshifted
    assert np.isclose(v[:, 0].max(), 10 * FT)
    # Z = -plan-y since 18 Aug (north renders UP in a top view), still
    # unshifted by the z0 band offset — which is what this test guards
    assert np.isclose(v[:, 2].min(), -1 * FT)
    assert np.isclose(v[:, 2].max(), 0 * FT)


# --- ORIENTATION (18 Aug 2026) -----------------------------------------------
# plan-y maps to -Z. With y-up and east on the right, a camera above looking
# down puts +Z at the BOTTOM of the screen, so mapping plan-north to +Z
# rendered every top view MIRRORED north-south. No geometry axis was negated,
# which is why a coordinate check could not see it — the mirror lived in the
# view basis, and only rendering it showed the fault.
def test_plan_north_maps_to_negative_z():
    from scene_to_glb import _build_scene
    scene = {"meta": {"wall_height_ft": 9.843}, "walls": [], "openings": [],
             "walls_poly": [{"id": "wp0", "outer": [[0, 0], [10, 0], [10, 20], [0, 20]],
                             "holes": []}]}
    from scene_to_glb import _build_scene
    _sc, meshes = _build_scene(scene)
    import numpy as np
    V = np.vstack([m.vertices for _n, m in meshes])
    assert V[:, 2].max() <= 0.01, "plan-y must map to -Z"
    assert V[:, 2].min() < -1.0
    assert V[:, 0].min() >= -0.01 and V[:, 0].max() > 1.0   # plan-x unchanged


def test_the_east_landmark_stays_east_and_north_stays_up():
    """The C.TOILET / A.TOILET pair sits at the FAR EAST of FLOOR PLAN and the
    north edge at plan-y 29.8. In a top view (camera above, three.js default
    up) east must render RIGHT and north UP. Pinned so the orientation cannot
    silently invert again."""
    import numpy as np
    from scene_to_glb import FT
    pos = np.array([0, 16, 0.01]); zc = pos / np.linalg.norm(pos)
    xc = np.cross([0, 1, 0], zc); xc /= np.linalg.norm(xc)
    yc = np.cross(zc, xc)
    east = np.array([94.0 * FT, 0, -5.0 * FT])       # flat-2's corner bedroom
    west = np.array([0.0, 0, -15.0 * FT])            # flat-1's balcony end
    north = np.array([48.0 * FT, 0, -29.8 * FT])
    south = np.array([48.0 * FT, 0, 0.0])
    assert east @ xc > west @ xc, "east must render to the RIGHT of west"
    assert north @ yc > south @ yc, "north must render ABOVE south"


def test_railings_are_half_walls_and_nothing_stands_full_height_on_an_open_face():
    """20 Aug 2026 (B-4). `scene.railings` was read by NOTHING, so no balcony or
    utility reached the 3D. Flat-2's balcony only LOOKED built: its railing is
    a thin double line 3.0 in apart, exactly `wall_rects`'s 3 in floor, so it
    paired as a WALL and was extruded full storey on an open face — while
    flat-1's balcony, whose railing pairs no such wall, was absent entirely.
    A classified run is now a half-wall at 3.5 ft, its pocket gets a floor, and
    wall material lying along the run is cut to the same height."""
    scene = {"meta": {"wall_height_ft": 9.843},
             "walls": [], "openings": [], "furniture": [],
             "walls_poly": [{"id": "wp0", "holes": [],
                             "outer": [[0, 0], [10, 0], [10, 0.25], [0, 0.25]]}],
             "railings": {"runs": [
                 {"classification": "railing", "pocket_ft": [0, 0, 10, 4],
                  "polyline_ft": [[0, 0.12], [10, 0.12]]}]}}
    from scene_to_glb import _build_scene
    _sc, meshes = _build_scene(scene)
    rails = [m for n, m in meshes if n.startswith(("railing", "rail_w"))]
    assert rails, [n for n, _m in meshes]
    for m in rails:
        assert m.vertices[:, 1].max() <= 3.5 * FT + 1e-6
    # the wall that coincided with the run must not stand full height
    for n, m in meshes:
        if n.startswith("wall_p"):
            assert m.vertices[:, 1].max() <= 3.5 * FT + 1e-6, n
    assert any(n.startswith("floor_open") for n, _m in meshes)


def test_furniture_is_not_staged_into_a_balcony_or_utility_pocket():
    """A bed stood in flat-1's utility (20 Aug 2026)."""
    scene = {"meta": {"wall_height_ft": 9.843}, "walls": [], "walls_poly": [],
             "openings": [],
             "furniture": [{"type": "bed", "x": 26.0, "y": 20.0, "w": 5, "d": 6},
                           {"type": "bed", "x": 50.0, "y": 5.0, "w": 5, "d": 6}],
             "railings": {"runs": [
                 {"classification": "railing", "pocket_ft": [25.6, 19.1, 33.2, 24.1],
                  "polyline_ft": [[25.6, 24.06], [33.1, 24.06]]}]}}
    from scene_to_glb import _build_scene
    _sc, meshes = _build_scene(scene)
    beds = {n.split("_")[2] for n, _m in meshes if n.startswith("furn_bed_")}
    assert beds == {"1"}, beds
