"""Optional Supabase logging of every parse — builds a data corpus for future
ML and lets us see what plans fail in production.

Design rules:
- OFF until SUPABASE_URL + SUPABASE_KEY env vars are set, so local/dev and the
  slim deploy run unchanged with zero config.
- NEVER blocks or breaks a request: the insert is fire-and-forget and every
  error is swallowed. A logging outage must not cost a single parse.
- build_parse_row() is a PURE function (no I/O) so it is fully unit-tested.
"""
import asyncio
import hashlib
import json
import logging
import os

log = logging.getLogger("drishti.db")


def build_parse_row(scene, *, filename=None, width_ft=None,
                    duration_ms=None, ok=True, error=None):
    """Flatten a scene dict into one DB row (metrics + full scene JSON).

    Pure: same inputs -> same output, no network. `scene` may be None (a failed
    parse) — then only filename/ok/error/timing are populated. `scene_hash` is a
    deterministic fingerprint of the result, so identical re-uploads dedupe.
    """
    meta = (scene or {}).get("meta", {}) or {}
    ops = (scene or {}).get("openings", []) or []
    rooms = (scene or {}).get("rooms", []) or []
    scale = meta.get("scale", {}) or {}
    wing = meta.get("wing", {}) or {}

    scene_hash = None
    if scene is not None:
        blob = json.dumps(scene, sort_keys=True, default=str).encode()
        scene_hash = hashlib.sha256(blob).hexdigest()

    return {
        "filename": filename,
        "scene_hash": scene_hash,
        "ok": ok,
        "error": error,
        "width_ft_override": width_ft,
        "source": meta.get("source"),
        "plan_width_ft": meta.get("plan_width_ft"),
        "plan_depth_ft": meta.get("plan_depth_ft"),
        "doors": sum(1 for o in ops if o.get("type") == "door"),
        "windows": sum(1 for o in ops if o.get("type") == "window"),
        "rooms": len(rooms),
        "scale_source": scale.get("source"),
        "ppf": scale.get("pt_per_ft"),
        "wing_count": wing.get("count"),
        "warnings": meta.get("warnings"),
        "scene": scene,
        "duration_ms": duration_ms,
    }


def enabled():
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"))


_TRUE = {"1", "true", "yes", "on"}


def store_uploads_enabled():
    """Also archive the UPLOADED PLAN FILE (the ML training input) to Supabase
    Storage. Off by default; needs STORE_UPLOADS=1 + a 'plans' bucket."""
    return enabled() and os.environ.get("STORE_UPLOADS", "").lower() in _TRUE


def upload_path(scene_hash, filename):
    """Deterministic storage path: hash-keyed so identical re-uploads overwrite
    instead of piling up. Pure."""
    ext = (os.path.splitext(filename or "")[1] or ".bin").lower()[:8]
    return f"{scene_hash or 'nohash'}{ext}"


async def _store_file(path, data):
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    bucket = os.environ.get("SUPABASE_BUCKET", "plans")
    if not (url and key and data):
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"{url.rstrip('/')}/storage/v1/object/{bucket}/{path}",
                content=data,
                headers={"apikey": key, "Authorization": f"Bearer {key}",
                         "Content-Type": "application/octet-stream",
                         "x-upsert": "true"},
            )
            if r.status_code >= 300:
                log.warning("supabase file store failed: %s %s",
                            r.status_code, r.text[:200])
    except Exception as e:
        log.warning("supabase file store error: %s", type(e).__name__)


async def _insert(row):
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not (url and key):
        return
    table = os.environ.get("SUPABASE_TABLE", "parses")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{url.rstrip('/')}/rest/v1/{table}",
                content=json.dumps(row, default=str),
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
            )
            if r.status_code >= 300:
                log.warning("supabase log failed: %s %s", r.status_code, r.text[:200])
    except Exception as e:                   # network/dns/timeout — never propagate
        log.warning("supabase log error: %s", type(e).__name__)


def log_parse(scene, *, filename=None, width_ft=None,
              duration_ms=None, ok=True, error=None, upload_bytes=None):
    """Fire-and-forget: schedule the insert (and optionally the uploaded plan
    file — the ML training input) without awaiting. Safe from any async
    handler; returns immediately. No-op when disabled."""
    if not enabled():
        return
    try:
        row = build_parse_row(scene, filename=filename, width_ft=width_ft,
                              duration_ms=duration_ms, ok=ok, error=error)
        if upload_bytes and store_uploads_enabled():
            path = upload_path(row.get("scene_hash"), filename)
            row["file_path"] = path
            asyncio.create_task(_store_file(path, upload_bytes))
        asyncio.create_task(_insert(row))
    except Exception as e:
        log.warning("supabase schedule error: %s", type(e).__name__)
