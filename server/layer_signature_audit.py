"""MEASUREMENT ONLY — layer0-wall-signature job (9 Nov 2026).

How much wall-signature linework sits on layer `0` (or any other layer the
named-wall/window gate never looks at) and never reaches `struct`, per sheet.

Builds nothing and changes nothing: every test below calls pdf_vector's own
PURE functions as-is — `_page_drawings`, `_is_wall_layer`, `_is_window_layer`,
`_filter_text_layers`, `_paired_indices` — the same functions `struct`,
`paired_extent` and `keep_structural_lines` already use to decide what is a
wall. Nothing here is a re-implementation of that logic; it is a report on
what it already does. See CLAUDE.md §12, "layer names lie" thread.

    python server/layer_signature_audit.py [plans_dir ...]
"""
import glob
import math
import os
import sys

import pdf_vector as pv

# The W-3 pairing test (`_paired_indices`) requires >=2 ft of overlap to call
# two lines a wall pair at all (`min_ovl_ft=2.0`), so a segment shorter than
# that can never carry the wall signature regardless of what it is paired
# with. "Long axis-aligned" here is that floor, not a new number.
LONG_FT = 2.0


def _axis(x0, y0, x1, y1):
    if abs(y1 - y0) < 0.5:
        return "H"
    if abs(x1 - x0) < 0.5:
        return "V"
    return "diag"


