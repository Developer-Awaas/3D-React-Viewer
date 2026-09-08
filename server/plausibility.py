"""Facts about BUILDINGS — the only checks that survive a blind sheet.

Coverage, invention and M-1 all compare two of our own readings of the SAME
INK, so they prove we did not mis-read the lines and can never prove the lines
mean something else. Scale, orientation, wing-pick and footprint all preserve
the ink-to-model relationship perfectly, which is exactly why those three miss
them — a wrong scale actually IMPROVES coverage.

A check can only police the scale if the quantity it measures was NOT SELECTED
by a band expressed in feet (26 Aug rule 4). That disqualifies almost all of
them: the door median sits inside the door band at any scale because the door
band is what chose the doors, and the measured wall sits inside 3-18 in for the
same reason. ROOM AREA IS DIFFERENT — a room is found by ENCLOSURE, not by a
size band, so its area is free to come out absurd, and on a 2x-wrong parse it
does.

BAND AND ITS SOURCE. National Building Code of India 2016, Part 3, and the
model building bye-laws set MINIMUM room areas: habitable room 7.5 m2 in a
multi-room dwelling (9.5 m2 for a single-room tenement), kitchen 5.0 m2,
bathroom 1.8 m2, water closet 1.1 m2. THE SMALLEST ENCLOSED ROOM THE CODE
PERMITS AT ALL IS THE WC AT 1.1 m2 = 11.8 sqft, so a floor whose MEDIAN room is
below that is not a floor. The upper bound is the same argument inverted: a
single room cannot be larger than an entire minimum dwelling, and the PMAY /
RERA 1-BHK carpet minimum is 30 m2 = 322.9 sqft.

Neither number is fitted to any drawing we hold. They are code minima, quoted.
"""

SQM_TO_SQFT = 10.7639
NBC_WC_MIN_SQM = 1.1              # smallest enclosed room the code permits
PMAY_1BHK_CARPET_SQM = 30.0       # a room cannot exceed a whole minimum flat
ROOM_MEDIAN_MIN_SQFT = round(NBC_WC_MIN_SQM * SQM_TO_SQFT, 1)        # 11.8
ROOM_MEDIAN_MAX_SQFT = round(PMAY_1BHK_CARPET_SQM * SQM_TO_SQFT, 1)  # 322.9


