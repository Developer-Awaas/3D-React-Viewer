"""Drishti "Visualize" (Beta) — turn an eye-level screenshot of the 3D scene
into a photoreal still (SDXL + ControlNet) and a short walkthrough clip (Stable
Video Diffusion).

Design mirrors perception.py:
  * the module is SAFE to import on a CPU-only deploy (no torch/diffusers at
    import time — everything heavy is imported lazily inside functions), so the
    API still boots on Render/Railway;
  * heavy calls go through a local _run_heavy() guard (one slot + timeout +
    OOM -> clean 503), just like main.py.

Two interchangeable backends behind the RENDER_BACKEND env var:
  local  -> run diffusers on THIS machine's GPU        (dev on the RTX 3060)
  fal    -> call fal.ai / any hosted GPU API           (production, no GPU)

Wire it into main.py with two lines (see README_VISUALIZE.md):
    import visualize
    app.include_router(visualize.router)
"""
import asyncio
import base64
import io
import os
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/visualize", tags=["visualize"])

RENDER_BACKEND = os.getenv("RENDER_BACKEND", "local").lower()

# at most N heavy render jobs at once (default 1): SDXL and the video model each
# want most of a 12 GB card, so extra requests QUEUE instead of racing into OOM
_SLOTS = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENT_RENDER", "1")))


# --------------------------------------------------------------------------- #
# heavy-call guard (kept local so this file drops in without editing main.py)
# --------------------------------------------------------------------------- #
async def _run_heavy(fn, *args, what="render"):
    timeout = float(os.getenv("RENDER_TIMEOUT_S", "240"))
    try:
        async with _SLOTS:
            return await asyncio.wait_for(run_in_threadpool(fn, *args), timeout)
    except asyncio.TimeoutError:
        raise HTTPException(504, f"{what} timed out after {timeout:.0f}s — "
                                 "lower RENDER_STEPS or the image size")
    except HTTPException:
        raise
    except Exception as e:
        m = str(e).lower()
        if "out of memory" in m or ("cuda" in m and "memory" in m):
            _free_gpu()
            raise HTTPException(503, "GPU ran out of memory — close other GPU "
                                     "apps, or lower RENDER_STEPS / SVD_FRAMES")
        raise HTTPException(500, f"{what} failed: {e}")


def _free_gpu():
    try:
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _cuda_ok():
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# prompts — the "style" turns into a text prompt; the walls come from ControlNet
# --------------------------------------------------------------------------- #
STYLE_PROMPTS = {
    "scandinavian": "modern Scandinavian interior, light oak floor, white walls, "
                    "natural linen furniture, soft morning daylight",
    "modern":       "modern contemporary interior, warm wood and matte black accents, "
                    "designer furniture, large windows, soft daylight",
    "warm minimal": "warm minimalist interior, beige and terracotta tones, boucle "
                    "furniture, plants, gentle afternoon light",
    "luxury":       "luxury interior, marble and brass details, plush velvet furniture, "
                    "statement lighting, editorial photography",
}
NEG_PROMPT = ("blurry, low quality, distorted, deformed, watermark, text, "
              "people, cartoon, cluttered, extra walls, warped perspective")


def _compose_prompt(room_type, style):
    look = STYLE_PROMPTS.get(style, STYLE_PROMPTS["scandinavian"])
    return (f"A photorealistic {room_type}, {look}, high-end interior design "
            f"photography, 8k, realistic lighting, sharp focus")


# --------------------------------------------------------------------------- #
# local diffusers backend  (runs on the RTX 3060)
# --------------------------------------------------------------------------- #
# warm pipelines, keyed by name. SDXL (~7 GB) and SVD (~6 GB) can't both live on
# a 12 GB card, so loading one EVICTS the other.
_PIPES = {}


def _evict(keep):
    for k in list(_PIPES):
        if k != keep:
            _PIPES.pop(k, None)
    _free_gpu()


def _canny(image_bytes, low=90, high=200, max_side=1024):
    """Screenshot bytes -> a canny edge image that locks the wall/room shape."""
    import cv2
    import numpy as np
    from PIL import Image
    img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    h, w = img.shape[:2]
    s = min(1.0, max_side / max(h, w))
    if s < 1.0:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    edges = cv2.Canny(img, low, high)
    return Image.fromarray(np.stack([edges] * 3, axis=-1))


def _require_local():
    if not _cuda_ok():
        raise HTTPException(503, "local render needs a CUDA GPU + diffusers. On a "
                                 "CPU host set RENDER_BACKEND=fal (hosted GPU).")


