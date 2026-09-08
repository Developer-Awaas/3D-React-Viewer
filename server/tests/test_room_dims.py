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
        # RE-DERIVED 2 Sep 2026 on Rahul's ruling: R-2's basis is now NAMED,
        # because area SQUARES the per-side error and a ratchet on an
        # unlabelled basis is a ratchet on an unknown quantity. The area
        # numbers themselves are unchanged - the basis did not move.
        assert s == {"rooms_checked": 3, "basis": "area",
                     "median_match_pct": 61.5,
                     "worst_match_pct": 60.0, "rooms_off": 2}
        assert R.summary([{"area_sqft": 10}]) is None

    def test_both_bases_are_emitted_when_a_room_has_a_polygon(self):
        rooms = [{"dim_match_pct": 90.2, "dim_side_match_pct": 95.0},
                 {"dim_match_pct": 80.0, "dim_side_match_pct": 89.4}]
        s = R.summary(rooms)
        assert s["basis"] == "area" and s["median_match_pct"] == 90.2
        assert s["median_side_match_pct"] == 95.0 and s["sides_checked"] == 2

    def test_area_squares_the_per_side_error(self):
        """A room 5% small on BOTH sides scores 90.2 on area, 95.0 per side -
        which is why R-2 reads harsher than per-side reality."""
        assert R.match_pct(0.95 * 0.95 * 100, 100) == 90.2
        assert R.side_match_pct([9.5, 9.5], [10.0, 10.0]) == 95.0
        assert R.side_match_pct([10.0], [10.0]) is None      # needs both sides


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


# --- RATCHET (15 Aug 2026): neelachala FIRST FLOOR is now INSTRUMENTED ------
# It read 31.1% over ONE matched room and was recorded as a failing sheet for
# four days. The rooms were never wrong: `_PAIR_RE` could not read the hyphen
# form `11'-5"`, which this sheet uses everywhere and FLOOR PLAN uses nowhere,
# so 4 pairs were read from 359 tokens. R-2 is the second instrumented plan
# and must not silently fall back.
import os

import pytest

import pdf_vector

_PLANS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "plans")


@pytest.mark.skipif(not os.path.exists(os.path.join(_PLANS, "neelachala FIRST FLOOR.pdf")),
                    reason="confidential corpus not present")
def test_first_floor_r2_ratchet():
    with open(os.path.join(_PLANS, "neelachala FIRST FLOOR.pdf"), "rb") as f:
        rooms = pdf_vector.parse(f.read())["rooms"]
    s = R.summary(rooms)
    # RATCHET BOTH (Rahul, 17 Aug 2026): R-2 held at 97.0 on FLOOR PLAN while
    # a printed, verifiable toilet was DELETED — the room left the SAMPLE
    # instead of lowering the score. A median cannot see a room that stops
    # existing, so the sample size is pinned beside it.
    # RAISED TWICE ON 22 Aug 2026 (Rahul), and the second time the MEDIAN FELL.
    #   8 -> 14: the second block arriving (the band rule).
    #  14 -> 16: the 16-room cap removed, which had been deleting three rooms.
    # The median went 98.4 -> 96.9 as those rooms entered the sample honestly.
    # A FALLING MEDIAN WITH A RISING SAMPLE IS AN IMPROVEMENT — pre-authorised
    # by Rahul, because the alternative is a score that stays high by not
    # looking. `rooms_off` (7 of 16) is what sees the two ~590 sqft blobs.
    assert s and s["rooms_checked"] >= 16, s
    assert s["median_match_pct"] >= 96.9, s


@pytest.mark.skipif(not os.path.exists(os.path.join(_PLANS, "neelachala FIRST FLOOR.pdf")),
                    reason="confidential corpus not present")
def test_no_absolute_room_cap():
    """`rooms = rooms[:16]` deleted the three smallest rooms on any sheet that
    found more (22 Aug 2026). On neelachala FIRST FLOOR — five flats over two
    blocks — it found NINETEEN and threw away 34.0, 33.5 and 29.1 sqft: BOTH
    of that sheet's balconies, and a bathroom that matched its printed
    dimension at 96.9%. A verifiable room was being destroyed silently, and
    B-5 read 0.0 while the sheet prints `balcony 9'-7" X 4'-0"` twice.

    Rooms are bounded by a DERIVED floor (the sheet's own minimum room area);
    an absolute count is a second, blunter filter on the same thing."""
    with open(os.path.join(_PLANS, "neelachala FIRST FLOOR.pdf"), "rb") as f:
        rooms = pdf_vector.parse(f.read())["rooms"]
    assert len(rooms) > 16, f"the room cap is back: {len(rooms)}"
    small = sorted(r["area_sqft"] for r in rooms)[:3]
    assert max(small) < 35.0, small          # the three the cap used to eat


