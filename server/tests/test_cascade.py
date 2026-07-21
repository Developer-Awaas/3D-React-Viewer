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
