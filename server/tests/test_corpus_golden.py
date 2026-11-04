"""Corpus GOLDEN tests - the full-corpus accuracy check as enforced code.

Every real plan in plans/ is parsed and pinned against golden numbers from
the 2026-07-14 accuracy sprint. Sizes are exact (small tolerance); door/
window counts are FLOORS (>=) so future improvements pass but regressions
fail. FIRST FLOOR wing 1 is additionally checked against the USER-CONFIRMED
real-world plot envelope (38'3" x 64'2") - the one true accuracy anchor.

plans/ holds confidential drawings (gitignored). This is the project's main
safety gate, so a missing corpus FAILS loudly instead of skipping - a skip
reads as a pass and lets the gate silently not run. Point DRISHTI_PLANS_DIR
at the folder holding the corpus to run these for real.
"""
import pytest

from conftest import require_corpus_file


def _load(name):
    path = require_corpus_file(name)
    with open(path, "rb") as f:
        return f.read()


def _counts(scene):
    ops = scene.get("openings", [])
    doors = [o for o in ops if o["type"] == "door"]
    return {
        "doors": len(doors),
        "snapped": sum(1 for o in doors if o.get("snapped")),
        "windows": sum(1 for o in ops if o["type"] == "window"),
        "w": scene["meta"]["plan_width_ft"],
        "d": scene["meta"]["plan_depth_ft"],
    }


def test_floor_plan_golden():
    # RE-BASELINED 2026-08-11: 113.9 x 35.6 -> 95.2 x 29.8. The old figure was
    # the parser marking its own homework (scale assumed from a 12-inch
    # column); the sheet's OWN printed room dimensions disproved it six times
    # independently, with the door gap and the printed stilt area agreeing.
    # Full evidence + the superseded number: plans/ground_truth.json ->
    # "FLOOR PLAN.pdf" -> envelope_rebaseline. Per PLAN-READING-RULES §0.1 a
    # golden moves ONLY on the drawing's own printed data, never to make new
    # code pass.
    from pdf_vector import parse
    c = _counts(parse(_load("FLOOR PLAN.pdf"), None))
    assert c["w"] == pytest.approx(95.2, abs=1.2)
    assert c["d"] == pytest.approx(29.8, abs=1.2)
    # 12 -> 16 on 21 Aug 2026 (Rahul), per §0.1: NOT a re-baseline to make code
    # pass. The sheet draws four openings with no leaf at all — KITCHEN,
    # BALCONY, LOBBY and FLAT-2's balcony — so the symbol path is blind at each
    # and the geometric gap finder was switched off sheet-wide by one door
    # layer existing anywhere. Per-location gating admits them; all four were
    # verified against the drawn faces either side and all 16 doors score
    # SOUND. Two of the four were not known to be there.
    assert c["doors"] == 16
    assert c["snapped"] >= 11          # golden 2026-07-14: 11/12
    assert c["windows"] >= 1           # data-limited sheet (dead text)


