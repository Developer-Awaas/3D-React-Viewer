# Drishti "Visualize" (Beta) — photoreal render + walkthrough

This adds a **second pillar** to Drishti. Pillar 1 is your accurate **Plan → 3D**
engine (unchanged). Pillar 2, "Visualize", takes the 3D model you already built,
grabs an eye-level view of it, and turns that into a **photorealistic still**
(SDXL + ControlNet) and a short **walkthrough video** (Stable Video Diffusion).

It reuses your existing 3D scene as the ControlNet stencil — so the walls stay
locked while the AI paints a furnished, photoreal version. No CubiCasa cropping,
no "flat plan → perspective" guesswork.

---

## ⚠️ READ FIRST — licensing (this affects your commercial launch)

| Model | License | Commercial use? |
|-------|---------|-----------------|
| **CubiCasa5K** (already in your `/scene` raster path) | **CC BY-NC 4.0** | ❌ **NonCommercial — NOT allowed in a paid product** |
| SDXL base 1.0 | CreativeML OpenRAIL++-M | ✅ Generally yes (follow the use-based restrictions) |
| ControlNet (canny SDXL) | OpenRAIL | ✅ Generally yes |
| Stable Video Diffusion XT | Stability Community License | ⚠️ Free under a revenue cap — **check the terms** |

**The big one:** `server/CubiCasa5k/LICENSE` is **Creative Commons
Attribution-NonCommercial**. That means the CubiCasa model powering your raster
`/perceive` and photo `/scene` path **cannot legally be used in a commercial
product**. Your *vector* CAD-PDF engine is your own code and is fine — this only
affects the raster/photo path. Before you charge anyone, do one of:

1. Ship **vector-only** at launch (photos stay an internal/disabled beta), or
2. Get a **commercial license** from CubiCasa (they sell a commercial API), or
3. Replace CubiCasa with a commercially-licensed raster parser / your own model.

For the render models, the safest commercial path is a **hosted API** (fal.ai) or
a permissively-licensed video model (e.g. LTX-Video) rather than SVD. See
**Dev vs Production** below.

---

## What I could and couldn't do for you

I **could not** clone/run anything on your GPU from the Cowork session — the
render has to run on *your* machine where the RTX 3060 and CUDA live. So instead
you get a **one-double-click setup script** plus all the integration code, ready
to drop into your repo. CubiCasa was **already cloned** (weights and all).

Files added to your repo:

```
setup_visualize.bat              # one-time install (run on your PC)
run_backend_gpu.bat              # start the backend with Visualize on
server/visualize.py              # /visualize/render + /visualize/animate
server/requirements-visualize.txt
src/api/visualize.ts             # frontend API calls
src/components/VisualizeButton.tsx   # the ✨ Visualize (Beta) panel
```

---

## Step 1 — one-time setup (on your PC)

Double-click **`setup_visualize.bat`**. It will:

1. create/activate the `server\venv`,
2. install the **CUDA build** of PyTorch (cu121),
3. install `diffusers` + the render deps,
4. print your GPU name to confirm CUDA works.

The AI models download automatically the **first** time you render (~7 GB SDXL +
~5 GB video). Stable Video Diffusion is **license-gated** on Hugging Face, so once:

```
huggingface-cli login
```

and accept the license at
<https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt>.

## Step 2 — wire it into your app (3 tiny edits)

**A. `server/main.py`** — add these lines just after `app = FastAPI(...)`:

```python
# Visualize (Beta): photoreal render + walkthrough. Optional, like perception.
try:
    import visualize
    app.include_router(visualize.router)
    print("visualize (Beta) enabled — backend:", visualize.RENDER_BACKEND)
except Exception as _e:
    print("visualize disabled:", _e)
```

**B. `src/App.tsx`** — let us screenshot the 3D canvas. Change the `<Canvas>` line:

