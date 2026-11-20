"""layer0-wall-signature MEASUREMENT (20 Nov 2026) - read-only instrument.

Measures, per sheet, how much wall-signature linework sits on layer 0 (or any
non-wall-named layer) and never reaches the wall reader. Builds NOTHING: it
only calls existing pdf_vector helpers (_page_drawings, _segs,
_filter_text_layers, _is_wall_layer, _is_window_layer, _paired_indices) and
reports what they already compute. No parser file is touched or imported
differently than main.py already does.

A "long axis-aligned segment" = a line/rect-edge/quad-edge whose run is
within 0.5pt of pure horizontal or vertical (pdf_vector's own tolerance,
see _paired_indices) and at least 2.0 ft long (implied_partners' own
min_len default). "Carries the wall signature" = has a parallel partner
3-18in away (W-3, WALL_GAP_MIN_IN/MAX_IN) overlapping it by >=2ft along the
run - exactly pdf_vector._paired_indices, run sheet-wide across ALL layers
(a wall's partner can sit on a different layer than the wall itself).

Usage: python layer_signature_report.py [PLANS_DIR] [--json out.json]
"""
import glob
import json
import os
import sys

import pdf_vector as pv

LONG_FT = 2.0        # implied_partners' own min_len default
AXIS_TOL_PT = 0.5    # pdf_vector._paired_indices' own axis-alignment tolerance


def _layer_segments(drawings, lname):
    """All line/rect/quad edges on one layer, in pt, via pdf_vector._segs -
    the exact decomposition _filter_text_layers feeds into `struct`."""
    ds = [d for d in drawings if d["lname"] == lname]
    return pv._segs(ds, lambda n: True, maxlen=10 ** 9)


def _is_long_axis(seg, ppf):
    x0, y0, x1, y1 = seg
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    if dy <= AXIS_TOL_PT and dx >= LONG_FT * ppf:
        return True
    if dx <= AXIS_TOL_PT and dy >= LONG_FT * ppf:
        return True
    return False


def _shape_bucket(seg, ppf):
    x0, y0, x1, y1 = seg
    length_ft = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 / ppf
    if _is_long_axis(seg, ppf):
        return "long_axis", length_ft
    if length_ft < 1.0:
        return "short_stroke", length_ft   # hatch / outlined text / fixtures
    return "diagonal_or_curved", length_ft  # furniture symbols, door swings, dim ticks


