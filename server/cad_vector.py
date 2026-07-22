"""CAD uploads (DXF / DWG) -> the SAME layered-PDF engine as CAD PDFs.

Strategy (v1.1, launch-safe): instead of a second parsing engine, a DXF is
re-drawn into an in-memory vector PDF whose optional-content groups (OCGs)
carry the original DXF layer names. pdf_vector.parse() then reads it exactly
like an AutoCAD-exported PDF - same wall morphology, door snapping, wing
split, rooms. One difference: CAD coordinates are REAL units, so the scale
is exact (no dimension-text/column guessing) - we pass ppf_hint to parse().

DWG is DXF's closed binary twin. If a converter binary is available
(dwg2dxf from LibreDWG, or ODA FileConverter via DWG_CONVERTER env), DWG is
converted first; otherwise the user gets a friendly "export DXF" message.
"""
import math
import os
import shutil
import subprocess
import tempfile

PDF_PPF = 8.0                # pt per foot in the generated PDF
MARGIN_FT = 8.0              # blank margin around the building bbox
MAX_PAGE_PT = 13000.0        # PDF page hard limit is 14400 pt
MAX_SEGS = 250000            # sanity cap - a plan is thousands, not millions

# $INSUNITS -> inches per drawing unit
_INCH_PER = {1: 1.0, 2: 12.0, 4: 1 / 25.4, 5: 1 / 2.54, 6: 39.3701}
# no/unknown header: try the units seen in real Indian residential CAD,
# most common first
_UNIT_GUESSES = [(1.0, "in"), (1 / 25.4, "mm"), (39.3701, "m"),
                 (1 / 2.54, "cm"), (12.0, "ft")]

DWG_HELP = ("DWG conversion is not enabled on this server. In AutoCAD use "
            "SAVEAS > DXF (any version) and upload the .dxf - it carries the "
            "same drawing with full accuracy.")


def looks_dwg(raw):
    return raw[:2] == b"AC" and raw[2:6].isdigit()


def looks_dxf(raw):
    head = raw[:4096]
    return (b"SECTION" in head and (b"HEADER" in head or b"ENTITIES" in head)) \
        or head.startswith(b"AutoCAD Binary DXF")