def test_combined_sheet_golden():
    """RE-BASELINED 2026-08-25 per §0.1 (Rahul): width 80.0 -> 36.6 ft.

    This sheet draws TWO VIEWS — FIRST FLOOR left, TYPICAL FLOOR (2nd/3rd/4th)
    right — separated by a vertical gutter. Parsed as one building it measured
    80.0 x 47.8 ft, which is two ~40 ft plans side by side: every room appeared
    TWICE at dx ~43.5 ft, and the counts were doubles, not measurements. The
    old numbers were never wrong about the pixels; they were counting the same
    building twice.

    The split is the empty-band rule's opposite operation: a group is divided
    when its interior holds a band with ZERO ink across the full perpendicular
    extent (`_empty_bands`). Evidence + superseded values:
    plans/ground_truth.json -> two_views_SPLIT_2026_08_25."""
    from pdf_vector import parse
    c = _counts(parse(_load("NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf"), None))
    # RE-DERIVED AGAIN 2026-08-25, and this time it is the SCALE, not the
    # split: the sheet's own printed room dimensions imply 7.19 pt/ft where the
    # column box guessed 8.80, so every measurement grows by 8.80/7.19 = 1.224.
    # Accepted on the INDEPENDENT dimension-anchor instrument (56% -> 69%),
    # never on R-2, which a scale fitted to printed dims cannot judge.
    assert c["w"] == pytest.approx(43.9, abs=1.5)     # 36.6 x 1.224
    assert c["d"] == pytest.approx(58.9, abs=1.5)     # 48.2 x 1.224
    # snapped lowered 15 -> 10: door-strip VALIDATION (23 Jul 2026) demotes
    # oversize/fat strips (>5.5 ft wide or >1.6 ft thick = merged walls, not
    # doors) to unsnapped, so the count now reflects only PLAUSIBLE door cuts.
    # RE-DERIVED 2026-08-31 (Rahul): 18 -> 8. TEN of this sheet's eighteen doors
    # were UNSNAPPED - tags we read but could not place against a wall gap - and
    # an unsnapped door is no longer counted as a door. They are still emitted,
    # flagged `door_unverified`, so nothing is lost from the report; they are
    # just no longer asserted to be somewhere.
    assert c["doors"] >= 8             # golden: 8 placed + 10 unverified
    assert c["snapped"] >= 3           # golden: 5/18
    assert c["windows"] >= 12          # golden: 14


def test_first_floor_default_wing_golden():
    """RE-BASELINED 2026-08-22 per §0.1 (Rahul): depth 64.167 -> 177.347 ft.

    The old assertion was not a verified observation, it was a misunderstanding
    written down twice. It pinned ONE of the sheet's two blocks and this test's
    own docstring called the other "the tall door-schedule/legend block". That
    was measured false on 21 Aug: the discarded block is the LARGER one —
    38.2 x 96.9 ft, 2812.1 sqft of footprint, 10 rooms, 31 doors, R-2 96.9 over
    8 rooms. Rahul ruled 15 Aug that this is ONE BUILDING IN TWO BLOCKS, five
    flats on one floor, joined at first floor by the terrace slab, and the band
    rule now keeps both.

    The old figure also called 38'-3" x 64'-2" "the user-confirmed plot". It is
    the BOTTOM BLOCK's own printed dimension, and reading it as a plot is what
    made `footprint <= plot` compare the building to itself. The real plot is
    11,500 sqft (Rahul). Evidence + superseded values: plans/ground_truth.json
    -> "neelachala FIRST FLOOR.pdf" -> envelope_rebaseline_2026_08_22.

    WIDTH IS UNCHANGED at 38.25 — both blocks are the same width, which is why
    38'-3" is printed twice on the sheet.
    """
    from pdf_vector import parse
    c = _counts(parse(_load("neelachala FIRST FLOOR.pdf"), None))
    assert abs(c["w"] - 38.25) / 38.25 < 0.025
    assert abs(c["d"] - 177.347) / 177.347 < 0.035   # both blocks + the 13.1 ft band
    assert c["doors"] >= 12            # golden: 54 (23 on the bottom block alone)
    assert c["snapped"] >= 6           # golden: 28
    assert c["windows"] >= 15          # golden: 47


def test_first_floor_has_exactly_one_wing():
    """RE-BASELINED 2026-08-22 per §0.1 (Rahul). Was
    `test_first_floor_wing1_matches_confirmed_envelope`, which pinned "wing 1"
    to 38.25 x 64.167 ft as "the user-confirmed plot". Both halves of that were
    wrong: 38'-3" x 64'-2" is the BOTTOM BLOCK's printed dimension, not a plot,
    and there is no wing 1 to select — the two blocks are one building, so the
    sheet now yields ONE wing and the `wing=` argument has nothing to choose.

    What is worth pinning is that: the sheet must not go back to offering a
    sub-block, because picking one silently discarded 63% of the footprint."""
    from pdf_vector import parse
    raw = _load("neelachala FIRST FLOOR.pdf")
    a = parse(raw, None)
    assert a["meta"]["wing"]["count"] == 1
    b = _counts(parse(raw, None, wing=1))      # no-op: there is only wing 0
    assert (b["w"], b["d"]) == (_counts(a)["w"], _counts(a)["d"])
    assert b["snapped"] >= 4           # golden: 28


