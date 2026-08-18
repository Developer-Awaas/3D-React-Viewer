"""R-8 — reading the sheet's own printed AREA STATEMENT and comparing it.

The extraction is PURE (tokens in, figures out), so these tests build the
FLOOR PLAN.pdf table as synthetic tokens and never need tesseract. One extra
test runs the real sheet end-to-end and is skipped when tesseract is absent.
"""
import os

import pytest

import area_compare

HERE = os.path.dirname(os.path.abspath(__file__))
PLANS = os.path.join(HERE, "..", "..", "plans")


def _tok(text, x, y, w=60.0, h=20.0):
    return {"text": text, "x0": x, "y0": y, "x1": x + w, "y1": y + h}


def _floor_plan_tokens():
    """The FLOOR PLAN.pdf area statement, laid out as it sits on the sheet:
    two label rows, a header row, two flat rows, and a common-area cell that
    spans both flat rows (so it lands on its own row)."""
    return [
        _tok("PLOT", 1617, 540), _tok("AREA", 1716, 540),
        _tok("3371", 2281, 541), _tok("SFT", 2365, 541),
        _tok("STILT", 1616, 595), _tok("FLOOR", 1713, 595),
        _tok("1900", 2281, 597), _tok("SFT", 2363, 597),
        _tok("AREA", 2713, 552), _tok("STATEMENT", 2868, 551),
        _tok("FLAT", 1730, 671), _tok("NO.S", 1834, 671),
        _tok("BUILT", 2204, 675), _tok("UP", 2325, 675), _tok("AREA", 2384, 674),
        _tok("CARPET", 2653, 674), _tok("AREA", 2808, 674),
        _tok("COMMON", 2988, 669), _tok("AREA", 3111, 669),
        _tok("FLAT-1", 1616, 781), _tok("(2-BHK)", 1753, 781),
        _tok("870", 2291, 781), _tok("680", 2738, 781),
        _tok("246", 3113, 807), _tok("SFT", 3173, 807),
        _tok("FLAT-2", 1616, 828), _tok("(2-BHK)", 1753, 828),
        _tok("835", 2291, 829), _tok("690", 2738, 829),
    ]


class TestParse:
    def test_reads_every_printed_figure(self):
        got = area_compare.parse_area_statement(_floor_plan_tokens())
        assert got["plot_area_sqft"] == 3371
        assert got["stilt_area_sqft"] == 1900
        assert got["common_area_sqft"] == 246
        assert got["built_up_total_sqft"] == 1705      # 870 + 835
        assert got["carpet_total_sqft"] == 1370        # 680 + 690

    def test_reads_per_flat_rows(self):
        flats = area_compare.parse_area_statement(_floor_plan_tokens())["flats"]
        assert [f["name"] for f in flats] == ["FLAT-1", "FLAT-2"]
        assert flats[0] == {"name": "FLAT-1", "built_up_sqft": 870,
                            "carpet_sqft": 680}
        assert flats[1]["built_up_sqft"] == 835

    def test_tolerates_ocr_dropping_a_letter(self):
        """OCR reads this sheet's 'STILT FLOOR' as 'SILT FLOOR'."""
        toks = [t if t["text"] != "STILT" else {**t, "text": "SILT"}
                for t in _floor_plan_tokens()]
        assert area_compare.parse_area_statement(toks)["stilt_area_sqft"] == 1900

    def test_ignores_the_same_numbers_printed_on_the_drawing(self):
        """'FLAT-1 B.U.A- 870 SFT' is lettered INSIDE the plan, far below the
        table. It must not be mistaken for a table row."""
        toks = _floor_plan_tokens() + [
            _tok("FLAT-1", 1058, 1521), _tok("B.U.A-", 1060, 1548),
            _tok("870", 1049, 1574), _tok("SFT", 1098, 1574),
            _tok("FLAT-2", 2413, 1578), _tok("835", 2406, 1632),
        ]
        got = area_compare.parse_area_statement(toks)
        assert len(got["flats"]) == 2                 # not 4
        assert got["built_up_total_sqft"] == 1705

    def test_no_table_returns_none(self):
        assert area_compare.parse_area_statement([]) is None
        assert area_compare.parse_area_statement(
            [_tok("BEDROOM", 700, 973), _tok("KITCHEN", 992, 1072)]) is None

    def test_header_without_readable_rows_returns_none(self):
        assert area_compare.parse_area_statement(
            [_tok("BUILT", 2204, 675), _tok("CARPET", 2653, 674)]) is None

    def test_rejects_implausible_figures(self):
        toks = [t if t["text"] != "870" else {**t, "text": "3"}
                for t in _floor_plan_tokens()]
        flats = area_compare.parse_area_statement(toks)["flats"]
        assert "built_up_sqft" not in flats[0]        # 3 sqft is not an area


