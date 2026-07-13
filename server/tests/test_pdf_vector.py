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
    assert o["z"][0] == 0 and o["z"][1] == pytest.approx(7.0)


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


# --- text-like decoy layers (real exports have a 'wall' layer full of outlined text) ---
def _make_pdf_with_text_junk():
    """Real building on 'AR Wall' + columns, PLUS a decoy layer named 'wall'
    holding hundreds of sub-point strokes (outlined title-block lettering)."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=1200, height=800)
    wall = doc.add_ocg("AR Wall")
    page.draw_rect(fitz.Rect(100, 100, 500, 300), color=(0, 0, 0), oc=wall)
    page.draw_rect(fitz.Rect(108, 108, 492, 292), color=(0, 0, 0), oc=wall)
    col = doc.add_ocg("COLUMN")
    for x, y in ((100, 100), (490, 290), (100, 290)):
        page.draw_rect(fitz.Rect(x, y, x + 10, y + 10),
                       color=(0, 0, 0), fill=(0, 0, 0), oc=col)
    junk = doc.add_ocg("wall")   # decoy: same keyword, but it's text linework
    for i in range(400):
        x = 700 + (i % 40) * 2.0
        y = 600 + (i // 40) * 3.0
        page.draw_line(fitz.Point(x, y), fitz.Point(x + 0.4, y + 0.3), oc=junk)
    return doc.tobytes()


def test_text_junk_wall_layer_is_dropped():
    s = parse(_make_pdf_with_text_junk())
    # junk must not stretch the plan (regression: it also disabled the crop guard)
    assert s["meta"]["plan_width_ft"] == pytest.approx(40.0, abs=0.2)
    assert s["meta"]["plan_depth_ft"] == pytest.approx(20.0, abs=0.2)
    assert any("text-like" in w for w in s["meta"]["warnings"])
    for w in s["walls_poly"]:
        assert max(p[0] for p in w["outer"]) < 45


def test_real_wall_layers_not_dropped_by_text_filter():
    s = parse(_make_pdf())
    assert not any("text-like" in w for w in s["meta"]["warnings"])
    assert len(s["walls_poly"]) >= 1


# --- door snapped onto the real doorway gap (header/lintel fix) ---
def _make_pdf_with_doorway():
    """Double-line building outline whose bottom edge has a REAL 30 pt doorway
    gap (both wall lines stop at the jambs), swing box drawn beside it."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=1200, height=800)
    wall = doc.add_ocg("AR Wall")

    def ln(a, b):
        page.draw_line(fitz.Point(*a), fitz.Point(*b), oc=wall)

    for y in (100, 108):                       # top edge: gap x 300..330
        ln((100, y), (300, y)); ln((330, y), (500, y))
    for y in (292, 300):                       # bottom edge, continuous
        ln((100, y), (500, y))
    for x in (100, 108):                       # left edge
        ln((x, 100), (x, 300))
    for x in (492, 500):                       # right edge
        ln((x, 100), (x, 300))
    door = doc.add_ocg("ALL DOOR")             # swing box just inside the room

    def dln(a, b):
        page.draw_line(fitz.Point(*a), fitz.Point(*b), oc=door)

    dln((300, 108), (300, 138))                # leaf (3 ft, open position)
    dln((300, 138), (315, 130)); dln((315, 130), (330, 112))  # arc fragments
    col = doc.add_ocg("COLUMN")
    for x, y in ((100, 100), (490, 290), (100, 290)):
        page.draw_rect(fitz.Rect(x, y, x + 10, y + 10),
                       color=(0, 0, 0), fill=(0, 0, 0), oc=col)
    return doc.tobytes()


