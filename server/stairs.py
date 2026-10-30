"""The human step relation — ONE definition, used by the parser and the builder.

A staircase is the one thing in a plan sized by the body rather than by the
drawing, so its two numbers come from the same standard relation and not from
anything we tune:

    2 x RISER + TREAD = 25 in          (the architect's rule of thumb)
    RISER 5-9 in                       (NBC/IS residential 150-190 mm, widened
                                        so a real stair is never refused)
    => TREAD 7-15 in

Both bands REFUSE; neither selects within a population it was derived from
(26 Aug rule 4). They are stated here once because two definitions of one
number is the `wing_at` / `wing_pick` trap: the parser gates which drawn
ladders are staircases, the builder gates whether a staircase can climb its
storey, and the two must never disagree about what a step is.

WHY THE TREAD MATTERS MORE THAN THE RISER (1 Sep 2026, Rahul). The riser is
INFERRED - storey height divided by treads drawn - so it inherits every
miscount. The tread is MEASURED: it is the drawn pitch of the ladder. Tile
hatch on GHATIKIA reads 18-21 "treads" at a 4.4 in pitch and implies risers of
5.6-6.6 in, which sit comfortably inside the human riser band; three fake
staircases were built from a tiled floor. The drawn 4.4 in tread is outside the
tread band by a wide margin, and that is what separates them.
"""

STEP_RULE_IN = 25.0                      # 2R + T
RISER_MIN_IN, RISER_MAX_IN = 5.0, 9.0
TREAD_MIN_IN = STEP_RULE_IN - 2.0 * RISER_MAX_IN     # 7 in
TREAD_MAX_IN = STEP_RULE_IN - 2.0 * RISER_MIN_IN     # 15 in


def riser_ok(riser_ft):
    """Can a person climb this? Refusal only."""
    return RISER_MIN_IN <= riser_ft * 12.0 <= RISER_MAX_IN


def tread_ok(pitch_ft):
    """Is this drawn pitch a stair tread, or is it hatch? Refusal only."""
    return TREAD_MIN_IN <= pitch_ft * 12.0 <= TREAD_MAX_IN


TREAD_MID_IN = (TREAD_MIN_IN + TREAD_MAX_IN) / 2.0      # 11 in


def tread_scale_check(pitches_ft):
    """SECOND PLAUSIBILITY CHECK ON SCALE (2 Sep 2026, Rahul), with no printed
    data: a stair tread is 7-15 in, so a 2x scale error reads 14-30 in and a
    0.5x error 3.5-7.5 in. Fact about buildings, not about our corpus.

    `pitches_ft` must be EVERY ladder the sheet drew - accepted AND rejected.
    Reading only the accepted ones would be circular: the accepted list is
    filtered BY the tread band, so at a 2x scale every real flight is thrown
    out as hatch and the list comes back empty and innocent.

    Returns (verdict, median_in, implied_oversize). `verdict` is None when the
    sheet draws no ladder at all - blind, and says so rather than passing.
    A sheet passes as soon as ONE ladder is a real flight; hatch alongside it
    is a hatch problem, not a scale problem. Pure -> unit-tested.
    """
    p = sorted(x * 12.0 for x in (pitches_ft or []) if x)
    if not p:
        return None, None, None
    med = p[len(p) // 2]
    if any(tread_ok(x / 12.0) for x in p):
        return True, round(med, 1), None
    return False, round(med, 1), round(med / TREAD_MID_IN, 3)


# L-6: A LIFT IS NOT A STAIRCASE, and the shape says which (15 Sep 2026).
# A flight is long and narrow; a shaft is square. `_stair_flight` used this to
# REFUSE building steps in a lift before the lift had a type of its own; it now
# also TYPES the room. Lives here because both the parser and the builder read
# it, and two definitions of one number is the `wing_at` / `wing_pick` trap.
STAIR_MIN_ASPECT = 1.6
# A lift shaft is SMALL. NBC/IS residential practice puts a passenger-lift shaft
# at roughly 2.5 x 2.5 m; 6.25 m2 = 67.3 sqft is taken as the ceiling. Quoted,
# not fitted: our own lifts measure 20.4-57.1 sqft and sit well inside it, while
# neelachala FIRST FLOOR's stair CORES measure 166.9 and 168.1 sqft and are
# correctly excluded - a 168 sqft "lift" is a room, and aspect alone typed it as
# one until this bound was added (15 Sep 2026).
LIFT_MAX_SQFT = round(6.25 * 10.7639, 1)      # 6.25 m2 -> sqft


def is_lift(long_ft, short_ft):
    """A room typed `stairs` that is ISOTROPIC is a lift. Refusal-shaped: it
    types nothing it is not sure about, and it CANNOT see inside a merge -
    GHATIKIA's lift is merged with its staircase along its length and measures
    aspect 2.41, so it reads as a flight. Pure."""
    if not short_ft or short_ft <= 0 or not long_ft:
        return False
    if long_ft * short_ft > LIFT_MAX_SQFT:
        return False
    return (max(long_ft, short_ft) / min(long_ft, short_ft)) < STAIR_MIN_ASPECT