class TestCompare:
    STMT = {"carpet_area": {"sqft": 1287.1}, "built_up_area": {"sqft": 1693.3}}

    def test_floor_plan_built_up_matches_the_sheet(self):
        """The anchor case, re-based 16 Aug 2026: the sheet prints 1705 for the
        two FLATS and 246 of common SEPARATELY, so the plate is 1951. A
        whole-floor parse of 1693.3 is 86.8% of that — it was only ever 99.3%
        of 1705 because the common area was missing from our side too."""
        printed = area_compare.parse_area_statement(_floor_plan_tokens())
        cmp_ = area_compare.compare(printed, self.STMT)
        bu = next(r for r in cmp_["rows"] if r["figure"] == "built_up")
        # BASIS (16 Aug 2026): the comparison is against the PLATE — the
        # sheet's flats-only 1705 PLUS its separately listed 246 of common.
        # The flats-only figure is still reported, on its own row.
        assert bu["printed_sqft"] == 1951.0
        assert bu["parsed_sqft"] == 1693.3
        assert bu["match_pct"] == 86.8
        # the flats-only row is still there, and still reads 99.3%
        fo = next(r for r in cmp_["rows"] if r["figure"] == "built_up_flats_only")
        assert fo["printed_sqft"] == 1705.0 and fo["match_pct"] == 99.3

    def test_verdict_bands(self):
        printed = {"built_up_total_sqft": 1000.0}
        for parsed, verdict in ((1000.0, "match"), (1040.0, "match"),
                                (1100.0, "close"), (1400.0, "mismatch"),
                                (600.0, "mismatch")):
            cmp_ = area_compare.compare(
                printed, {"built_up_area": {"sqft": parsed}})
            assert cmp_["verdict"] == verdict, parsed

    def test_a_27pct_scale_error_would_read_as_mismatch(self):
        """§0.1's worked example, inverted: the scale 'correction' once
        proposed for this sheet would have made built-up 38% wrong, and R-8
        must call that a mismatch rather than let it through."""
        printed = area_compare.parse_area_statement(_floor_plan_tokens())
        cmp_ = area_compare.compare(
            printed, {"built_up_area": {"sqft": 1693.3 * 0.787 ** 2}})
        assert cmp_["verdict"] == "mismatch"

    def test_missing_side_is_not_compared(self):
        assert area_compare.compare(None, self.STMT) is None
        assert area_compare.compare({"built_up_total_sqft": 100.0}, None) is None
        assert area_compare.compare({"flats": []}, self.STMT) is None


