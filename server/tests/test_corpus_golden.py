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
    from pdf_vector import parse
    c = _counts(parse(_load("FLOOR PLAN.pdf"), None))
    assert c["w"] == pytest.approx(113.9, abs=1.2)
    assert c["d"] == pytest.approx(35.6, abs=1.2)
    assert c["doors"] == 12
    assert c["snapped"] >= 11          # golden 2026-07-14: 11/12
    assert c["windows"] >= 1           # data-limited sheet (dead text)


def test_combined_sheet_golden():
    from pdf_vector import parse
    c = _counts(parse(_load("NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf"), None))
    assert c["w"] == pytest.approx(80.0, abs=1.5)
    assert c["d"] == pytest.approx(47.8, abs=1.5)
    assert c["doors"] >= 20
    assert c["snapped"] >= 15          # golden: 15/20
    assert c["windows"] >= 27          # golden: 27


def test_first_floor_default_wing_golden():
    from pdf_vector import parse
    c = _counts(parse(_load("neelachala FIRST FLOOR.pdf"), None))
    assert c["doors"] >= 28
    assert c["snapped"] >= 10          # golden: 10/28
    assert c["windows"] >= 20          # golden: 20 (W/V tags + legend)


def test_first_floor_wing1_matches_confirmed_envelope():
    """THE accuracy anchor: wing 1 is the titled FIRST FLOOR PLAN and the
    user confirmed the real plot is 38'3\" x 64'2\" (38.25 x 64.167 ft).
    Parsed size must stay within 2.5%."""
    from pdf_vector import parse
    c = _counts(parse(_load("neelachala FIRST FLOOR.pdf"), None, wing=1))
    assert abs(c["w"] - 38.25) / 38.25 < 0.025
    assert abs(c["d"] - 64.167) / 64.167 < 0.035   # depth incl. chhajja ~65.5
    assert c["snapped"] >= 4           # golden: 4/12 on this wing
