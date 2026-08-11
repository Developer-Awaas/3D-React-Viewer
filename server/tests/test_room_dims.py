"""R-2 — printed room dimensions check the measured rooms.

Pure: synthetic tokens reproduce how OCR actually splits a label on
FLOOR PLAN.pdf (`BEDROOM` / `13'6"` / `X` / `10'3"`), including the misreads
that must NOT be repaired by guesswork.
"""
import room_dims as R


def _tok(text, x, y, w=None, h=16.0):
    w = len(text) * 8.0 if w is None else w
    return {"text": text, "x0": x, "y0": y, "x1": x + w, "y1": y + h}


def _label(name, wtxt, htxt, x, y):
    """A room label as OCR emits it: name above, dimensions on the next line
    as three tokens."""
    return [_tok(name, x, y - 26),
            _tok(wtxt, x, y), _tok("X", x + 52, y), _tok(htxt, x + 72, y)]


class TestPairs:
    def test_reads_a_split_label(self):
        (p,) = R.dimension_pairs(_label("BEDROOM", "13'6\"", "10'3\"", 680, 999))
        assert (p["w_ft"], p["h_ft"]) == (13.5, 10.25)

    def test_reads_an_unsplit_label(self):
        (p,) = R.dimension_pairs([_tok("11'6\"X11'6\"", 700, 500)])
        assert (p["w_ft"], p["h_ft"]) == (11.5, 11.5)

    def test_inch_mark_is_optional(self):
        """The dimension re-read whitelist has no `"`, so it returns 13'6X10'3."""
        (p,) = R.dimension_pairs([_tok("13'6X10'3", 700, 500)])
        assert (p["w_ft"], p["h_ft"]) == (13.5, 10.25)

    def test_seventy_one_inches_is_not_a_dimension(self):
        """OCR turned 12'1" into 12'71. Read naively that is 17.92 ft and looks
        entirely plausible — it must be rejected instead."""
        assert R.dimension_pairs([_tok("13'6X12'71", 700, 500)]) == []

    def test_does_not_join_labels_across_the_sheet(self):
        """Two rooms far apart must never combine into one pair."""
        toks = [_tok("13'6\"", 100, 500), _tok("X", 900, 500),
                _tok("10'3\"", 2000, 500)]
        assert R.dimension_pairs(toks) == []

    def test_implausible_sides_are_ignored(self):
        assert R.dimension_pairs([_tok("1'0\"X2'0\"", 10, 10)]) == []      # tiny
        assert R.dimension_pairs([_tok("99'0\"X99'0\"", 10, 10)]) == []    # huge

    def test_position_is_the_centre_of_the_tokens_used(self):
        (p,) = R.dimension_pairs(_label("BEDROOM", "13'6\"", "10'3\"", 100, 200))
        assert 100 <= p["x"] <= 200 and 195 <= p["y"] <= 220


class TestMerge:
    A = [{"w_ft": 10.0, "h_ft": 17.917, "x": 1028, "y": 1492}]
    B = [{"w_ft": 13.5, "h_ft": 10.25, "x": 751, "y": 1009}]

    def test_union_of_two_passes(self):
        assert len(R.merge_pairs(self.A, self.B)) == 2

    def test_same_label_read_twice_is_kept_once(self):
        assert len(R.merge_pairs(self.A, list(self.A))) == 1

    def test_conflicting_reads_of_one_label_are_both_dropped(self):
        other = [{"w_ft": 11.5, "h_ft": 17.5, "x": 1030, "y": 1494}]
        assert R.merge_pairs(self.A, other) == []