class TestDoctor:
    """A printed-vs-parsed gap is the strongest accuracy signal there is, so it
    must move the grade."""

    def _scene(self, built_up, carpet=1370.0):
        import plan_doctor
        printed = area_compare.parse_area_statement(_floor_plan_tokens())
        stmt = {"carpet_area": {"sqft": carpet},
                "built_up_area": {"sqft": built_up},
                "efficiency_pct": 76.0, "carpet_source": "rooms"}
        scene = {"meta": {"plan_width_ft": 113.9, "plan_depth_ft": 35.6,
                          "scale": {"source": "dimension_text"}},
                 "rooms": [{"id": "r0", "area_sqft": 615.3, "type": "living"}],
                 "openings": [{"type": "door", "along": [0, 3]},
                              {"type": "window"}],
                 "area_statement": stmt, "vastu": {}, "boq": {},
                 "printed_areas": printed}
        scene["area_comparison"] = area_compare.compare(printed, stmt)
        return plan_doctor.diagnose(scene)

    def test_match_is_an_ok_issue_and_keeps_grade_a(self):
        # 1938 against the PLATE of 1951 = 99.3%, the same margin 1693.3 used
        # to have against the old flats-only basis of 1705
        d = self._scene(1938.0)
        assert d["grade"] == "A"
        assert any(i["tag"] == "printed_area_verified" for i in d["issues"])

    def test_carpet_gap_alone_downgrades_to_a_warning(self):
        """Built-up matches the plate at 99.3% but carpet is 6% light."""
        d = self._scene(1938.0, carpet=1287.1)
        assert any(i["tag"] == "printed_area_close" for i in d["issues"])

    def test_mismatch_fails_the_plan(self):
        d = self._scene(1050.0, carpet=900.0)
        assert d["grade"] in ("D", "F")
        bad = [i for i in d["issues"] if i["tag"] == "printed_area_mismatch"]
        assert bad and bad[0]["level"] == "fail"
        assert "1705" in bad[0]["message"]           # names the printed figure


@pytest.mark.skipif(not os.path.exists(os.path.join(PLANS, "FLOOR PLAN.pdf")),
                    reason="confidential corpus not present")
def test_floor_plan_pdf_end_to_end():
    """The real sheet: dead text, so this only passes via OCR. Skipped when
    tesseract is not installed (optional dependency)."""
    pytest.importorskip("pytesseract")
    import pytesseract
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        pytest.skip("tesseract binary not installed")
    import area_statement
    import pdf_vector
    with open(os.path.join(PLANS, "FLOOR PLAN.pdf"), "rb") as f:
        scene = pdf_vector.parse(f.read())
    printed = scene.get("printed_areas")
    assert printed, "the sheet prints an area statement; it must be read"
    assert printed["built_up_total_sqft"] == 1705
    assert printed["carpet_total_sqft"] == 1370
    assert printed["plot_area_sqft"] == 3371
    assert printed["common_area_sqft"] == 246
    assert printed["stilt_area_sqft"] == 1900
    cmp_ = area_compare.compare(
        printed, area_statement.compute_area_statement(scene))
    bu = next(r for r in cmp_["rows"] if r["figure"] == "built_up")
    # R-8 is KNOWINGLY RED here, and this pins how red. It read 99.3% until
    # 2026-08-11, but that was a coincidence: a ~1.2x scale inflation was
    # cancelling ~40% of missing rooms. With the scale corrected against the
    # sheet's printed room dimensions, the coverage gap is now visible —
    # 1161 sqft parsed vs 1705 printed, because we find 9 pockets of ~16 rooms.
    # This number MUST RISE as room coverage improves, and must never silently
    # fall. If this assertion FAILS, it means one of two things and both need a
    # human ruling: coverage improved (good — re-baseline this floor upward,
    # with the evidence, per §0.1) or something regressed (bad — investigate).
    # Do not delete the check, and do not relax it to make a change pass.
    # RATCHET RE-DERIVED 16 Aug 2026 (Rahul) — 99.4 -> 87.2, and this is NOT a
    # regression. R-8 was comparing our WHOLE-FLOOR built-up against the
    # sheet's FLATS-ONLY 1705, while the common area was missing from ours:
    # a wrong basis and a missing area cancelling to a flattering 99.8%.
    # The correct basis is the PLATE = flats 1705 + common 246 = 1951, which
    # the sheet self-confirms: its printed STILT reads 1900, the same plate
    # without the 51 sqft that projects beyond the external wall (§10.2 D-8).
    # 87.2 is the UNCONFIRMED value; confirming the missing south edge (§0.2)
    # takes it to 96.6, but confirmation is USER INPUT and must never be
    # assumed by a test.
    # RATCHET RE-DERIVED AGAIN 17 Aug 2026 (Rahul) — 87.2 -> 91.8, and this is
    # a BASIS fix, not tuning. Built-up was `floor_inside + wall_material`, and
    # `wall_material` is the wall polygon's own footprint: it COLLAPSES when
    # the ring closes (380.9 sqft here, 15.1 when `ar stairs` was admitted), so
    # every correct wall admission DROPPED built-up and R-8 with it. An
    # instrument that falls when the parse improves is measuring the gap, not
    # the building. Built-up is now the PLATE: footprint + projections beyond
    # the ring (1705.3 + 86.2 = 1791.5 of the printed 1951), which rises as
    # walls are read. Both older formulas stay reported on `built_up_branch`.
    # RATCHET RAISED 91.8 -> 96.6 on 17 Aug 2026 (Rahul), per §0.1: Phase 1
    # attempt 7 admitted the `ar stairs` wall, and the ring stopped biting a
    # notch around the staircase — footprint 1702.7 -> 1799.3, of which 88.5
    # sqft is that zone. Verified against a THIRD figure, the printed STILT of
    # 1900 (the same plate without projections): 89.6% -> 94.7% of it. The
    # identical admission read R-8 78.4 on 16 Aug; only the instrument changed.
    assert bu["match_pct"] >= 96.6
    assert bu["printed_sqft"] == 1951.0       # the PLATE: flats 1705 + common 246


