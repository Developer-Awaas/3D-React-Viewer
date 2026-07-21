"""Tests for the corpus evaluation harness (pure scoring parts). The runner
itself needs real plans (gitignored/confidential), so only the pure helpers are
tested here."""
import batch_eval as be


def test_health_flags_clean_plan():
    m = {"width_ft": 40, "depth_ft": 45, "rooms": 5, "doors": 8}
    assert be.health_flags(m) == []


def test_health_flags_catches_tiny_envelope():
    m = {"width_ft": 8, "depth_ft": 6, "rooms": 0, "doors": 0}
    flags = be.health_flags(m)
    assert "envelope_tiny" in flags
    assert "no_rooms" in flags
    assert "no_doors" in flags


def test_health_flags_catches_huge_envelope():
    assert "envelope_huge" in be.health_flags({"width_ft": 900, "depth_ft": 40,
                                               "rooms": 3, "doors": 3})


def test_door_score_ratio_and_pass():
    assert be.door_score(10, 12) == (0.83, True)     # 0.83 >= 0.8 -> pass
    assert be.door_score(12, 12) == (1.0, True)
    assert be.door_score(6, 12) == (0.5, False)      # 0.5 < 0.8 -> fail


def test_door_score_no_expected():
    assert be.door_score(5, "TBC") == (None, None)
    assert be.door_score(5, None) == (None, None)
    assert be.door_score(5, 0) == (None, None)


def test_parse_metrics_shape():
    scene = {
        "meta": {"plan_width_ft": 20.0, "plan_depth_ft": 45.0,
                 "scale": {"source": "assumed_width"}, "wing": {"count": 1},
                 "source": "vector_pdf_geometry"},
        "openings": [{"type": "door"}, {"type": "door"}, {"type": "window"}],
        "rooms": [{"id": "r0", "type": "bedroom"}, {"id": "r1"}],
        "furniture": [{"type": "bed"}],
    }
    m = be.parse_metrics(scene)
    assert m["doors"] == 2 and m["windows"] == 1
    assert m["rooms"] == 2 and m["typed_rooms"] == 1
    assert m["furniture"] == 1 and m["wings"] == 1