# --- COLUMNS (12 Aug 2026) ---------------------------------------------------
# Pinned because they moved UNSEEN: the 11 Aug scale correction (23.80 -> 28.47
# pt/ft) left behind a fixed 0.6 POINT match tolerance in _column_rects, and
# FLOOR PLAN went 26 columns -> 0 with every test and every batch_eval column
# still green. The wall overlay found it. The band is now derived from ppf
# (C-4: 8-48 in on the SHORT side), and these numbers guard it.
def test_floor_plan_columns():
    from pdf_vector import parse
    scene = parse(_load("FLOOR PLAN.pdf"), None)
    cols = scene["columns"]
    assert len(cols) == 26                       # was 0 while the bug was live
    short = min(min(c["w"], c["d"]) for c in cols)
    long_ = max(max(c["w"], c["d"]) for c in cols)
    assert 8 / 12 * 0.9 <= short and long_ <= 4.0    # C-4 band, in feet


def test_first_floor_has_no_column_layer():
    """0 here is CORRECT, not the bug: this sheet carries no column layer at
    all, so there is nothing to find. Pinned so the two cases stay distinct."""
    from pdf_vector import parse
    import fitz
    import pdf_vector as pv
    raw = _load("neelachala FIRST FLOOR.pdf")
    page = fitz.open(stream=raw, filetype="pdf")[0]
    assert pv._column_rects(pv._page_drawings(page)) == []
    assert parse(raw, None)["columns"] == []


def test_columns_survive_a_scale_change():
    """The regression in one line: the same drawing at a different scale must
    still yield columns. A tolerance in page units cannot do this."""
    from pdf_vector import parse
    a = parse(_load("BRICK WORK LAYOUT.pdf"), None)
    b = parse(_load("BRICK WORK LAYOUT.pdf"), 30.0)      # forces a rescale path
    assert len(a["columns"]) > 0 and len(b["columns"]) > 0


def test_ghatikia_columns():
    """40 columns, held by a 10% margin under C-4's 8 in floor: this sheet's
    columns measure 7.0-8.4 in on the short side, so a hard floor takes all 40
    to zero. Pinned because that margin is the only thing keeping them."""
    from pdf_vector import parse
    cols = parse(_load("NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf"), None)["columns"]
    # RE-BASELINED 2026-08-25: 40 -> 20. The 40 counted this sheet's TWO VIEWS,
    # i.e. the same 20 columns twice. The C-4 margin this test exists to guard
    # is unchanged — it is still the only thing keeping them.
    assert len(cols) == 20
    assert all(min(c["w"], c["d"]) >= 0.9 * 8 / 12 for c in cols)


# --- ROUTE FINGERPRINT (22 Aug 2026) -----------------------------------------
# Nine absolute FLOORS switch which code path runs. Six are already visible in
# output (meta.source, meta.scale.source, the OCR/anchor warnings, meta.wing,
# built_up_branch.fired); THREE left no trace at all, so two similar drawings
# could be parsed by different code with nothing recording which route each
# took. Purely additive — the parser reads none of it back.
def test_route_fingerprint_has_a_constant_shape():
    """A run diff needs 'this key CHANGED' and 'this key is MISSING' to be
    different findings, so every branch reports even when never reached."""
    from pdf_vector import parse
    m = parse(_load("FLOOR PLAN.pdf"), None)["meta"]
    assert set(m["route"]) == {"stair_ladder_dedupe", "door_median",
                               "door_symbol_paths", "seal", "scale_refit",
                               "wing_pick"}


def test_route_fingerprint_separates_the_corpus():
    """It earns its place immediately: FLOOR PLAN is the ONLY sheet where the
    arc branch fires (12 arc paths), which is why door swing can be read there
    and nowhere else; and BRICK WORK hands the symbol grouper NOTHING at all,
    which is why 15 of its 17 doors are leafless."""
    from pdf_vector import parse
    fp = parse(_load("FLOOR PLAN.pdf"), None)["meta"]["route"]
    bw = parse(_load("BRICK WORK LAYOUT.pdf"), None)["meta"]["route"]
    assert fp["door_symbol_paths"]["arc"] > 0
    assert bw["door_symbol_paths"] == {"arc": 0, "line": 0, "leaf_segs_kept": 0}
    # the ladder de-dupe has ONE caller, on the geometry branch, so a
    # layers-route sheet must say so rather than silently omitting it
    assert fp["stair_ladder_dedupe"] == "not reached"
    ff = parse(_load("neelachala FIRST FLOOR.pdf"), None)["meta"]["route"]
    assert ff["stair_ladder_dedupe"].startswith("ran ")