def measure_sheet(path):
    raw = open(path, "rb").read()
    import fitz
    page = fitz.open(stream=raw, filetype="pdf")[0]
    drawings = pv._page_drawings(page)

    try:
        scene = pv.parse(raw)
        ppf = float(scene["meta"]["scale"]["pt_per_ft"])
        route = scene.get("meta", {}).get("route")
        parse_err = None
    except Exception as e:
        ppf, route, parse_err = None, None, f"{type(e).__name__}: {e}"

    layers = sorted({d["lname"] for d in drawings})
    result = {"sheet": os.path.basename(path), "ppf": ppf, "route": route,
              "parse_error": parse_err, "layers": {}}
    if ppf is None:
        return result   # can't size anything in feet without a scale

    # struct as the pipeline builds it today (parse()'s own two calls)
    warnings = []
    wall_segs, _ = pv._filter_text_layers(drawings, pv._is_wall_layer, warnings,
                                          maxlen=10 ** 9)
    win_segs, _ = pv._filter_text_layers(drawings, pv._is_window_layer, warnings,
                                         maxlen=10 ** 9)
    struct_today = len(wall_segs) + len(win_segs)

    # parse()'s OWN route decision: named-layer struct < 30 -> geometry
    # fallback, which scans ALL layers (except GEOM_SKIP keywords - "0" is
    # not one of them) regardless of layer name. On that route the
    # layer-NAME gate below does not actually apply to the sheet's real
    # build, so the per-layer "excluded" counts are what the layers-route
    # WOULD exclude, not what this sheet's own parse actually drops.
    if struct_today < 30:
        route_mode = "geometry (named-layer struct < 30 -> ALL layers scanned, gate bypassed)"
        gsegs = pv._geometry_wall_segs(drawings, ppf, [])
        struct_actual = len(gsegs) if len(gsegs) >= 8 else struct_today
    else:
        route_mode = "layers (named wall/window layers only -> gate applies)"
        struct_actual = struct_today

    # every long axis-aligned segment on the sheet, tagged with its layer,
    # so the wall-signature test below runs ACROSS layers (a wall's partner
    # may be drawn on a different layer than the wall itself)
    all_long, owner = [], []
    other_by_layer = {}
    for lname in layers:
        segs = _layer_segments(drawings, lname)
        buckets = {"long_axis": 0, "short_stroke": 0, "diagonal_or_curved": 0}
        lengths = {"long_axis": [], "short_stroke": [], "diagonal_or_curved": []}
        for s in segs:
            kind, length_ft = _shape_bucket(s, ppf)
            buckets[kind] += 1
            lengths[kind].append(length_ft)
            if kind == "long_axis":
                all_long.append(s)
                owner.append(lname)
        other_by_layer[lname] = {
            "total_segments": len(segs),
            "long_axis_aligned": buckets["long_axis"],
            "short_strokes_under_1ft": buckets["short_stroke"],
            "diagonal_or_curved": buckets["diagonal_or_curved"],
            "diagonal_or_curved_total_ft": round(sum(lengths["diagonal_or_curved"]), 1),
            "short_stroke_total_ft": round(sum(lengths["short_stroke"]), 1),
            "is_wall_layer": pv._is_wall_layer(lname),
            "is_window_layer": pv._is_window_layer(lname),
        }

    signature = pv._paired_indices(all_long, ppf)  # W-3 band, sheet-wide

    for lname in layers:
        n_long = sum(1 for o in owner if o == lname)
        n_sig = sum(1 for i, o in enumerate(owner) if o == lname and i in signature)
        reaches_struct = other_by_layer[lname]["is_wall_layer"] or \
            other_by_layer[lname]["is_window_layer"]
        other_by_layer[lname].update({
            "long_axis_with_wall_signature": n_sig,
            "long_axis_without_signature": n_long - n_sig,
            "reaches_struct_today": reaches_struct,
            "excluded_by_layer_gate": n_sig if not reaches_struct else 0,
        })

    result["layers"] = other_by_layer
    result["struct_segments_today"] = struct_today
    result["route_mode"] = route_mode
    result["struct_actual_this_sheet"] = struct_actual
    total_sig = sum(1 for i in signature)
    result["total_long_axis_segments"] = len(all_long)
    result["total_wall_signature_segments"] = total_sig
    result["total_excluded_by_layer_gate"] = sum(
        v["excluded_by_layer_gate"] for v in other_by_layer.values())
    return result


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    plans_dir = args[0] if args else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "plans")
    out = []
    for path in sorted(glob.glob(os.path.join(plans_dir, "*.pdf"))):
        out.append(measure_sheet(path))

    for r in out:
        print(f"\n=== {r['sheet']} === ppf={r['ppf']} route={r['route']} "
              f"error={r['parse_error']}")
        if r["ppf"] is None:
            continue
        print(f"  named-layer struct: {r['struct_segments_today']} | route: "
              f"{r['route_mode']} | actual struct this sheet: "
              f"{r['struct_actual_this_sheet']}")
        print(f"  long axis-aligned on sheet: {r['total_long_axis_segments']} | "
              f"carry wall signature: {r['total_wall_signature_segments']} | "
              f"signature lines NAME-gate would exclude: "
              f"{r['total_excluded_by_layer_gate']}")
        for lname, v in sorted(r["layers"].items(),
                               key=lambda kv: -kv[1]["long_axis_with_wall_signature"]):
            if v["total_segments"] == 0:
                continue
            print(f"  layer {lname!r:22s} segs={v['total_segments']:5d} "
                  f"long_axis={v['long_axis_aligned']:4d} "
                  f"w/signature={v['long_axis_with_wall_signature']:4d} "
                  f"gate={'WALL' if v['is_wall_layer'] else ('WIN' if v['is_window_layer'] else 'excluded')} "
                  f"short<1ft={v['short_strokes_under_1ft']:4d} "
                  f"diag/curve={v['diagonal_or_curved']:4d} "
                  f"({v['diagonal_or_curved_total_ft']} ft)")

    json_path = None
    for i, a in enumerate(sys.argv):
        if a == "--json" and i + 1 < len(sys.argv):
            json_path = sys.argv[i + 1]
    if json_path:
        with open(json_path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\nwrote {json_path}")
    return out


if __name__ == "__main__":
    main()
