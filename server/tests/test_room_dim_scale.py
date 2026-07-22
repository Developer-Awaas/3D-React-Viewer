"""Regression test for scale-from-room-dimension-text (9'0"X12'0" labels).
Uses a real internet plan that has NO column layer and NO on-line dimensions —
before this feature it failed with 'no scale'; now it must self-scale."""
import os

import pytest

from pdf_vector import parse

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "plan_roomdim_342.pdf")


@pytest.mark.skipif(not os.path.exists(FIXTURE), reason="fixture absent")
def test_self_scales_from_room_dimension_text():
    scene = parse(open(FIXTURE, "rb").read())      # NO width_ft — must self-scale
    meta = scene["meta"]
    assert meta["scale"]["source"] == "room_dim_text"
    # a real building envelope, not a degenerate few-feet block
    assert meta["plan_width_ft"] > 12
    assert meta["plan_depth_ft"] > 12
    # scale is physical (points per foot in a sane range)
    assert 4 < meta["scale"]["pt_per_ft"] < 60
