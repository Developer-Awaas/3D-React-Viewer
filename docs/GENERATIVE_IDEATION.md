# Drishti × Generative Models — Ideation & Integration Plan

_How to extract maximum value from SDXL / ControlNet (and friends) inside the
existing pipeline. Compiled 20 Jul 2026._

---

## 0. The core thesis (why Drishti wins here)

Every "photo → interior render" tool on the market has the same weakness: it
gets a flat image and must **guess** the 3D structure (depth, surfaces, what's a
wall vs a window) using yet another neural net, and it guesses wrong at the edges.

Drishti is different because **it built the scene**. After parsing, we know
exactly:
- the 3D geometry (walls_poly, wall heights, openings) → we can render a perfect
  **depth map** and **normal map**,
- what every mesh *is* — the GLB names meshes `floor`, `wall_N`, `glass_N`
  (windows), `column`, `furn_bed_i_part` → we can render a pixel-perfect
  **segmentation map**,
- the exact scale, room polygons, room interior points, furniture footprints.

So Drishti can hand a diffusion model a **complete G-buffer** (depth + normals +
segmentation + edges), which is the single best conditioning input that exists.
**The thesis: Drishti's accuracy pillar makes its beauty pillar better than
anyone else's.** Accurate *and* photoreal, because the generation is locked to
real geometry — not an artistic guess.

Everything below is about feeding the models richer signals than a screenshot.

---

## 1. Conditioning upgrades — from "a screenshot" to a G-buffer

Ranked by value. Each is a new pass rendered from the SAME three.js scene, then
sent as a ControlNet input.

**1.1 Depth ControlNet (do first — biggest fidelity jump, ~half day).**
Render a depth pass (three.js `MeshDepthMaterial` / depth texture) → normalized
depth image → `controlnet-depth-sdxl`. Depth preserves 3D perspective and room
volume far better than 2D Canny edges. Trivial for us: we have exact geometry.

**1.2 Segmentation ControlNet (the differentiator).**
Render a second pass where each mesh is flat-shaded by its semantic class
(floor = colour A, wall = B, window = C, furniture = D), read from the mesh
name. Feed to a segmentation ControlNet (or use as regional masks). Now SDXL
paints *floor as floor, window as sky/light, bed as bedding* — no bleed, no
"window melting into wall". **No competitor can do this cleanly; we can, because
our meshes are labelled.** This is the crown jewel.

**1.3 Multi-ControlNet stack.**
diffusers supports MultiControlNet: depth (structure) + segmentation (semantics)
+ canny (crisp edges), weighted. This is maximum fidelity — the generated room
matches your measured plan.

