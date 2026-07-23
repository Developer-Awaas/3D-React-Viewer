"""D1: a real designer door LEAF stands ajar in every door opening (vector +
ML paths). Geometry-level tests, no GPU."""
import trimesh

import scene_to_glb as G


def _door_scene_ml():
    """A 4-wall box (axis-aligned 'walls') with ONE door on the south wall,
    given by wall id + along (the ML-path door shape, no footprint)."""
    return {
        "meta": {"wall_height_ft": 9.8},
        "walls": [
            {"id": "w0", "axis": "x", "x0": 0, "x1": 20, "y0": 0, "y1": 0.5},
            {"id": "w1", "axis": "x", "x0": 0, "x1": 20, "y0": 15, "y1": 15.5},
            {"id": "w2", "axis": "y", "x0": 0, "x1": 0.5, "y0": 0, "y1": 15},
            {"id": "w3", "axis": "y", "x0": 19.5, "x1": 20, "y0": 0, "y1": 15},
        ],
        "openings": [{"id": "o0", "type": "door", "wall": "w0",
                      "along": [8.0, 11.0], "z": [0, 7.0], "hinge": "x0"}],
        "walls_poly": [], "columns": [], "furniture": [],
    }


def _mesh_names(scene):
    sc, meshes = G._build_scene(scene)
    return [n for n, _ in meshes]


def test_ml_door_gets_a_leaf():
    names = _mesh_names(_door_scene_ml())
    assert any(n.startswith("door_") for n in names), "every door needs a leaf"


def test_leaf_sits_at_the_opening_and_has_height():
    sc, meshes = G._build_scene(_door_scene_ml())
    leaf = next(m for n, m in meshes if n.startswith("door_"))
    lo, hi = leaf.bounds
    assert leaf.volume > 0
    # leaf top ~ door head 7ft in metres (Y = height axis), within tolerance
    assert 1.9 < hi[1] < 2.2                       # 7ft ~= 2.13 m
    # leaf stands near the south wall plane (plan-y ~ 0 -> glTF Z ~ 0): its
    # centre stays within ~1 ft of the wall even though it swings ajar
    cz = (lo[2] + hi[2]) / 2.0
    assert abs(cz) < 0.4                            # ~1 ft in metres
    # and it starts from the hinge jamb around x ~ 8 ft (2.44 m)
    assert 2.0 < lo[0] < 3.0


def test_vector_door_with_footprint_gets_a_leaf():
    scene = {
        "meta": {"wall_height_ft": 9.8},
        "walls": [], "walls_poly": [
            {"id": "wp0", "outer": [[0, 0], [20, 0], [20, 15], [0, 15]], "holes": []}],
        "openings": [{"id": "o0", "type": "door", "wall": "wp0",
                      "footprint": [8.0, 0.0, 11.0, 0.75], "z": [0, 7.0],
                      "hinge": "x0"}],
        "columns": [], "furniture": [],
    }
    assert any(n.startswith("door_") for n in _mesh_names(scene))


def test_no_door_no_leaf():
    scene = _door_scene_ml()
    scene["openings"] = [{"id": "o0", "type": "window", "wall": "w0",
                          "along": [8, 11], "z": [3, 7], "footprint": [8, 0, 11, 0.5]}]
    assert not any(n.startswith("door_") for n in _mesh_names(scene))


def test_glb_bytes_still_export_with_leaves():
    glb = G.build_glb_bytes(_door_scene_ml())
    assert glb[:4] == b"glTF" and len(glb) > 500
