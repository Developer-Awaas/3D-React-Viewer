# ONE render of FLOOR PLAN — a runbook for Rahul's RTX machine

**`docs/RENDER-TEST-PLAN.md` does not exist in this repo** (checked 8 Sep 2026;
the render docs present are `RENDER-QA.md` and `DEPLOY-GPU.md`). This is written
from the code instead — `server/visualize.py`, `server/main.py`,
`server/fetch_models.py` — so it can be run without reading any of them.

## 1. Install

| step | command | note |
|---|---|---|
| deps | `cd server && pip install -r requirements-visualize.txt` | on top of the normal backend deps |
| weights | `python fetch_models.py` | pulls exactly what the runtime loads — the IDs come from `visualize.required_models()`, the same function the loader reads, so they cannot drift |
| verify | `python -c "import visualize,json; print(json.dumps(visualize.models_status(), indent=2))"` | wait for `"models_ready": true` |

**Weights pulled (fp16 variants only — roughly half the download):**
`stabilityai/stable-diffusion-xl-base-1.0` (~7 GB) ·
`diffusers/controlnet-canny-sdxl-1.0` (~2.5 GB) ·
`diffusers/controlnet-depth-sdxl-1.0` (~2.5 GB). **~12 GB total.**
A **segmentation** ControlNet (~5 GB) is optional and auto-enables once cached —
`SEG_CONTROLNET` in `server/.env`. **Do the first run without it.**

## 2. Run

```
cd server && source venv/bin/activate      # Windows: run_backend_gpu.bat
uvicorn main:app --port 8000
```
Then in the browser: `npm run dev` → upload `plans/FLOOR PLAN.pdf` → open the 3D
view → stand inside a room at eye level → **Visualize**. The button uploads the
screenshot plus the depth and segmentation maps the viewer renders.

Set once in `server/.env` for a first-ever run: **`RENDER_TIMEOUT_S=600`**
(default 240 is tight while weights load) and **`MAX_CONCURRENT_RENDER=1`**.

## 3. What Rahul should look at

Use `docs/RENDER-QA.md`'s 5-point check. In priority order for a **first** run:
1. **Geometry lock** — do walls and openings sit where the 3D view puts them? If
   the AI moved a wall, depth conditioning was too weak (`control_scale` ↑ 0.9).
2. **Surface separation** — wall/floor/window boundaries crisp?
3. **Artifacts** — melted furniture, doubled doors, text-like smudges.
4. Ignore style fidelity on run one; it needs the 4-style grid to judge.

## 4. Runtime

**~30–60 s per 1024² image on a 12 GB RTX at the default 28 steps**, plus a
one-off 1–3 minutes on the first call while SDXL and the two ControlNets load
into VRAM. Raise `RENDER_TIMEOUT_S` for that first call only.

## 5. The conditioning question — answered, and it is NOT a blocker

**The renderer reads no scene field.** `/visualize/render` takes uploaded PNGs
(screenshot, depth, segmentation) and nothing else, so **a July renderer cannot
be broken by any parser schema change** — that half of the concern is sound.

**But the premise about the maps is stale.** Railings and door leaves have **not**
segmented as `other` since **1 Sep**, when `door`, `railing`, `stair` and
`terrace` classes were added to `src/three/gbuffer.ts`.
**`meta.glb.seg_unclassified_pct` reads 0.0% on all nine parseable sheets.**

The one real gap was **`chhajja`**, created by us on 7 Sep — 25 new meshes on
neelachala FIRST FLOOR that would have painted as `other`. **Fixed 8 Sep**
(`chhajja: '#b4a882'`).

**So: nothing must be fixed before the first test.** FLOOR PLAN carries **no
chhajja at all**, so its maps were already clean; and the seg ControlNet is off
by default on a first run, which means the segmentation map is not even consumed
until the optional 5 GB model is cached.
