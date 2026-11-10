"""MEASUREMENT ONLY (layer0-wall-signature job). Reports, per sheet:

  A. every layer's count of LONG AXIS-ALIGNED segments (>=2 ft, axis-aligned
     within 0.5 pt) and how many of those carry a wall SIGNATURE — a parallel
     partner 3-18 in away overlapping >=2 ft. That is exactly the band
     `pdf_vector._paired_indices` already uses (WALL_GAP_MIN_IN/MAX_IN), reused
     here read-only rather than re-derived.
  B. how many signature-carrying lines sit on a layer the wall reader already
     admits (`pdf_vector._is_wall_layer`) vs excluded by the layer-name gate,
     and how many segments reach `struct` today (the same
     `_filter_text_layers` call `parse()` makes).
  C. for layer '0' specifically, what else lives there besides wall-signature
     lines, broken out by shape (line/rect/quad/curve) and length.

Reads pdf_vector's own pure helpers read-only. Writes nothing, changes no
parser file, no ground truth. Builds no admission change.

Run:
    DRISHTI_PLANS_DIR=/path/to/corpus python wall_layer_signature_report.py
    (falls back to ../plans, then the eval-plans folder beside the repo, if unset)
"""
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdf_vector as pv  # noqa: E402
import fitz  # noqa: E402

LONG_MIN_FT = 2.0   # a line shorter than this can never be a wall face — the
                    # same overlap floor `_geometry_wall_segs`/`wall_gap_pairs`
                    # already use, reused rather than re-derived.
AXIS_TOL_PT = 0.5   # same axis tolerance `_paired_indices` uses
_NOCAP = 10 ** 9    # mirrors pdf_vector.parse()'s own wall-layer scan (no cap)


def _is_long_axis(seg, ppf):
    x0, y0, x1, y1 = seg
    dx, dy = x1 - x0, y1 - y0
    axis = abs(dy) <= AXIS_TOL_PT or abs(dx) <= AXIS_TOL_PT
    length_ft = ((dx * dx + dy * dy) ** 0.5) / ppf
    return axis and length_ft >= LONG_MIN_FT


def _selftest():
    """One runnable check on synthetic data before trusting the real corpus."""
    ppf = 10.0  # 10 pt/ft
    segs = [
        (0, 0, 0, 32.2 * ppf),                       # long vertical (a "west wall")
        (0.94 * ppf, 0, 0.94 * ppf, 32.2 * ppf),     # partner, 0.94 ft = 11.3in away
        (5 * ppf, 5 * ppf, 5 * ppf, 5.3 * ppf),      # short vertical (furniture edge)
        (50 * ppf, 50 * ppf, 55 * ppf, 55 * ppf),    # long diagonal (not axis-aligned)
    ]
    long_axis = [i for i, s in enumerate(segs) if _is_long_axis(s, ppf)]
    assert long_axis == [0, 1], long_axis
    paired = pv._paired_indices(segs, ppf)
    assert paired == {0, 1}, paired