# --- B: doors_placed_sound EXTENDED TO POSITION (25 Aug 2026) ----------------
def test_door_position_is_pinned_and_states_its_route():
    """The width rule scores a cut against its drawn leaf, and a cut can match
    that width perfectly while sitting on the wrong wall. `hinge_on_cut` is the
    check that catches it, and it is a real one: 6 of 12 before the 20 Aug fix
    put the hinge on the drawn symbol's wall line, 12 of 12 after.

    ROUTE (the 24 Aug standing rule): every position check needs the drawn ARC,
    which only the door-symbol path produces. FLOOR PLAN is the ONLY sheet in
    the corpus that reaches it — 12 arc paths against 0 on the other three — so
    this test pins ONE ROUTE and says so. The other sheets report their doors
    as `not_scorable`, never as passes: an absent branch is not a green result.
    """
    from pdf_vector import parse
    m = parse(_load("FLOOR PLAN.pdf"), None)["meta"]
    pos = m["doors_placed_sound"]["position"]
    assert m["route"]["door_symbol_paths"]["arc"] == 12
    assert pos["scored"] == 12                  # the 12 leafed doors
    assert pos["not_scorable"] == 4             # the 4 leafless gap openings
    assert pos["hinge_on_cut"] == 12            # RATCHET: was 6 before 20 Aug
    # leaf_inside_plan is REPORTED, NOT RATCHETED. Its one miss is o6, the door
    # onto flat-1's UTILITY, and a utility projects beyond the wall ring by
    # design (§10.1 / CE-5) — so a leaf outside the footprint is correct there.
    # Pinning 12/12 would demand a wrong answer.
    assert pos["leaf_inside_plan"] == 11 and pos["outside_plan"] == ["o6"]


def test_sheets_without_arcs_report_not_scorable_never_pass():
    from pdf_vector import parse
    for name in ("neelachala FIRST FLOOR.pdf", "BRICK WORK LAYOUT.pdf"):
        m = parse(_load(name), None)["meta"]
        assert m["route"]["door_symbol_paths"]["arc"] == 0
        pos = m["doors_placed_sound"]["position"]
        assert pos["scored"] == 0 and pos["not_scorable"] > 0


def test_a_near_tied_wing_pick_is_announced_as_an_ask():
    """A 0.3% ppf change was measured swapping which of GHATIKIA's two views
    gets built — every number on the sheet then describes a DIFFERENT DRAWING
    and nothing in any output said so (28 Aug 2026). A magnitude error can be
    measured; an identity swap cannot, so the pick is now announced with its
    runner-up, and a one-unit margin is raised as a §0.2 ASK rather than
    resolved by an invented tie-break."""
    from pdf_vector import parse
    scene = parse(_load("NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf"), None)
    w = scene["meta"]["route"]["wing_pick"]
    assert w["of"] == 2 and w["runner_up"] is not None
    assert w["margin"] == {"rooms": 1, "doors": 1}
    assert w["near_tie"] is True            # one room or one door would flip it
    # INDEX IS NOT IDENTITY. At ppf 7.1485 and 7.150 this sheet builds its
    # RIGHT view (origin x 53.6) while `chosen` stays 0 and `of` stays 2, and
    # it FLICKERS — left either side. Footprint moves under 1% across a swap
    # that built the opposite half, so no numeric instrument can see it; the
    # bbox ORIGIN is what says which half was built.
    assert w["origin_ft"][0] < 25.0                      # the LEFT view
    assert w["runner_up"]["origin_ft"][0] > 25.0         # the RIGHT one
    import json
    json.dumps(w)                                        # must serialise
    assert any("§0.2 ASK: wing" in x for x in scene["meta"]["warnings"])


