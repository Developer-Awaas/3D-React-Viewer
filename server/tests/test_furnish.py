"""Tests for room typing + auto-staging (pure). Each label and each room type is
pinned individually before either is wired into the parser."""
import furnish


# ---------- classify_room_type ----------

def test_labels_from_real_indian_plans():
    cases = {
        "Bed Room 10' x 8'2\"": "bedroom",
        "Master Bedroom": "bedroom",
        "Kitchen 7'6\" x 8'2\"": "kitchen",
        "C. Bath 4' x 5'": "bathroom",
        "Toilet": "bathroom",
        "Drawing Room 10' x 8'": "living",
        "Dining Room": "dining",
        "Parking 10' x 11'9\"": "parking",
        "Pooja": "pooja",
        "O.T.S": None,            # punctuated OTS won't match "ots" literal
        "OTS": "balcony",
        "Balcony": "balcony",
        "Study": "study",
        "Staircase": "stairs",
    }
    for text, expected in cases.items():
        assert furnish.classify_room_type(text) == expected, text


def test_unknown_and_empty_return_none():
    assert furnish.classify_room_type("Plot Area") is None
    assert furnish.classify_room_type("") is None
    assert furnish.classify_room_type(None) is None


def test_bathroom_beats_store_for_washroom():
    # 'washroom' contains 'wash' (store kw) but bathroom must win (listed first)
    assert furnish.classify_room_type("Washroom") == "bathroom"


# ---------- stage_room ----------

def test_bedroom_gets_a_bed_inside_the_box():
    items = furnish.stage_room("bedroom", 0, 0, 10, 12)
    assert len(items) == 1 and items[0]["type"] == "bed"
    b = items[0]
    assert b["x"] >= 0 and b["y"] >= 0
    assert b["x"] + b["w"] <= 10 and b["y"] + b["d"] <= 12   # fully inside
    assert b["staged"] is True


def test_bathroom_gets_commode_and_basin_when_wide():
    items = furnish.stage_room("bathroom", 0, 0, 6, 8)
    types = {i["type"] for i in items}
    assert "commode" in types and "basin" in types


def test_kitchen_counter_and_living_sofa_and_dining_table():
    assert furnish.stage_room("kitchen", 0, 0, 8, 8)[0]["type"] == "counter"
    assert furnish.stage_room("living", 0, 0, 12, 10)[0]["type"] == "sofa"
    assert furnish.stage_room("dining", 0, 0, 10, 10)[0]["type"] == "table"


def test_non_stageable_types_stay_empty():
    for t in ("parking", "balcony", "stairs", "lobby", "store", "pooja"):
        assert furnish.stage_room(t, 0, 0, 12, 12) == []


def test_tiny_room_is_not_furnished():
    assert furnish.stage_room("bedroom", 0, 0, 3, 3) == []


def test_all_staged_items_stay_inside_a_small_room():
    items = furnish.stage_room("bathroom", 0, 0, 4, 4)
    for i in items:
        assert i["x"] >= 0 and i["y"] >= 0
        assert i["x"] + i["w"] <= 4 and i["y"] + i["d"] <= 4


# ---------- plausible_area (mis-label guard) ----------

def test_plausible_area_rejects_giant_bathroom():
    assert furnish.plausible_area("bathroom", 40) is True
    assert furnish.plausible_area("bathroom", 454) is False   # merged region
    assert furnish.plausible_area("bedroom", 128) is True
    assert furnish.plausible_area("bedroom", 454) is False
    assert furnish.plausible_area("unknown", 9999) is True    # no band -> allow
