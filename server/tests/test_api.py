"""Endpoint tests. The heavy model is stubbed out via monkeypatch, so these
verify the API contract (status codes, validation, JSON shape) only."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    import perception
    import main
    monkeypatch.setattr(perception, "load_model", lambda: None)  # skip real load
    with TestClient(main.app) as c:
        yield c


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_perceive_rejects_empty_file(client):
    r = client.post("/perceive", files={"image": ("x.png", b"", "image/png")})
    assert r.status_code == 400


def test_perceive_rejects_non_image(client):
    r = client.post("/perceive", files={"image": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 415


def test_perceive_success_shape(client, monkeypatch):
    import perception
    fake = {
        "device": "cpu", "width": 10, "height": 10,
        "rooms_found": ["Wall", "Bed Room"], "icons_found": ["Door"],
        "rooms_overlay_png_base64": "AA", "icons_overlay_png_base64": "BB",
    }
    monkeypatch.setattr(perception, "detect", lambda raw: fake)
    r = client.post("/perceive", files={"image": ("p.png", b"\x89PNG data", "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["rooms_found"] == ["Wall", "Bed Room"]
    assert body["icons_found"] == ["Door"]
