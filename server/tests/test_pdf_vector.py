"""Tests for Step D1 - vector CAD PDF -> scene.json (layer parser).
Builds synthetic layered PDFs in memory with PyMuPDF - no real plan needed.
Layer names deliberately mimic the real export ('AR Wall', 'COLUMN', 'ALL DOOR')."""
import pytest

from pdf_vector import is_vector_plan, parse


def _make_pdf(with_columns=True, with_window=True, with_door=False,
              wall_layer="wall", rotation=0, stray_wall=False):
    """400x200 pt building outline (double-line rect) + optional 10 pt (=1 ft)
    corner columns => ppf 10, a 40x8 pt window, a ~30 pt door fragment cluster,
    and optionally a stray far-away 'wall' square (site compound wall)."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=1200, height=800)
    wall = doc.add_ocg(wall_layer)
    page.draw_rect(fitz.Rect(100, 100, 500, 300), color=(0, 0, 0), oc=wall)
    page.draw_rect(fitz.Rect(108, 108, 492, 292), color=(0, 0, 0), oc=wall)
    if stray_wall:
        page.draw_rect(fitz.Rect(700, 500, 1100, 780), color=(0, 0, 0), oc=wall)
    if with_window:
        win = doc.add_ocg("window")
        page.draw_rect(fitz.Rect(200, 100, 240, 108), color=(0, 0, 0), oc=win)
    if with_door:
        door = doc.add_ocg("ALL DOOR")
        # a door as several small fragments (leaf + arc pieces), like real CAD
        page.draw_line(fitz.Point(300, 108), fitz.Point(300, 138), oc=door)
        page.draw_line(fitz.Point(300, 138), fitz.Point(315, 130), oc=door)
        page.draw_line(fitz.Point(315, 130), fitz.Point(330, 112), oc=door)
    if with_columns:
        col = doc.add_ocg("COLUMN")
        for x, y in ((100, 100), (490, 290), (100, 290)):
            page.draw_rect(fitz.Rect(x, y, x + 10, y + 10),
                           color=(0, 0, 0), fill=(0, 0, 0), oc=col)
    if rotation:
        page.set_rotation(rotation)
    return doc.tobytes()


def test_is_vector_plan_true_for_layered_pdf():
    assert is_vector_plan(_make_pdf()) is True


def test_is_vector_plan_true_for_real_style_names():
    assert is_vector_plan(_make_pdf(wall_layer="AR Wall")) is True


def test_is_vector_plan_false_for_flat_pdf():
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    page.draw_rect(fitz.Rect(100, 100, 500, 300), color=(0, 0, 0))  # no layer
    assert is_vector_plan(doc.tobytes()) is False


def test_is_vector_plan_false_for_non_pdf():
    assert is_vector_plan(b"\x89PNG not a pdf") is False


def test_parse_scale_from_columns_case_insensitive():
    s = parse(_make_pdf(wall_layer="AR Wall"))
    assert s["meta"]["scale"]["source"] == "column_box_12in"
    assert s["meta"]["scale"]["pt_per_ft"] == pytest.approx(10.0)
    assert s["meta"]["plan_width_ft"] == pytest.approx(40.0, abs=0.2)
    assert s["meta"]["plan_depth_ft"] == pytest.approx(20.0, abs=0.2)


def test_parse_scale_fallback_to_width_ft():
    s = parse(_make_pdf(with_columns=False, with_window=False), width_ft=40.0)
    assert s["meta"]["scale"]["source"] == "assumed_width"
    assert s["meta"]["scale"]["pt_per_ft"] == pytest.approx(10.0, abs=0.1)


def test_parse_no_scale_raises():
    with pytest.raises(ValueError):
        parse(_make_pdf(with_columns=False, with_window=False), width_ft=None)


def test_parse_walls_poly_ring_with_hole():
    s = parse(_make_pdf())
    assert s["walls"] == []
    assert len(s["walls_poly"]) >= 1
    w = s["walls_poly"][0]
    assert len(w["outer"]) >= 4 and len(w["holes"]) >= 1
    xs = [p[0] for p in w["outer"]]; ys = [p[1] for p in w["outer"]]
    assert max(xs) - min(xs) == pytest.approx(40.0, abs=1.5)
    assert max(ys) - min(ys) == pytest.approx(20.0, abs=1.5)


def test_stray_drawing_outside_columns_is_cropped():
    s = parse(_make_pdf(stray_wall=True))
    # the far-away compound-wall square must NOT stretch the plan
    assert s["meta"]["plan_width_ft"] == pytest.approx(40.0, abs=0.2)
    assert s["meta"]["plan_depth_ft"] == pytest.approx(20.0, abs=0.2)
    for w in s["walls_poly"]:
        assert max(p[0] for p in w["outer"]) < 45


def test_rotated_page_parses_to_same_building():
    s = parse(_make_pdf(rotation=270))
    dims = sorted([s["meta"]["plan_width_ft"], s["meta"]["plan_depth_ft"]])
    assert dims[0] == pytest.approx(20.0, abs=0.3)
    assert dims[1] == pytest.approx(40.0, abs=0.3)
    assert len(s["walls_poly"]) >= 1


def test_parse_window_footprint_and_z():
    s = parse(_make_pdf())
    wins = [o for o in s["openings"] if o["type"] == "window"]
    assert len(wins) == 1
    o = wins[0]
    x0, y0, x1, y1 = o["footprint"]
    assert x0 == pytest.approx(10.0, abs=0.1) and x1 == pytest.approx(14.0, abs=0.1)
    assert y1 == pytest.approx(20.0, abs=0.2)
    assert o["z"] == [3.0, 7.0]


def test_parse_door_cluster():
    s = parse(_make_pdf(with_door=True))
    doors = [o for o in s["openings"] if o["type"] == "door"]
    assert len(doors) == 1
    o = doors[0]
    x0, y0, x1, y1 = o["footprint"]
    assert x1 - x0 == pytest.approx(3.0, abs=0.3)     # 30 pt cluster = 3 ft door
    assert o["z"][0] == 0 and o["z"][1] == pytest.approx(6.89)


def test_parse_columns_deduplicated():
    s = parse(_make_pdf())
    assert len(s["columns"]) == 3
    c = s["columns"][0]
    assert c["w"] == pytest.approx(1.0) and c["d"] == pytest.approx(1.0)


def test_parse_flat_pdf_raises():
    import fitz
    doc = fitz.open()
    doc.new_page(width=600, height=400)
    with pytest.raises(ValueError):
        parse(doc.tobytes(), width_ft=40.0)


# --- GLB banding for polygon walls ---
def test_poly_bands_no_window_single_prism():
    from scene_to_glb import poly_bands
    wall = {"id": "wp0", "outer": [[0, 0], [10, 0], [10, 2], [0, 2]], "holes": []}
    bands = poly_bands(wall, 9.843, [])
    assert len(bands) == 1
    geom, z0, z1 = bands[0]
    assert (z0, z1) == (0.0, 9.843) and geom.area == pytest.approx(20.0)


def test_poly_bands_window_cuts_middle_band():
    from scene_to_glb import poly_bands
    wall = {"id": "wp0", "outer": [[0, 0], [10, 0], [10, 2], [0, 2]], "holes": []}
    ops = [{"id": "o0", "type": "window", "footprint": [4, 0, 6, 2], "z": [3.0, 7.0]}]
    bands = poly_bands(wall, 9.843, ops)
    assert len(bands) == 3
    (g0, a0, a1), (g1, b0, b1), (g2, c0, c1) = bands
    assert (a0, a1) == (0.0, 3.0) and g0.area == pytest.approx(20.0)
    assert (b0, b1) == (3.0, 7.0) and g1.area == pytest.approx(16.0)
    assert (c0, c1) == (7.0, 9.843) and g2.area == pytest.approx(20.0)


def test_poly_bands_door_cuts_bottom_band():
    from scene_to_glb import poly_bands
    wall = {"id": "wp0", "outer": [[0, 0], [10, 0], [10, 2], [0, 2]], "holes": []}
    ops = [{"id": "o0", "type": "door", "footprint": [4, 0, 7, 2], "z": [0, 6.89]}]
    bands = poly_bands(wall, 9.843, ops)
    assert len(bands) == 2
    (g0, a0, a1), (g1, b0, b1) = bands
    assert (a0, a1) == (0.0, 6.89) and g0.area == pytest.approx(20.0 - 6.0)
    assert (b0, b1) == (6.89, 9.843) and g1.area == pytest.approx(20.0)


def test_build_glb_from_polygon_scene(tmp_path):
    from scene_to_glb import build_glb
    scene = {
        "meta": {"wall_height_ft": 9.843},
        "walls": [],
        "walls_poly": [{"id": "wp0", "outer": [[0, 0], [10, 0], [10, 2], [0, 2]],
                        "holes": []}],
        "openings": [{"id": "o0", "type": "window", "footprint": [4, 0, 6, 2],
                      "z": [3.0, 7.0]},
                     {"id": "o1", "type": "door", "footprint": [7, 0, 10, 2],
                      "z": [0, 6.89]}],
    }
    out = tmp_path / "poly.glb"
    build_glb(scene, str(out))
    assert out.exists() and out.stat().st_size > 500
