"""RERA-style area statement from a parsed scene — pure geometry, no GPU.

India's RERA Act mandates that flats are sold on CARPET area, and developers
must publish an area statement per unit. We already have the geometry to compute
it, so this turns every parse into a draft area statement.

Definitions (RERA Act 2016), and how we estimate each from the parse:
  * Carpet area   — net usable floor area inside the walls. We estimate it as
                    the sum of detected room floor areas (the enclosed free-space
                    pockets). Slight under-count: RERA carpet also counts internal
                    partition-wall footprint; we note this.
  * Built-up area — carpet + wall thickness (+ balconies). We estimate it as the
                    gross footprint = area enclosed by the outer wall outline.
  * Super built-up— built-up + a share of common areas (lobby, stairs, lifts).
                    Not derivable from one flat's plan, so we apply a developer-set
                    LOADING FACTOR (typ. 1.25-1.35 in India), clearly labelled.

Everything here is a PURE function so it is fully unit-tested. It is an ESTIMATE
for drafting/analysis — a licensed architect must verify before any RERA filing.
"""

SQFT_TO_SQM = 0.09290304

# room types that are COMMON area, never carpet (R-5, L-5, S-5). "stairs" also
# carries lifts — furnish.classify_room_type maps lift/elevator to it.
COMMON_TYPES = frozenset({"stairs", "lobby", "duct", "lift"})  # §4 D-5: a duct is
# common area; `lift` joined 15 Sep when it stopped being folded into "stairs" -
# R-5/L-5/S-5 already counted the lift as common, so this keeps carpet identical

# B-5: balconies are reported SEPARATELY in Indian practice - neither carpet
# nor common. They are part of the built-up plate.
BALCONY_TYPES = frozenset({"balcony"})
# §10.1 CE-5 (Rahul, 16 Aug 2026): a UTILITY is a covered-but-not-enclosed
# strip like a balcony — two sides closed, two open — but it is NOT a balcony
# and it is NOT carpet, and it is private to the flat so it is not common
# either. It gets its OWN line until ruled otherwise.
UTILITY_TYPES = frozenset({"utility"})


def polygon_area(pts):
    """Shoelace area (absolute) of a polygon given as [[x, y], ...]. 0 if <3
    points. Unit-agnostic: feet in -> square feet out."""
    n = len(pts)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return float(abs(s) / 2.0)


def _pair(sqft):
    sqft = float(sqft)               # cast away numpy floats so JSON stays clean
    return {"sqft": round(sqft, 1), "sqm": round(sqft * SQFT_TO_SQM, 2)}


