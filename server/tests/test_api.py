"""Endpoint tests. The heavy model is stubbed out via monkeypatch, so these
verify the API contract (status codes, validation, JSON shape) only."""
import io

import pytest
from fastapi.testclient import TestClient


def _tiny_png():
    """A real, decodable 4x4 PNG (uploads are now verified before inference)."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


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
    r = client.post("/perceive", files={"image": ("p.png", _tiny_png(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["rooms_found"] == ["Wall", "Bed Room"]


def test_scene_returns_openings(client, monkeypatch):
    import perception
    fake = ([[10, 50, 90, 50]],
            [{"type": "door", "x0": 40, "y0": 44, "x1": 55, "y1": 56}],
            100, 100)
    monkeypatch.setattr(perception, "detections", lambda raw: fake)
    r = client.post("/scene?width_ft=10", files={"image": ("p.png", _tiny_png(), "image/png")})
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
    monkeypatch.setattr(pdf_vector, "parse",
                        lambda raw, w, wing="largest": marker)
    r = client.post("/scene", files={"image": ("p.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert r.status_code == 200
    assert r.json()["meta"]["source"] == "vector_pdf_layers"


def test_vector_only_deploy_photo_gets_beta_503(client, monkeypatch):
    """Slim deploys ship without torch: photo uploads must get the friendly
    beta message, and the API must keep serving (v1 scope lock)."""
    import main
    monkeypatch.setattr(main, "perception", None)
    r = client.post("/scene", files={"image": ("p.png", _tiny_png(), "image/png")})
    assert r.status_code == 503
    assert "beta" in r.text.lower()
    r = client.post("/perceive", files={"image": ("p.png", _tiny_png(), "image/png")})
    assert r.status_code == 503
    assert client.get("/health").status_code == 200


def test_upload_too_large_returns_413(client, monkeypatch):
    import main
    monkeypatch.setattr(main, "MAX_UPLOAD_MB", 0)   # any non-empty file is over
    r = client.post("/scene", files={"image": ("p.png", _tiny_png(), "image/png")})
    assert r.status_code == 413


def test_upload_rejects_garbage_image_bytes(client):
    """Valid extension, junk content -> 422 up front (was a 500 mid-inference)."""
    r = client.post("/scene", files={"image": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 422


def test_inference_timeout_returns_504(client, monkeypatch):
    import time
    import perception
    monkeypatch.setenv("INFER_TIMEOUT_S", "0.2")
    monkeypatch.setattr(perception, "detections", lambda raw: time.sleep(2))
    r = client.post("/scene", files={"image": ("p.png", _tiny_png(), "image/png")})
    assert r.status_code == 504
    assert "timed out" in r.text


def test_gpu_oom_returns_503(client, monkeypatch):
    import perception

    def boom(raw):
        raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")
    monkeypatch.setattr(perception, "detections", boom)
    r = client.post("/scene", files={"image": ("p.png", _tiny_png(), "image/png")})
    assert r.status_code == 503
    assert "memory" in r.text


def test_scene_glb_uses_unique_temp_file(client, monkeypatch):
    """Regression: a fixed temp filename let concurrent users download each
    other's building. Two calls must write two different paths."""
    import main, pdf_vector, scene_to_glb
    marker = {"meta": {"source": "vector_pdf_layers", "wall_height_ft": 9.8},
              "walls": [], "openings": [],
              "walls_poly": [{"id": "wp0", "outer": [[0, 0], [10, 0], [10, 1], [0, 1]],
                              "holes": []}]}
    monkeypatch.setattr(pdf_vector, "is_vector_plan", lambda raw: True)
    monkeypatch.setattr(pdf_vector, "parse",
                        lambda raw, w, wing="largest": marker)
    paths = []
    real_build = scene_to_glb.build_glb
    monkeypatch.setattr(scene_to_glb, "build_glb",
                        lambda s, out: (paths.append(out), real_build(s, out))[1])
    for _ in range(2):
        r = client.post("/scene.glb",
                        files={"image": ("p.pdf", b"%PDF-1.4 fake", "application/pdf")})
        assert r.status_code == 200
    assert len(paths) == 2 and paths[0] != paths[1]


def test_scene_flat_pdf_falls_back_to_raster(client, monkeypatch):
    import pdf_vector, perception, main
    monkeypatch.setattr(pdf_vector, "is_vector_plan", lambda raw: False)
    monkeypatch.setattr(main, "_pdf_first_page_png", lambda raw: b"fake png")
    fake = ([[10, 50, 90, 50]], [], 100, 100)
    monkeypatch.setattr(perception, "detections", lambda raw: fake)
    r = client.post("/scene", files={"image": ("p.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert r.status_code == 200
    assert r.json()["meta"]["source"] == "cubicasa detection"