def dwg_to_dxf(raw):
    """DWG bytes -> DXF bytes via an external converter, if one is installed.

    Looked up in order: DWG_CONVERTER env (full command path), dwg2dxf on
    PATH (LibreDWG). Raises ValueError with user guidance when absent."""
    conv = os.getenv("DWG_CONVERTER") or shutil.which("dwg2dxf")
    if not conv:
        raise ValueError(DWG_HELP)
    with tempfile.TemporaryDirectory(prefix="drishti_dwg_") as td:
        src = os.path.join(td, "in.dwg")
        dst = os.path.join(td, "out.dxf")
        with open(src, "wb") as f:
            f.write(raw)
        try:
            subprocess.run([conv, "-o", dst, src], check=True, timeout=120,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise ValueError("DWG conversion timed out - try exporting DXF instead")
        except Exception:
            raise ValueError("DWG conversion failed on this file. " + DWG_HELP)
        if not os.path.exists(dst) or os.path.getsize(dst) == 0:
            raise ValueError("DWG conversion produced nothing. " + DWG_HELP)
        with open(dst, "rb") as f:
            return f.read()


def _load_doc(raw):
    """DXF bytes -> ezdxf document (recover mode: real-world files are dirty)."""
    import ezdxf
    from ezdxf import recover
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        f.write(raw)
        path = f.name
    try:
        try:
            doc = ezdxf.readfile(path)
        except Exception:
            doc, _auditor = recover.readfile(path)
        return doc
    finally:
        os.unlink(path)


def _flatten(e, depth=0):
    """One DXF entity -> ('seg', layer, [(x1,y1,x2,y2)...]) and/or
    ('text', layer, (x, y, height, string)) tuples. INSERTs are exploded."""
    kind = e.dxftype()
    layer = e.dxf.layer if e.dxf.hasattr("layer") else "0"
    if kind == "LINE":
        a, b = e.dxf.start, e.dxf.end
        yield ("seg", layer, [(a.x, a.y, b.x, b.y)])
    elif kind == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in e.get_points()]
        segs = [(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                for i in range(len(pts) - 1)]
        if e.closed and len(pts) > 2:
            segs.append((pts[-1][0], pts[-1][1], pts[0][0], pts[0][1]))
        if segs:
            yield ("seg", layer, segs)
    elif kind == "POLYLINE" and not e.is_3d_polyline:
        pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
        segs = [(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                for i in range(len(pts) - 1)]
        if e.is_closed and len(pts) > 2:
            segs.append((pts[-1][0], pts[-1][1], pts[0][0], pts[0][1]))
        if segs:
            yield ("seg", layer, segs)
    elif kind in ("ARC", "CIRCLE", "ELLIPSE", "SPLINE"):
        try:
            pts = [(p.x, p.y) for p in e.flattening(0.5)]
            if len(pts) >= 2:      # degenerate curves flatten to 0-1 points
                yield ("seg", layer, [(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                                      for i in range(len(pts) - 1)])
        except Exception:
            pass
    elif kind in ("SOLID", "TRACE", "3DFACE"):
        try:
            pts = [(e.dxf.vtx0.x, e.dxf.vtx0.y), (e.dxf.vtx1.x, e.dxf.vtx1.y),
                   (e.dxf.vtx3.x, e.dxf.vtx3.y), (e.dxf.vtx2.x, e.dxf.vtx2.y)]
            yield ("seg", layer, [(pts[i][0], pts[i][1],
                                   pts[(i + 1) % 4][0], pts[(i + 1) % 4][1])
                                  for i in range(4)])
        except Exception:
            pass
    elif kind == "TEXT":
        p = e.dxf.insert
        yield ("text", layer, (p.x, p.y, float(e.dxf.height or 1.0),
                               e.dxf.text or ""))
    elif kind == "MTEXT":
        p = e.dxf.insert
        yield ("text", layer, (p.x, p.y, float(e.dxf.char_height or 1.0),
                               e.plain_text() or ""))
    elif kind == "INSERT" and depth < 4:
        try:
            for v in e.virtual_entities():
                yield from _flatten(v, depth + 1)
        except Exception:
            pass


def _extract(doc):
    """Modelspace -> (seg_items, text_items). seg_items = list of
    (layer, [segs]) per source entity (bbox per entity matters for columns,
    doors and windows downstream)."""
    seg_items, text_items, n = [], [], 0
    for e in doc.modelspace():
        for kind, layer, data in _flatten(e):
            if kind == "seg":
                n += len(data)
                if n > MAX_SEGS:
                    raise ValueError("drawing too complex (segment cap hit)")
                seg_items.append((layer, data))
            else:
                text_items.append((layer, data))
    if not seg_items:
        raise ValueError("no 2D geometry found in this CAD file")
    return seg_items, text_items


def _is_wall_name(name):
    n = name.lower()
    return "wall" in n and "door" not in n and "boundary" not in n


def _is_col_name(name):
    n = name.lower()
    return "column" in n or n == "col"


def _bbox(items):
    xs, ys = [], []
    for _layer, segs in items:
        for x1, y1, x2, y2 in segs:
            xs += [x1, x2]
            ys += [y1, y2]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def _dominant_col_ft(seg_items, inch_per_unit):
    """Dominant column-box size in ft (columns are drawn as small squares)."""
    sizes = []
    for layer, segs in seg_items:
        if not _is_col_name(layer):
            continue
        b = _bbox([(layer, segs)])
        w = (b[2] - b[0]) * inch_per_unit / 12.0
        h = (b[3] - b[1]) * inch_per_unit / 12.0
        m = max(w, h)
        if 0.3 < m < 3.0 and 0.5 < (w / (h + 1e-9)) < 2.0:
            sizes.append(round(m, 1))
    if not sizes:
        return None
    return max(set(sizes), key=sizes.count)


def detect_units(doc, seg_items):
    """(inch_per_unit, source_str). The $INSUNITS header is only a CANDIDATE:
    real-world files routinely carry a wrong one (it controls block insert
    scaling, not what the drafter actually drew - ezdxf even defaults new
    files to metres). Every candidate is scored by plausibility: building
    width from the wall layers must land in 12..400 ft, and the dominant
    column box (if any) in 0.5..2.2 ft. Header wins ties only."""
    iu = doc.header.get("$INSUNITS", 0)
    walls = [it for it in seg_items if _is_wall_name(it[0])]
    ref = _bbox(walls) or _bbox(seg_items)
    span_units = max(ref[2] - ref[0], ref[3] - ref[1])
    cands = []
    if iu in _INCH_PER:
        cands.append((_INCH_PER[iu], f"insunits_{iu}", 0.5))   # tie-break bonus
    cands += [(k, f"guessed_{tag}", 0.0) for k, tag in _UNIT_GUESSES]
    best = None
    for k, tag, bonus in cands:
        w_ft = span_units * k / 12.0
        if not (12.0 <= w_ft <= 400.0):
            continue
        col = _dominant_col_ft(seg_items, k)
        score = 1.0 + bonus
        if col is not None:
            score += 2.0 if 0.5 <= col <= 2.2 else -2.0
        if best is None or score > best[0]:
            best = (score, k, tag)
    if best:
        return best[1], best[2]
    if iu in _INCH_PER:                  # nothing plausible - trust the header
        return _INCH_PER[iu], f"insunits_{iu}"
    return 1.0, "fallback_in"            # parser warnings will flag the rest


def to_layered_pdf(raw, filename=""):
    """CAD bytes (.dxf or .dwg) -> (pdf_bytes, ppf, info dict).

    ppf is EXACT (pt per foot of the generated page) - hand it to
    pdf_vector.parse(..., ppf_hint=ppf) so no scale guessing happens."""
    import fitz

    name = (filename or "").lower()
    if looks_dwg(raw) or name.endswith(".dwg"):
        raw = dwg_to_dxf(raw)
    doc = _load_doc(raw)
    seg_items, text_items = _extract(doc)
    inch_per_unit, unit_src = detect_units(doc, seg_items)

    # region of interest = wall+column layers bbox + margin (sheets carry
    # title blocks / elevations / site boundaries far from the plan)
    core = [it for it in seg_items
            if _is_wall_name(it[0]) or _is_col_name(it[0])]
    roi = _bbox(core) or _bbox(seg_items)
    m_units = MARGIN_FT * 12.0 / inch_per_unit
    rx0, ry0 = roi[0] - m_units, roi[1] - m_units
    rx1, ry1 = roi[2] + m_units, roi[3] + m_units

    def _touches(b):
        return not (b[2] < rx0 or rx1 < b[0] or b[3] < ry0 or ry1 < b[1])

    w_ft = (rx1 - rx0) * inch_per_unit / 12.0
    d_ft = (ry1 - ry0) * inch_per_unit / 12.0
    ppf = PDF_PPF
    if max(w_ft, d_ft) * ppf > MAX_PAGE_PT:
        ppf = MAX_PAGE_PT / max(w_ft, d_ft)
    s = ppf * inch_per_unit / 12.0          # pdf pt per drawing unit

    def tx(x):
        return (x - rx0) * s

    def ty(y):
        return (ry1 - y) * s                # DXF y-up -> PDF y-down

    pdf = fitz.open()
    page = pdf.new_page(width=(rx1 - rx0) * s, height=(ry1 - ry0) * s)
    ocgs = {}

    def ocg(layer):
        if layer not in ocgs:
            ocgs[layer] = pdf.add_ocg(layer, on=True)
        return ocgs[layer]

    kept = 0
    for layer, segs in seg_items:
        b = _bbox([(layer, segs)])
        if b is None or not _touches(b):
            continue
        sh = page.new_shape()
        # a small axis-aligned closed box becomes a RECT item (columns and
        # window symbols are detected via rect-ish drawing bboxes downstream)
        for x1, y1, x2, y2 in segs:
            sh.draw_line(fitz.Point(tx(x1), ty(y1)), fitz.Point(tx(x2), ty(y2)))
        sh.finish(width=0.5, color=(0, 0, 0), oc=ocg(layer))
        sh.commit()
        kept += 1
    for layer, (x, y, h, txt) in text_items:
        if not txt.strip():
            continue
        if not (rx0 <= x <= rx1 and ry0 <= y <= ry1):
            continue
        fs = max(2.0, min(24.0, h * s))
        try:
            page.insert_text(fitz.Point(tx(x), ty(y)), txt.strip()[:80],
                             fontsize=fs, oc=ocg(layer))
        except Exception:
            pass
    if not kept:
        raise ValueError("no drawing geometry near the wall/column layers")

    info = {"units": unit_src, "inch_per_unit": inch_per_unit,
            "entities": kept, "layers": sorted(ocgs),
            "roi_ft": [round(w_ft, 1), round(d_ft, 1)]}
    return pdf.tobytes(), ppf, info
