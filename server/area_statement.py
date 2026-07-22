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

    carpet = sum(float(r.get("area_sqft", 0) or 0) for r in rooms)
    carpet_source = "rooms"
    if carpet <= 0:
        # GENERAL fallback (any plan, no per-plan logic): when room detection
        # found nothing, the enclosed free space inside the wall rings — the
        # wall polygons' interior "holes" — IS the usable floor area. Slight
        # over-count vs true carpet (includes circulation), noted below.
        carpet = sum(polygon_area(h)
                     for wp in walls_poly for h in (wp.get("holes") or []))
        carpet_source = "wall_interior" if carpet > 0 else "none"

    # built-up = gross footprint = area inside the outer wall outline(s)
    built_up = sum(polygon_area(wp.get("outer") or []) for wp in walls_poly)
    if built_up <= 0:                       # fallback: envelope box
        built_up = float(meta.get("plan_width_ft", 0) or 0) * \
                   float(meta.get("plan_depth_ft", 0) or 0)

    # built-up can't be less than carpet; if geometry is odd, clamp up
    built_up = max(built_up, carpet)
    loading_factor = float(loading_factor) if loading_factor else 1.30
    super_built = built_up * loading_factor
    wall_loss = max(0.0, built_up - carpet)

    notes = []
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
    notes.append("Balconies / open-to-sky / service shafts are not separated out "
                 "automatically — adjust manually if present.")

    return {
        "carpet_area": _pair(carpet),
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