# --- §10.2 D-9 BASIS (17 Aug 2026) -------------------------------------------
# Three basis defects surfaced in one week, so all eight comparisons were swept.
# These pin the two that are WRONG, so neither can quietly start driving a
# verdict, and the one that is right, so it cannot be re-broken.
def test_the_flats_only_row_is_reported_but_never_judged():
    printed = area_compare.parse_area_statement(_floor_plan_tokens())
    cmp_ = area_compare.compare(printed, {"built_up_area": {"sqft": 1702.2},
                                          "carpet_area": {"sqft": 1203.5}})
    figs = {r["figure"] for r in cmp_["rows"]}
    assert "built_up_flats_only" in figs          # reported...
    fo = next(r for r in cmp_["rows"] if r["figure"] == "built_up_flats_only")
    # ...but it must not set the verdict: it compares a whole-floor parse
    # against the sheet's flats-only figure, which is a different basis
    assert cmp_["worst_diff_pct"] != abs(fo["diff_pct"])


def test_the_projection_row_does_not_drive_the_verdict():
    """The sheet's own stilt arithmetic omits the utility (Rahul, 17 Aug), so
    this row disagrees BY THE DRAWING'S ERROR. It is surfaced as an `ask`, and
    must not fail the sheet or mask R-8."""
    printed = area_compare.parse_area_statement(_floor_plan_tokens())
    cmp_ = area_compare.compare(printed, {"built_up_area": {"sqft": 1951.0},
                                          "carpet_area": {"sqft": 1370.0},
                                          "projection_area": {"sqft": 86.2}})
    pr = next(r for r in cmp_["rows"] if r["figure"] == "projection")
    assert pr["printed_sqft"] == 51.0 and pr["parsed_sqft"] == 86.2
    assert cmp_["verdict"] == "match"             # the other rows are exact


def test_carpet_keeps_its_basis():
    """Printed carpet is FLATS ONLY (680 + 690) and ours excludes common,
    balcony and utility — the same axis. This comparison was checked, not
    assumed, on 17 Aug."""
    printed = area_compare.parse_area_statement(_floor_plan_tokens())
    assert printed["carpet_total_sqft"] == 1370.0
    assert [f["carpet_sqft"] for f in printed["flats"]] == [680.0, 690.0]
