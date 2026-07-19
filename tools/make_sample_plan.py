#!/usr/bin/env python3
"""Build the bundled DEMO assets: a synthetic 2BHK CAD-style PDF (layers,
double-line walls, door swings, window rects, columns) run through the REAL
engine -> public/sample.glb + sample.meta.json + sample-plan.pdf.

Why synthetic: client drawings are confidential (plans/ is gitignored); the
demo must ship clean. Run from repo root or tools/:

    python tools/make_sample_plan.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "server"))

PPF = 10.0          # pt per ft (columns 10 pt = 12 in drive the scale)
X0, Y0 = 100, 100   # building origin on the page
W_FT, D_FT = 40, 28


def _pt(xf, yf):
    return X0 + xf * PPF, Y0 + yf * PPF


def build_pdf():
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=800, height=560)
    wall = doc.add_ocg("AR Wall")
    win = doc.add_ocg("window")
    door = doc.add_ocg("ALL DOOR")
    col = doc.add_ocg("COLUMN")
    furn = doc.add_ocg("furniture")
    san = doc.add_ocg("SANITARY")
    kit = doc.add_ocg("KITCHEN-SYMB")

    def ln(a, b, oc=wall):
        page.draw_line(fitz.Point(*a), fitz.Point(*b), oc=oc)

    def _split(spans, gaps):
        """Subtract gap ranges from spans - a gap only cuts spans it
        actually intersects (the old one-liner bridged doorways)."""
        for g0, g1 in gaps:
            out = []
            for a, b in spans:
                if g1 <= a or g0 >= b:
                    out.append((a, b))
                    continue
                if g0 - a > 0.05:
                    out.append((a, g0))
                if b - g1 > 0.05:
                    out.append((g1, b))
            spans = out
        return spans

    def dwall(x0f, y0f, x1f, y1f, gaps=()):
        """Axis-aligned double-line wall (6 in) with door gaps (ft ranges
        along the wall). gaps apply to BOTH faces - CAD style."""
        horiz = y0f == y1f
        off = 0.5  # ft between the two faces
        for k in (0, off):
            if horiz:
                for a, b in _split([(x0f, x1f)], gaps):
                    ln(_pt(a, y0f + k), _pt(b, y0f + k))
            else:
                for a, b in _split([(y0f, y1f)], gaps):
                    ln(_pt(x0f + k, a), _pt(x0f + k, b))

    def swing_h(gx, wy, wf, up=1):
        """Swing beside a gap in a HORIZONTAL wall: leaf on the hinge jamb,
        two arc fragments sweeping to the far jamb (real CAD anatomy)."""
        p0 = _pt(gx, wy + 0.55 * up)
        p1 = _pt(gx, wy + (0.55 + wf) * up)
        ln(p0, p1, oc=door)
        m = _pt(gx + 0.45 * wf, wy + (0.55 + 0.8 * wf) * up)
        e = _pt(gx + wf, wy + 0.7 * up)
        ln(p1, m, oc=door)
        ln(m, e, oc=door)

    def swing_v(wx, gy, wf, right=1):
        """Swing beside a gap in a VERTICAL wall."""
        p0 = _pt(wx + 0.55 * right, gy)
        p1 = _pt(wx + (0.55 + wf) * right, gy)
        ln(p0, p1, oc=door)
        m = _pt(wx + (0.55 + 0.8 * wf) * right, gy + 0.45 * wf)
        e = _pt(wx + 0.7 * right, gy + wf)
        ln(p1, m, oc=door)
        ln(m, e, oc=door)

    def wrect(x0f, y0f, x1f, y1f):
        page.draw_rect(fitz.Rect(*_pt(x0f, y0f), *_pt(x1f, y1f)), oc=win)

    def column(xf, yf):
        r = fitz.Rect(*_pt(xf, yf), *_pt(xf + 1, yf + 1))
        page.draw_rect(r, fill=(0, 0, 0), oc=col)

    # ---- outer envelope 40 x 28 ft, door gap = main entrance on the south
    dwall(0, 0, 40, 0, gaps=[(18, 21.5)])          # south (entrance 3'6")
    dwall(0, 28, 40, 28)                           # north
    dwall(0, 0, 0, 28)                             # west
    dwall(40, 0, 40, 28)                           # east
    # ---- interior: living | bed1 split, corridor, bed2/bath/kitchen
    dwall(17, 0.5, 17, 13, gaps=[(5, 8)])          # living/bed1, door 3'
    dwall(0.5, 13, 40, 13, gaps=[(2.5, 5.5), (24, 27), (33.5, 36)])
    dwall(17, 13.5, 17, 27.5, gaps=[(20, 23)])     # bed2 | bath+kitchen
    dwall(28, 13.5, 28, 27.5, gaps=[(17.5, 20)])   # bath | kitchen, door 2'6"
    # ---- door swings (leaf + arc fragments near each gap)
    swing_h(18, 0, 3.5, up=1)                      # entrance (south wall)
    swing_v(17, 5, 3, right=-1)                    # living->bed1
    swing_h(2.5, 13, 3, up=1)
    swing_h(24, 13, 3, up=1)
    swing_h(33.5, 13, 2.5, up=1)
    swing_v(28, 17.5, 2.5, right=-1)               # bath door (clear of the
                                                   # corridor swing - clusters
                                                   # must not merge)
    # ---- windows (rects embedded in the wall band)
    wrect(5, -0.05, 10, 0.55)                      # south, living
    wrect(26, -0.05, 30, 0.55)                     # south, bed1
    wrect(4, 27.45, 8, 28.05)                      # north, bed2
    wrect(31, 27.45, 35, 28.05)                    # north, kitchen
    wrect(-0.05, 6, 0.55, 10)                      # west, living tall window
    wrect(39.45, 20, 40.05, 23)                    # east, bath vent
    # ---- furniture: frame rects on the furniture-ish layers, footprint
    # sizes matched to the classifier (beds/sofa/table/chairs/cupboards +
    # sanitary + kitchen counters). Kept clear of door swings and walls.
    def frect(x0f, y0f, x1f, y1f, oc):
        page.draw_rect(fitz.Rect(*_pt(x0f, y0f), *_pt(x1f, y1f)), oc=oc)

    frect(33, 1.5, 39.5, 8.5, furn)      # bed1: double bed 6.5 x 7
    frect(31, 1.5, 32.8, 3.3, furn)      # bed1: side table
    frect(31, 6.7, 32.8, 8.5, furn)      # bed1: side table
    frect(18, 10.8, 19.5, 12.5, furn)    # bed1: side unit
    frect(1.5, 20, 7.5, 26.8, furn)      # bed2: double bed 6 x 6.8
    frect(8.2, 25.6, 10, 27.4, furn)     # bed2: side table
    frect(13.2, 14.5, 14.7, 20.5, furn)  # bed2: wardrobe 1.5 x 6
    frect(1, 3.5, 3.8, 9, furn)          # living: sofa 2.8 x 5.5
    frect(4.2, 9.7, 5.7, 11.2, furn)     # living: side table
    frect(10, 6, 13.5, 11, furn)         # living: dining table 3.5 x 5
    frect(10.3, 3.6, 12.3, 5.8, furn)    # dining chair
    frect(11.2, 11.2, 13.2, 12.9, furn)  # dining chair (1.7 -> sidetable-ish ok)
    frect(15.3, 9, 16.8, 12.3, furn)     # living: cupboard 1.5 x 3.3
    frect(18, 25, 19.5, 27.2, san)       # bath: commode
    frect(25.9, 25.6, 27.1, 27.2, san)   # bath: basin
    frect(33.5, 25.2, 39, 27.4, kit)     # kitchen: counter 2.2 x 5.5
    frect(28.8, 15, 30.8, 18, kit)       # kitchen: counter return

    # ---- columns: corners + midspans (12 in -> drives the scale)
    for xf, yf in ((0, 0), (39, 0), (0, 27), (39, 27), (16.5, 0), (16.5, 27)):
        column(xf, yf)
    return doc.tobytes()


def main():
    import pdf_vector
    import scene_to_glb
    raw = build_pdf()
    pub = os.path.join(REPO, "public")
    os.makedirs(pub, exist_ok=True)
    open(os.path.join(pub, "sample-plan.pdf"), "wb").write(raw)
    scene = pdf_vector.parse(raw, None)
    ops = scene.get("openings", [])
    doors = [o for o in ops if o["type"] == "door"]
    meta = {
        "meta": scene["meta"],
        "doors": len(doors),
        "doors_snapped": sum(1 for o in doors if o.get("snapped")),
        "windows": sum(1 for o in ops if o["type"] == "window"),
        "rooms": scene.get("rooms", []),   # walk-inside beacons
        "furniture": len(scene.get("furniture", [])),
    }
    scene_to_glb.build_glb(scene, os.path.join(pub, "sample.glb"))
    json.dump(meta, open(os.path.join(pub, "sample.meta.json"), "w"), indent=1)
    m = scene["meta"]
    print(f"sample: {m['plan_width_ft']} x {m['plan_depth_ft']} ft, "
          f"doors {meta['doors']} (snapped {meta['doors_snapped']}), "
          f"windows {meta['windows']}, scale {m['scale']['source']}")


if __name__ == "__main__":
    main()
