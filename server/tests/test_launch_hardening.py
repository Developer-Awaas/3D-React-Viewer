"""Pre-launch hardening (22 Jul 2026 audit): /review auth + XSS escape,
real-IP rate limiting behind Cloudflare Tunnel, shared GPU gate, upload caps
on the render endpoints, license gates, tf2 door/window typing."""
import asyncio
import importlib
import io

import numpy as np
import pytest
from fastapi.testclient import TestClient

import main
import rate_limit
import tf2_floorplan
import visualize


@pytest.fixture()
def client():
    return TestClient(main.app)


# --------------------------------------------------------------------------- #
# /review auth
# --------------------------------------------------------------------------- #
def test_review_localhost_allowed_when_no_token(client, monkeypatch):
    monkeypatch.delenv("REVIEW_TOKEN", raising=False)
    r = client.get("/review")            # testclient is an EXEMPT (local) client
    assert r.status_code == 200          # falls into the "not configured" page


def test_review_public_client_denied_when_no_token(client, monkeypatch):
    monkeypatch.delenv("REVIEW_TOKEN", raising=False)
    monkeypatch.setenv("TRUST_PROXY", "1")
    r = client.get("/review", headers={"cf-connecting-ip": "203.0.113.9"})
    assert r.status_code == 401


def test_review_requires_token_when_set(client, monkeypatch):
    monkeypatch.setenv("REVIEW_TOKEN", "s3cret")
    assert client.get("/review").status_code == 401
    assert client.get("/review", params={"token": "wrong"}).status_code == 401


def test_review_accepts_token_query_and_bearer(client, monkeypatch):
    monkeypatch.setenv("REVIEW_TOKEN", "s3cret")
    assert client.get("/review", params={"token": "s3cret"}).status_code == 200
    assert client.get("/review",
                      headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_review_escapes_user_fields(client, monkeypatch):
    """filename/error come from uploads -> must be HTML-escaped (stored XSS)."""
    monkeypatch.setenv("REVIEW_TOKEN", "s3cret")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "k")
    rows = [{"created_at": "2026-07-22T10:00:00", "ok": False,
             "filename": "<script>alert(1)</script>.pdf",
             "error": "<img src=x onerror=alert(2)>",
             "plan_width_ft": 0, "plan_depth_ft": 0, "doors": 0, "rooms": 0,
             "scale_source": "", "duration_ms": 5}]

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return rows

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return _Resp()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    html_out = client.get("/review", params={"token": "s3cret"}).text
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;" in html_out
    assert "<img src=x" not in html_out


# --------------------------------------------------------------------------- #
# real client IP behind the tunnel
# --------------------------------------------------------------------------- #
class _Req:
    def __init__(self, host, headers=None):
        class _C:
            pass
        self.client = _C()
        self.client.host = host
        self.headers = headers or {}


def test_client_key_direct_without_proxy(monkeypatch):
    monkeypatch.delenv("TRUST_PROXY", raising=False)
    # forwarded headers are IGNORED unless TRUST_PROXY=1 (spoof protection)
    req = _Req("9.9.9.9", {"x-forwarded-for": "1.2.3.4"})
    assert rate_limit.client_key(req) == "9.9.9.9"


