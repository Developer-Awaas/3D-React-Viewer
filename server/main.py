"""Drishti Perception API (Step 2).

Loads the CubiCasa model once at startup, then answers /perceive requests.
Dev: runs locally (uvicorn). Prod: same app deploys to any GPU host - only
.env and the frontend's API URL change, no code change.
"""
import asyncio
import io
import os
import tempfile
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.concurrency import run_in_threadpool
from starlette.background import BackgroundTask

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
    worker thread keeps running to completion in the background - the CLIENT
    is released; the semaphore slot frees when the thread finishes."""
    timeout = float(os.getenv("INFER_TIMEOUT_S", "120"))
    try:
        async with _INFER_SLOTS:
            return await asyncio.wait_for(run_in_threadpool(fn, *args), timeout)
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
            or name.endswith((".pdf", ".png", ".jpg", ".jpeg", ".webp")))


async def _read_upload_bytes(image: UploadFile):
    """Read + validate an upload. Returns (raw_bytes, is_pdf) - no conversion."""
    if not _looks_supported(image):
        raise HTTPException(415, "upload a PNG/JPG image or a PDF")
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "empty file")
    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"file too large (> {MAX_UPLOAD_MB} MB)")
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
    """PDF bytes -> PNG bytes of page 1 (for the raster/CubiCasa path)."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=raw, filetype="pdf")
        return doc[0].get_pixmap(dpi=200).tobytes("png")
    except Exception as e:
        raise HTTPException(422, f"could not read PDF: {e}")


async def _read_upload(image: UploadFile):
    """Read an upload; accept images OR PDFs (PDF -> PNG of page 1). Returns image bytes."""
    raw, is_pdf = await _read_upload_bytes(image)
    return _pdf_first_page_png(raw) if is_pdf else raw


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
    raw, is_pdf = await _read_upload_bytes(image)
    if is_pdf and await run_in_threadpool(pdf_vector.is_vector_plan, raw):
        try:
            return await _run_heavy(pdf_vector.parse, raw, width_ft,
                                    pdf_vector.wing_arg(wing), what="vector parse")
        except ValueError as e:
            raise HTTPException(422, f"vector PDF parse failed: {e}")
    if is_pdf:
        raw = _pdf_first_page_png(raw)   # flat PDF -> raster path
    if perception is None:               # vector-only deploy: photos are beta
        raise HTTPException(503, BETA_MSG)
    try:
        segs, boxes, w, h = await _run_heavy(perception.detections, raw,
                                             what="detection")
    except HTTPException:
        raise
    except Exception as e:               # model/env broken -> guidance, not a 500
        raise HTTPException(503, f"{BETA_MSG} ({type(e).__name__})")
    segs, ops = openings.attach_openings(segs, boxes, openings.default_tol(w))
    return scene_builder.scene_from_segments(segs, w, h, width_ft, openings=ops)


@app.post("/scene")
async def scene(image: UploadFile = File(...), width_ft: float = scene_builder.DEFAULT_WIDTH_FT,
                wing: str = "largest"):
    """Detect walls and return them as canonical scene.json (feet, z-up).
    wing: which building block to build when a sheet holds several ("largest" or 0,1,...)."""
    try:
        s = await _scene_from_upload(image, width_ft, wing)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"scene build failed: {e}")
    return JSONResponse(s)


@app.post("/scene.glb")
async def scene_glb(image: UploadFile = File(...), width_ft: float = scene_builder.DEFAULT_WIDTH_FT,
                    wing: str = "largest"):
    """Detect walls, build a .glb 3D model, and return the file."""
    try:
        s = await _scene_from_upload(image, width_ft, wing)
        # unique temp file per request (a fixed name let concurrent users
        # download each other's building), deleted after the response is sent
        fd, out = tempfile.mkstemp(suffix=".glb", prefix="drishti_")
        os.close(fd)
        await run_in_threadpool(scene_to_glb.build_glb, s, out)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"glb build failed: {e}")
    return FileResponse(out, media_type="model/gltf-binary", filename="scene.glb",
                        background=BackgroundTask(os.remove, out))


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
