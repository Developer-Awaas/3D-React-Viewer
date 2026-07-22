"""Unit tests for reading brick-HATCHED walls (the case where a wall layer is
thousands of tiny hatch strokes + a few long real wall lines). Synthetic input
so no confidential plan is needed. Pins the two rules:
  1. no proper wall layer -> recover the long lines from the hatch layer;
  2. a proper wall layer present -> use it, ignore the hatch layer.
"""
import fitz

from pdf_vector import _filter_text_layers, _is_wall_layer


def _line(x0, y0, x1, y1):
    return ("l", fitz.Point(x0, y0), fitz.Point(x1, y1))


def _layer(name, items):
    return {"lname": name, "items": items}


def _hatch_wall_layer(name="wall", n_hatch=400, n_long=30):
    items = []
    for i in range(n_hatch):                      # tiny diagonal brick-hatch strokes
        items.append(_line(i, i, i + 0.3, i + 0.3))
    for k in range(n_long):                        # real long wall lines
        items.append(_line(0, k * 5, 300, k * 5))
    return _layer(name, items)


def test_recovers_walls_from_hatch_when_no_proper_layer():
    warns = []
    segs, dropped = _filter_text_layers([_hatch_wall_layer()], _is_wall_layer, warns)
    assert len(segs) >= 30                          # the long wall lines survive
    assert "wall" not in dropped
    assert any("brick-hatch" in w for w in warns)


def test_proper_wall_layer_suppresses_hatch_recovery():
    # a real 'ar wall' (long median) + a hatch 'wall' -> use ar wall, drop hatch
    proper = _layer("ar wall", [_line(0, i * 4, 400, i * 4) for i in range(40)])
    warns = []
    segs, dropped = _filter_text_layers([proper, _hatch_wall_layer()],
                                        _is_wall_layer, warns)
    assert "wall" in dropped                         # hatch layer ignored
    assert len(segs) == 40                           # only the proper walls


def test_pure_text_layer_is_dropped():
    # tiny strokes only, too few long lines -> genuinely text, dropped
    text = _layer("wall", [_line(i, i, i + 0.2, i + 0.2) for i in range(200)])
    warns = []
    segs, dropped = _filter_text_layers([text], _is_wall_layer, warns)
    assert segs == [] and "wall" in dropped