def layer_items(drawings):
    """Every drawn item, tagged with its layer / kind / axis / length (pt).
    Lines, rect edges and quad edges get a straight length; curves do not.
    Pure."""
    rows = []
    for d in drawings:
        name = d["lname"]
        for it in d["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                seg = (a.x, a.y, b.x, b.y)
                rows.append({"layer": name, "kind": "line",
                             "axis": _axis(*seg), "len_pt": math.hypot(b.x - a.x, b.y - a.y),
                             "seg": seg})
            elif it[0] == "re":
                r = it[1]
                for seg in ((r.x0, r.y0, r.x1, r.y0), (r.x1, r.y0, r.x1, r.y1),
                            (r.x1, r.y1, r.x0, r.y1), (r.x0, r.y1, r.x0, r.y0)):
                    L = math.hypot(seg[2] - seg[0], seg[3] - seg[1])
                    rows.append({"layer": name, "kind": "rect_edge",
                                 "axis": _axis(*seg), "len_pt": L, "seg": seg})
            elif it[0] == "qu":
                pts = it[1]
                for i in range(4):
                    a, b = pts[i], pts[(i + 1) % 4]
                    seg = (a.x, a.y, b.x, b.y)
                    L = math.hypot(b.x - a.x, b.y - a.y)
                    rows.append({"layer": name, "kind": "quad_edge",
                                 "axis": _axis(*seg), "len_pt": L, "seg": seg})
            elif it[0] == "c":
                rows.append({"layer": name, "kind": "curve", "axis": "curve",
                             "len_pt": None, "seg": None})
    return rows


def audit(drawings, ppf):
    """Per-layer wall-signature report at this sheet's own scale. Pure.

    'wall signature' = has a parallel partner 3-18 in away (W-3), tested
    across ALL layers at once with the parser's own `_paired_indices` — a
    layer-`0` line can pair with a named wall-layer line or with another
    layer-`0` line, exactly as the real pairing functions allow.

    'reaches struct today' is read off `_filter_text_layers` run with
    `_is_wall_layer` / `_is_window_layer` — the actual predicate `struct` is
    built from in `pdf_vector.parse` — never re-derived.
    """
    rows = layer_items(drawings)
    long_axis = [r for r in rows if r["axis"] in ("H", "V")
                 and r["len_pt"] >= LONG_FT * ppf]
    segs = [r["seg"] for r in long_axis]
    paired_idx = pv._paired_indices(segs, ppf, pv.WALL_GAP_MIN_IN, pv.WALL_GAP_MAX_IN, LONG_FT)

    by_layer = {}
    for i, r in enumerate(long_axis):
        e = by_layer.setdefault(r["layer"], {"long_segs": 0, "long_ft": 0.0,
                                              "paired_segs": 0, "paired_ft": 0.0})
        e["long_segs"] += 1
        e["long_ft"] += r["len_pt"] / ppf
        if i in paired_idx:
            e["paired_segs"] += 1
            e["paired_ft"] += r["len_pt"] / ppf

    wall_segs, wall_dropped = pv._filter_text_layers(drawings, pv._is_wall_layer, [], maxlen=10 ** 9)
    win_segs, win_dropped = pv._filter_text_layers(drawings, pv._is_window_layer, [], maxlen=10 ** 9)

    for name, e in by_layer.items():
        is_candidate = pv._is_wall_layer(name) or pv._is_window_layer(name)
        if not is_candidate:
            e["layer_gate"] = "excluded: not a wall/window layer NAME"
        elif name in wall_dropped or name in win_dropped:
            e["layer_gate"] = "excluded: text-like (median-length test dropped it)"
        else:
            e["layer_gate"] = "reaches struct"
        e["long_ft"] = round(e["long_ft"], 1)
        e["paired_ft"] = round(e["paired_ft"], 1)

    return {"ppf": round(ppf, 3), "by_layer": by_layer,
            "struct_segs_today": len(wall_segs) + len(win_segs),
            "total_items": len(rows)}


def layer_composition(drawings, ppf, layer_name="0"):
    """What else sits on `layer_name` besides wall-signature lines, by
    length and shape. Measurement only, pure."""
    rows = [r for r in layer_items(drawings) if r["layer"] == layer_name]
    out = {"items": len(rows), "by_kind": {}, "axis_long_ft": 0.0,
           "axis_short_ft": 0.0, "diag_ft": 0.0, "curves": 0}
    for r in rows:
        out["by_kind"][r["kind"]] = out["by_kind"].get(r["kind"], 0) + 1
        if r["kind"] == "curve":
            out["curves"] += 1
            continue
        ft = r["len_pt"] / ppf
        if r["axis"] == "diag":
            out["diag_ft"] += ft
        elif ft >= LONG_FT:
            out["axis_long_ft"] += ft
        else:
            out["axis_short_ft"] += ft
    out["axis_long_ft"] = round(out["axis_long_ft"], 1)
    out["axis_short_ft"] = round(out["axis_short_ft"], 1)
    out["diag_ft"] = round(out["diag_ft"], 1)
    return out


def audit_pdf_bytes(raw, layer_name="0"):
    """Convenience: open the PDF, run `parse()` once for scale/route/
    footprint, and report. `parse()` is called for READING ONLY — nothing
    about it is changed, and the footprint it returns is the proof the
    golden sheets did not move."""
    import fitz
    page = fitz.open(stream=raw, filetype="pdf")[0]
    drawings = pv._page_drawings(page)
    scene = pv.parse(raw)
    ppf = scene["meta"]["scale"]["pt_per_ft"]
    report = audit(drawings, ppf)
    report["footprint_sqft"] = scene["meta"]["footprint_sqft"]
    report["route"] = scene["meta"].get("route")
    report["scale_source"] = scene["meta"]["scale"]["source"]
    report["layer0"] = layer_composition(drawings, ppf, layer_name)
    return report


def run(paths):
    for p in paths:
        name = os.path.basename(p)
        try:
            with open(p, "rb") as f:
                report = audit_pdf_bytes(f.read())
        except Exception as e:
            print(f"\n=== {name} === RAISES: {e}")
            continue
        print(f"\n=== {name} === ppf {report['ppf']} route={report['route']} "
              f"scale={report['scale_source']} footprint_sqft={report['footprint_sqft']}")
        print(f"{'layer':<20}{'long segs':>10}{'long ft':>10}"
              f"{'paired':>8}{'paired ft':>10}  struct?")
        for lname, e in sorted(report["by_layer"].items(),
                                key=lambda kv: -kv[1]["long_ft"]):
            print(f"{lname:<20}{e['long_segs']:>10}{e['long_ft']:>10.1f}"
                  f"{e['paired_segs']:>8}{e['paired_ft']:>10.1f}  {e['layer_gate']}")
        print(f"struct segments today (named wall/window layers): "
              f"{report['struct_segs_today']}")
        c = report["layer0"]
        print(f"layer '0' composition: {c['items']} items {c['by_kind']} — "
              f"long-axis {c['axis_long_ft']} ft, short-axis {c['axis_short_ft']} ft, "
              f"diagonal {c['diag_ft']} ft, curves {c['curves']}")


if __name__ == "__main__":
    dirs = sys.argv[1:] or [os.path.join(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))), "plans")]
    files = [f for d in dirs for f in sorted(glob.glob(os.path.join(d, "*.pdf")))]
    run(files)