def _load_sdxl():
    if "sdxl" in _PIPES:
        return _PIPES["sdxl"]
    _require_local()
    _evict("sdxl")
    import torch
    from diffusers import ControlNetModel, StableDiffusionXLControlNetPipeline
    cn = ControlNetModel.from_pretrained(
        os.getenv("CONTROLNET_MODEL", "diffusers/controlnet-canny-sdxl-1.0"),
        torch_dtype=torch.float16)
    pipe = StableDiffusionXLControlNetPipeline.from_pretrained(
        os.getenv("SDXL_MODEL", "stabilityai/stable-diffusion-xl-base-1.0"),
        controlnet=cn, torch_dtype=torch.float16, use_safetensors=True,
        variant="fp16")
    pipe.enable_model_cpu_offload()   # only the active submodule sits on GPU -> fits 12 GB
    try:
        pipe.enable_vae_tiling()
    except Exception:
        pass
    _PIPES["sdxl"] = pipe
    return pipe


def _render_local(image_bytes, prompt, negative, steps, guidance, cn_scale, seed):
    import torch
    pipe = _load_sdxl()
    control = _canny(image_bytes)
    gen = torch.Generator(device="cpu").manual_seed(int(seed))
    out = pipe(prompt=prompt, negative_prompt=negative, image=control,
               num_inference_steps=int(steps), guidance_scale=float(guidance),
               controlnet_conditioning_scale=float(cn_scale), generator=gen)
    buf = io.BytesIO()
    out.images[0].save(buf, format="PNG")
    return buf.getvalue()


def _load_svd():
    if "svd" in _PIPES:
        return _PIPES["svd"]
    _require_local()
    _evict("svd")
    import torch
    from diffusers import StableVideoDiffusionPipeline
    pipe = StableVideoDiffusionPipeline.from_pretrained(
        os.getenv("SVD_MODEL", "stabilityai/stable-video-diffusion-img2vid-xt"),
        torch_dtype=torch.float16, variant="fp16")
    pipe.enable_model_cpu_offload()
    try:
        pipe.unet.enable_forward_chunking()
    except Exception:
        pass
    _PIPES["svd"] = pipe
    return pipe


def _animate_local(image_bytes, motion, fps, seed, frames):
    import torch
    from PIL import Image
    from diffusers.utils import export_to_video
    pipe = _load_svd()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((1024, 576))
    gen = torch.Generator(device="cpu").manual_seed(int(seed))
    result = pipe(img, num_frames=int(frames), motion_bucket_id=int(motion),
                  fps=int(fps), decode_chunk_size=int(os.getenv("SVD_DECODE_CHUNK", "4")),
                  noise_aug_strength=0.02, generator=gen)
    fd, path = tempfile.mkstemp(suffix=".mp4", prefix="drishti_walk_")
    os.close(fd)
    try:
        export_to_video(result.frames[0], path, fps=int(fps))
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# hosted (fal.ai) backend  — production, no local GPU. See README to fill in.
# --------------------------------------------------------------------------- #
def _render_fal(image_bytes, prompt, negative, steps, guidance, cn_scale, seed):
    raise HTTPException(501, "RENDER_BACKEND=fal is not configured yet — add your "
                             "fal.ai call in visualize._render_fal (README_VISUALIZE.md).")


def _animate_fal(image_bytes, motion, fps, seed, frames):
    raise HTTPException(501, "RENDER_BACKEND=fal is not configured yet — add your "
                             "fal.ai call in visualize._animate_fal (README_VISUALIZE.md).")


def _render(*a):
    return (_render_fal if RENDER_BACKEND == "fal" else _render_local)(*a)


def _animate(*a):
    return (_animate_fal if RENDER_BACKEND == "fal" else _animate_local)(*a)


# --------------------------------------------------------------------------- #
# endpoints
# --------------------------------------------------------------------------- #
@router.get("/health")
def vhealth():
    """Is the Visualize feature ready, and on which backend?"""
    return {"backend": RENDER_BACKEND, "cuda": _cuda_ok(),
            "warm": sorted(_PIPES.keys())}


@router.post("/render")
async def render_ep(
    image: UploadFile = File(...),
    room_type: str = Form("living room"),
    style: str = Form("scandinavian"),
    prompt: str = Form(""),
    steps: int = Form(28),
    guidance: float = Form(6.0),
    control_scale: float = Form(0.7),
    seed: int = Form(12345),
):
    """Eye-level screenshot of the 3D scene -> photorealistic furnished still.
    The walls are locked by ControlNet (canny); `style`/`room_type` set the look."""
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "empty image")
    full_prompt = prompt.strip() or _compose_prompt(room_type, style)
    png = await _run_heavy(_render, raw, full_prompt, NEG_PROMPT, steps,
                           guidance, control_scale, seed, what="render")
    return JSONResponse({"image_base64": base64.b64encode(png).decode(),
                         "prompt": full_prompt})


@router.post("/animate")
async def animate_ep(
    image: UploadFile = File(...),
    motion: int = Form(127),
    fps: int = Form(7),
    frames: int = Form(int(os.getenv("SVD_FRAMES", "25"))),
    seed: int = Form(12345),
):
    """Photoreal still -> a short (~3-4s) cinematic walkthrough .mp4."""
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "empty image")
    mp4 = await _run_heavy(_animate, raw, motion, fps, seed, frames, what="animate")
    return JSONResponse({"video_base64": base64.b64encode(mp4).decode(),
                         "mime": "video/mp4"})
