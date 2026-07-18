# CubiCasa integration — architecture review (2026-07-14)

How the CubiCasa floor-plan model is wired into the Drishti backend, why it is
an in-process module and not a microservice, and what protects the API from a
misbehaving model. Written as the answer to the four-part integration review.

## 1. Architecture: internal module, not Celery/Redis

CubiCasa lives behind ONE module boundary: `server/perception.py`. `main.py`
never touches tensors — it calls three plain functions (`load_model`,
`detect`, `detections`) and gets Python lists back.

Decision: keep it **in-process** (FastAPI + threadpool). Reasons:

- The PRIMARY path for v1 is the vector CAD parser (`pdf_vector.py`) — pure
  CPU, sub-second. CubiCasa is the fallback for photos/scans (beta).
- Deploy target is a single Docker container (Render/Railway). A Celery/Redis
  queue adds a broker, a worker fleet, result storage and new failure modes,
  and buys nothing at launch traffic.
- The model is loaded ONCE at startup (FastAPI `lifespan`), so per-request
  cost is inference only.
- The seam is already clean: if a GPU box is ever needed, lift
  `perception.py` behind its own tiny FastAPI on the GPU host and have
  `_scene_from_upload` call it over HTTP. The `/scene` contract does not
  change. Move to a queue only when jobs regularly exceed ~60 s or retry /
  fan-out semantics are needed.

## 2. Endpoints (already production-shaped)

- `POST /perceive` — image/PDF -> what the model saw (room/icon lists +
  base64 overlay previews). Debug/demo endpoint.
- `POST /scene` — image/PDF -> canonical `scene.json`. Router: vector CAD
  PDF -> exact layer/geometry parser; everything else -> CubiCasa raster path.
- `POST /scene.glb` — same, but returns a ready 3D model (binary glTF).
- `GET /health` — liveness + `model_loaded` flag.

No endpoint blocks the event loop: every heavy call goes through
`_run_heavy()` = threadpool + concurrency slot + timeout + OOM translation.

## 3. Data contract (model output -> frontend JSON)

Raw CubiCasa output (44-channel tensor) is flattened in `perception.py`
(argmax -> room/icon masks), vectorized (`walls.py` -> wall segments,
`openings.py` -> door/window boxes), then normalized by `scene_builder.py` /
`pdf_vector.py` into ONE schema both paths share:

```
meta:      units (ft), plan_width_ft/plan_depth_ft, wall_height_ft,
           scale {source, pt_per_ft}, wing {count, index, bbox_ft}, warnings[]
walls:     axis-aligned boxes (raster path)
walls_poly:exact polygons with holes (vector path)
openings:  {id, type: door|window, footprint [x0,y0,x1,y1] ft,
            z [bottom,top] ft, snapped: bool, swing_area?, tag?}
columns:   {id, x, y, w, d} ft
```

Feet, origin bottom-left, z-up. The React viewer consumes this directly
(`src/api/scene.ts`).

## 4. Error handling (hardened 2026-07-14)

| Failure | Where caught | Client sees |
|---|---|---|
| wrong file type | `_looks_supported` | 415 |
| empty file | `_read_upload_bytes` | 400 |
| > 25 MB | `_read_upload_bytes` | 413 |
| junk bytes with image name | PIL `verify()` up front | 422 |
| unreadable PDF | `_pdf_first_page_png` | 422 |
| unusable CAD PDF | `pdf_vector.parse` ValueError | 422 |
| slow/hung inference | `_run_heavy` timeout (`INFER_TIMEOUT_S`, default 120 s) | 504 |
| GPU out of memory | `_run_heavy` -> `torch.cuda.empty_cache()` | 503 |
| parallel uploads | semaphore (`MAX_CONCURRENT_INFER`, default 1) queues them | (just slower) |
| anything else | endpoint catch-all | 500 with reason |

Also fixed: `/scene.glb` used one fixed temp filename — concurrent users
could download each other's building. Now a unique temp file per request,
deleted after the response is sent.

Ops notes: on timeout the worker thread finishes in the background (Python
threads cannot be killed) — the client is released and the slot frees when
the thread ends. Tune `INFER_TIMEOUT_S`, `MAX_CONCURRENT_INFER`,
`MAX_SIDE_GPU`/`MAX_SIDE_CPU` (inference downscale) via env.

## Test coverage

`tests/test_api.py`: type/empty/oversize validation, garbage-image 422,
timeout 504, OOM 503, unique-GLB regression, vector/raster routing.
Run: `pytest` in `server/` (77 tests).
