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


def test_scene_returns_openings(client, monkeypatch):
    import perception
    fake = ([[10, 50, 90, 50]],
            [{"type": "door", "x0": 40, "y0": 44, "x1": 55, "y1": 56}],
            100, 100)
    monkeypatch.setattr(perception, "detections", lambda raw: fake)
    r = client.post("/scene?width_ft=10", files={"image": ("p.png", b"\x89PNG data", "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert len(body["walls"]) == 1
    assert len(body["openings"]) == 1
    o = body["openings"][0]
    assert o["type"] == "door" and o["wall"] == "w0" and o["z"][0] == 0


def test_scene_routes_vector_pdf(client, monkeypatch):
    import pdf_vector
    marker = {"meta": {"source": "vector_pdf_layers"}, "walls": [],
              "walls_poly": [{"id": "wp0", "outer": [[0, 0], [1, 0], [1, 1]], "holes": []}],
              "openings": []}
    monkeypatch.setattr(pdf_vector, "is_vector_plan", lambda raw: True)
    monkeypatch.setattr(pdf_vector, "parse", lambda raw, w: marker)
    r = client.post("/scene", files={"image": ("p.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert r.status_code == 200
    assert r.json()["meta"]["source"] == "vector_pdf_layers"


def test_scene_flat_pdf_falls_back_to_raster(client, monkeypatch):
    import pdf_vector, perception, main
    monkeypatch.setattr(pdf_vector, "is_vector_plan", lambda raw: False)
    monkeypatch.setattr(main, "_pdf_first_page_png", lambda raw: b"fake png")
    fake = ([[10, 50, 90, 50]], [], 100, 100)
    monkeypatch.setattr(perception, "detections", lambda raw: fake)
    r = client.post("/scene", files={"image": ("p.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert r.status_code == 200
    assert r.json()["meta"]["source"] == "cubicasa detection"