def room_median_check(areas_sqft):
    """Is this set of polygons a FLOOR? -> (verdict, median_sqft, why).

    `verdict` is None when there are no rooms at all - blind, and it says so
    rather than passing; `no_rooms` is a separate flag and catches that case.
    The MEDIAN is used, not the mean: half the rooms lie above it, so a single
    merged blob or a single sliver cannot move it, which is the failure mode
    both `rooms_off` and this check exist to survive. Pure -> unit-tested.
    """
    a = sorted(x for x in (areas_sqft or []) if x and x > 0)
    if not a:
        return None, None, "no rooms - blind, see the `no_rooms` flag"
    med = a[len(a) // 2]
    if med < ROOM_MEDIAN_MIN_SQFT:
        return False, round(med, 1), (
            f"median room is {med:.1f} sqft - smaller than the smallest room "
            f"the NBC permits at all (a WC, 1.1 m2 = {ROOM_MEDIAN_MIN_SQFT} "
            f"sqft). These polygons are not rooms")
    if med > ROOM_MEDIAN_MAX_SQFT:
        return False, round(med, 1), (
            f"median room is {med:.1f} sqft - larger than an entire minimum "
            f"dwelling (PMAY 1-BHK carpet, 30 m2 = {ROOM_MEDIAN_MAX_SQFT} "
            f"sqft). Half the rooms on this floor are bigger than a whole flat")
    return True, round(med, 1), f"median room {med:.1f} sqft is a room"


def builtup_check(sqft):
    """Is this a FLOOR of a building? -> (verdict, sqft, why).

    Same sourcing as the room band and the same escape from rule 4: the
    footprint is a TRACED RING, not a quantity selected by a size threshold in
    feet, so it is free to come out absurd.

    A floor of a residential building holds at least one dwelling, and built-up
    is never less than carpet, so it cannot be smaller than the PMAY / RERA
    1-BHK carpet minimum of 30 m2 = 322.9 sqft. THERE IS NO CODE MAXIMUM for a
    floor plate - a single floor may legitimately carry fifty flats - so none
    is asserted here. Asserting one would be a number from our corpus, not from
    a building. Pure -> unit-tested.
    """
    if not sqft or sqft <= 0:
        return None, None, "no footprint - blind"
    if sqft < ROOM_MEDIAN_MAX_SQFT:
        return False, round(sqft, 1), (
            f"built-up is {sqft:.1f} sqft for a whole floor - smaller than the "
            f"minimum carpet of ONE dwelling (PMAY 1-BHK, 30 m2 = "
            f"{ROOM_MEDIAN_MAX_SQFT} sqft). This is not a floor")
    return True, round(sqft, 1), f"built-up {sqft:.1f} sqft is a floor"


def scale_guard(scene, refit_info=None, min_sides=8):
    """COLD-SHEET GUARD: is the scale backed by anything PRINTED? (2 Sep 2026)

    Lives here, not in the parser, because THE PATH THAT MOST NEEDS IT IS THE
    ONE THAT DID NOT HAVE IT: the ML/raster reader builds its scene through
    `scene_builder.scene_from_segments`, which assumes a 40 ft plan width and
    stamps `scale.source = "assumed_width"`. An assumed width is the definition
    of an unverified scale, and that path had no refusal at all.

    Verified by EVIDENCE, never by route name: printed dimension text or a
    printed statement SET the scale, or the printed-dimension refit had a
    usable sample - printed dims had the chance to contradict it and either
    corrected it or did not. Mutates and returns `scene`.
    """
    m = scene.setdefault("meta", {})
    sc = m.setdefault("scale", {})
    src = str(sc.get("source") or "")
    info = refit_info if refit_info is not None else \
        (m.get("route", {}) or {}).get("scale_refit")
    n = (info or {}).get("sides", 0) if isinstance(info, dict) else 0
    printed = src in ("room_dim_text", "dimension_text",
                      "printed_area_statement", "overall_dimension_text")
    corrob = n >= min_sides
    sc["verified"] = ok = bool(printed or corrob)
    sc["verified_by"] = ("printed dimension text set the scale" if printed
                         else f"printed room dims corroborated it ({n} sides)"
                         if corrob else
                         f"NOTHING PRINTED - `{src or 'unknown'}` is a guess and "
                         f"no printed dimension could contradict it "
                         f"({n} side samples)")
    scene["scale_verified"] = ok
    # MERGE, never overwrite: other checks append refusals before this runs, and
    # it is called twice on a refit. Keyed on `code` so it cannot duplicate one.
    keep = [r for r in (scene.get("refusals") or [])
            if r.get("code") != "scale_unverified"]
    if not ok:
        keep.append({
            "code": "scale_unverified",
            "message": (f"SCALE IS A GUESS (`{src or 'unknown'}`) and no printed "
                        f"dimension on this sheet can contradict it. Every ft, "
                        f"sqft and rupee below scales with it. Confirm the real "
                        f"plan width before any number here is used.")})
    scene["refusals"] = keep
    return scene


ENVELOPE_VS_INK_MIN_PCT = 20.0


def envelope_vs_ink_check(plan_sqft, ink_sqft):
    """Did we find a BUILDING, or a fragment of one? -> (verdict, pct, why).

    A sheet whose drawn ink covers 88 x 47 ft while the parse offers a 15.6 x
    11.5 ft plan has not read that building - it has read a corner of it. The
    ratio is the check, and it needs nothing printed: the ink extent is the
    drawing's own statement of how big the drawing is.

    NOT a pairing ratio. The obvious test - "admits many lines, pairs almost
    none" - is DISQUALIFIED by measurement: paired share reads 0.1% on
    BRICK WORK and 0.2% on FLOOR PLAN, our two most-trusted sheets, against
    1.1% on the sheet we want to refuse, because the denominator is every drawn
    line including outlined text glyphs. It would refuse the golden sheets
    first.

    Measured 7 Sep across the corpus, plan extent over ink extent:
        DHAL-01 (stilt parking)   4.3%     <- the fragment
        every other sheet         41.8 - 76.1%
    a 37-point empty band, so the 20% floor satisfies the cluster rule by a
    wide margin. REFUSES ONLY; it never selects. Pure -> unit-tested.
    """
    if not plan_sqft or not ink_sqft or ink_sqft <= 0:
        return None, None, "no extent - blind"
    pct = 100.0 * plan_sqft / ink_sqft
    if pct < ENVELOPE_VS_INK_MIN_PCT:
        return False, round(pct, 1), (
            f"the parse offers a plan covering {pct:.1f}% of the drawn ink "
            f"extent - a fragment, not a building. The rest of the drawing was "
            f"read and not enclosed, so no area, volume or cost figure from "
            f"this sheet is offered")
    return True, round(pct, 1), f"plan covers {pct:.1f}% of the drawn extent"