def test_client_key_prefers_cf_header_with_proxy(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY", "1")
    req = _Req("127.0.0.1", {"cf-connecting-ip": "198.51.100.7",
                             "x-forwarded-for": "10.0.0.1"})
    assert rate_limit.client_key(req) == "198.51.100.7"


def test_client_key_falls_back_to_xff_first_hop(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY", "1")
    req = _Req("127.0.0.1", {"x-forwarded-for": "203.0.113.5, 172.16.0.1"})
    assert rate_limit.client_key(req) == "203.0.113.5"


def test_client_key_local_call_stays_local_with_proxy_on(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY", "1")
    req = _Req("127.0.0.1", {})          # no forwarded header -> direct/local
    assert rate_limit.client_key(req) == "127.0.0.1"


def test_public_ip_is_rate_limited_through_tunnel(client, monkeypatch):
    """End-to-end: with TRUST_PROXY=1 a tunnel visitor gets 429 after the
    budget — previously everyone arrived as exempt 127.0.0.1 and the limiter
    never fired at all."""
    monkeypatch.setenv("TRUST_PROXY", "1")
    monkeypatch.setattr(main, "_limiter", rate_limit.Limiter(per_min=2))
    codes = []
    for _ in range(4):                    # /scene without a file -> 422 once allowed
        r = client.post("/scene", headers={"cf-connecting-ip": "203.0.113.77"})
        codes.append(r.status_code)
    assert 429 in codes
    assert codes[0] != 429                # first requests pass


# --------------------------------------------------------------------------- #
# one GPU, one gate
# --------------------------------------------------------------------------- #
def test_parse_and_render_share_one_semaphore():
    import gpu_gate
    assert main._INFER_SLOTS is gpu_gate.GPU_SLOTS
    assert visualize._SLOTS is gpu_gate.GPU_SLOTS


# --------------------------------------------------------------------------- #
# /visualize upload caps + license gate (all run BEFORE any GPU work)
# --------------------------------------------------------------------------- #
def test_render_rejects_oversize_screenshot(client, monkeypatch):
    monkeypatch.setattr(visualize, "MAX_RENDER_UPLOAD_MB", 1)
    blob = b"x" * (2 * 1024 * 1024)
    r = client.post("/visualize/render", files={"image": ("s.png", blob, "image/png")})
    assert r.status_code == 413


def test_render_rejects_empty_screenshot(client):
    r = client.post("/visualize/render", files={"image": ("s.png", b"", "image/png")})
    assert r.status_code == 400


def test_animate_license_gate(client, monkeypatch):
    monkeypatch.setenv("DISABLE_SVD", "1")
    r = client.post("/visualize/animate", files={"image": ("s.png", b"abc", "image/png")})
    assert r.status_code == 403


# --------------------------------------------------------------------------- #
# tf2: openings now typed door (interior) / window (outer edge)
# --------------------------------------------------------------------------- #
def _boundary_mask():
    """200x200 plan: wall rectangle border 20..180, one opening ON the border
    (window) and one on an interior wall (door)."""
    m = np.zeros((200, 200), dtype=np.int32)
    W, O = tf2_floorplan.WALL_CLASS, tf2_floorplan.OPENING_CLASS
    m[20:24, 20:180] = W          # top wall
    m[176:180, 20:180] = W        # bottom wall
    m[20:180, 20:24] = W          # left wall
    m[20:180, 176:180] = W        # right wall
    m[98:102, 20:180] = W         # interior wall across the middle
    m[20:24, 90:110] = O          # opening in the TOP (external) wall
    m[98:102, 60:80] = O          # opening in the INTERIOR wall
    return m


def test_tf2_emits_both_doors_and_windows():
    segs, boxes = tf2_floorplan.masks_to_detections(_boundary_mask(), 200, 200)
    types = sorted(b["type"] for b in boxes)
    assert "door" in types, "tf2 could never emit a door before this fix"
    assert "window" in types
    assert len(segs) >= 4


def test_tf2_interior_opening_is_door():
    _, boxes = tf2_floorplan.masks_to_detections(_boundary_mask(), 200, 200)
    interior = [b for b in boxes if 90 < (b["y0"] + b["y1"]) / 2 < 110]
    assert interior and all(b["type"] == "door" for b in interior)


def test_tf2_edge_opening_is_window():
    _, boxes = tf2_floorplan.masks_to_detections(_boundary_mask(), 200, 200)
    edge = [b for b in boxes if (b["y0"] + b["y1"]) / 2 < 30]
    assert edge and all(b["type"] == "window" for b in edge)


# --------------------------------------------------------------------------- #
# capped corpus read when STORE_UPLOADS=1
# --------------------------------------------------------------------------- #
def test_store_uploads_read_is_capped(client, monkeypatch):
    monkeypatch.setenv("STORE_UPLOADS", "1")
    monkeypatch.setattr(main, "MAX_UPLOAD_MB", 1)
    blob = b"y" * (2 * 1024 * 1024)
    r = client.post("/scene", files={"image": ("big.pdf", blob, "application/pdf")})
    assert r.status_code == 413


# --------------------------------------------------------------------------- #
# E1: fast scheduler (DPM++ 2M Karras) — wiring + safety, no GPU needed
# --------------------------------------------------------------------------- #
def test_fast_scheduler_disabled_by_env(monkeypatch):
    monkeypatch.setenv("FAST_SCHEDULER", "0")
    class _Pipe:
        scheduler = object()
    p = _Pipe()
    before = p.scheduler
    assert visualize._apply_fast_scheduler(p) is False
    assert p.scheduler is before          # untouched when opted out


def test_fast_scheduler_never_breaks_on_failure(monkeypatch):
    """diffusers missing / config error -> False and pipeline unchanged (a
    scheduler problem must never take a render down)."""
    monkeypatch.delenv("FAST_SCHEDULER", raising=False)
    class _Boom:
        @property
        def scheduler(self):              # any access explodes
            raise RuntimeError("no diffusers here")
    assert visualize._apply_fast_scheduler(_Boom()) is False


def test_render_steps_default_is_22():
    """The render endpoint's default steps must follow RENDER_STEPS/22 (the
    DPM++ sweet spot), not the old hardcoded 28."""
    import inspect
    sig = inspect.signature(visualize.render_ep)
    assert sig.parameters["steps"].default.default == 22


# --------------------------------------------------------------------------- #
# E2: CPU-offload only when the pipeline doesn't fit whole on the card
# --------------------------------------------------------------------------- #
def test_offload_auto_single_controlnet_stays_on_gpu(monkeypatch):
    monkeypatch.delenv("GPU_OFFLOAD", raising=False)
    assert visualize._wants_offload(("canny",)) is False      # fits 12 GB whole


def test_offload_auto_multi_controlnet_offloads(monkeypatch):
    monkeypatch.delenv("GPU_OFFLOAD", raising=False)
    assert visualize._wants_offload(("depth", "seg")) is True  # needs headroom


def test_offload_env_overrides(monkeypatch):
    monkeypatch.setenv("GPU_OFFLOAD", "always")
    assert visualize._wants_offload(("canny",)) is True
    monkeypatch.setenv("GPU_OFFLOAD", "never")
    assert visualize._wants_offload(("depth", "seg")) is False