**1.4 Per-surface inpainting.**
Use the segmentation mask to inpaint ONE surface at a time ("change only the
floor to marble") while freezing everything else. Precise, editable materials.

---

## 2. Semantic prompting — let the parse write the prompt

Right now room type + style are manual dropdowns. We already extract the data to
automate it.

**2.1 Auto room-type labelling.** Classify each detected room from signals we
already have: area, furniture types inside it (we now extract bed/sofa/counter),
and sanitary/kitchen layer hints. Bedroom / kitchen / bath / living → auto-prompt
per room. No user input needed.

**2.2 Furniture-aware prompts.** We know a room contains a bed + 2 side tables →
the prompt and segmentation say so → SDXL paints the actual furniture, in place.

**2.3 Style memory.** Store the user's chosen style per project (Supabase) so a
whole plan renders in one coherent look.

---

## 3. Products — turn renders into deliverables (the business value)

The models are worth most when their output is a *product*, not a toy button.

**3.1 One-click Listing Pack.** One plan → exterior hero shot + a photoreal still
of **every room** (we already have a walk-inside camera per room) + a short
walkthrough video → a real-estate / architect deliverable. This is monetizable
per-plan. Reuses the room beacons + camera presets already built.

**3.2 Style grid.** Same locked geometry, N styles (Scandi / modern / luxury /
warm-minimal) rendered as a 2×2 grid — client picks a direction in seconds.
Cheap: fixed seed + ControlNet lock, just swap the prompt.

**3.3 Staging variants.** Empty vs furnished, day vs night (relight), material
swaps — all from the same conditioning, different prompts/inpaint.

**3.4 Walkthrough video (SVD, already scaffolded).** Photoreal still → cinematic
clip per room, or stitch room-to-room into a tour. Big shareability.

**3.5 Before/After.** Raw CAD plan ↔ photoreal render, side by side — the single
most convincing marketing asset for the product itself.

---

## 4. The data flywheel — this is the long-term moat

The Supabase logger already stores every parse (scene.json + metrics). Extend it
to also store the **rendered images + the conditioning maps + the chosen style**.
Then:

**4.1 Proprietary LoRA.** Fine-tune a LoRA on SDXL from Drishti's own
(geometry → photoreal) pairs. Over months this becomes a model that renders
*architectural interiors from real plans* better than base SDXL — a proprietary
asset no one else has, trained on data only Drishti produces.

**4.2 Preference loop.** Users pick their favourite of N renders → preference
data → tunes the default prompts/styles automatically.

**4.3 Render cache.** Key renders by `(scene_hash, camera, style, seed)` —
`scene_hash` already exists in the logger. Identical requests return instantly
and cost zero GPU. Directly reuses work already shipped.

---

## 5. Fitting it on a 12 GB GPU (infra)

- `enable_model_cpu_offload()` + VAE tiling are already in `visualize.py` — SDXL
  fits comfortably; SVD evicts SDXL when it loads (one at a time on 12 GB).
- **LoRA hot-swap** for styles: keep base SDXL warm, swap lightweight LoRA
  weights per style instead of reloading pipelines.
- **Queue + cache**: the semaphore (1 job) already queues; add the `scene_hash`
  cache (4.3) so repeats are free.
- **Two-tier backend**: `RENDER_BACKEND=local` (your GPU, dev + launch demo) vs
  `=fal` (hosted GPU, public scale) — the seam already exists in the code.

---

## 6. Recommended sequence

**Phase A — Launch (fidelity you can ship now):**
1. Depth ControlNet (1.1) — the single biggest quality jump.
2. Style grid (3.2) — makes the feature feel like a product, cheap to add.
3. Render cache by scene_hash (4.3) — free after first render.

**Phase B — Differentiate (2–3 weeks):**
4. Segmentation conditioning (1.2) + multi-ControlNet (1.3) — the moat feature.
5. Auto room-type + per-room Listing Pack (2.1, 3.1) — the sellable output.
6. SVD walkthrough polish (3.4).

**Phase C — Moat (ongoing):**
7. Store render pairs → LoRA fine-tune (4.1).
8. Preference loop (4.2).

---

## 7. Where each piece hooks into the current code

| Idea | Frontend | Backend |
|------|----------|---------|
| Depth / seg / normal passes | new render passes off the three.js scene (a `<GBuffer>` capture beside the canvas screenshot) | accept extra conditioning images in `/visualize/render` |
| Multi-ControlNet | — | `MultiControlNetModel` in `visualize._load_sdxl` |
| Auto room-type | — | classify in `pdf_vector.parse` (rooms already carry area; furniture already extracted) |
| Listing Pack / per-room | iterate `pPlan.rooms` camera presets, POST each | batch endpoint or loop |
| Style grid | N calls, fixed seed | none (prompt swap) |
| Render cache | — | key on `scene_hash` (already logged) |
| LoRA fine-tune | — | offline training job on the Supabase corpus |

---

### One-line summary
Stop sending SDXL a screenshot. Send it the **depth + segmentation** Drishti
already knows, auto-write the prompt from the **parsed rooms + furniture**, and
turn the output into a **per-room Listing Pack** — then log every pair to grow a
**proprietary fine-tuned model**. Accuracy feeds beauty; beauty feeds the moat.

---

## 8. Proptech-manager lens — what actually sells (India-first)

The photoreal render is the *wow*. But in Indian residential proptech (developers,
brokers, buyers — the "Awaas" market), the features that **close deals and are
legally required** are geometry-driven and need **no GPU**. A specialist would
prioritise these ALONGSIDE the renders, because they monetise faster and are
defensible.

**8.1 RERA carpet-area statement (highest ROI, non-ML).** Indian law (RERA)
requires developers to declare **carpet area** per unit when selling. We have
`walls_poly` + `rooms` in feet → compute carpet area, built-up, and super
built-up per room and per unit, and auto-generate a RERA-format area statement
(PDF/Excel). Every developer needs this for every unit. Pure geometry — reuses
the parse we already do. **This may be more valuable than the render for B2B.**

**8.2 Vastu analysis.** Indian buyers weigh Vastu heavily. Given the plan +
North direction (one user input, or infer from a compass symbol), score room
placement (kitchen SE, master SW, entrance N/NE, no toilet in NE) and produce a
Vastu report + a "compliant/needs-attention" overlay on the 3D. Strong
differentiator; competitors ignore it.

**8.3 BOQ + construction cost estimate.** From wall lengths × height + floor area
→ rough Bill of Quantities (brick, cement, plaster, flooring, paint) and a ₹
cost estimate using regional rates. Contractors and self-builders pay for this.
Geometry-driven.

**8.4 Listing syndication pack.** Auto-fill a listing for MagicBricks / 99acres /
Housing.com (and MLS abroad): area, room count, dimensions, + the photoreal
Listing Pack images. Turns a plan into a ready-to-post listing in one click.

**8.5 Space-planning / furniture-fit check.** We know room dimensions → verify
standard furniture fits, flag tight circulation, suggest layouts. Ties to the
furniture we already extract; feeds the render's segmentation.

**8.6 Daylight & orientation study.** We already place a sun + cast shadows in
three.js → compute daylight hours and a comfort score per room. Sells the
"livability" story; also feeds an energy angle.

**8.7 AR/VR walk-through (WebXR).** The GLB already exists → let a buyer walk the
unfurnished-or-photoreal flat on their phone in VR before it's built. Huge for
under-construction sales (the Indian norm).

**8.8 Renovation mode.** Upload an existing flat's plan → per-surface inpaint new
finishes → sell renovation/interior-design leads. Monetises the inpainting work
(1.4) directly.

**8.9 Multi-unit / developer scale.** Stack floors + render every unit type →
one project = hundreds of sellable renders + area statements. This is where B2B
revenue compounds: you sell per-project, not per-plan.

**8.10 White-label for architects/brokers.** Branded output (their logo, their
palette) → B2B SaaS seat, not a one-off. Recurring revenue.

### Proptech priority call
For the **Indian launch**, ship **8.1 (RERA area statement)** and the **photoreal
render** together: the render wins attention, the area statement wins the
developer's wallet. Vastu (8.2) and BOQ (8.3) are the next two that are cheap
(geometry, no GPU) and uniquely sticky in this market.
