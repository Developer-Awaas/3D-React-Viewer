"""G4: CubiCasa fixture icons (Toilet/Sink/Bathtub/Closet) -> renderable
furniture (was discarded). Pure tests + scene_builder + GLB wiring, no torch."""
import numpy as np

import perception
import scene_builder as SB
import scene_to_glb as G


def _icon_map():
    """80x80 icon map with a Toilet block and a Sink block (indices from
    perception.ICON_CLASSES)."""
    m = np.zeros((80, 80), dtype=int)
    m[10:20, 10:20] = perception.ICON_CLASSES.index("Toilet")
    m[10:20, 50:58] = perception.ICON_CLASSES.index("Sink")
    m[50:66, 50:66] = perception.ICON_CLASSES.index("Bathtub")
    return m


def test_furniture_from_icons_maps_types():
    furn = perception.furniture_from_icons(_icon_map(), min_area_frac=0.0)
    types = sorted(f["type"] for f in furn)
    assert types == ["basin", "bathtub", "commode"]
    toi = next(f for f in furn if f["type"] == "commode")
    assert 14 < toi["cx"] < 16 and 14 < toi["cy"] < 16     # centroid ~ (15,15)


def test_tiny_icon_specks_dropped():
    m = np.zeros((200, 200), dtype=int)
    m[0:2, 0:2] = perception.ICON_CLASSES.index("Toilet")   # 4px speck
    assert perception.furniture_from_icons(m) == []


def test_scene_builder_places_nominal_sized_furniture():
    furn_px = [{"type": "commode", "cx": 50.0, "cy": 25.0}]
    scene = SB.scene_from_segments([[0, 0, 100, 0]], 100, 50, width_ft=20.0,
                                   furniture_px=furn_px)
    assert len(scene["furniture"]) == 1
    f = scene["furniture"][0]
    assert f["type"] == "commode"
    assert f["w"] == 1.5 and f["d"] == 2.2                  # nominal size in ft
    # centred at the icon (50,25)px -> (10, 5)ft, corner = centre - size/2
    assert abs(f["x"] - (10.0 - 0.75)) < 0.01
    assert abs(f["y"] - (5.0 - 1.1)) < 0.01


def test_glb_renders_all_fixture_types():
    scene = {
        "meta": {"wall_height_ft": 9.8}, "walls": [], "walls_poly": [],
        "openings": [], "columns": [],
        "furniture": [
            {"type": "commode", "x": 2, "y": 2, "w": 1.5, "d": 2.2},
            {"type": "basin", "x": 6, "y": 2, "w": 1.3, "d": 1.0},
            {"type": "bathtub", "x": 2, "y": 8, "w": 2.5, "d": 5.0},
            {"type": "cupboard", "x": 10, "y": 2, "w": 2.0, "d": 2.0},
        ],
    }
    glb = G.build_glb_bytes(scene)
    assert glb[:4] == b"glTF" and len(glb) > 500
    _sc, meshes = G._build_scene(scene)
    names = [n for n, _ in meshes]
    assert any("furn_bathtub" in n for n in names)          # bathtub renderer ran
