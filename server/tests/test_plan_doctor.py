"""Plan Doctor — the self-checking agent (rules core). Pure-function tests:
every check that feeds the layman explanation is pinned here."""
import os

import plan_doctor as PD


def _healthy_scene():
    return {
        "meta": {"plan_width_ft": 38.25, "plan_depth_ft": 64.167,
                 "reader": "vector",
                 "scale": {"source": "dimension_text",
                           "envelope": "overall_dimension_text"}},
        "rooms": [{"id": "r0", "type": "bedroom", "area_sqft": 140},
                  {"id": "r1", "type": "kitchen", "area_sqft": 80}],
        "openings": [{"type": "door", "along": [10.0, 13.0]},
                     {"type": "door", "along": [20.0, 22.8]},
                     {"type": "window", "along": [5.0, 9.0]}],
        "area_statement": {"efficiency_pct": 74.0, "carpet_source": "rooms"},
        "vastu": {}, "boq": {},
    }


def test_healthy_plan_grades_a():
    d = PD.diagnose(_healthy_scene())
    assert d["grade"] == "A"
    assert d["score"] == 100
    assert d["efficiency_display"] == "74.0%"
    assert "passed" in d["headline"]


def test_no_rooms_is_a_fail_with_layman_reason():
    s = _healthy_scene()
    s["rooms"] = []
    s["area_statement"] = {"efficiency_pct": 0, "carpet_source": "none"}
    d = PD.diagnose(s)
    assert d["grade"] in ("D", "F")
    assert d["efficiency_display"] == "needs_review"   # never a silent 0%
    assert "don't close" in d["headline"]              # the layman explanation
    assert "no_rooms" in d["learn_tags"]


def test_efficiency_zero_explained_not_reported():
    s = _healthy_scene()
    s["rooms"] = []
    s["area_statement"] = {"efficiency_pct": 0, "carpet_source": "none"}
    d = PD.diagnose(s)
    assert any(i["tag"] == "efficiency_zero" for i in d["issues"])


def test_wall_interior_fallback_is_warn_not_fail():
    s = _healthy_scene()
    s["rooms"] = []
    s["area_statement"] = {"efficiency_pct": 68.0, "carpet_source": "wall_interior"}
    d = PD.diagnose(s)
    assert all(i["level"] != "fail" for i in d["issues"])
    assert "no_rooms_fallback" in d["learn_tags"]


def test_column_scale_guess_warns():
    s = _healthy_scene()
    s["meta"]["scale"] = {"source": "column_box_12in"}
    d = PD.diagnose(s)
    assert "scale_column_guess" in d["learn_tags"]
    assert d["grade"] != "A"


def test_implausible_envelope_fails():
    s = _healthy_scene()
    s["meta"]["plan_width_ft"] = 4.5          # the old '343' failure mode
    d = PD.diagnose(s)
    assert "envelope_implausible" in d["learn_tags"]
    assert d["grade"] in ("D", "F")


def test_odd_door_width_flags_scale():
    s = _healthy_scene()
    s["openings"] = [{"type": "door", "along": [0.0, 8.0]},
                     {"type": "door", "along": [10.0, 18.0]},
                     {"type": "window", "along": [1.0, 4.0]}]
    d = PD.diagnose(s)
    assert "door_width_odd" in d["learn_tags"]


def test_missing_analysis_blocks_are_reported():
    s = _healthy_scene()
    del s["vastu"]
    d = PD.diagnose(s)
    assert "missing_vastu" in d["learn_tags"]


def test_efficiency_band_warnings():
    lo = _healthy_scene()
    lo["area_statement"]["efficiency_pct"] = 40.0
    assert "efficiency_low" in PD.diagnose(lo)["learn_tags"]
    hi = _healthy_scene()
    hi["area_statement"]["efficiency_pct"] = 95.0
    assert "efficiency_high" in PD.diagnose(hi)["learn_tags"]


def test_learning_log_appends_and_never_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGS_FILE", str(tmp_path / "LEARNINGS.md"))
    d = PD.diagnose(_healthy_scene())
    PD.record(d, filename="plan ✓ (unicode).pdf")
    PD.record(d, filename=None)
    text = (tmp_path / "LEARNINGS.md").read_text(encoding="utf-8")
    assert text.count("grade A") == 2
    assert "Plan Doctor" in text                     # header written once
    # unwritable path must not raise (fire-and-forget contract)
    monkeypatch.setenv("LEARNINGS_FILE", str(tmp_path / ("no" * 200) / "x.md"))
    PD.record(d)                                     # should swallow silently


def test_llm_disabled_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("LLM_DOCTOR", "1")
    assert PD.llm_enabled() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("LLM_DOCTOR", "0")
    assert PD.llm_enabled() is False
    monkeypatch.setenv("LLM_DOCTOR", "1")
    assert PD.llm_enabled() is True
