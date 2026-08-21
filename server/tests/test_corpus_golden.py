"""Corpus GOLDEN tests - the full-corpus accuracy check as enforced code.

Every real plan in plans/ is parsed and pinned against golden numbers from
the 2026-07-14 accuracy sprint. Sizes are exact (small tolerance); door/
window counts are FLOORS (>=) so future improvements pass but regressions
fail. FIRST FLOOR wing 1 is additionally checked against the USER-CONFIRMED
real-world plot envelope (38'3" x 64'2") - the one true accuracy anchor.

plans/ holds confidential drawings (gitignored), so every test skips cleanly
where the file is absent (e.g. CI without the corpus).
"""
import os

import pytest

PLANS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "plans")


def _load(name):
    path = os.path.join(PLANS, name)
    if not os.path.exists(path):
        pytest.skip(f"corpus file not present: {name}")
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
    from pdf_vector import parse
    c = _counts(parse(_load("NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf"), None))
    assert c["w"] == pytest.approx(80.0, abs=1.5)
    assert c["d"] == pytest.approx(47.8, abs=1.5)
    assert c["doors"] >= 20
    # snapped lowered 15 -> 10: door-strip VALIDATION (23 Jul 2026) demotes
    # oversize/fat strips (>5.5 ft wide or >1.6 ft thick = merged walls, not
    # doors) to unsnapped, so the count now reflects only PLAUSIBLE door cuts.
    assert c["snapped"] >= 9           # golden: 10/20 plausible
    assert c["windows"] >= 27          # golden: 27


def test_first_floor_default_wing_golden():
    """The DEFAULT wing pick must now be the REAL floor plan (wing 1), not the
    tall door-schedule/legend block it used to wrongly pick (which inflated
    depth to 96.9 ft). Fixed 23 Jul 2026: wings are scored by enclosed ROOMS
    first, so the actual plan wins even without a door layer."""
    from pdf_vector import parse
    c = _counts(parse(_load("neelachala FIRST FLOOR.pdf"), None))
    # default now matches the user-confirmed plot (38'3" x 64'2"), like wing=1
    assert abs(c["w"] - 38.25) / 38.25 < 0.025
    assert abs(c["d"] - 64.167) / 64.167 < 0.035
    assert c["doors"] >= 12            # real plan doors (was 28 from the schedule)
    assert c["snapped"] >= 6           # golden: 9/16
    assert c["windows"] >= 15          # golden: 19


def test_first_floor_wing1_matches_confirmed_envelope():
    """THE accuracy anchor: wing 1 is the titled FIRST FLOOR PLAN and the
    user confirmed the real plot is 38'3\" x 64'2\" (38.25 x 64.167 ft).
    Parsed size must stay within 2.5%."""
    from pdf_vector import parse
    c = _counts(parse(_load("neelachala FIRST FLOOR.pdf"), None, wing=1))
    assert abs(c["w"] - 38.25) / 38.25 < 0.025
    assert abs(c["d"] - 64.167) / 64.167 < 0.035   # depth incl. chhajja ~65.5
    assert c["snapped"] >= 4           # golden: 4/12 on this wing


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
    assert len(cols) == 40
    assert all(min(c["w"], c["d"]) >= 0.9 * 8 / 12 for c in cols)
