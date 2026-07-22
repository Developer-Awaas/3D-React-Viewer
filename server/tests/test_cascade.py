"""Integration test for the vector-first / ML-fallback cascade. Proves the key
'never worse' guarantee: a HEALTHY vector reading is returned as-is and the ML
model is never even invoked (so it can't degrade a good result)."""
import os

from fastapi.testclient import TestClient

import main

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "plan_roomdim_342.pdf")


def test_healthy_vector_result_never_runs_ml(monkeypatch):
    if not os.path.exists(FIXTURE):
        return

    class _Boom:
        def detections(self, *a, **k):
            raise AssertionError("ML reader must NOT run on a healthy vector plan")

    monkeypatch.setattr(main, "perception", _Boom())   # would blow up if called
    with open(FIXTURE, "rb") as f:
        r = TestClient(main.app).post("/scene",
                                      files={"image": ("342.pdf", f.read(), "application/pdf")})
    assert r.status_code == 200
    assert r.json()["meta"]["reader"] == "vector"      # kept the vector reading


def test_reader_field_present():
    if not os.path.exists(FIXTURE):
        return
    with open(FIXTURE, "rb") as f:
        r = TestClient(main.app).post("/scene",
                                      files={"image": ("342.pdf", f.read(), "application/pdf")})
    assert r.status_code == 200
    assert r.json()["meta"].get("reader") in ("vector", "ml_fallback")


def test_geometry_retry_rescues_unnamed_layer_walls():
    """343-class sheets: real walls on an unnamed layer ('6'), the named wall
    layer holds decoys -> layers mode yields a tiny envelope. The cascade's
    geometry retry must rescue it (38 ft envelope, rooms found)."""
    fx = os.path.join(os.path.dirname(__file__), "fixtures",
                      "plan_unnamed_layers_343.pdf")
    if not os.path.exists(fx):
        return
    with open(fx, "rb") as f:
        r = TestClient(main.app).post("/scene",
                                      files={"image": ("343.pdf", f.read(),
                                                       "application/pdf")})
    assert r.status_code == 200
    j = r.json()
    assert j["meta"]["reader"] == "vector_geometry_retry"
    assert j["meta"]["plan_width_ft"] > 30          # real envelope, not the decoy
    assert len(j["rooms"]) >= 2