def test_door_snaps_onto_doorway_gap():
    from shapely.geometry import Polygon, box as sbox
    s = parse(_make_pdf_with_doorway())
    doors = [o for o in s["openings"] if o["type"] == "door"]
    assert len(doors) == 1
    o = doors[0]
    assert "swing_area" in o
    assert not any("gap not found" in w for w in s["meta"]["warnings"])
    assert o["snapped"] is True
    x0, y0, x1, y1 = o["footprint"]
    assert x1 - x0 == pytest.approx(3.0, abs=0.8)      # door-width along the wall
    assert y1 - y0 < 2.0                               # thin like a wall
    assert y1 > 18.0                                   # sits ON the top wall band
    # the strip must genuinely overlap wall geometry (it was filled in)
    walls = [Polygon(w["outer"], w.get("holes") or None).buffer(0)
             for w in s["walls_poly"]]
    cut = sbox(x0, y0, x1, y1)
    assert sum(cut.intersection(w).area for w in walls) > 0.5


def test_door_without_gap_falls_back_with_warning():
    s = parse(_make_pdf(with_door=True))       # continuous walls, no gap
    doors = [o for o in s["openings"] if o["type"] == "door"]
    assert len(doors) == 1
    assert "swing_area" in doors[0]
    assert doors[0]["snapped"] is False
    assert any("gap not found" in w for w in s["meta"]["warnings"])


# --- Stage 1-3 (2026-07-10 late): text scale, geometry walls, wing split ---
def _add_dim_lines(doc, page, ppf=10.0, n=9, y0=740):
    """n horizontal dimension lines of 10'-0\" with the text hugging each line
    (the pattern _text_scale votes on)."""
    import fitz
    for k in range(n):
        y = y0 + k * 6
        page.draw_line(fitz.Point(600, y), fitz.Point(600 + 10 * ppf, y))
        page.insert_text(fitz.Point(600 + 5 * ppf - 8, y - 1.5), "10'-0\"", fontsize=4)


def test_scale_from_dimension_text_beats_columns():
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=1200, height=800)
    wall = doc.add_ocg("AR Wall")
    page.draw_rect(fitz.Rect(100, 100, 500, 300), color=(0, 0, 0), oc=wall)
    page.draw_rect(fitz.Rect(108, 108, 492, 292), color=(0, 0, 0), oc=wall)
    col = doc.add_ocg("COLUMN")
    for x, y in ((100, 100), (490, 290), (100, 290)):
        page.draw_rect(fitz.Rect(x, y, x + 10, y + 10),
                       color=(0, 0, 0), fill=(0, 0, 0), oc=col)
    _add_dim_lines(doc, page, ppf=10.0)
    s = parse(doc.tobytes())
    assert s["meta"]["scale"]["source"] == "dimension_text"
    assert s["meta"]["scale"]["pt_per_ft"] == pytest.approx(10.0, abs=0.3)


def _double_line_box(page, x0, y0, x1, y1, off=4.0, oc=None):
    """A wall drawn the honest way: two parallel LINES per side, `off` pt apart."""
    import fitz
    for d in (0, off):
        page.draw_line(fitz.Point(x0 + d, y0 + d), fitz.Point(x1 - d, y0 + d), oc=oc)
        page.draw_line(fitz.Point(x1 - d, y0 + d), fitz.Point(x1 - d, y1 - d), oc=oc)
        page.draw_line(fitz.Point(x1 - d, y1 - d), fitz.Point(x0 + d, y1 - d), oc=oc)
        page.draw_line(fitz.Point(x0 + d, y1 - d), fitz.Point(x0 + d, y0 + d), oc=oc)


