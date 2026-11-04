"""TG-5 — the sheet's own opening schedule overrides our defaults.

Pure: the table is rebuilt as synthetic tokens (positions taken from the real
OCR of BRICK WORK LAYOUT.pdf, OCR quirks included), so no tesseract is needed.
"""
import pytest

import opening_schedule as S
from conftest import require_corpus_file

# "SCHEDULE OF DOOR & WINDOW" as OCR actually reads it: every ft-in value is
# exact, but two single-letter names come back doubled ('V'->'Vv', 'W'->'WwW').
ROWS = [
    ("D", "3'9\"", "7'0\"", "0'0\"", "7'0\""),
    ("D1", "3'3\"", "7'0\"", "0'0\"", "7'0\""),
    ("D2", "3'0\"", "7'0\"", "0'0\"", "7'0\""),
    ("D3", "2'6\"", "7'0\"", "0'0\"", "7'0\""),
    ("SD", "7'0\"", "7'0\"", "0'0\"", "7'0\""),
    ("Vv", "2'0\"", "2'0\"", "5'0\"", "7'0\""),
    ("WwW", "6'0\"", "4'6\"", "2'6\"", "7'0\""),
    ("W1", "5'0\"", "4'6\"", "2'6\"", "7'0\""),
]


def _tok(text, x, y, w=40.0, h=16.0):
    return {"text": text, "x0": x, "y0": y, "x1": x + w, "y1": y + h}


def _sheet_tokens():
    toks = [_tok("SCHEDULE", 179, 2730), _tok("OF", 326, 2730),
            _tok("DOOR", 370, 2730), _tok("WINDOW", 477, 2730),
            _tok("SL", 135, 2791), _tok("NAME", 200, 2791),
            _tok("DIMENSION", 312, 2782, w=90), _tok("SILL", 485, 2782),
            _tok("LINTEL", 582, 2782)]
    y = 2838
    for i, (name, w, h, sill, lintel) in enumerate(ROWS, start=1):
        toks += [_tok(str(i), 135, y), _tok(name, 216, y),
                 _tok(w, 314, y), _tok("X", 353, y), _tok(h, 373, y),
                 _tok(sill, 493, y), _tok(lintel, 587, y)]
        y += 34
    return toks


class TestParse:
    def test_reads_all_eight_rows(self):
        got = S.parse_opening_schedule(_sheet_tokens())
        assert sorted(got) == ["D", "D1", "D2", "D3", "SD", "V", "W", "W1"]

    def test_window_row_beats_our_default(self):
        """The whole point: our LEGEND said W = 4'0" wide, sill 3'0". The
        sheet says 6'0" x 4'6", sill 2'6"."""
        w = S.parse_opening_schedule(_sheet_tokens())["W"]
        assert w == {"w_ft": 6.0, "h_ft": 4.5, "sill_ft": 2.5, "head_ft": 7.0}

    def test_doubled_ocr_names_are_normalised(self):
        got = S.parse_opening_schedule(_sheet_tokens())
        assert got["V"]["w_ft"] == 2.0 and got["V"]["sill_ft"] == 5.0
        assert "VV" not in got and "WWW" not in got

    def test_door_rows(self):
        got = S.parse_opening_schedule(_sheet_tokens())
        assert [got[k]["w_ft"] for k in ("D", "D1", "D2", "D3", "SD")] == \
               [3.75, 3.25, 3.0, 2.5, 7.0]

    def test_no_schedule_returns_none(self):
        assert S.parse_opening_schedule([]) is None
        assert S.parse_opening_schedule(
            [_tok("BEDROOM", 700, 973), _tok("KITCHEN", 992, 1072)]) is None

    def test_row_without_a_width_is_dropped_not_guessed(self):
        toks = [t for t in _sheet_tokens() if t["text"] != "6'0\""]
        assert "W" not in (S.parse_opening_schedule(toks) or {})

    def test_head_derived_from_sill_plus_height_when_no_lintel_column(self):
        toks = [t for t in _sheet_tokens()
                if t["text"] != "LINTEL" and not (t["x0"] == 587)]
        assert S.parse_opening_schedule(toks)["W"]["head_ft"] == 7.0   # 2.5+4.5


class TestHelpers:
    def test_ft_in(self):
        assert S.ft_in("3'9\"") == 3.75
        assert S.ft_in("0'0\"") == 0.0
        assert S.ft_in("X") is None and S.ft_in("") is None

    def test_normalize_tag(self):
        assert S.normalize_tag("WwW") == "W"
        assert S.normalize_tag("Vv") == "V"
        assert S.normalize_tag("W1") == "W1"      # digit survives
        assert S.normalize_tag("BEDROOM") is None

    def test_overrides_fall_back_to_defaults(self):
        sched = S.parse_opening_schedule(_sheet_tokens())
        assert S.window_size(sched, "W", (4.0, 3.0, 7.0)) == (6.0, 2.5, 7.0)
        assert S.window_size(None, "W", (4.0, 3.0, 7.0)) == (4.0, 3.0, 7.0)
        assert S.window_size(sched, "W9", (4.0, 3.0, 7.0)) == (4.0, 3.0, 7.0)
        assert S.door_width(sched, "D1", 3.25) == 3.25
        assert S.door_width(None, "D1", 9.9) == 9.9

    def test_tag_openings_uses_the_schedule(self):
        import tag_openings
        walls = [(0.0, 0.0, 20.0, 0.0)]
        sched = S.parse_opening_schedule(_sheet_tokens())
        (op,) = tag_openings.detect_tag_openings(
            [(10.0, 1.0, "W")], walls, [], schedule=sched)
        x0, _y0, x1, _y1 = op["footprint"]
        assert round(x1 - x0, 2) == 6.0            # sheet's 6'0", not our 4'0"
        assert op["z"] == [2.5, 7.0]               # sheet's sill, not our 3'0"


def test_brick_work_pdf_end_to_end():
    """The real sheet: 0 live words, so this only passes via OCR. Skipped when
    tesseract is not installed (optional dependency) - a different gate from
    the corpus, which must FAIL loudly, not skip, if missing."""
    path = require_corpus_file("BRICK WORK LAYOUT.pdf")
    pytest.importorskip("pytesseract")
    import pytesseract
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        pytest.skip("tesseract binary not installed")
    import pdf_vector
    with open(path, "rb") as f:
        scene = pdf_vector.parse(f.read())
    ws = [o for o in scene["openings"] if o.get("tag") == "W"]
    assert ws, "the sheet tags a W window; it must be placed"
    fp = ws[0]["footprint"]
    assert round(max(fp[2] - fp[0], fp[3] - fp[1]), 2) == 6.0   # not 4.0
    assert ws[0]["z"] == [2.5, 7.0]                             # not [3.0, 7.0]