def _lines(drawings):
    """Every ('l') line item on the sheet as (layer_name, (x0,y0,x1,y1))."""
    out = []
    for d in drawings:
        for it in d["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                out.append((d["lname"], (a.x, a.y, b.x, b.y)))
    return out


def _layer0_other(drawings, ppf, long_entries, sig_idx):
    """For layer '0': what sits there besides wall-signature lines, by shape."""
    def bucket(n, lens):
        return {"count": n,
                "total_ft": round(sum(lens), 1),
                "median_ft": round(statistics.median(lens), 2) if lens else None,
                "max_ft": round(max(lens), 2) if lens else None}

    sig_lens, other_long_lens, short_diag_lens = [], [], []
    for i, (lname, seg) in enumerate(long_entries):
        if lname != "0":
            continue
        x0, y0, x1, y1 = seg
        length_ft = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 / ppf
        (sig_lens if i in sig_idx else other_long_lens).append(length_ft)

    rects = quads = curves = 0
    rect_sizes_ft = []
    for d in drawings:
        if d["lname"] != "0":
            continue
        for it in d["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                seg = (a.x, a.y, b.x, b.y)
                if not _is_long_axis(seg, ppf):
                    dx, dy = seg[2] - seg[0], seg[3] - seg[1]
                    short_diag_lens.append(((dx * dx + dy * dy) ** 0.5) / ppf)
            elif it[0] == "re":
                rects += 1
                r = it[1]
                rect_sizes_ft.append(round(max(r.width, r.height) / ppf, 2))
            elif it[0] == "qu":
                quads += 1
            elif it[0] == "c":
                curves += 1

    return {
        "wall_signature_lines": bucket(len(sig_lens), sig_lens),
        "other_long_axis_lines": bucket(len(other_long_lens), other_long_lens),
        "short_or_diagonal_lines": bucket(len(short_diag_lens), short_diag_lens),
        "rects": {"count": rects,
                  "median_longest_side_ft": (round(statistics.median(rect_sizes_ft), 2)
                                             if rect_sizes_ft else None)},
        "quads": quads,
        "curves": curves,
    }


def layer_report(path):
    raw = open(path, "rb").read()
    sheet = os.path.basename(path)
    try:
        scene = pv.parse(raw)
    except Exception as e:
        return {"sheet": sheet, "error": f"{type(e).__name__}: {e}"}

    ppf = scene["meta"]["scale"]["pt_per_ft"]
    page = fitz.open(stream=raw, filetype="pdf")[0]
    drawings = pv._page_drawings(page)

    # Today's admission: the exact call parse() makes for the wall reader,
    # before dedupe / implied-faces / signature-union additions.
    wall_segs, _ = pv._filter_text_layers(drawings, pv._is_wall_layer, [],
                                          maxlen=_NOCAP)

    long_entries = [(lname, seg) for lname, seg in _lines(drawings)
                    if _is_long_axis(seg, ppf)]
    sig_idx = pv._paired_indices([s for _, s in long_entries], ppf)

    by_layer = {}
    for i, (lname, _seg) in enumerate(long_entries):
        row = by_layer.setdefault(lname, {"long": 0, "signature": 0,
                                          "is_wall_layer": pv._is_wall_layer(lname)})
        row["long"] += 1
        if i in sig_idx:
            row["signature"] += 1

    total_signature = len(sig_idx)
    excluded_by_gate = sum(r["signature"] for r in by_layer.values()
                           if not r["is_wall_layer"])

    return {
        "sheet": sheet,
        "mode": scene["meta"]["source"],
        "ppf": round(ppf, 3),
        "struct_today": len(wall_segs),
        "total_long_axis": len(long_entries),
        "total_signature": total_signature,
        "excluded_by_layer_gate": excluded_by_gate,
        "by_layer": by_layer,
        "layer0_other": _layer0_other(drawings, ppf, long_entries, sig_idx),
    }


def _print_report(r):
    if "error" in r:
        print(f"\n=== {r['sheet']}: COULD NOT PARSE — {r['error']} ===")
        return
    print(f"\n=== {r['sheet']}  (route={r['mode']}, ppf={r['ppf']}) ===")
    print(f"struct today (reaches the wall reader): {r['struct_today']} segments")
    print(f"long axis-aligned segments on the sheet: {r['total_long_axis']}")
    print(f"of those, carry the wall signature (3-18in parallel partner, "
          f">=2ft overlap): {r['total_signature']}")
    print(f"signature-carrying but excluded by the layer-name gate: "
          f"{r['excluded_by_layer_gate']}")
    print(f"{'layer':<20}{'long':>6}{'signature':>11}{'admitted?':>11}")
    for lname, row in sorted(r["by_layer"].items(),
                             key=lambda kv: -kv[1]["signature"]):
        print(f"{lname or '(none)':<20}{row['long']:>6}{row['signature']:>11}"
              f"{'yes' if row['is_wall_layer'] else 'no':>11}")
    lo = r["layer0_other"]
    if lo["wall_signature_lines"]["count"] or lo["other_long_axis_lines"]["count"] \
            or lo["short_or_diagonal_lines"]["count"] or lo["rects"]["count"]:
        print("layer '0' breakdown:")
        print(f"  wall-signature lines      : {lo['wall_signature_lines']}")
        print(f"  other long axis-aligned   : {lo['other_long_axis_lines']}")
        print(f"  short/diagonal lines      : {lo['short_or_diagonal_lines']}")
        print(f"  rects                     : {lo['rects']}")
        print(f"  quads                     : {lo['quads']}")
        print(f"  curves                    : {lo['curves']}")


def main():
    _selftest()
    dirs = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not dirs:
        env_dir = os.getenv("DRISHTI_PLANS_DIR")
        dirs = [env_dir] if env_dir else [
            os.path.join(os.path.dirname(__file__), "..", "plans")]
    results = []
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, "*.pdf"))):
            r = layer_report(path)
            results.append(r)
            _print_report(r)
    if "--save" in sys.argv:
        out = os.path.join(os.path.dirname(__file__), "wall_layer_signature_report.json")
        json.dump(results, open(out, "w"), indent=1)
        print(f"\nsaved -> {out}")
    return results


if __name__ == "__main__":
    main()
