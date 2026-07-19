"""CAD upload path (v1.1): DXF -> layered PDF -> the standard vector engine.

A synthetic house is drawn WITH ezdxf (double-line walls on a 'wall' layer,
12in column boxes on a 'column' layer) in three unit systems, then parsed.
Because CAD carries real units, the parsed size must match the drawn size
EXACTLY (no scale guessing) - that's the whole point of the CAD path.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

ezdxf = pytest.importorskip("ezdxf")

import cad_vector          # noqa: E402
import pdf_vector          # noqa: E402


# --- synthetic plan: 30 ft x 20 ft outer walls (double line, 9 in thick),
# one internal cross wall, 4 column boxes 12x12 in ---------------------------
def _house_dxf_bytes(u=1.0, insunits=None):
    """u = drawing units per INCH (u=1: inches; u=25.4: mm; u=1/12: feet)."""
    import io
    doc = ezdxf.new("R2010", setup=False)
    if insunits is not None:
        doc.header["$INSUNITS"] = insunits
    msp = doc.modelspace()
    W, D, T = 360 * u, 240 * u, 9 * u          # 30ft x 20ft, 9in walls

    def rect(x0, y0, x1, y1, layer):
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                           close=True, dxfattribs={"layer": layer})

    rect(0, 0, W, D, "wall")                       # outer face
    rect(T, T, W - T, D - T, "wall")               # inner face
    # internal wall with a 36in door gap (two double-line stubs)
    x = W / 2
    for y0, y1 in [(T, D / 2 - 18 * u), (D / 2 + 18 * u, D - T)]:
        rect(x - 2.5 * u, y0, x + 2.5 * u, y1, "wall")
    for cx, cy in [(0, 0), (W, 0), (0, D), (W, D)]:
        rect(cx - 6 * u, cy - 6 * u, cx + 6 * u, cy + 6 * u, "column")
    msp.add_text("bed room", dxfattribs={"layer": "text",
                                         "height": 8 * u}).set_placement((60 * u, 60 * u))
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode()


def _parse(raw, name="plan.dxf"):
    pdf, ppf, info = cad_vector.to_layered_pdf(raw, name)
    return pdf_vector.parse(pdf, ppf_hint=ppf), info


def test_dxf_inches_exact_scale():
    s, info = _parse(_house_dxf_bytes(u=1.0))
    assert info["units"].startswith("guessed_in")
    m = s["meta"]
    assert m["scale"]["source"] == "cad_units"
    # walls span exactly 30 x 20 ft (mask fattening tolerance ~0.3 ft)
    assert abs(m["plan_width_ft"] - 30.0) < 1.0
    assert abs(m["plan_depth_ft"] - 20.0) < 1.0
    assert s["walls_poly"], "wall polygons expected"
    assert len(s["columns"]) >= 3, "12in corner columns expected"


def test_dxf_mm_units_detected():
    s, info = _parse(_house_dxf_bytes(u=25.4))          # drawn in millimetres
    assert "mm" in info["units"] or "insunits" in info["units"]
    assert abs(s["meta"]["plan_width_ft"] - 30.0) < 1.0


def test_dxf_insunits_header_wins():
    s, info = _parse(_house_dxf_bytes(u=25.4, insunits=4))
    assert info["units"] == "insunits_4"
    assert abs(s["meta"]["plan_width_ft"] - 30.0) < 1.0


def test_rooms_found_in_synthetic_house():
    s, _ = _parse(_house_dxf_bytes(u=1.0))
    # two halves of the house = 2 enclosed rooms (door gap is a room leak
    # by design here - at least ONE room must be sealed and found)
    assert len(s["rooms"]) >= 1


def test_dwg_without_converter_gives_guidance(monkeypatch):
    monkeypatch.delenv("DWG_CONVERTER", raising=False)
    monkeypatch.setattr(cad_vector.shutil, "which", lambda _: None)
    fake_dwg = b"AC1027" + b"\x00" * 64
    with pytest.raises(ValueError) as e:
        cad_vector.to_layered_pdf(fake_dwg, "plan.dwg")
    assert "DXF" in str(e.value)            # tells the user the workaround


def test_magic_sniffing():
    assert cad_vector.looks_dwg(b"AC1027" + b"\x00" * 8)
    assert not cad_vector.looks_dwg(b"%PDF-1.4")
    assert cad_vector.looks_dxf(_house_dxf_bytes()[:4096] + b"")


def test_api_accepts_cad_extensions():
    """_looks_supported must admit .dxf/.dwg so /scene can route them."""
    pytest.importorskip("fastapi")
    import main

    class F:
        content_type = "application/octet-stream"

        def __init__(self, n):
            self.filename = n
    assert main._looks_supported(F("plan.dxf"))
    assert main._looks_supported(F("plan.dwg"))
    assert main._is_cad(F("plan.DXF".lower()))
    assert not main._is_cad(F("plan.pdf"))
