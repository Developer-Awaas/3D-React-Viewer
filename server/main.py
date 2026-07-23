"""Drishti Perception API (Step 2).

Loads the CubiCasa model once at startup, then answers /perceive requests.
Dev: runs locally (uvicorn). Prod: same app deploys to any GPU host - only
.env and the frontend's API URL change, no code change.
"""
import asyncio
import functools
import html
import io
import math
import os
import secrets
import time
from contextlib import asynccontextmanager

import anyio.to_thread
from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, Query, Request, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.concurrency import run_in_threadpool

import area_report
import area_statement
import boq
import cad_vector
import corrections
import db
import opening_fusion
import pipeline
import plan_doctor
import plan_health

# strong refs for fire-and-forget LLM-doctor tasks (a bare create_task can be
# garbage-collected mid-flight)
_LLM_TASKS = set()
import vastu
import openings
import pdf_vector
import scene_builder
import scene_to_glb

import logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger("drishti")

# .env must load BEFORE the ML reader registry below reads TF2FP_MODEL etc.
load_dotenv()

# The photo/scan (raster) path needs torch + the CubiCasa repo. On slim
# vector-only deploys those are absent ON PURPOSE (v1 scope: CAD PDFs are the
# product; photos are beta) - the API must still boot and serve /scene.
try:
    import perception
    _PERCEPTION_ERR = None
except Exception as _e:          # torch/CubiCasa not installed
    perception = None
    _PERCEPTION_ERR = str(_e)

# Pluggable ML reader for the cascade: CubiCasa (perception) by default, or
# TF2DeepFloorplan when ML_READER=tf2 (the commercial-viable model). Both expose
# detections(image_bytes) -> (segs, boxes, w, h), so the cascade is unchanged.
# ML reader REGISTRY — every installed model, by name. The cascade can run one
# (ML_READER=cubicasa|tf2) or, with ML_READER=best (default), run ALL available
# readers on the hard cases and keep the highest-scoring scene: a bounded
# best-of ensemble that extracts value from every model without merging
# conflicting geometry. A healthy vector read still short-circuits everything.
# LICENSE GATES (flip in .env, no redeploy of code needed):
#   DISABLE_CUBICASA=1 — CubiCasa weights are CC BY-NC (non-commercial). Fine
#     for an internal demo; MUST be off in any paid/commercial product.
#   DISABLE_TF2=1      — TF2DeepFloorplan is GPL-3.0 (copyleft) — lawyer-check
#     before charging money.
def _env_on(name):
    return os.getenv(name, "0").lower() in ("1", "true", "yes")


_READERS = {}
if perception is not None and not _env_on("DISABLE_CUBICASA"):
    _READERS["cubicasa"] = perception
elif perception is not None:
    log.info("cubicasa reader disabled by DISABLE_CUBICASA (license gate)")
try:
    import tf2_floorplan
    if _env_on("DISABLE_TF2"):
        log.info("tf2 reader disabled by DISABLE_TF2 (license gate)")
    elif os.getenv("TF2FP_MODEL"):        # only usable once weights are pointed at
        _READERS["tf2"] = tf2_floorplan
except Exception as _e:
    log.warning("TF2DeepFloorplan not available: %s", _e)

_ML_READER_NAME = os.getenv("ML_READER", "best").lower()
if _ML_READER_NAME in ("tf2", "tf2deepfloorplan", "deepfloorplan"):
    _ACTIVE_READERS = {k: v for k, v in _READERS.items() if k == "tf2"}
elif _ML_READER_NAME in ("cubicasa", "perception"):
    _ACTIVE_READERS = {k: v for k, v in _READERS.items() if k == "cubicasa"}
else:                                     # 'best' -> all installed models
    _ACTIVE_READERS = dict(_READERS)
ml_reader = next(iter(_ACTIVE_READERS.values()), None)   # legacy single handle
log.info("ML readers active: %s (mode=%s)",
         list(_ACTIVE_READERS) or "none", _ML_READER_NAME)

BETA_MSG = ("This looks like a photo or scanned plan - that engine is in beta "
            "and not enabled on this server. Upload a CAD-exported PDF "
            "(vector) for full-quality 3D.")



@asynccontextmanager
async def lifespan(app):
    # warm the model once when the server boots (the slow part happens here, not per request)
    if perception is None:
        log.info("perception disabled (vector-only deploy): %s", _PERCEPTION_ERR)
    else:
        try:
            perception.load_model()
            log.info("CubiCasa model loaded and ready")
        except Exception as e:
            log.warning("model failed to load at startup: %s", e)
    yield


app = FastAPI(title="Drishti Perception API", version="0.2.0", lifespan=lifespan)


def parse_origins(value, default="http://localhost:5173"):
    """ALLOWED_ORIGINS env -> origin list: comma-separated, whitespace and
    trailing-slash tolerant (a trailing slash silently breaks CORS)."""
    out = []
    for o in (value or default).split(","):
        o = o.strip().rstrip("/")
        if o:
            out.append(o)
    return out or [default]


origins = parse_origins(os.getenv("ALLOWED_ORIGINS"))
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

# per-client rate limit on the heavy endpoints (parser/GPU) — public-deploy
# protection. Local dev + tests are exempt; RATE_LIMIT_PER_MIN=0 disables.
import rate_limit as _rl
_limiter = _rl.Limiter()


