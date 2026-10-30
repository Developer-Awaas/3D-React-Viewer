"""The human step relation, and the tread test that the riser test cannot do."""
from stairs import riser_ok, tread_ok, TREAD_MIN_IN, TREAD_MAX_IN


def test_the_tread_band_is_the_riser_band_seen_through_2R_plus_T():
    """No number is tuned: 2R + T = 25 in over risers of 5-9 in."""
    assert (TREAD_MIN_IN, TREAD_MAX_IN) == (7.0, 15.0)


def test_the_drawn_tread_separates_a_flight_from_tile_hatch():
    """Measured 1 Sep 2026 across both geometry-route sheets: every real flight
    draws 9.2-10.1 in, GHATIKIA's tile hatch draws 4.4 in."""
    for real_in in (9.2, 10.0, 10.1):
        assert tread_ok(real_in / 12.0), real_in
    assert not tread_ok(4.4 / 12.0)


def test_the_riser_band_CANNOT_see_the_hatch_which_is_why_the_tread_test_exists():
    """The hatch reads 18-21 `treads` and implies a 5.6-6.6 in riser - inside
    the human band. Three fake staircases were built from a tiled floor."""
    assert riser_ok(5.6 / 12.0) and riser_ok(6.6 / 12.0)


def test_both_bands_refuse_the_impossible_cases_actually_measured():
    assert not riser_ok(14.8 / 12.0)      # GHATIKIA, one flight of two found
    assert not riser_ok(9.8 / 12.0)       # FIRST FLOOR, treads under-counted
    assert not riser_ok(3.3 / 12.0)       # the same flight counted twice


def test_tread_scale_check_reads_every_ladder_not_just_the_accepted_ones():
    """Reading only the accepted list would be circular: it is filtered BY the
    tread band, so at a 2x scale every real flight is thrown out as hatch and
    the list comes back empty and innocent."""
    from stairs import tread_scale_check
    ok, med, over = tread_scale_check([9.2 / 12, 4.4 / 12])   # a flight + hatch
    assert ok is True and med == 9.2 and over is None
    bad, med, over = tread_scale_check([18.4 / 12, 20.0 / 12])  # everything at 2x
    assert bad is False and over > 1.6
    assert tread_scale_check([]) == (None, None, None)         # blind, says so


def test_a_lift_is_isotropic_AND_small():
    """L-6, 15 Sep 2026: a room typed `stairs` that is square is a lift - the
    same test `_stair_flight` already used to refuse building steps in one.

    The SIZE bound is not optional: aspect alone typed neelachala FIRST FLOOR's
    166.9 and 168.1 sqft stair CORES as lifts, because a core is roughly square.
    An NBC residential lift shaft is about 2.5 x 2.5 m."""
    from stairs import is_lift, LIFT_MAX_SQFT, STAIR_MIN_ASPECT
    assert LIFT_MAX_SQFT == 67.3 and STAIR_MIN_ASPECT == 1.6
    assert is_lift(4.7, 4.6)            # FLOOR PLAN, printed `LIFT 5'X5"`
    assert is_lift(7.0, 5.8)            # Typical FP (19.06)
    assert not is_lift(16.6, 14.1)      # FIRST FLOOR's stair core - too big
    assert not is_lift(11.7, 4.9)       # GHATIKIA's flight - aspect 2.41
    assert not is_lift(5.0, 0)


def test_it_cannot_see_inside_a_merge():
    """GHATIKIA's lift is merged with its staircase ALONG ITS LENGTH: 4.85 x
    11.71 ft, aspect 2.41, so it reads as a flight. Only the printed label
    saves it, and the merge has to be split before geometry can."""
    from stairs import is_lift
    assert not is_lift(11.71, 4.85)
