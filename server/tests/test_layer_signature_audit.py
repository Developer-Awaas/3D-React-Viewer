"""Measurement-only tool (layer0-wall-signature job, 9 Nov 2026). Confirms
the audit reports what pdf_vector's own pairing/struct functions actually
do — it changes nothing in pdf_vector itself."""
import layer_signature_audit as lsa


class P:
    """Stand-in for fitz.Point: layer_items only reads .x / .y."""
    def __init__(self, x, y):
        self.x, self.y = x, y


def _line(layer, x0, y0, x1, y1):
    return {"lname": layer, "items": [("l", P(x0, y0), P(x1, y1))]}


def test_layer_items_splits_axis_and_diagonal():
    drawings = [
        _line("0", 0, 0, 20, 0),      # long H
        _line("0", 5, 5, 5, 6),       # short V (1 ft)
        _line("0", 0, 0, 3, 3),       # diagonal
    ]
    rows = lsa.layer_items(drawings)
    axes = sorted(r["axis"] for r in rows)
    assert axes == ["H", "V", "diag"]


def test_wall_signature_pairs_across_layers():
    # ppf = 10 pt/ft. Two 20 ft H lines, 10 in (8.33 pt) apart, fully
    # overlapping -> a W-3 wall pair, one line on '0', one on 'ar wall'.
    ppf = 10.0
    gap = (10.0 / 12.0) * ppf
    drawings = [
        _line("0", 0, 0, 200, 0),
        _line("ar wall", 0, gap, 200, gap),
    ]
    report = lsa.audit(drawings, ppf)
    assert report["by_layer"]["0"]["paired_segs"] == 1
    assert report["by_layer"]["0"]["long_segs"] == 1
    # the unpaired layer name gate verdicts
    assert report["by_layer"]["0"]["layer_gate"] == "excluded: not a wall/window layer NAME"
    assert report["by_layer"]["ar wall"]["layer_gate"] == "reaches struct"
    # struct is built from the named wall layer only, regardless of pairing
    assert report["struct_segs_today"] == 1


def test_unpaired_short_line_never_counts_as_long():
    ppf = 10.0
    drawings = [_line("0", 0, 0, 1.0 * ppf, 0)]   # 1 ft, below the 2 ft floor
    report = lsa.audit(drawings, ppf)
    assert "0" not in report["by_layer"]


def test_layer_composition_buckets_by_length_and_shape():
    ppf = 10.0
    drawings = [
        _line("0", 0, 0, 20 * ppf, 0),     # long axis (20 ft)
        _line("0", 0, 0, 0.5 * ppf, 0),    # short axis (0.5 ft)
        _line("0", 0, 0, 3 * ppf, 3 * ppf),  # diagonal, length 3*sqrt(2) ft
    ]
    comp = lsa.layer_composition(drawings, ppf, "0")
    assert comp["items"] == 3
    assert comp["axis_long_ft"] == 20.0
    assert comp["axis_short_ft"] == 0.5
    assert comp["diag_ft"] > 0