@app.middleware("http")
async def _rate_limit_mw(request, call_next):
    # NEVER rate-limit CORS preflight: an OPTIONS 429 kills the preflight, the
    # real request never fires, and the browser shows an opaque CORS error
    # (also, preflight would burn the heavy-endpoint budget 2x per call).
    if request.method == "OPTIONS":
        return await call_next(request)
    # real visitor IP: behind Cloudflare Tunnel everyone arrives as 127.0.0.1
    # (which is exempt!) — with TRUST_PROXY=1 client_key() reads the visitor's
    # IP from CF-Connecting-IP / X-Forwarded-For instead.
    client = _rl.client_key(request)
    if _rl.is_heavy(request.url.path) and client not in _rl.EXEMPT_CLIENTS:
        if not _limiter.allow(client):
            log.warning("rate limited %s on %s", client, request.url.path)
            # echo CORS headers so the browser can READ the 429 body (the
            # CORSMiddleware runs AFTER this short-circuit, so add them here)
            origin = request.headers.get("origin")
            hdrs = {}
            if origin and (origin.rstrip("/") in origins or "*" in origins):
                hdrs["Access-Control-Allow-Origin"] = origin
            return JSONResponse({"detail": "Too many requests — please slow down."},
                                status_code=429, headers=hdrs)
    return await call_next(request)

# Visualize (Beta): SDXL + ControlNet photoreal render / SVD walkthrough. Safe
# to mount on any host — torch/diffusers are imported lazily inside the calls,
# and every endpoint returns a clean 503 when no CUDA GPU is present, so a slim
# CPU deploy is unaffected. Set RENDER_BACKEND=local on your GPU box.
try:
    import visualize
    app.include_router(visualize.router)
except Exception as _ve:          # never let an optional feature block boot
    log.warning("visualize not mounted: %s: %s", type(_ve).__name__, _ve)


@app.api_route("/health", methods=["GET", "HEAD"])   # HEAD too: LB/uptime probes
def health():
    """Quick check the server is up (and whether the model is loaded)."""
    return {"ok": True,
            "model_loaded": bool(perception and perception._MODEL is not None),
            "raster_beta": perception is not None}


