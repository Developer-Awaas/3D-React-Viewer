"""Tests for the render disk cache. Each behaviour is pinned individually before
the endpoint uses it: key determinism, round-trip, miss, and the disable switch."""
import render_cache as rc

ARGS = dict(control=b"depthmap-bytes", prompt="a photorealistic bedroom",
            negative="blurry", steps=28, guidance=6.0, cn_scale=0.7,
            seed=12345, ctype="depth")


def test_key_is_deterministic():
    assert rc.make_key(**ARGS) == rc.make_key(**ARGS)


def test_key_changes_with_any_input():
    base = rc.make_key(**ARGS)
    assert rc.make_key(**{**ARGS, "seed": 999}) != base
    assert rc.make_key(**{**ARGS, "prompt": "a kitchen"}) != base
    assert rc.make_key(**{**ARGS, "control": b"different"}) != base
    assert rc.make_key(**{**ARGS, "ctype": "canny"}) != base


def test_put_then_get_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setenv("RENDER_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("RENDER_CACHE", "1")
    k = rc.make_key(**ARGS)
    assert rc.get(k) is None                 # cold
    rc.put(k, b"\x89PNG-fake-image")
    assert rc.get(k) == b"\x89PNG-fake-image" # warm


def test_miss_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("RENDER_CACHE_DIR", str(tmp_path))
    assert rc.get("deadbeef" * 8) is None


def test_disabled_never_stores_or_reads(tmp_path, monkeypatch):
    monkeypatch.setenv("RENDER_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("RENDER_CACHE", "0")
    k = rc.make_key(**ARGS)
    rc.put(k, b"data")                        # no-op when disabled
    assert rc.get(k) is None
    assert not list(tmp_path.iterdir())       # nothing written


def test_put_empty_data_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("RENDER_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("RENDER_CACHE", "1")
    rc.put(rc.make_key(**ARGS), b"")
    assert not list(tmp_path.iterdir())


def test_render_endpoint_serves_cache_hit_without_gpu(tmp_path, monkeypatch):
    """A primed cache must short-circuit the GPU: on a machine with no CUDA the
    render would 503, but a cache hit returns 200 + cached:true instead."""
    import io

    from fastapi.testclient import TestClient
    from PIL import Image

    import main
    import render_cache
    import visualize

    monkeypatch.setenv("RENDER_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("RENDER_CACHE", "1")
    buf = io.BytesIO(); Image.new("RGB", (8, 8)).save(buf, "PNG"); img = buf.getvalue()
    prompt = visualize._compose_prompt("living room", "scandinavian")
    # prime with the ENDPOINT'S current default steps (22 since the E1 fast-
    # scheduler change; was hardcoded 28 here and broke when the default moved)
    import inspect
    steps_default = inspect.signature(visualize.render_ep).parameters["steps"].default.default
    key = render_cache.make_key(img, prompt, visualize.NEG_PROMPT,
                                steps_default, 6.0, 0.7, 12345, "canny")
    render_cache.put(key, b"\x89PNG-cached")
    r = TestClient(main.app).post("/visualize/render",
                                  files={"image": ("v.png", img, "image/png")})
    assert r.status_code == 200
    assert r.json().get("cached") is True
