"""G2 OCR activation: room-label assignment is now ADDITIVE — live text is
authoritative, OCR fills only the rooms live text missed (not all-or-nothing).
The pure assignment helper is tested here (no tesseract needed)."""
import pdf_vector as P


def _rooms():
    # two rooms in two different free-space components (_lab 1 and 2)
    return [{"id": "r0", "_lab": 1, "x": 10.0, "y": 10.0},
            {"id": "r1", "_lab": 2, "x": 30.0, "y": 10.0}]


def test_assign_nearest_token_in_same_component():
    rooms = _rooms()
    tokens = [(11.0, 11.0, 1, "bedroom"), (31.0, 11.0, 2, "kitchen")]
    gained = P._assign_room_labels(rooms, tokens)
    assert gained == 2
    assert rooms[0]["type"] == "bedroom"
    assert rooms[1]["type"] == "kitchen"


def test_token_in_other_component_is_ignored():
    rooms = _rooms()
    # a kitchen token sits in component 2 but geometrically near room r0 (comp 1)
    tokens = [(10.5, 10.5, 2, "kitchen")]
    P._assign_room_labels(rooms, tokens)
    assert rooms[0].get("type") is None       # wrong component -> not stolen
    assert rooms[1]["type"] == "kitchen"


def test_ocr_fills_only_untyped_and_never_overwrites_live():
    rooms = _rooms()
    rooms[0]["type"] = "bedroom"              # r0 already typed by LIVE text
    ocr_tokens = [(10.0, 10.0, 1, "kitchen"),  # would-be overwrite of r0
                  (30.0, 10.0, 2, "bathroom")] # fills untyped r1
    gained = P._assign_room_labels(rooms, ocr_tokens, only_untyped=True)
    assert gained == 1                        # only r1 newly typed
    assert rooms[0]["type"] == "bedroom"      # live label preserved
    assert rooms[1]["type"] == "bathroom"


def test_no_tokens_types_nothing():
    rooms = _rooms()
    assert P._assign_room_labels(rooms, []) == 0
    assert all(r.get("type") is None for r in rooms)