TEST_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Drishti - detection test</title>
<style>
 body{font-family:system-ui,Arial,sans-serif;margin:24px;background:#0f172a;color:#e2e8f0}
 h1{font-size:20px} h3{margin:6px 0;font-size:13px;color:#94a3b8}
 .row{display:flex;gap:16px;flex-wrap:wrap;margin-top:16px}
 .card{background:#1e293b;padding:10px;border-radius:10px}
 img{max-width:380px;display:block;border-radius:6px}
 .lists{margin-top:16px;font-size:15px;line-height:1.6}
 button{background:#22d3ee;color:#0f172a;border:0;padding:9px 18px;border-radius:8px;font-weight:700;cursor:pointer;margin-left:8px}
 #status{margin-top:12px;color:#94a3b8}
</style></head><body>
<h1>Drishti - floor-plan detection test</h1>
<p>Pick a floor-plan <b>image or PDF</b> (PNG/JPG/PDF). This is the same result as Colab, drawn for you.</p>
<input type="file" id="file" accept="image/*,application/pdf">
<button onclick="run()">Detect</button>
<div id="status"></div>
<div class="lists" id="lists"></div>
<div class="row" id="imgs"></div>
<script>
async function run(){
  const f=document.getElementById('file').files[0];
  if(!f){alert('Pick an image first');return;}
  const s=document.getElementById('status'); s.textContent='Running the model...';
  const fd=new FormData(); fd.append('image',f);
  const res=await fetch('/perceive',{method:'POST',body:fd});
  if(!res.ok){s.textContent='Error '+res.status+': '+await res.text();return;}
  const d=await res.json();
  s.textContent='Done  ('+d.device+',  '+d.width+' x '+d.height+')';
  document.getElementById('lists').innerHTML=
    '<b>Rooms found:</b> '+d.rooms_found.join(', ')+'<br><b>Icons found:</b> '+d.icons_found.join(', ');
  const orig=URL.createObjectURL(f);
  document.getElementById('imgs').innerHTML=
    card('Your plan',orig)+
    card('Detected rooms','data:image/png;base64,'+d.rooms_overlay_png_base64)+
    card('Detected icons (doors/windows)','data:image/png;base64,'+d.icons_overlay_png_base64);
}
function card(t,src){return '<div class="card"><h3>'+t+'</h3><img src="'+src+'"></div>';}
</script></body></html>"""


@app.get("/test", response_class=HTMLResponse)
def test_page():
    """A simple visual page to SEE the detection (plan + rooms + icons), like Colab."""
    return TEST_PAGE


def _review_authorized(request: Request):
    """Gate for the internal /review dashboard. REVIEW_TOKEN set -> require it
    (?token=... or Authorization: Bearer ...), compared timing-safely. Not
    set -> allow ONLY local/dev clients, so a public tunnel can never expose
    customer parse data by accident."""
    expected = os.getenv("REVIEW_TOKEN", "")
    if expected:
        supplied = request.query_params.get("token", "")
        if not supplied:
            auth = request.headers.get("authorization", "")
            supplied = auth[7:] if auth.lower().startswith("bearer ") else ""
        return secrets.compare_digest(supplied, expected)
    return _rl.client_key(request) in _rl.EXEMPT_CLIENTS


@app.get("/review", response_class=HTMLResponse)
async def review_dashboard(request: Request, limit: int = Query(200, gt=0, le=1000)):
    """Team review dashboard (Stage 6 of the pipeline): every logged parse,
    worst-first, with a needs-review queue. Server-side Supabase fetch — the
    service key never reaches the browser. Auth: REVIEW_TOKEN (see
    _review_authorized) — this page lists customer plan data and must never
    be public."""
    if not _review_authorized(request):
        return HTMLResponse(
            "<html><body style='font-family:system-ui;background:#0f172a;"
            "color:#e2e8f0;padding:40px'><h2>401 — review is private</h2>"
            "<p>Open /review?token=&lt;REVIEW_TOKEN&gt; (set in server/.env).</p>"
            "</body></html>", status_code=401)
    if not db.enabled():
        return ("<html><body style='font-family:system-ui;background:#0f172a;"
                "color:#e2e8f0;padding:40px'><h2>Review dashboard</h2>"
                "<p>Parse logging isn't configured yet — set SUPABASE_URL / "
                "SUPABASE_KEY (see docs/SUPABASE.md) and restart.</p></body></html>")
    import httpx
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_KEY"]
    table = os.environ.get("SUPABASE_TABLE", "parses")
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{url}/rest/v1/{table}",
                            params={"select": "created_at,filename,ok,error,source,"
                                              "plan_width_ft,plan_depth_ft,doors,"
                                              "windows,rooms,scale_source,duration_ms",
                                    "order": "created_at.desc", "limit": str(limit)},
                            headers={"apikey": key, "Authorization": f"Bearer {key}"})
            r.raise_for_status()
            rows = r.json()
    except Exception as e:
        return HTMLResponse(f"<html><body style='font-family:system-ui'>"
                            f"Supabase fetch failed: {type(e).__name__}</body></html>",
                            status_code=502)

    def needs_review(x):
        return (not x.get("ok") or (x.get("rooms") or 0) == 0
                or (x.get("doors") or 0) == 0
                or min(x.get("plan_width_ft") or 0, x.get("plan_depth_ft") or 0) < 12)

    flagged = [x for x in rows if needs_review(x)]
    def tr(x):
        bad = needs_review(x)
        env = (f"{(x.get('plan_width_ft') or 0):.0f}×{(x.get('plan_depth_ft') or 0):.0f}"
               if x.get("ok") else "—")
        # filename/error are user-controlled -> escape (stored-XSS guard)
        return (f"<tr class='{'bad' if bad else ''}'>"
                f"<td>{(x.get('created_at') or '')[:16].replace('T', ' ')}</td>"
                f"<td>{html.escape((x.get('filename') or '')[:38])}</td>"
                f"<td>{'✓' if x.get('ok') else '✗ ' + html.escape(str(x.get('error') or '')[:40])}</td>"
                f"<td>{env}</td><td>{x.get('doors') or 0}</td>"
                f"<td>{x.get('rooms') or 0}</td><td>{x.get('scale_source') or ''}</td>"
                f"<td>{x.get('duration_ms') or ''}</td></tr>")
    body = "".join(tr(x) for x in flagged) + "".join(tr(x) for x in rows if not needs_review(x))
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<title>Drishti — review</title><style>
body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:24px}}
h1{{font-size:20px}} .pill{{color:#fb923c;font-size:13px}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin-top:14px}}
th,td{{padding:6px 10px;text-align:left;border-bottom:1px solid #1e293b}}
th{{color:#94a3b8;font-weight:600}} tr.bad{{background:#7f1d1d22}}
tr.bad td:first-child{{border-left:3px solid #ef4444}}
</style></head><body>
<h1>Drishti — parse review <span class='pill'>{len(flagged)} of {len(rows)} need attention</span></h1>
<table><tr><th>when</th><th>plan</th><th>ok</th><th>envelope ft</th><th>doors</th>
<th>rooms</th><th>scale</th><th>ms</th></tr>{body}</table>
</body></html>"""


MAX_UPLOAD_MB = 25

# at most N heavy model jobs at once (default 1): extra requests QUEUE for a
# moment instead of racing each other into GPU/CPU out-of-memory. SHARED with
# visualize.py so a render and a parse can never double-book the one GPU.
import gpu_gate
_INFER_SLOTS = gpu_gate.GPU_SLOTS


def _is_gpu_oom(e):
    try:
        import torch
        if isinstance(e, torch.cuda.OutOfMemoryError):
            return True
    except ImportError:
        pass
    return isinstance(e, RuntimeError) and "out of memory" in str(e).lower()


def _free_gpu():
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


async def _run_heavy(fn, *args, what="inference"):
    """Run a heavy/model call off the event loop with (a) a concurrency slot,
    (b) a wall-clock timeout, (c) GPU-OOM translated to a clean 503. The API
    stays responsive no matter what the model does. Note: on timeout the
    worker thread keeps running to completion in the background (abandoned) -
    the CLIENT is released and the semaphore slot frees immediately."""
    timeout = float(os.getenv("INFER_TIMEOUT_S", "120"))
    try:
        async with _INFER_SLOTS:
            # abandon_on_cancel: wait_for's cancellation must actually reach
            # this await (run_in_threadpool ignores it - the 504 never fired)
            return await asyncio.wait_for(
                anyio.to_thread.run_sync(functools.partial(fn, *args),
                                         abandon_on_cancel=True),
                timeout)
    except asyncio.TimeoutError:
        raise HTTPException(504, f"{what} timed out after {timeout:.0f}s - "
                                 "try a smaller image or PDF")
    except Exception as e:
        if _is_gpu_oom(e):
            _free_gpu()
            raise HTTPException(503, "model ran out of GPU memory - try a "
                                     "smaller image or retry in a moment")
        raise


def _looks_supported(image: UploadFile):
    ct = image.content_type or ""
    name = (image.filename or "").lower()
    return (ct.startswith("image/") or ct == "application/pdf"
            or name.endswith((".pdf", ".png", ".jpg", ".jpeg", ".webp",
                              ".dxf", ".dwg")))


def _is_cad(image: UploadFile):
    """CAD drawing uploads (.dxf / .dwg) by extension."""
    name = (image.filename or "").lower()
    return name.endswith((".dxf", ".dwg"))


async def _read_capped(image: UploadFile):
    """Read an upload in chunks, rejecting oversize files EARLY (declared size
    first, then abort mid-stream) instead of buffering the whole body."""
    cap = MAX_UPLOAD_MB * 1024 * 1024
    declared = getattr(image, "size", None)
    if declared is None:
        try:
            declared = int(image.headers.get("content-length", ""))
        except (AttributeError, TypeError, ValueError):
            declared = None
    if declared is not None and declared > cap:
        raise HTTPException(413, f"file too large (> {MAX_UPLOAD_MB} MB)")
    chunks, size = [], 0
    while True:
        chunk = await image.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > cap:
            raise HTTPException(413, f"file too large (> {MAX_UPLOAD_MB} MB)")
        chunks.append(chunk)
    return b"".join(chunks)


async def _read_upload_bytes(image: UploadFile):
    """Read + validate an upload. Returns (raw_bytes, is_pdf) - no conversion."""
    if not _looks_supported(image):
        raise HTTPException(415, "upload a PNG/JPG image, a PDF, or a CAD file (.dxf/.dwg)")
    raw = await _read_capped(image)
    if not raw:
        raise HTTPException(400, "empty file")
    ct = image.content_type or ""
    name = (image.filename or "").lower()
    is_pdf = (ct == "application/pdf" or name.endswith(".pdf"))
    if not is_pdf:                    # fail fast on undecodable "images"
        try:
            from PIL import Image
            Image.open(io.BytesIO(raw)).verify()
        except Exception:
            raise HTTPException(422, "file is not a readable image")
    return raw, is_pdf


def _pdf_first_page_png(raw):
    """PDF bytes -> PNG bytes of page 1 (for the raster/CubiCasa path).
    dpi is clamped so the longest page side renders <= 4000 px (a huge sheet
    at a fixed 200 dpi could eat all the RAM). CPU-heavy: call via _run_heavy."""
    doc = None
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=raw, filetype="pdf")
        page = doc[0]
        side_pt = max(page.rect.width, page.rect.height)
        dpi = 200
        if side_pt > 0:
            dpi = max(1, min(dpi, int(4000 * 72 / side_pt)))
        return page.get_pixmap(dpi=dpi).tobytes("png")
    except Exception as e:
        raise HTTPException(422, f"could not read PDF: {e}")
    finally:
        if doc is not None:
            doc.close()


async def _read_upload(image: UploadFile):
    """Read an upload; accept images OR PDFs (PDF -> PNG of page 1). Returns image bytes."""
    raw, is_pdf = await _read_upload_bytes(image)
    if is_pdf:
        return await _run_heavy(_pdf_first_page_png, raw, what="PDF render")
    return raw


@app.post("/perceive")
async def perceive(image: UploadFile = File(...)):
    """Send a floor-plan image or PDF, get back what the model detected."""
    raw = await _read_upload(image)
    # honor the reader registry: if cubicasa is disabled by the license gate
    # (DISABLE_CUBICASA) or its weights aren't installed, return the friendly
    # beta 503 like /scene does — NOT a 500, and never bypass the gate.
    if perception is None or "cubicasa" not in _ACTIVE_READERS:
        raise HTTPException(503, BETA_MSG)
    try:
        result = await _run_heavy(perception.detect, raw, what="perception")
    except HTTPException:
        raise
    except Exception as e:
        if _is_gpu_oom(e):
            raise HTTPException(503, "model ran out of GPU memory - retry shortly")
        raise HTTPException(503, BETA_MSG)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Step B/D: upload -> scene.json. Router: vector CAD PDF -> layer parser (exact,
# incl. angled walls); anything else -> CubiCasa raster path.
# ---------------------------------------------------------------------------
async def _scene_from_upload(image: UploadFile, width_ft: float, wing: str = "largest"):
    # CAD files (.dxf native; .dwg via converter): real units, exact scale.
    # Re-drawn as a layered PDF in memory, then parsed by the SAME engine as
    # CAD-exported PDFs (walls, doors, wings, rooms all reused).
    if _is_cad(image):
        raw = await _read_capped(image)
        if not raw:
            raise HTTPException(400, "empty file")
        try:
            pdf_bytes, ppf, _info = await _run_heavy(
                cad_vector.to_layered_pdf, raw, image.filename or "",
                what="CAD conversion")
            return await _run_heavy(pdf_vector.parse, pdf_bytes, width_ft,
                                    pdf_vector.wing_arg(wing), ppf,
                                    what="CAD parse")
        except ValueError as e:
            raise HTTPException(422, f"CAD parse failed: {e}")
    raw, is_pdf = await _read_upload_bytes(image)
    if is_pdf and await run_in_threadpool(pdf_vector.is_vector_plan, raw):
        # VECTOR-FIRST / ML-FALLBACK cascade: run the fast, exact vector parser;
        # keep its result if healthy. Only when it's unhealthy (or failed) do we
        # rasterize + run the ML reader, and keep whichever scores higher. A good
        # vector reading is never replaced -> output can only get better.
        try:
            vscene = await _run_heavy(pdf_vector.parse, raw, width_ft,
                                      pdf_vector.wing_arg(wing), what="vector parse")
            vscene.setdefault("meta", {})["reader"] = "vector"
        except ValueError as e:
            vscene, vec_err = None, str(e)
        else:
            vec_err = None
        if plan_health.is_healthy(vscene):
            return vscene
        # retry 1 (cheap, no GPU): geometry-only vector parse — rescues sheets
        # whose real walls sit on unnamed layers while a named 'wall' layer
        # carries decoys. Keep whichever scene scores better.
        try:
            gscene = await _run_heavy(
                functools.partial(pdf_vector.parse, raw, width_ft,
                                  pdf_vector.wing_arg(wing), force_geometry=True),
                what="geometry retry")
            gscene.setdefault("meta", {})["reader"] = "vector_geometry_retry"
            vscene = plan_health.better_scene(vscene, gscene)
            if plan_health.is_healthy(vscene):
                return vscene
        except Exception as e:
            log.info("geometry retry didn't help: %s: %s", type(e).__name__, e)
        if _ACTIVE_READERS:              # ML reader(s) available -> try to do better
            try:
                png = await _run_heavy(_pdf_first_page_png, raw, what="PDF render")
                ml_scene = await _ml_scene_from_png(png, width_ft)
                best = plan_health.better_scene(vscene, ml_scene)
                if best is not None:
                    return best
            except Exception as e:
                log.warning("cascade: ML fallback skipped: %s: %s", type(e).__name__, e)
        if vscene is not None:
            return vscene               # flagged but it's the best we have
        raise HTTPException(422, f"vector PDF parse failed: {vec_err}")
    if is_pdf:                           # flat PDF -> raster path
        raw = await _run_heavy(_pdf_first_page_png, raw, what="PDF render")
    if not _ACTIVE_READERS:              # vector-only deploy: photos are beta
        raise HTTPException(503, BETA_MSG)
    return await _ml_scene_from_png(raw, width_ft)


async def _one_ml_scene(reader, name, png_bytes, width_ft):
    """One model -> one scene (raises on failure; caller decides what to do).
    E5: readers exposing detect_parts() also hand back typed rooms (CubiCasa's
    room-type map) in the SAME single inference; readers with only the older
    detections() contract (e.g. tf2) keep working with no rooms."""
    rooms_px = furniture_px = None
    if hasattr(reader, "detect_parts"):
        parts = await _run_heavy(reader.detect_parts, png_bytes,
                                 what=f"detection ({name})")
        segs, boxes = parts["segments"], parts["boxes"]
        w, h, rooms_px = parts["width"], parts["height"], parts.get("rooms")
        furniture_px = parts.get("furniture")
    else:
        segs, boxes, w, h = await _run_heavy(reader.detections, png_bytes,
                                             what=f"detection ({name})")
    segs, ops = openings.attach_openings(segs, boxes, openings.default_tol(w))
    scene = scene_builder.scene_from_segments(segs, w, h, width_ft, openings=ops,
                                              rooms_px=rooms_px,
                                              furniture_px=furniture_px)
    scene.setdefault("meta", {})["reader"] = f"ml:{name}"
    return scene


async def _ml_scene_from_png(png_bytes, width_ft):
    """Best-of arbitration across every ACTIVE ML reader: each model reads the
    plan independently, each candidate scene is scored (plan_health), and the
    highest-scoring one wins. Scores of all contenders are recorded on the
    winner (meta.reader_scores) so you can see which model earned it — and a
    photo read by two models is strictly better than by one. Raises 503 only
    when no reader is available/succeeds."""
    if not _ACTIVE_READERS:
        raise HTTPException(503, BETA_MSG)
    candidates, scores, last_err = [], {}, None
    for name, reader in _ACTIVE_READERS.items():
        try:
            scene = await _one_ml_scene(reader, name, png_bytes, width_ft)
            score = plan_health.score_scene(scene)
            scores[name] = score
            candidates.append((score, len(candidates), scene))
        except Exception as e:            # one broken model never blocks the rest
            last_err = e
            log.warning("reader %s failed: %s: %s", name, type(e).__name__, e)
    if not candidates:
        if isinstance(last_err, HTTPException):
            raise last_err
        raise HTTPException(503, f"{BETA_MSG} ({type(last_err).__name__})")
    candidates.sort(key=lambda c: (-c[0], c[1]))       # best score, stable order
    best = candidates[0][2]
    if len(scores) > 1:
        best["meta"]["reader_scores"] = scores          # transparency: who won
        log.info("ml best-of: %s won %s", best["meta"]["reader"], scores)
        # G5: union doors/windows the LOSERS found onto the winner's walls, so
        # an opening seen by either model survives (no conflicting geometry).
        others = [c[2] for c in candidates[1:]]
        best, n_fused = opening_fusion.augment_openings(best, others)
        if n_fused:
            best["meta"]["fused_openings"] = n_fused
            log.info("ml fusion: added %d opening(s) from other readers", n_fused)
    return best


def _check_width_ft(width_ft):
    """Query(gt/le) rejects out-of-range values; older pydantic still lets
    inf/nan through the comparisons - refuse them explicitly."""
    if not math.isfinite(width_ft):
        raise HTTPException(422, "width_ft must be a finite number")


@app.post("/scene")
async def scene(image: UploadFile = File(...),
                width_ft: float = Query(scene_builder.DEFAULT_WIDTH_FT, gt=0, le=2000),
                loading_factor: float = Query(1.30, gt=1.0, le=2.0),
                north_deg: float = Query(0.0, ge=0.0, lt=360.0),
                wing: str = "largest"):
    """Detect walls and return them as canonical scene.json (feet, z-up), plus a
    RERA-style area statement (carpet / built-up / super built-up) and a Vastu
    report. wing: which building block when a sheet holds several.
    loading_factor: developer's super-built-up loading (India typ. 1.25-1.35).
    north_deg: compass North on the sheet, degrees clockwise from up (default 0)."""
    _check_width_ft(width_ft)
    fname = getattr(image, "filename", None)
    # ML data pipeline: when STORE_UPLOADS=1, keep the raw upload so the corpus
    # stores (input file -> labels) training pairs. Zero-cost when off.
    corpus_bytes = None
    if db.store_uploads_enabled():
        # capped, chunked read: the plain image.read() here buffered an
        # UNBOUNDED body into RAM before any size check ran (memory-DoS)
        corpus_bytes = await _read_capped(image)
        from starlette.datastructures import UploadFile as _SU
        image = _SU(file=io.BytesIO(corpus_bytes), filename=fname,
                    headers=getattr(image, "headers", None))
    t0 = time.perf_counter()
    try:
        s = await _scene_from_upload(image, width_ft, wing)
    except HTTPException as e:
        db.log_parse(None, filename=fname, width_ft=width_ft, ok=False,
                     duration_ms=int((time.perf_counter() - t0) * 1000),
                     error=f"{e.status_code}: {e.detail}")
        raise
    except Exception as e:
        db.log_parse(None, filename=fname, width_ft=width_ft, ok=False,
                     duration_ms=int((time.perf_counter() - t0) * 1000),
                     error=f"{type(e).__name__}: {e}")
        raise HTTPException(500, f"scene build failed: {e}")
    # RERA-style area statement (pure geometry) — never let it break the scene
    try:
        s["area_statement"] = area_statement.compute_area_statement(s, loading_factor)
    except Exception as e:
        log.warning("area statement skipped: %s: %s", type(e).__name__, e)
    # Vastu report (pure geometry; guidance only) — never breaks the scene
    try:
        s["vastu"] = vastu.analyze(s, north_deg)
    except Exception as e:
        log.warning("vastu skipped: %s: %s", type(e).__name__, e)
    # rough BOQ + cost estimate (pure geometry) — never breaks the scene
    try:
        s["boq"] = boq.compute_boq(s)
    except Exception as e:
        log.warning("boq skipped: %s: %s", type(e).__name__, e)
    # streamlined analysis block: scored + reviewable value extraction, the one
    # object a dashboard/reviewer reads (also logged to Supabase below)
    try:
        s["analysis"] = pipeline.analyze(s, loading_factor)
    except Exception as e:
        log.warning("pipeline analyze skipped: %s: %s", type(e).__name__, e)
    # Plan Doctor: rules diagnosis on EVERY parse (layman explanation + grade),
    # appended to docs/LEARNINGS.md (the auto-learn loop); optional LLM second
    # opinion runs in PARALLEL and never blocks or overrides the rules
    try:
        s["diagnosis"] = plan_doctor.diagnose(s)
        plan_doctor.record(s["diagnosis"], filename=fname)
        if plan_doctor.llm_enabled():
            _t = asyncio.create_task(plan_doctor.llm_second_opinion(
                s["diagnosis"], s.get("meta", {}), filename=fname))
            _LLM_TASKS.add(_t)
            _t.add_done_callback(_LLM_TASKS.discard)
    except Exception as e:
        log.warning("plan doctor skipped: %s: %s", type(e).__name__, e)
    # one triageable summary line per parse (the prod debugging lifeline)
    _m = s.get("meta", {})
    log.info("parse ok file=%s reader=%s %.1fx%.1fft doors=%d rooms=%d scale=%s %dms",
             fname, _m.get("reader"), _m.get("plan_width_ft", 0),
             _m.get("plan_depth_ft", 0),
             sum(1 for o in s.get("openings", []) if o.get("type") == "door"),
             len(s.get("rooms", [])), _m.get("scale", {}).get("source"),
             int((time.perf_counter() - t0) * 1000))
    # fire-and-forget corpus log (no-op unless SUPABASE_URL/KEY are set);
    # with STORE_UPLOADS=1 the raw plan file is archived too (training pairs)
    db.log_parse(s, filename=fname, width_ft=width_ft,
                 duration_ms=int((time.perf_counter() - t0) * 1000), ok=True,
                 upload_bytes=corpus_bytes)
    return JSONResponse(s)


def _reanalyze(s, loading_factor, north_deg):
    """Re-run the pure-geometry analysis blocks on a scene (area / vastu / boq /
    pipeline / doctor). Each is guarded so one failure never breaks the rest.
    Shared shape with /scene; used by /recompute after user corrections."""
    for name, fn in (
        ("area_statement", lambda: area_statement.compute_area_statement(s, loading_factor)),
        ("vastu", lambda: vastu.analyze(s, north_deg)),
        ("boq", lambda: boq.compute_boq(s)),
        ("analysis", lambda: pipeline.analyze(s, loading_factor)),
    ):
        try:
            s[name] = fn()
        except Exception as e:
            log.warning("%s skipped on recompute: %s: %s", name, type(e).__name__, e)
    try:
        # diagnose so the UI shows a fresh grade, but do NOT record() — a
        # recompute fires on every user edit and would spam docs/LEARNINGS.md
        # with low-value "(recompute)" lines (the log is for real parses).
        s["diagnosis"] = plan_doctor.diagnose(s)
    except Exception as e:
        log.warning("plan doctor skipped on recompute: %s: %s", type(e).__name__, e)
    return s


@app.post("/recompute")
async def recompute(payload: dict = Body(...)):
    """G7 user correction: apply human fixes (true width -> rescale, room-type
    edits, delete phantom rooms) to an already-parsed scene and return it with
    FRESH area / Vastu / BOQ / diagnosis. Pure geometry — no re-parse, no GPU,
    instant. Body: {scene: <scene.json>, corrections: {true_width_ft?,
    room_types?, delete_rooms?, loading_factor?, north_deg?}}."""
    scene = payload.get("scene")
    corr = payload.get("corrections") or {}
    if not isinstance(scene, dict) or "meta" not in scene:
        raise HTTPException(422, "body.scene must be a parsed scene object")
    if not isinstance(corr, dict):
        raise HTTPException(422, "body.corrections must be an object")
    try:
        scene, info = corrections.apply_corrections(scene, corr)
        # coerce inside the guard too: a bad loading_factor/north_deg must be a
        # clean 422, not a 500 (both floats are client-supplied)
        loading = float(corr.get("loading_factor", 1.30) or 1.30)
        north = float(corr.get("north_deg",
                               (scene.get("meta", {}) or {}).get("north_deg", 0)) or 0)
    except (ValueError, TypeError) as e:
        raise HTTPException(422, f"invalid correction: {e}")
    if not (math.isfinite(loading) and math.isfinite(north)):
        raise HTTPException(422, "loading_factor / north_deg must be finite")
    scene = _reanalyze(scene, loading, north)
    scene.setdefault("meta", {})["correction_info"] = info
    return JSONResponse(scene)


@app.post("/area-statement.xlsx")
async def area_statement_xlsx(image: UploadFile = File(...),
                             width_ft: float = Query(scene_builder.DEFAULT_WIDTH_FT, gt=0, le=2000),
                             loading_factor: float = Query(1.30, gt=1.0, le=2.0),
                             project: str = Query(""),
                             wing: str = "largest"):
    """Parse the plan and return a downloadable RERA area-statement spreadsheet."""
    _check_width_ft(width_ft)
    try:
        s = await _scene_from_upload(image, width_ft, wing)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"scene build failed: {e}")
    st = area_statement.compute_area_statement(s, loading_factor)
    plan_name = getattr(image, "filename", "") or ""
    xlsx = await run_in_threadpool(area_report.build_area_xlsx, st, project,
                                   plan_name, time.strftime("%Y-%m-%d"))
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="area-statement.xlsx"'})


@app.post("/scene.glb")
async def scene_glb(image: UploadFile = File(...),
                    width_ft: float = Query(scene_builder.DEFAULT_WIDTH_FT, gt=0, le=2000),
                    wing: str = "largest"):
    """Detect walls, build a .glb 3D model, and return the file."""
    _check_width_ft(width_ft)
    try:
        s = await _scene_from_upload(image, width_ft, wing)
        # export straight to bytes: no temp file to leak (or to collide
        # between concurrent users), nothing to clean up on failure
        glb = await run_in_threadpool(scene_to_glb.build_glb_bytes, s)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"glb build failed: {e}")
    return Response(content=glb, media_type="model/gltf-binary",
                    headers={"Content-Disposition": 'attachment; filename="scene.glb"'})


SCENE_VIEW_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Drishti - plan to 3D</title>
<style>
 body{margin:0;font-family:system-ui,Arial,sans-serif;background:#0f172a;color:#e2e8f0;overflow:hidden}
 #ui{position:absolute;top:12px;left:12px;z-index:10;background:rgba(15,23,42,.9);padding:14px;border-radius:12px;max-width:300px}
 button{background:#22d3ee;color:#0f172a;border:0;padding:8px 14px;border-radius:8px;font-weight:700;cursor:pointer;margin-top:8px}
 #status{margin-top:10px;font-size:13px;color:#94a3b8}
 label{font-size:13px}
</style></head><body>
<div id="ui">
 <div style="font-weight:700;font-size:15px">Drishti - plan to 3D walls</div>
 <input type="file" id="file" accept="image/*,application/pdf"><br>
 <label>Building width (ft): <input type="number" id="wft" value="40" style="width:64px"></label><br>
 <button onclick="run()">Build 3D</button>
 <button onclick="dl()">Download .glb</button>
 <div id="status">Pick a PNG/JPG/PDF plan, set the real width, then Build 3D.</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const FT=0.3048;
let scene,camera,renderer,group,theta=0.9,phi=1.0,radius=24,target=new THREE.Vector3();
function init(){
  scene=new THREE.Scene(); scene.background=new THREE.Color(0x0f172a);
  camera=new THREE.PerspectiveCamera(55,innerWidth/innerHeight,0.1,2000);
  renderer=new THREE.WebGLRenderer({antialias:true});
  renderer.setSize(innerWidth,innerHeight); document.body.appendChild(renderer.domElement);
  scene.add(new THREE.HemisphereLight(0xffffff,0x334455,0.95));
  const d=new THREE.DirectionalLight(0xffffff,0.7); d.position.set(10,20,10); scene.add(d);
  group=new THREE.Group(); scene.add(group);
  orbit(); animate();
}
function clearGroup(){ while(group.children.length) group.remove(group.children[0]); }
function build(s){
  clearGroup();
  const H=s.meta.wall_height_ft*FT;
  let minx=1e9,maxx=-1e9,minz=1e9,maxz=-1e9;
  // polygon walls (vector-PDF path); axis swap: plan (x,y) -> world (x, z)
  (s.walls_poly||[]).forEach(w=>{
    const shp=new THREE.Shape(w.outer.map(p=>new THREE.Vector2(p[0]*FT,p[1]*FT)));
    (w.holes||[]).forEach(h=>shp.holes.push(new THREE.Path(h.map(p=>new THREE.Vector2(p[0]*FT,p[1]*FT)))));
    const g=new THREE.ExtrudeGeometry(shp,{depth:H,bevelEnabled:false});
    g.applyMatrix4(new THREE.Matrix4().set(1,0,0,0, 0,0,1,0, 0,1,0,0, 0,0,0,1)); // (x,y,z)->(x,z,y)
    const m=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:0xcfcabd,side:THREE.DoubleSide}));
    group.add(m);
    w.outer.forEach(p=>{minx=Math.min(minx,p[0]*FT);maxx=Math.max(maxx,p[0]*FT);
      minz=Math.min(minz,p[1]*FT);maxz=Math.max(maxz,p[1]*FT);});
  });
  s.walls.forEach(w=>{
    const sx=Math.abs(w.x1-w.x0)*FT, sz=Math.abs(w.y1-w.y0)*FT;
    const cx=(w.x0+w.x1)/2*FT, cz=(w.y0+w.y1)/2*FT;
    const m=new THREE.Mesh(new THREE.BoxGeometry(Math.max(sx,0.02),H,Math.max(sz,0.02)),
      new THREE.MeshStandardMaterial({color:w.type==='external'?0xcfcabd:0xe4dfd2}));
    m.position.set(cx,H/2,cz); group.add(m);
    minx=Math.min(minx,cx-sx/2);maxx=Math.max(maxx,cx+sx/2);
    minz=Math.min(minz,cz-sz/2);maxz=Math.max(maxz,cz+sz/2);
  });
  // floor = the actual plan footprint, so the base always matches & grows with size
  const pw=(s.meta.plan_width_ft||20)*FT, pd=(s.meta.plan_depth_ft||20)*FT;
  const floor=new THREE.Mesh(new THREE.PlaneGeometry(pw,pd),
    new THREE.MeshStandardMaterial({color:0x2a3550}));
  floor.rotation.x=-Math.PI/2; floor.position.set(pw/2,0,pd/2); group.add(floor);
  target.set(pw/2,H/2,pd/2);
  radius=Math.max(pw,pd)*1.6+5;
}
function orbit(){
  let down=false,px,py;
  renderer.domElement.addEventListener('mousedown',e=>{down=true;px=e.clientX;py=e.clientY;});
  addEventListener('mouseup',()=>down=false);
  addEventListener('mousemove',e=>{ if(!down)return;
    theta-=(e.clientX-px)*0.01; phi=Math.max(0.15,Math.min(1.5,phi-(e.clientY-py)*0.01));
    px=e.clientX;py=e.clientY;});
  renderer.domElement.addEventListener('wheel',e=>{radius=Math.max(3,radius+e.deltaY*0.02);e.preventDefault();},{passive:false});
  addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);});
}
function animate(){
  requestAnimationFrame(animate);
  camera.position.set(target.x+radius*Math.sin(phi)*Math.cos(theta),
    target.y+radius*Math.cos(phi), target.z+radius*Math.sin(phi)*Math.sin(theta));
  camera.lookAt(target); renderer.render(scene,camera);
}
function wft(){ return document.getElementById('wft').value||40; }
function pick(){ const f=document.getElementById('file').files[0]; if(!f) alert('pick an image first'); return f; }
async function run(){
  const f=pick(); if(!f) return;
  document.getElementById('status').textContent='Detecting + building...';
  const fd=new FormData(); fd.append('image',f);
  const r=await fetch('/scene?width_ft='+wft(),{method:'POST',body:fd});
  if(!r.ok){document.getElementById('status').textContent='Error '+r.status+': '+await r.text();return;}
  const s=await r.json(); build(s);
  const nw=s.walls.length+(s.walls_poly||[]).length, no=(s.openings||[]).length;
  document.getElementById('status').textContent='Built '+nw+' walls, '+no+' openings ('+s.meta.source+'). Drag to orbit, scroll to zoom.';
}
async function dl(){
  const f=pick(); if(!f) return;
  document.getElementById('status').textContent='Building .glb...';
  const fd=new FormData(); fd.append('image',f);
  const r=await fetch('/scene.glb?width_ft='+wft(),{method:'POST',body:fd});
  if(!r.ok){document.getElementById('status').textContent='Error '+r.status;return;}
  const b=await r.blob(),u=URL.createObjectURL(b);
  const a=document.createElement('a'); a.href=u; a.download='scene.glb'; a.click(); URL.revokeObjectURL(u);
  document.getElementById('status').textContent='Downloaded scene.glb';
}
init();
</script></body></html>"""


@app.get("/scene-view", response_class=HTMLResponse)
def scene_view():
    """Upload a plan and SEE the detected walls in 3D (orbit/zoom) + download .glb."""
    return SCENE_VIEW_PAGE
