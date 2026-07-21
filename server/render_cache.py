"""Disk cache for photoreal renders. SDXL with a fixed seed is deterministic, so
identical inputs -> identical image. We key each render on a hash of EVERYTHING
that feeds the pipeline (control image + prompt + params + seed); a repeat hits
the cache and returns instantly, spending zero GPU.

Pure, side-effect-light, and unit-tested. Disabled with RENDER_CACHE=0; cache
dir is RENDER_CACHE_DIR (default ./.render_cache). Misses are harmless — they
just render normally.
"""
import hashlib
import os

_FALSE = {"0", "false", "no", "off", ""}


def enabled():
    return os.getenv("RENDER_CACHE", "1").strip().lower() not in _FALSE


def _dir():
    return os.getenv("RENDER_CACHE_DIR",
                     os.path.join(os.path.dirname(__file__), ".render_cache"))


def make_key(control, prompt, negative, steps, guidance, cn_scale, seed, ctype):
    """Deterministic cache key from the exact pipeline inputs. `control` is the
    conditioning image bytes (depth map or screenshot); the rest are the render
    params. Any change to any input yields a different key."""
    h = hashlib.sha256()
    h.update(control or b"")
    meta = f"|{prompt}|{negative}|{steps}|{guidance}|{cn_scale}|{seed}|{ctype}"
    h.update(meta.encode("utf-8"))
    return h.hexdigest()


def get(key):
    """Cached PNG bytes for this key, or None (miss / disabled / unreadable)."""
    if not enabled():
        return None
    try:
        with open(os.path.join(_dir(), key + ".png"), "rb") as f:
            return f.read()
    except OSError:
        return None


def put(key, data):
    """Store PNG bytes under this key. Best-effort: never raises. Writes to a
    temp file then atomically renames, so a crash can't leave a half image."""
    if not enabled() or not data:
        return
    d = _dir()
    try:
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, key + ".tmp")
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, os.path.join(d, key + ".png"))
    except OSError:
        pass
