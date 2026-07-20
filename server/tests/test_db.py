"""Tests for the Supabase parse logger. Only the PURE parts are tested here
(row building + env gating); the network insert is fire-and-forget and mocked
elsewhere. No Supabase project needed to run these."""
import db


SCENE = {
    "meta": {
        "source": "vector_pdf_geometry",
        "plan_width_ft": 20.0,
        "plan_depth_ft": 45.0,
        "scale": {"source": "assumed_width", "pt_per_ft": 16.74},
        "wing": {"count": 1, "index": 0},
        "warnings": ["one", "two"],
    },
    "openings": [
        {"type": "door"}, {"type": "door"}, {"type": "window"},
    ],
    "rooms": [{"id": "r0"}, {"id": "r1"}],
}


def test_row_extracts_headline_metrics():
    row = db.build_parse_row(SCENE, filename="plan.pdf", width_ft=20, duration_ms=812)
    assert row["source"] == "vector_pdf_geometry"
    assert row["plan_width_ft"] == 20.0
    assert row["plan_depth_ft"] == 45.0
    assert row["doors"] == 2
    assert row["windows"] == 1
    assert row["rooms"] == 2
    assert row["scale_source"] == "assumed_width"
    assert row["ppf"] == 16.74
    assert row["wing_count"] == 1
    assert row["ok"] is True
    assert row["filename"] == "plan.pdf"
    assert row["duration_ms"] == 812
    assert row["scene"] == SCENE


def test_scene_hash_is_deterministic_and_dedupes():
    a = db.build_parse_row(SCENE)["scene_hash"]
    b = db.build_parse_row(dict(SCENE))["scene_hash"]  # equal content
    assert a == b and a is not None


def test_failed_parse_row_has_no_scene():
    row = db.build_parse_row(None, filename="bad.pdf", ok=False, error="422: nope")
    assert row["ok"] is False
    assert row["error"] == "422: nope"
    assert row["scene"] is None
    assert row["scene_hash"] is None
    assert row["doors"] == 0 and row["rooms"] == 0


def test_disabled_without_env(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    assert db.enabled() is False
    # log_parse must be a safe no-op when disabled (no event loop needed)
    db.log_parse(SCENE, filename="x.pdf")  # must not raise


def test_enabled_with_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://demo.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "service-key")
    assert db.enabled() is True