def test_geometry_mode_without_wall_layer():
    """Walls on layer '0' (no wall/column layer names) -> geometry detection +
    text scale must still produce the building."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=1200, height=800)
    zero = doc.add_ocg("0")
    _double_line_box(page, 100, 100, 500, 300, oc=zero)
    _add_dim_lines(doc, page, ppf=10.0)
    s = parse(doc.tobytes())
    assert s["meta"]["source"] == "vector_pdf_geometry"
    assert s["meta"]["scale"]["source"] == "dimension_text"
    assert len(s["walls_poly"]) >= 1
    assert s["meta"]["plan_width_ft"] == pytest.approx(40.0, abs=1.5)
    assert s["meta"]["plan_depth_ft"] == pytest.approx(20.0, abs=1.5)


def test_is_vector_plan_true_for_bare_linework():
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=1200, height=800)
    zero = doc.add_ocg("0")
    for k in range(80):
        y = 100 + k * 2
        page.draw_line(fitz.Point(100, y), fitz.Point(300, y), oc=zero)
    assert is_vector_plan(doc.tobytes()) is True


def test_wing_split_two_blocks():
    """Two separate blocks on one sheet -> wing 0 = largest, translated to
    origin; wing=1 = the other; no overlap between modules."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=1200, height=800)
    zero = doc.add_ocg("0")
    _double_line_box(page, 100, 100, 500, 300, oc=zero)   # big block 40x20 ft
    _double_line_box(page, 100, 600, 300, 700, oc=zero)   # small block 20x10 ft
    _add_dim_lines(doc, page, ppf=10.0, y0=740)
    s0 = parse(doc.tobytes())
    assert s0["meta"]["wing"]["count"] == 2
    assert s0["meta"]["plan_width_ft"] == pytest.approx(40.0, abs=1.5)
    assert s0["meta"]["plan_depth_ft"] == pytest.approx(20.0, abs=1.5)
    xs = [p[0] for w in s0["walls_poly"] for p in w["outer"]]
    ys = [p[1] for w in s0["walls_poly"] for p in w["outer"]]
    assert min(xs) > -1.5 and min(ys) > -1.5          # translated to origin
    assert max(xs) < 42 and max(ys) < 22              # ...and ONLY this wing
    s1 = parse(doc.tobytes(), wing=1)
    assert s1["meta"]["plan_width_ft"] == pytest.approx(20.0, abs=1.5)
    assert s1["meta"]["plan_depth_ft"] == pytest.approx(10.0, abs=1.5)


def test_door_scale_sanity_warns_on_bad_scale():
    from pdf_vector import _door_scale_sanity
    mk = lambda w: {"type": "door", "snapped": True, "footprint": [0, 0, w, 0.6]}
    warnings = []
    _door_scale_sanity([mk(1.4)] * 6, warnings)        # 1.4 ft "doors" = wrong scale
    assert any("SCALE SUSPECT" in w for w in warnings)
    warnings = []
    _door_scale_sanity([mk(3.0)] * 6, warnings)        # healthy doors -> silent
    assert not warnings
    warnings = []
    _door_scale_sanity([mk(1.4)] * 3, warnings)        # too few to judge -> silent
    assert not warnings


def test_wing_arg_conversion():
    from pdf_vector import wing_arg
    assert wing_arg("1") == 1 and wing_arg(0) == 0
    assert wing_arg("largest") == "largest"
    assert wing_arg(None) == "largest" and wing_arg("x") == "largest"


def test_stair_treads_are_not_walls():
    """>=4 parallel lines at tread spacing (a staircase) must NOT become
    walls, while the real double-line building survives."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=1200, height=800)
    zero = doc.add_ocg("0")
    _double_line_box(page, 100, 100, 500, 300, oc=zero)
    for k in range(8):                       # stair: treads 8 pt (=0.8 ft) apart
        y = 150 + k * 8
        page.draw_line(fitz.Point(200, y), fitz.Point(280, y), oc=zero)
    _add_dim_lines(doc, page, ppf=10.0)
    s = parse(doc.tobytes())
    assert any("stair filter" in w for w in s["meta"]["warnings"])
    # treads span x 10..18 ft, y 15..20.6 ft: no wall poly may FILL that patch
    from shapely.geometry import Polygon, box as sbox
    patch = sbox(10.5, 9.8, 17.5, 14.6)      # centre of the tread field (ft, y-up)
    filled = sum(Polygon(w["outer"], w.get("holes") or None).buffer(0)
                 .intersection(patch).area for w in s["walls_poly"])
    assert filled < 0.25 * patch.area
    assert s["meta"]["plan_width_ft"] == pytest.approx(40.0, abs=1.5)
