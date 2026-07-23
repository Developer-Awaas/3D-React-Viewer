"""Per-client rate limiting for the heavy endpoints — simple in-memory token
bucket, no extra dependency. Protects a public deploy from one client hammering
the parser/GPU. Pure core (injectable clock) so it's unit-tested.

RATE_LIMIT_PER_MIN (default 30) requests per client per minute across the heavy
paths; RATE_LIMIT=0 disables (dev default-friendly: localhost is exempt).
"""
import os
import time


class TokenBucket:
    """capacity tokens, refilled at capacity/60 per second. allow() spends one."""

    def __init__(self, capacity, now=time.monotonic):
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.rate = float(capacity) / 60.0
        self._now = now
        self._last = now()

    def allow(self):
        t = self._now()
        self.tokens = min(self.capacity, self.tokens + (t - self._last) * self.rate)
        self._last = t
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class Limiter:
    """One bucket per client key, capped registry (drops oldest on overflow)."""

    def __init__(self, per_min=None, max_clients=10000, now=time.monotonic):
        self.per_min = int(per_min if per_min is not None
                           else os.getenv("RATE_LIMIT_PER_MIN", "30"))
        self._now = now
        self._max = max_clients
        self._buckets = {}

    def allow(self, key):
        if self.per_min <= 0:                     # disabled
            return True
        b = self._buckets.get(key)
        if b is None:
            if len(self._buckets) >= self._max:   # bounded memory
                self._buckets.pop(next(iter(self._buckets)))
            b = self._buckets[key] = TokenBucket(self.per_min, self._now)
        return b.allow()


HEAVY_PREFIXES = ("/scene", "/perceive", "/visualize", "/area-statement",
                  "/recompute")   # public + accepts an arbitrary JSON body
EXEMPT_CLIENTS = {"127.0.0.1", "::1", "testclient"}   # local dev + tests


def is_heavy(path):
    return any(path.startswith(p) for p in HEAVY_PREFIXES)


def trust_proxy():
    """TRUST_PROXY=1 -> we are behind a reverse proxy / Cloudflare Tunnel and
    the proxy's forwarded-IP headers are trustworthy. MUST be set in prod:
    behind cloudflared every request reaches uvicorn from 127.0.0.1, which is
    in EXEMPT_CLIENTS — without this flag rate limiting silently never fires."""
    return os.getenv("TRUST_PROXY", "0").lower() in ("1", "true", "yes")


def client_key(request):
    """The real per-visitor key for rate limiting (and /review locality checks).

    Direct deploys: the socket peer IP. With TRUST_PROXY=1: prefer
    CF-Connecting-IP (set by Cloudflare itself — a visitor cannot forge it
    through the tunnel), then the first hop of X-Forwarded-For. Falls back to
    the socket IP when no forwarded header is present, so local dev calls
    keep their localhost exemption even with the flag on."""
    direct = request.client.host if request.client else "unknown"
    if trust_proxy():
        h = request.headers
        fwd = (h.get("cf-connecting-ip")
               or (h.get("x-forwarded-for") or "").split(",")[0].strip())
        if fwd:
            return fwd
    return direct
