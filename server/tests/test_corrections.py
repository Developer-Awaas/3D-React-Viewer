

# --- §0.2 CONTRADICTS: the user answers "is there a wall here?" (16 Aug 2026)
# The paisa-vasool path: the tool spots a drafting error and ASKS, instead of
# silently getting it wrong. Nothing is auto-answered, and the answer travels
# with the scene so /recompute never asks twice.
def _scene_with_flag():
    return {"meta": {"open_side_regions": [
                {"open_side": "south", "area_as_drawn_sqft": 189.9,
                 "area_if_closed_sqft": 182.7, "bbox_ft": [27.1, -0.2, 41.2, 18.3],
                 "question": "is there a wall here?"}]},
            "rooms": [{"id": "r0", "type": "stairs", "x": 29.9, "y": 10.4,
                       "area_sqft": 23.6}]}


def test_confirming_the_wall_counts_the_space():
    import corrections
    s, info = corrections.apply_corrections(_scene_with_flag(),
                                            {"confirm_open_sides": [0]})
    added = [r for r in s["rooms"] if r.get("confirmed_open_side")]
    assert len(added) == 1
    assert added[0]["area_sqft"] == 182.7
    # it holds the lift/stair, so it is COMMON area, not carpet
    assert added[0]["type"] == "lobby"
    assert s["meta"]["open_side_regions"][0]["answer"] == "confirmed"
    assert any("confirmed the missing south edge" in a for a in info["applied"])


def test_rejecting_leaves_it_uncounted_and_stops_asking():
    import corrections
    s, _i = corrections.apply_corrections(_scene_with_flag(),
                                          {"reject_open_sides": [0]})
    assert not [r for r in s["rooms"] if r.get("confirmed_open_side")]
    assert s["meta"]["open_side_regions"][0]["answer"] == "rejected"


def test_the_answer_survives_a_second_recompute():
    """The space must not be added twice when /recompute fires again."""
    import corrections
    s, _i = corrections.apply_corrections(_scene_with_flag(),
                                          {"confirm_open_sides": [0]})
    s, _i2 = corrections.apply_corrections(s, {})
    assert len([r for r in s["rooms"] if r.get("confirmed_open_side")]) == 1


def test_a_bad_index_is_a_clean_error():
    import corrections
    import pytest as _p
    with _p.raises(ValueError):
        corrections.apply_corrections(_scene_with_flag(), {"confirm_open_sides": [7]})