class TestAttach:
    def _rooms(self):
        return [{"id": "r0", "x": 10.0, "y": 10.0, "area_sqft": 138.4, "_lab": 3},
                {"id": "r1", "x": 40.0, "y": 40.0, "area_sqft": 200.0, "_lab": 7}]

    def _pairs(self):
        return [{"w_ft": 13.5, "h_ft": 10.25, "x": 0, "y": 0,
                 "fx": 10.5, "fy": 10.5, "lab": 3}]

    def test_attaches_to_the_room_it_sits_in(self):
        rooms = self._rooms()
        assert R.attach_printed_dims(rooms, self._pairs()) == 1
        assert rooms[0]["printed_dim_ft"] == [13.5, 10.25]
        assert rooms[0]["printed_area_sqft"] == 138.4
        assert rooms[0]["dim_match_pct"] == 100.0
        assert "printed_dim_ft" not in rooms[1]        # different component

    def test_never_touches_area_sqft(self):
        rooms = self._rooms()
        before = [r["area_sqft"] for r in rooms]
        R.attach_printed_dims(rooms, self._pairs())
        assert [r["area_sqft"] for r in rooms] == before

    def test_one_label_serves_one_room(self):
        rooms = self._rooms()
        rooms[1]["_lab"] = 3                          # both in one component
        assert R.attach_printed_dims(rooms, self._pairs()) == 1

    def test_match_pct(self):
        assert R.match_pct(100, 100) == 100.0
        assert R.match_pct(120, 100) == 80.0
        assert R.match_pct(51.7, 37.5) == 62.1        # FLOOR PLAN's toilet
        assert R.match_pct(1000, 100) == 0.0          # floored, never negative

    def test_summary(self):
        rooms = [{"dim_match_pct": 95.0}, {"dim_match_pct": 61.5},
                 {"dim_match_pct": 60.0}, {}]
        s = R.summary(rooms)
        assert s == {"rooms_checked": 3, "median_match_pct": 61.5,
                     "worst_match_pct": 60.0, "rooms_off": 2}
        assert R.summary([{"area_sqft": 10}]) is None


class TestDoctor:
    def _diagnose(self, matches):
        import plan_doctor
        return plan_doctor.diagnose({
            "meta": {"plan_width_ft": 40, "plan_depth_ft": 60,
                     "scale": {"source": "dimension_text"}},
            "rooms": [{"id": f"r{i}", "type": "bedroom", "area_sqft": 120,
                       "dim_match_pct": m} for i, m in enumerate(matches)],
            "openings": [{"type": "door", "along": [0, 3]}, {"type": "window"}],
            "area_statement": {"efficiency_pct": 70.0, "carpet_source": "rooms"},
            "vastu": {}, "boq": {}})

    def test_wide_mismatch_fails(self):
        d = self._diagnose([60.0, 61.5, 62.1])
        assert d["grade"] in ("D", "F")
        assert any(i["tag"] == "room_dims_mismatch" and i["level"] == "fail"
                   for i in d["issues"])

    def test_good_match_is_an_ok_issue(self):
        d = self._diagnose([97.0, 95.0, 92.0])
        assert any(i["tag"] == "room_dims_verified" for i in d["issues"])
        assert d["grade"] == "A"

    def test_no_printed_dims_is_silent(self):
        d = self._diagnose([])
        assert not any(i["tag"].startswith("room_dims") for i in d["issues"])


class TestPrintedWidths:
    """B-5 depth bound: a balcony is a strip, so the sheet prints its WIDTH
    ('BALCONY 4' WIDE'), not a W x H pair. The name usually sits on its own
    line above the dimension, so the search has to be 2D."""

    def _label(self, name, wtxt, x, y):
        return [_tok(name, x, y - 22),
                _tok(wtxt, x, y), _tok("WIDE", x + 40, y)]

    def test_reads_a_stacked_balcony_label(self):
        toks = self._label("BALCONY", "4'", 359, 1583)
        assert R.printed_widths(toks, "BALCON") == [4.0]

    def test_reads_an_inline_label(self):
        toks = [_tok("3'6\"", 2326, 1216), _tok("WIDE", 2375, 1216),
                _tok("BALCONY", 2328, 1245)]
        assert R.printed_widths(toks, "BALCON") == [3.5]

    def test_keyword_must_be_near(self):
        toks = self._label("KITCHEN", "4'", 359, 1583)
        assert R.printed_widths(toks, "BALCON") == []

    def test_needs_the_word_wide(self):
        toks = [_tok("BALCONY", 359, 1561), _tok("4'", 359, 1583)]
        assert R.printed_widths(toks, "BALCON") == []

    def test_utility_uses_the_same_reader(self):
        toks = self._label("UTILITY", "4'6\"", 1239, 1089)
        assert R.printed_widths(toks, "UTI") == [4.5]
