"""Visualize (SDXL+ControlNet) wiring tests. These run WITHOUT a GPU: they pin
that the router is mounted, health reports honestly, and the render endpoint
degrades to a clean 503 on a CPU host (never a 500 or a hang). The actual GPU
render is exercised on the user's machine, not in CI."""
import io

from fastapi.testclient import TestClient
from PIL import Image

import main

client = TestClient(main.app)


def _png(size=(8, 8)):
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 200, 200)).save(buf, "PNG")
    return buf.getvalue()


def test_visualize_health_mounted():
    r = client.get("/visualize/health")
    assert r.status_code == 200
    body = r.json()
    assert "backend" in body and "cuda" in body
    assert "models" in body and "models_ready" in body


def test_required_models_match_the_loaders():
    """Download source-of-truth must list the exact IDs _load_sdxl() loads, so
    fetch_models.py and the runtime can never drift."""
    import visualize
    req = {m["name"]: m["id"] for m in visualize.required_models()}
    # SDXL base + both ControlNets the render path can load
    assert "stable-diffusion-xl" in req["sdxl"]
    assert req["controlnet_canny"] == visualize._CONTROLNETS["canny"][1]
    assert req["controlnet_depth"] == visualize._CONTROLNETS["depth"][1]


def test_models_status_shape():
    import visualize
    st = visualize.models_status()
    assert isinstance(st, list) and st
    for m in st:
        assert set(m) >= {"name", "id", "cached"}


def test_render_without_gpu_returns_clean_503():
    r = client.post("/visualize/render",
                    files={"image": ("view.png", _png(), "image/png")})
    # no CUDA in CI -> a friendly 503 telling you to use a GPU or the fal backend
    assert r.status_code == 503
    assert "GPU" in r.text or "fal" in r.text


def test_render_rejects_empty_image():
    r = client.post("/visualize/render",
                    files={"image": ("view.png", b"", "image/png")})
    assert r.status_code == 400