def test_a_single_wing_sheet_says_the_pick_was_not_reached():
    from pdf_vector import parse
    for name in ("FLOOR PLAN.pdf", "neelachala FIRST FLOOR.pdf"):
        m = parse(_load(name), None)["meta"]
        assert m["route"]["wing_pick"] == "not reached (single wing)"


def test_threshold_margins_are_emitted_for_the_scorecard():
    """ONE DEFINITION, computed in the parser (31 Aug 2026). The scorecard
    consumes `meta.threshold_margins` rather than re-deriving it — two
    derivations of one number is the wing_at / wing_pick trap, where index and
    identity disagreed about which half of a sheet had been built.

    It must reproduce the known cliff: GHATIKIA's `geom_max` at 11.04 in sits
    on that sheet's 11 in external-wall peak."""
    import json
    from pdf_vector import parse
    m = parse(_load("NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf"), None)["meta"]
    t = m["threshold_margins"]
    json.dumps(t)                                  # must serialise
    assert 11 in t["gap_peaks_in"]
    assert "geom_max" in t["latent_cliffs"]
    rows = {r["threshold"]: r for r in t["thresholds"]}
    assert rows["geom_max"]["nearest_peak_in"] == 11
    # SIZING thresholds sit on their own peak by definition and are NOT cliffs
    assert rows["wall_median"]["kind"] == "sizing"
    assert rows["wall_median"]["on_a_cluster"] is True
    assert rows["wall_median"]["latent_cliff"] is False
    assert "wall_median" not in t["latent_cliffs"]


def test_brick_work_w3_floor_is_reported_as_a_latent_cliff():
    """BRICK WORK's median wall IS 3.0 in and W-3's floor is exactly 3.0 in,
    so its dominant wall class sits on the admission floor — 38 pairs within
    5%, on the one sheet no instrument can judge. Live at FIVE sites."""
    from pdf_vector import parse
    t = parse(_load("BRICK WORK LAYOUT.pdf"), None)["meta"]["threshold_margins"]
    assert t["wall_in"] == 3.0 and 3 in t["gap_peaks_in"]
    assert "W3_min" in t["latent_cliffs"]


# --- §13 PLAN REGIONS (31 Aug 2026) -----------------------------------------
def test_regions_are_enumerated_and_keyed_by_origin():
    """The splitter ENUMERATES regions; it never picks one and discards the
    rest. And a region is keyed by its ORIGIN, never its index: an index
    reorders the moment enumeration changes, and every pinned number then
    silently refers to a different building — the same lesson as
    `wing_pick.origin_ft`."""
    from pdf_vector import parse
    m = parse(_load("NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf"), None)["meta"]
    rs = m["regions"]
    assert len(rs) == 2                       # both, not just the built one
    assert [r["key"] for r in rs] == ["r@0,0", "r@53,0"]
    assert [r["built"] for r in rs] == [True, False]
    # the TITLE signal is reported, never acted on
    assert "TYPICAL" in " ".join(rs[1]["title_text_near"])
    assert any("PLAN REGIONS" in w for w in m["warnings"])


def test_every_scene_says_which_parse_pass_it_is():
    """`parse` re-enters itself for the scale refit and the two passes DISAGREE
    about nearly everything on GHATIKIA — including which half of the sheet is
    built (origin x 43.5 on pass 1, -0.2 on pass 2). A value without its pass is
    ambiguous, so every scene stamps one."""
    from pdf_vector import parse
    raw = _load("NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf")
    shipped = parse(raw, None)["meta"]["parse_pass"]
    assert shipped == {"index": 2, "ppf": 7.189, "from_scale_refit": True}
    first = parse(raw, None, _refit=False)["meta"]["parse_pass"]
    assert first["index"] == 1 and first["from_scale_refit"] is False
    assert first["ppf"] != shipped["ppf"]
    # single-pass sheets say so too, rather than leaving it to be inferred
    fp = parse(_load("FLOOR PLAN.pdf"), None)["meta"]["parse_pass"]
    assert fp["index"] == 1 and fp["from_scale_refit"] is False
