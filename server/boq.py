"""Rough Bill of Quantities (BOQ) + construction cost estimate from the parsed
geometry — pure, assumption-documented, unit-tested. India-first defaults.

What we can honestly derive from a plan:
  * wall footprint area = built-up − carpet (sqft of plan covered by walls)
  * wall volume = footprint × wall height
  * wall length ≈ footprint / avg wall thickness → plaster + paint area (2 faces)
  * flooring = carpet area

Quantities use standard Indian thumb rules (documented inline). Rates are a
DEFAULT table in ₹ — every rate can be overridden per project/region. This is a
budgeting estimate, not a tender document; the disclaimer says so.
"""

# thumb rules (documented so an engineer can audit/adjust)
BRICKS_PER_CUFT = 12.5          # 9"x4.5"x3" modular brick with mortar
CEMENT_BAGS_PER_CUFT_BRICK = 0.036   # ~1.26 bags/m3 of 1:6 brickwork
SAND_CUFT_PER_CUFT_BRICK = 0.26      # ~9.2 cft/m3
PLASTER_CEMENT_BAGS_PER_SQFT = 0.0115  # 12mm 1:4 both-coat avg
PLASTER_SAND_CUFT_PER_SQFT = 0.055
AVG_WALL_THICK_FT = 0.5         # 6 in average (9" external / 4.5" partitions mix)

DEFAULT_RATES_INR = {
    "brick_pc": 9.0,
    "cement_bag": 400.0,
    "sand_cuft": 65.0,
    "flooring_sqft": 120.0,      # vitrified tile incl. laying
    "paint_sqft": 28.0,          # putty + primer + 2 coats
    "labour_factor": 1.35,       # labour + wastage multiplier on material cost
}


def compute_boq(scene, wall_height_ft=None, rates=None):
    """Scene -> {quantities, costs, assumptions, disclaimer}. Pure."""
    import area_statement
    meta = scene.get("meta", {}) or {}
    h = float(wall_height_ft or meta.get("wall_height_ft") or 9.84)
    rates = {**DEFAULT_RATES_INR, **(rates or {})}

    area = area_statement.compute_area_statement(scene)
    carpet = float(area["carpet_area"]["sqft"])
    built = float(area["built_up_area"]["sqft"])
    wall_fp = max(0.0, built - carpet)              # sqft of plan under walls

    wall_vol = wall_fp * h                          # cuft of masonry
    wall_len = (wall_fp / AVG_WALL_THICK_FT) if wall_fp else 0.0
    plaster_area = 2.0 * wall_len * h               # both faces
    paint_area = plaster_area
    floor_area = carpet

    bricks = wall_vol * BRICKS_PER_CUFT
    cement = (wall_vol * CEMENT_BAGS_PER_CUFT_BRICK
              + plaster_area * PLASTER_CEMENT_BAGS_PER_SQFT)
    sand = (wall_vol * SAND_CUFT_PER_CUFT_BRICK
            + plaster_area * PLASTER_SAND_CUFT_PER_SQFT)

    material = (bricks * rates["brick_pc"] + cement * rates["cement_bag"]
                + sand * rates["sand_cuft"]
                + floor_area * rates["flooring_sqft"]
                + paint_area * rates["paint_sqft"])
    total = material * rates["labour_factor"]

    r1 = lambda v: round(float(v), 1)
    return {
        "quantities": {
            "wall_footprint_sqft": r1(wall_fp),
            "wall_volume_cuft": r1(wall_vol),
            "wall_length_ft": r1(wall_len),
            "bricks_pcs": int(round(bricks)),
            "cement_bags": r1(cement),
            "sand_cuft": r1(sand),
            "plaster_area_sqft": r1(plaster_area),
            "paint_area_sqft": r1(paint_area),
            "flooring_sqft": r1(floor_area),
        },
        "cost_inr": {
            "material": int(round(material)),
            "total_with_labour": int(round(total)),
            "rates_used": rates,
        },
        "assumptions": [
            f"wall height {h:.2f} ft; average wall thickness {AVG_WALL_THICK_FT*12:.0f} in",
            "brickwork 1:6, plaster 12mm 1:4 both faces; thumb-rule coefficients",
            "excludes RCC (footing/columns/slab), doors/windows, electrical, "
            "plumbing, sanitary — superstructure masonry finish only",
        ],
        "disclaimer": ("Budgeting estimate from parsed geometry with regional "
                       "default rates; get a licensed engineer's BOQ before "
                       "contracting."),
    }
