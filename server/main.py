"""Drishti Perception API (Step 2).

Loads the CubiCasa model once at startup, then answers /perceive requests.
Dev: runs locally (uvicorn). Prod: same app deploys to any GPU host - only
.env and the frontend's API URL change, no code change.
"""
import asyncio
import functools
import io
import math
import os
import time
from contextlib import asynccontextmanager

import anyio.to_thread
from dotenv import load_dotenv
from fastapi import FastAPI, File, Query, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.concurrency import run_in_threadpool

import area_report
import area_statement
import boq
import cad_vector
import db
import pipeline
import plan_health
import vastu
import openings
import pdf_vector
import scene_builder
import scene_to_glb

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
_ML_READER_NAME = os.getenv("ML_READER", "cubicasa").lower()
if _ML_READER_NAME in ("tf2", "tf2deepfloorplan", "deepfloorplan"):
    try:
        import tf2_floorplan as ml_reader
    except Exception as _e:
        ml_reader = None
        print(f"[ml] TF2DeepFloorplan not available: {_e}")
else:
    ml_reader = perception

BETA_MSG = ("This looks like a photo or scanned plan - that engine is in beta "
            "and not enabled on this server. Upload a CAD-exported PDF "
            "(vector) for full-quality 3D.")

load_dotenv()


@asynccontextmanager
async def lifespan(app):
    # warm the model once when the server boots (the slow part happens here, not per request)
    if perception is None:
        print("perception disabled (vector-only deploy):", _PERCEPTION_ERR)
    else:
        try:
            perception.load_model()
            print("CubiCasa model loaded and ready.")
        except Exception as e:
            print("WARNING: model failed to load at startup:", e)
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

# Visualize (Beta): SDXL + ControlNet photoreal render / SVD walkthrough. Safe
# to mount on any host — torch/diffusers are imported lazily inside the calls,
# and every endpoint returns a clean 503 when no CUDA GPU is present, so a slim
# CPU deploy is unaffected. Set RENDER_BACKEND=local on your GPU box.
try:
    import visualize
    app.include_router(visualize.router)
except Exception as _ve:          # never let an optional feature block boot
    print(f"[visualize] not mounted: {type(_ve).__name__}: {_ve}")


@app.get("/health")
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


MAX_UPLOAD_MB = 25

# at most N model inferences at once (default 1): extra requests QUEUE for a
# moment instead of racing each other into GPU/CPU out-of-memory
_INFER_SLOTS = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENT_INFER", "1")))


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
    if perception is None:
        raise HTTPException(503, BETA_MSG)
    try:
        result = await _run_heavy(perception.detect, raw, what="perception")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"perception failed: {e}")
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
        if ml_reader is not None:        # ML reader available -> try to do better
            try:
                png = await _run_heavy(_pdf_first_page_png, raw, what="PDF render")
                ml_scene = await _ml_scene_from_png(png, width_ft)
                best = plan_health.better_scene(vscene, ml_scene)
                if best is not None:
                    return best
            except Exception as e:
                print(f"[cascade] ML fallback skipped: {type(e).__name__}: {e}")
        if vscene is not None:
            return vscene               # flagged but it's the best we have
        raise HTTPException(422, f"vector PDF parse failed: {vec_err}")
    if is_pdf:                           # flat PDF -> raster path
        raw = await _run_heavy(_pdf_first_page_png, raw, what="PDF render")
    if ml_reader is None:                # vector-only deploy: photos are beta
        raise HTTPException(503, BETA_MSG)
    return await _ml_scene_from_png(raw, width_ft)


async def _ml_scene_from_png(png_bytes, width_ft):
    """Run the selected ML reader (CubiCasa or TF2DeepFloorplan, per ML_READER)
    on a rasterized plan and build a scene. Model-agnostic: the cascade doesn't
    care which model produced it. Raises HTTPException(503) if the model is
    unavailable/broken so the caller can fall back."""
    if ml_reader is None:
        raise HTTPException(503, BETA_MSG)
    try:
        segs, boxes, w, h = await _run_heavy(ml_reader.detections, png_bytes,
                                             what="detection")
    except HTTPException:
        raise
    except Exception as e:               # model/env broken -> guidance, not a 500
        raise HTTPException(503, f"{BETA_MSG} ({type(e).__name__})")
    segs, ops = openings.attach_openings(segs, boxes, openings.default_tol(w))
    scene = scene_builder.scene_from_segments(segs, w, h, width_ft, openings=ops)
    scene.setdefault("meta", {})["reader"] = "ml_fallback"
    return scene


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
        print(f"[area] skipped: {type(e).__name__}: {e}")
    # Vastu report (pure geometry; guidance only) — never breaks the scene
    try:
        s["vastu"] = vastu.analyze(s, north_deg)
    except Exception as e:
        print(f"[vastu] skipped: {type(e).__name__}: {e}")
    # rough BOQ + cost estimate (pure geometry) — never breaks the scene
    try:
        s["boq"] = boq.compute_boq(s)
    except Exception as e:
        print(f"[boq] skipped: {type(e).__name__}: {e}")
    # streamlined analysis block: scored + reviewable value extraction, the one
    # object a dashboard/reviewer reads (also logged to Supabase below)
    try:
        s["analysis"] = pipeline.analyze(s, loading_factor)
    except Exception as e:
        print(f"[pipeline] analyze skipped: {type(e).__name__}: {e}")
    # fire-and-forget corpus log (no-op unless SUPABASE_URL/KEY are set)
    db.log_parse(s, filename=fname, width_ft=width_ft,
                 duration_ms=int((time.perf_counter() - t0) * 1000), ok=True)
    return JSONResponse(s)


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