@pytest.mark.skipif(not os.path.exists(os.path.join(_PLANS, "FLOOR PLAN.pdf")),
                    reason="confidential corpus not present")
def test_floor_plan_r2_sample_is_ratcheted():
    """A score that holds while its sample shrinks is not holding (Rahul,
    17 Aug 2026). Pair-built walls took this sheet to 98.0 over 8 rooms."""
    with open(os.path.join(_PLANS, "FLOOR PLAN.pdf"), "rb") as f:
        s = R.summary(pdf_vector.parse(f.read())["rooms"])
    assert s["rooms_checked"] >= 8, s
    assert s["median_match_pct"] >= 95.0, s


@pytest.mark.skipif(not os.path.exists(os.path.join(_PLANS, "NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf")),
                    reason="confidential corpus not present")
def test_ghatikia_r2_sample_is_ratcheted():
    """RE-DERIVED 2026-08-25: sample 14 -> 7, because the sheet's TWO VIEWS are
    now split and we no longer count the same rooms twice. Expected, not a
    regression (Rahul).

    The median is still NOT ratcheted, and the split shows why: it moved only
    60.1 -> 60.7 even though the 541.9 sqft blob that straddled the gutter is
    GONE (the largest room is now 168.6 sqft). What DID move is what a median
    cannot show — `worst_match_pct` 0.0 -> 57.2 and `rooms_off` 12 -> 6. The
    median is held near 60 by this sheet's UNTOUCHED 19% scale error, which is
    a separate one-variable change."""
    with open(os.path.join(_PLANS, "NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf"), "rb") as f:
        s = R.summary(pdf_vector.parse(f.read())["rooms"])
    # RE-DERIVED 2026-08-25 after the SCALE refit (7.19 pt/ft from the printed
    # room dimensions, accepted on dimension anchors 56% -> 69%):
    #   rooms_checked 7 -> 12   median 60.7 -> 83.5   rooms_off 6 -> 3
    #   worst 57.2 -> 0.0
    # The QUARTET is why that reads as a win: the SAMPLE grew by five rooms and
    # three of the twelve are still off. `worst` is 0.0 because of ONE room —
    # `stairs`, measured 4.85 x 11.71 against a printed 5.15 x 5.35, i.e. sides
    # 0.942 / 2.189. That is anisotropic, so it is a MERGE, not scale: nine of
    # the twelve now read 0.907-1.036 on BOTH sides.
    assert s["rooms_checked"] >= 12, s
    assert s["median_match_pct"] >= 83.5, s
    assert s["rooms_off"] <= 3, s


def test_printed_labels_in_room_counts_merges():
    """THE CORRECTED DISCRIMINATOR (28 Aug 2026, Rahul): count the printed
    dimension labels inside a room FIRST. More than one = the room is a MERGE
    of spaces the sheet names separately, whatever the side ratios do —
    isotropy is only meaningful at a count of 1, because a merge is isotropic
    whenever the absorbed neighbours sit on BOTH axes. Scored on GHATIKIA:
    label-count 12 of 12 correct, isotropy 10 of 12."""
    rooms = [{"_lab": 1, "x": 0, "y": 0, "area_sqft": 100},
             {"_lab": 2, "x": 50, "y": 0, "area_sqft": 100}]
    pairs = [{"lab": 1, "fx": 0, "fy": 0, "w_ft": 10, "h_ft": 10},
             {"lab": 1, "fx": 2, "fy": 2, "w_ft": 4, "h_ft": 4},
             {"lab": 2, "fx": 50, "fy": 0, "w_ft": 10, "h_ft": 10}]
    R.attach_printed_dims(rooms, pairs)
    assert rooms[0]["printed_labels_in_room"] == 2      # a MERGE
    assert rooms[1]["printed_labels_in_room"] == 1      # one room