```tsx
// before
<Canvas shadows camera={{ position: PRESETS.default.position, fov: 50 }} className="!absolute inset-0">
// after — add gl={{ preserveDrawingBuffer: true }}
<Canvas shadows gl={{ preserveDrawingBuffer: true }} camera={{ position: PRESETS.default.position, fov: 50 }} className="!absolute inset-0">
```

**C. `src/App.tsx`** — add the button. At the top with the other imports:

```tsx
import VisualizeButton from './components/VisualizeButton'
```

and next to the plan HUD (right after the `{mode === 'plan' && pPlan && ( ...meta HUD... )}` block):

```tsx
{mode === 'plan' && pPlan && <VisualizeButton />}
```

## Step 3 — run it

Terminal 1 (backend, on the GPU machine):

```
run_backend_gpu.bat
```

Terminal 2 (frontend):

```
npm run dev
```

Open the app → **Plan → 3D** → build a model → orbit to a nice angle →
click **✨ Visualize** → pick a room + style → **Render** → optionally **Animate**.

---

## Test each piece from the command line

```bash
# 1) is Visualize up, and on which backend?
curl http://localhost:8000/visualize/health
#    -> {"backend":"local","cuda":true,"warm":[]}

# 2) render a still from any screenshot / image
curl -X POST http://localhost:8000/visualize/render \
  -F "image=@some_view.png" -F "room_type=living room" -F "style=scandinavian" \
  -o render.json      # contains image_base64

# 3) animate a still into an mp4
curl -X POST http://localhost:8000/visualize/animate \
  -F "image=@render.png" -o walk.json    # contains video_base64
```

---

## Dev vs Production (important)

- **Dev (your 3060):** `RENDER_BACKEND=local` — diffusers runs on your GPU, free.
- **Production (Render/Railway = CPU only):** these models **can't run on CPU**.
  The module boots fine but the render endpoints need a GPU. For prod, set
  `RENDER_BACKEND=fal` and add your hosted-GPU call in `visualize._render_fal` /
  `_animate_fal`. Sketch:

  ```python
  import base64, fal_client   # pip install fal-client ; set FAL_KEY env
  def _render_fal(image_bytes, prompt, negative, steps, guidance, cn_scale, seed):
      data_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode()
      out = fal_client.run("fal-ai/sdxl-controlnet-canny", arguments={
          "image_url": data_url, "prompt": prompt, "negative_prompt": negative,
          "num_inference_steps": steps, "controlnet_conditioning_scale": cn_scale,
      })
      import urllib.request
      return urllib.request.urlopen(out["images"][0]["url"]).read()  # PNG bytes
  ```

  (Check fal.ai for the current model id + argument names.) The frontend and the
  rest of the backend don't change — only this one function.

So: **develop free on your GPU, deploy pointing at a hosted GPU.** Same code.

---

## Troubleshooting (12 GB card)

- **`torch.cuda.is_available()` is False** → you have the CPU build. Re-run
  `setup_visualize.bat`, or: `pip uninstall torch torchvision` then
  `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121`.
- **Out of memory on Animate** → SVD is the hungry one. Lower it: set
  `SVD_FRAMES=14` and `SVD_DECODE_CHUNK=2` in `run_backend_gpu.bat`, and close
  other GPU apps (games, Chrome with hardware accel).
- **CubiCasa + SDXL fighting over VRAM** → loading SDXL evicts other render
  pipes automatically, but CubiCasa (in the main app) also holds ~2 GB. If tight,
  run Visualize without the raster path warm, or give render its own process.
- **First render is slow / seems stuck** → it's downloading ~7 GB of weights the
  first time. Watch the terminal. Subsequent renders are ~20–40s.
- **401 / gated on the video model** → do the `huggingface-cli login` + accept
  the SVD license (Step 1).

---

## Honest expectations

The still render is genuinely good — the walls stay put and the room looks
photoreal. The **video** invents motion, so over 3–4 seconds furniture can
morph slightly and the "camera" drifts. It's a great marketing/mood clip, not a
measured walkthrough — which is exactly why the panel labels it an *artistic
impression*. Keep that framing with clients and it's pure upside.