def compute_area_statement(scene, loading_factor=1.30):
    """Scene dict -> RERA-style area statement dict (sqft + sqm)."""
    rooms = scene.get("rooms", []) or []
    walls_poly = scene.get("walls_poly", []) or []
    meta = scene.get("meta", {}) or {}

    # R-5 / L-5 / S-5: the lift, the staircase and the lobby are COMMON area.
    # They are inside the building and they count in built-up, but they are not
    # carpet and a flat is not sold on them. Counting them as carpet inflates
    # every flat's headline area — the single most consequential misreport a
    # RERA tool can make. `furnish.classify_room_type` folds lift/elevator into
    # "stairs", so both arrive under that one type.
    common_rooms = [r for r in rooms if r.get("type") in COMMON_TYPES]
    balcony_rooms = [r for r in rooms if r.get("type") in BALCONY_TYPES]
    utility_rooms = [r for r in rooms if r.get("type") in UTILITY_TYPES]
    carpet_rooms = [r for r in rooms if r.get("type") not in COMMON_TYPES
                    and r.get("type") not in BALCONY_TYPES
                    and r.get("type") not in UTILITY_TYPES]
    common = sum(float(r.get("area_sqft", 0) or 0) for r in common_rooms)
    balcony = sum(float(r.get("area_sqft", 0) or 0) for r in balcony_rooms)
    carpet = sum(float(r.get("area_sqft", 0) or 0) for r in carpet_rooms)
    carpet_source = "rooms"
    if carpet <= 0:
        # GENERAL fallback (any plan, no per-plan logic): when room detection
        # found nothing, the enclosed free space inside the wall rings — the
        # wall polygons' interior "holes" — IS the usable floor area. Slight
        # over-count vs true carpet (includes circulation), noted below.
        carpet = sum(polygon_area(h)
                     for wp in walls_poly for h in (wp.get("holes") or []))
        carpet_source = "wall_interior" if carpet > 0 else "none"

    # built-up = gross footprint. The parser emits walls_poly in TWO shapes:
    #   (a) ONE building outline whose outer ring IS the gross area and whose
    #       holes are the rooms — then sum(outer) already = gross.
    #   (b) MANY thin wall STRIPS (the common case) — then sum(outer) is just
    #       the wall footprint (~15-20% of carpet), NOT the gross area.
    # The old code used sum(outer) for both, so in case (b) built_up came out
    # SMALLER than carpet and the clamp below forced built_up == carpet — which
    # made wall_and_circulation = 0 and BOQ report ZERO masonry on every real
    # plan, and pinned efficiency. Fix: detect which shape we have.
    gross_outer = sum(polygon_area(wp.get("outer") or []) for wp in walls_poly)
    wall_material = sum(
        max(0.0, polygon_area(wp.get("outer") or [])
            - sum(polygon_area(h) for h in (wp.get("holes") or [])))
        for wp in walls_poly)
    # NB: built-up covers the whole floor plate — carpet AND common area (the
    # lift, stair and lobby are inside the building even though they are not
    # carpet). Using carpet alone here silently deducted the common area from
    # built-up the moment R-5 split it out.
    utility = round(sum(r.get("area_sqft") or 0.0 for r in utility_rooms), 1)
    # §10.2 D-8 PROJECTION (Rahul, 16 Aug 2026): the part of a balcony or
    # utility that sits BEYOND the external wall ring. It is what makes the
    # upper floor bigger than the stilt below it, and the sheet states both, so
    # it is checkable: FLOOR PLAN prints plate 1951 and stilt 1900, i.e. 51 sqft
    # of projection. Measured against the footprint polygon, never assumed.
    projection = 0.0
    try:
        from shapely.geometry import Polygon
        _fp = Polygon(scene.get("footprint_ft") or []).buffer(0)
        if _fp.area > 0:
            for r in balcony_rooms + utility_rooms:
                _g = Polygon(r.get("polygon_ft") or []).buffer(0)
                if _g.area > 0:
                    projection += _g.difference(_fp).area
    except Exception:
        projection = 0.0
    projection = round(projection, 1)
    # covered area inside the building line, so it belongs in BUILT-UP even
    # though it is neither carpet nor balcony (§10.1)
    floor_inside = carpet + common + balcony + utility
    # INSTRUMENT (16 Aug 2026): which branch fired, and what the OTHER branch
    # would have said. This is a CLIFF, not a gradient — on FLOOR PLAN ten
    # admitted wall lines flipped the condition and moved built-up by 366 sqft
    # — and R-8, our best instrument, sits directly downstream of it (§12).
    _branch_a = round(gross_outer, 1)
    _branch_b = round(floor_inside + wall_material, 1)
    # BRANCH C (17 Aug 2026) — THE PLATE FROM THE WALL RING. Built-up is the
    # floor plate: the footprint enclosed by the outer wall ring, plus what
    # projects beyond it (§10.2 D-8). Branches a and b are artefacts of
    # INCOMPLETENESS: `wall_material` is the wall polygon's own footprint and
    # it COLLAPSES when the ring closes — 380.9 sqft on FLOOR PLAN today, 15.1
    # when `ar stairs` was admitted, so built-up fell 366 sqft and R-8 to 78.4.
    # An instrument that falls when the parse improves is measuring the gap,
    # not the building. The ring's outer contour only gets MORE complete as
    # walls are admitted, so this rises where the others fall.
    _fp = meta.get("footprint_sqft")
    try:
        _branch_c = round(float(_fp) + projection, 1) if _fp else None
    except (TypeError, ValueError):
        _branch_c = None
    if _branch_c and _branch_c >= floor_inside:
        built_up = _branch_c
        _branch = "c_footprint_plus_projection"
    elif gross_outer >= floor_inside and gross_outer > 0:
        built_up = gross_outer                 # shape (a): outer already gross
        _branch = "a_gross_outer"
    elif wall_material > 0:
        built_up = floor_inside + wall_material  # shape (b): walls sit ON floor
        _branch = "b_floor_plus_walls"
    else:
        built_up = gross_outer
        _branch = "c_fallback_gross_outer"
    if built_up <= 0:                          # fallback: envelope box
        built_up = float(meta.get("plan_width_ft", 0) or 0) * \
                   float(meta.get("plan_depth_ft", 0) or 0)

    # built-up can never be less than the floor it covers — carpet AND the
    # common area, both of which are inside the building
    built_up = max(built_up, carpet + common + balcony)
    loading_factor = float(loading_factor) if loading_factor else 1.30
    # Indian market convention: the developer's loading factor is applied to
    # CARPET (super = carpet x loading; loading already covers walls + common
    # areas). The previous built_up * loading double-counted the wall footprint,
    # inflating super area and understating efficiency. Never below built-up.
    super_built = max(carpet * loading_factor, built_up)
    wall_loss = max(0.0, built_up - carpet - common - balcony)

    notes = []
    if balcony > 0:
        notes.append("Balcony area is reported separately from carpet (B-5, "
                     "Indian practice); its open side is not built as a wall.")
    if common > 0:
        notes.append(
            f"Common area ({', '.join(sorted({str(r.get('type')) for r in common_rooms}))})"
            f" is reported separately and is NOT part of carpet (RERA: a flat "
            f"is sold on carpet).")
    if carpet_source == "wall_interior":
        notes.append("No individual rooms detected — carpet estimated from the "
                     "enclosed area inside the walls (includes internal "
                     "circulation; slight over-count).")
    elif carpet_source == "none":
        notes.append("No rooms detected — carpet area is 0; needs a sealed plan.")
    if meta.get("scale", {}).get("source") == "assumed_width":
        notes.append("Scale came from a width override, not on-sheet dimensions — "
                     "areas scale with that number; confirm the plan width.")
    notes.append("Carpet excludes internal partition-wall footprint (slight "
                 "under-count vs the strict RERA definition).")
    if balcony <= 0:
        notes.append("No balcony/open space was detected; if the plan has one, "
                     "adjust manually. Service shafts are not separated out.")
    notes.append("Super built-up = carpet x loading factor (market convention; "
                 "loading covers walls + common-area share), floored at built-up.")

    return {
        "carpet_area": _pair(carpet),
        "common_area": _pair(common),          # lift + staircase + lobby
        "common_rooms": [r.get("id") for r in common_rooms],
        "built_up_branch": {"fired": _branch,
                            "a_gross_outer": _branch_a,
                            "b_floor_plus_walls": _branch_b,
                            "c_footprint_plus_projection": _branch_c,
                            "why_c": "a and b FALL when walls are admitted; "
                                     "the ring's outer contour does not",
                            "cliff_sqft": round(abs(_branch_a - _branch_b), 1),
                            "condition": "gross_outer >= floor_inside"},
        "balcony_area": _pair(balcony),        # B-5: reported separately
        "utility_area": _pair(utility),        # CE-5: its own line
        "projection_area": _pair(projection),  # D-8: beyond the external wall
        "balcony_rooms": [r.get("id") for r in balcony_rooms],
        "built_up_area": _pair(built_up),
        "super_built_up_area": _pair(super_built),
        "wall_and_circulation": _pair(wall_loss),
        "loading_factor": round(loading_factor, 3),
        "carpet_source": carpet_source,
        "efficiency_pct": round(100 * carpet / super_built, 1) if super_built else 0.0,
        "carpet_vs_builtup_pct": round(100 * carpet / built_up, 1) if built_up else 0.0,
        "rooms": [{"id": r.get("id"), **_pair(float(r.get("area_sqft", 0) or 0))}
                  for r in rooms],
        "notes": notes,
        "disclaimer": ("Estimate from parsed geometry for drafting/analysis only. "
                       "Verify with a licensed architect before any RERA filing."),
    }
