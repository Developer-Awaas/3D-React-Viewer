"""Tests for the rate limiter — each behaviour pinned with an injectable clock."""
import rate_limit as rl


def _clock(start=0.0):
    t = {"v": start}
    def now():
        return t["v"]
    def advance(s):
        t["v"] += s
    return now, advance


def test_bucket_allows_up_to_capacity_then_blocks():
    now, _ = _clock()
    b = rl.TokenBucket(3, now=now)
    assert [b.allow() for _ in range(4)] == [True, True, True, False]


def test_bucket_refills_over_time():
    now, advance = _clock()
    b = rl.TokenBucket(60, now=now)          # 1 token/second
    for _ in range(60):
        b.allow()
    assert b.allow() is False
    advance(2.0)                              # 2 seconds -> ~2 tokens back
    assert b.allow() is True
    assert b.allow() is True
    assert b.allow() is False


def test_limiter_is_per_client():
    now, _ = _clock()
    lim = rl.Limiter(per_min=1, now=now)
    assert lim.allow("a") is True
    assert lim.allow("a") is False            # a exhausted
    assert lim.allow("b") is True             # b unaffected


def test_limiter_disabled_with_zero():
    lim = rl.Limiter(per_min=0)
    assert all(lim.allow("x") for _ in range(100))


def test_heavy_path_matcher():
    assert rl.is_heavy("/scene")
    assert rl.is_heavy("/scene.glb")
    assert rl.is_heavy("/visualize/render")
    assert rl.is_heavy("/area-statement.xlsx")
    assert not rl.is_heavy("/health")
    assert not rl.is_heavy("/")


def test_registry_bounded():
    now, _ = _clock()
    lim = rl.Limiter(per_min=5, max_clients=3, now=now)
    for k in ("a", "b", "c", "d"):
        lim.allow(k)
    assert len(lim._buckets) <= 3
