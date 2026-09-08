"""Facts about buildings — the one check that escapes rule 4.

Bands are CODE MINIMA, quoted, not fitted to any drawing we hold: NBC of India
2016 (WC 1.1 m2, the smallest enclosed room the code permits) and the PMAY/RERA
1-BHK carpet minimum (30 m2).
"""
from plausibility import (room_median_check, ROOM_MEDIAN_MIN_SQFT,
                          ROOM_MEDIAN_MAX_SQFT)


def test_the_band_is_the_code_minima_not_our_corpus():
    assert (ROOM_MEDIAN_MIN_SQFT, ROOM_MEDIAN_MAX_SQFT) == (11.8, 322.9)


def test_it_catches_the_case_the_door_median_calls_perfect():
    """BRICK WORK at a 2x scale: 29 rooms, 22 doors, door median 3.01 ft - a
    completely plausible reading of a building twice its real size. Its median
    room is 5.0 sqft."""
    ok, med, why = room_median_check([1.0, 2.0, 5.0, 40.0, 300.0])
    assert ok is False and med == 5.0 and "not rooms" in why


def test_every_real_sheet_passes_including_the_cold_one():
    """Medians measured 2 Sep: 49.6 - 51.2 - 106.5 - 141.0 on the corpus and
    114.1 on the cold sheet that shaped none of our constants."""
    for med in (49.6, 51.2, 106.5, 114.1, 141.0):
        ok, got, _ = room_median_check([med / 2, med, med * 2])
        assert ok is True and got == med


def test_half_the_rooms_bigger_than_a_whole_flat_is_refused():
    ok, med, why = room_median_check([400.0, 500.0, 600.0])
    assert ok is False and "minimum dwelling" in why


def test_no_rooms_is_blind_and_says_so_rather_than_passing():
    v, med, why = room_median_check([])
    assert v is None and med is None and "blind" in why


def test_one_blob_and_one_sliver_cannot_move_the_verdict():
    """The MEDIAN, not the mean: `rooms_off` exists because a median survives a
    merge, and this check needs the same property."""
    assert room_median_check([0.5, 60.0, 61.0, 62.0, 900.0])[0] is True


def test_builtup_catches_a_half_scale_parse_and_passes_every_real_floor():
    """Measured 2 Sep: at 0.5x the footprints read 315.5 / 241.9 / 218.8 sqft
    (BRICK WORK / GHATIKIA / FIRST FLOOR); the real ones read 1247 / 1797 /
    1739 / 4472, and the cold sheet 1436."""
    from plausibility import builtup_check
    for bad in (315.5, 241.9, 218.8):
        ok, got, why = builtup_check(bad)
        assert ok is False and "not a floor" in why
    for good in (480.2, 1247.1, 1436.3, 1796.8, 1738.4, 4472.1):
        assert builtup_check(good)[0] is True
    assert builtup_check(0) == (None, None, "no footprint - blind")


def test_no_upper_bound_is_asserted_because_no_code_sets_one():
    """A single floor may legitimately carry fifty flats. An upper bound here
    would be a number from our corpus, not from a building."""
    from plausibility import builtup_check
    assert builtup_check(250000.0)[0] is True


def test_the_scale_guard_refuses_an_assumed_width():
    """The ML/raster path stamps `assumed_width` from a 40 ft guess, and until
    2 Sep the refusal existed only on the vector path."""
    from plausibility import scale_guard
    s = scale_guard({"meta": {"scale": {"source": "assumed_width"}}})
    assert s["scale_verified"] is False
    assert [r["code"] for r in s["refusals"]] == ["scale_unverified"]
    ok = scale_guard({"meta": {"scale": {"source": "room_dim_text"}}})
    assert ok["scale_verified"] is True and ok["refusals"] == []


def test_the_guard_merges_refusals_it_did_not_write():
    from plausibility import scale_guard
    s = {"meta": {"scale": {"source": "assumed_width"}},
         "refusals": [{"code": "rooms_implausible", "message": "x"}]}
    scale_guard(s); scale_guard(s)          # twice, as a refit does
    assert sorted(r["code"] for r in s["refusals"]) == [
        "rooms_implausible", "scale_unverified"]


def test_a_fragment_is_refused_and_every_real_plan_passes():
    """Measured 7 Sep: DHAL-01 offers a plan covering 4.3% of the drawn ink;
    every other sheet reads 41.8-76.1%. A 37-point empty band."""
    from plausibility import envelope_vs_ink_check
    ok, pct, why = envelope_vs_ink_check(15.6 * 11.5, 88.1 * 46.9)
    assert ok is False and pct == 4.3 and "fragment" in why
    for plan, ink in ((95.2 * 29.8, 117 * 58), (29.6 * 48.7, 47 * 64),
                      (43.9 * 58.9, 99 * 62), (38.2 * 177.3, 55 * 189),
                      (87.1 * 37.8, 99 * 59), (34 * 57 * 0.76, 34 * 57)):
        assert envelope_vs_ink_check(plan, ink)[0] is True, (plan, ink)
    assert envelope_vs_ink_check(0, 0) == (None, None, "no extent - blind")


def test_the_pairing_ratio_would_have_refused_the_golden_sheets_first():
    """Why this is NOT a pairing test, recorded as a measurement: paired share
    reads 0.1% on BRICK WORK and 0.2% on FLOOR PLAN - our two most-trusted
    sheets - against 1.1% on the sheet we want to refuse."""
    paired_pct = {"BRICK WORK": 0.1, "FLOOR PLAN": 0.2, "DHAL-01": 1.1}
    assert paired_pct["DHAL-01"] > paired_pct["FLOOR PLAN"]
