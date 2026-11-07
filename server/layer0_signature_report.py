"""MEASUREMENT ONLY — how much wall-signature linework sits on a layer the
wall reader never looks at (the layer-name gate), per sheet.

Precedent (PLAN-READING-RULES.md, 3 Sep 2026): "counting lines with a
parallel partner 3-18 in away overlapping >= 2 ft" found layer `0` carrying
MORE paired wall-signature lines than the sheet's own named `wall` layer. This
script reproduces that measurement, generalised to every layer on every sheet,
and reports what else (besides wall signature) each layer actually holds.

Calls pdf_vector's own pure helpers (`_page_drawings`, `_segs`,
`_paired_indices`, `_is_wall_layer`, `_is_window_layer`,
`_filter_text_layers`) read-only. NOTHING in pdf_vector.py is changed, and
nothing here feeds back into the parser.

Run:  python layer0_signature_report.py [plans_dir]
"""
import glob
import os
import statistics
import sys

import pdf_vector as pv

LONG_FT = 2.0        # "long" = the W-3 overlap floor already used for pairing
                      # everywhere else in pdf_vector.py (min_ovl_ft default)
_NOCAP = 10 ** 9      # no page-unit length cap — that is the point of this job


def _canon(seg):
    return tuple(round(v, 2) for v in seg)


def _length_pt(seg):
    x0, y0, x1, y1 = seg
    return ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5


def axis_aligned_long(segs, ppf, min_ft=LONG_FT):
    """Horizontal or vertical (0.5 pt tolerance — the same split every H/V
    function in pdf_vector.py uses) segments at least `min_ft` long."""
    out = []
    for s in segs:
        x0, y0, x1, y1 = s
        if _length_pt(s) < min_ft * ppf:
            continue
        if abs(y1 - y0) < 0.5 or abs(x1 - x0) < 0.5:
            out.append(s)
    return out


def measure_sheet(raw):
    """One sheet's bytes -> {ppf, route, rows:[{layer, ...}]}. Pure (no I/O
    besides the PDF bytes already in memory)."""
    import fitz
    page = fitz.open(stream=raw, filetype="pdf")[0]
    drawings = pv._page_drawings(page)

    # The EXACT admission pdf_vector.parse() runs (lines ~3326-3331) — called,
    # not re-implemented, so "reaches struct" means what the parser means.
    warnings = []
    wall_segs, _ = pv._filter_text_layers(drawings, pv._is_wall_layer, warnings,
                                          maxlen=_NOCAP)
    win_segs, _ = pv._filter_text_layers(drawings, pv._is_window_layer,
                                         warnings, maxlen=_NOCAP)
    struct_layers_gate = {_canon(s) for s in wall_segs + win_segs}
    layers_route = len(wall_segs) + len(win_segs) >= 30

    scene = pv.parse(raw)
    ppf = scene["meta"]["scale"]["pt_per_ft"]
    route = scene["meta"]["source"]      # "vector_pdf_layers" | "vector_pdf_geometry"

    # On a GEOMETRY-route sheet (named wall layers too thin to trust), struct
    # comes from `_geometry_wall_segs` instead — a DIFFERENT admission (its
    # own 3-11.04 in band + GEOM_SKIP keywords), not the layer-name gate this
    # job measures. Computed too, so "reaches struct TODAY" is never blank
    # for a sheet this job's gate never touches.
    struct_today = struct_layers_gate
    if route == "vector_pdf_geometry":
        _, _, dim_keys = pv._text_scale(page, drawings, [])
        gsegs = pv._geometry_wall_segs(drawings, ppf, [], dim_keys)
        struct_today = {_canon(s) for s in gsegs}

    by_layer = {}
    for d in drawings:
        by_layer.setdefault(d["lname"] or "(blank)", []).append(d)

    rows = []
    for lname, ds in sorted(by_layer.items()):
        all_segs = pv._segs(ds, lambda n: True, maxlen=_NOCAP)
        long_av = axis_aligned_long(all_segs, ppf)
        paired_idx = pv._paired_indices(long_av, ppf) if long_av else set()
        in_struct_gate = sum(1 for s in long_av if _canon(s) in struct_layers_gate)
        in_struct_today = sum(1 for s in long_av if _canon(s) in struct_today)
        item_types = {}
        for d in ds:
            for it in d["items"]:
                item_types[it[0]] = item_types.get(it[0], 0) + 1
        paired_ft = sum(_length_pt(long_av[k]) for k in paired_idx) / ppf
        long_ft = sum(_length_pt(s) for s in long_av) / ppf
        lens_ft = sorted(_length_pt(s) / ppf for s in all_segs)
        rows.append({
            "layer": lname,
            "admitted_by_name": bool(pv._is_wall_layer(lname) or pv._is_window_layer(lname)),
            "n_items": sum(len(d["items"]) for d in ds),
            "item_types": item_types,
            "n_segs": len(all_segs),
            "median_seg_ft": round(statistics.median(lens_ft), 3) if lens_ft else 0.0,
            "n_long_axis": len(long_av),
            "long_axis_ft": round(long_ft, 1),
            "n_paired": len(paired_idx),
            "paired_ft": round(paired_ft, 1),
            "n_in_struct_layers_gate": in_struct_gate,
            "n_in_struct_today": in_struct_today,
        })
    return {"ppf": ppf, "route": route, "layers_route_eligible": layers_route,
            "rows": rows}


def _fmt_types(d):
    return ",".join(f"{k}={v}" for k, v in sorted(d.items())) or "-"


def print_report(plans_dir):
    paths = sorted(glob.glob(os.path.join(plans_dir, "*.pdf")))
    if not paths:
        print(f"no *.pdf files in {plans_dir!r}")
        return
    for path in paths:
        name = os.path.basename(path)
        with open(path, "rb") as f:
            raw = f.read()
        try:
            m = measure_sheet(raw)
        except Exception as e:
            print(f"\n=== {name}: SKIPPED ({type(e).__name__}: {e}) ===")
            continue
        print(f"\n=== {name}  (ppf={m['ppf']:.2f} pt/ft, route={m['route']}) ===")
        print(f"{'layer':<22} {'gate':<4} {'items':>6} {'types':<18} "
              f"{'long>=2ft':>9} {'paired':>7} {'paired_ft':>9} "
              f"{'in_struct(gate)':>16} {'in_struct(today)':>16}")
        for r in m["rows"]:
            if r["n_items"] == 0:
                continue
            print(f"{r['layer']:<22} {'YES' if r['admitted_by_name'] else 'no':<4} "
                  f"{r['n_items']:>6} {_fmt_types(r['item_types']):<18} "
                  f"{r['n_long_axis']:>9} {r['n_paired']:>7} {r['paired_ft']:>9} "
                  f"{r['n_in_struct_layers_gate']:>16} {r['n_in_struct_today']:>16}")
        total_paired = sum(r["n_paired"] for r in m["rows"])
        total_paired_gated_out = sum(r["n_paired"] for r in m["rows"]
                                     if not r["admitted_by_name"])
        print(f"  total paired (wall-signature) lines: {total_paired}  "
              f"-- excluded by the layer-name gate: {total_paired_gated_out}")


if __name__ == "__main__":
    print_report(sys.argv[1] if len(sys.argv) > 1
                 else os.getenv("DRISHTI_PLANS_DIR", "plans"))
