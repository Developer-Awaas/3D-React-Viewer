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
    assert np.isclose(v[:, 2].min(), 0 * FT)   # Z = plan-y, unshifted
    assert np.isclose(v[:, 2].max(), 1 * FT)
