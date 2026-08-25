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


class TestCarpetR2Together:
    """Carpet rising while R-2 falls is a REGRESSION (24 Aug 2026, Rahul).
    From a real run: the seal split took FLOOR PLAN carpet 1191.1 -> 1328.1
    and R-2 98.0 -> 94.6 in the same change. Carpet alone reads as +137 sqft
    of recovered floor; together they say the rooms grew past their printed
    dimensions."""

    def test_the_real_case_is_caught(self):
        v = be.carpet_r2_verdict({"carpet_sqft": 1191.1, "r2_median": 98.0},
                                {"carpet_sqft": 1328.1, "r2_median": 94.6})
        assert v and v.startswith("REGRESSION")
        assert "137.0" in v and "-3.4" in v

    def test_both_rising_is_not_flagged(self):
        assert be.carpet_r2_verdict({"carpet_sqft": 1191.1, "r2_median": 98.0},
                                   {"carpet_sqft": 1328.1,
                                    "r2_median": 98.4}) is None

    def test_noise_below_tolerance_is_not_flagged(self):
        assert be.carpet_r2_verdict({"carpet_sqft": 1191.1, "r2_median": 98.0},
                                   {"carpet_sqft": 1191.4,
                                    "r2_median": 97.7}) is None

    def test_a_missing_figure_returns_none_not_a_guess(self):
        assert be.carpet_r2_verdict({"carpet_sqft": 1.0},
                                   {"carpet_sqft": 2.0}) is None
        assert be.carpet_r2_verdict(None, None) is None

    def test_the_mirror_case_is_flagged_UNVERIFIED_not_scored(self):
        """Carpet falling while R-2 rises is BOTH the sign-flipped phenomenon
        and what an honest correction looks like — the 20 Aug footprint fix
        lost 2.6 sqft of wall we had been claiming at twice its drawn
        thickness. The numbers cannot separate them, so it goes to a human
        rather than being scored either way (Rahul, 25 Aug 2026)."""
        v = be.carpet_r2_verdict({"carpet_sqft": 1328.1, "r2_median": 94.6},
                                 {"carpet_sqft": 1191.1, "r2_median": 98.0})
        assert v and v.startswith("UNVERIFIED")
        assert "human must rule" in v

    def test_the_two_verdicts_are_routable_without_reading_the_sentence(self):
        up = be.carpet_r2_verdict({"carpet_sqft": 100.0, "r2_median": 98.0},
                                  {"carpet_sqft": 200.0, "r2_median": 90.0})
        dn = be.carpet_r2_verdict({"carpet_sqft": 200.0, "r2_median": 90.0},
                                  {"carpet_sqft": 100.0, "r2_median": 98.0})
        assert up.split(":")[0] == "REGRESSION"
        assert dn.split(":")[0] == "UNVERIFIED"
