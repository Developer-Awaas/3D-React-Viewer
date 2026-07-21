# Drishti — Ideal Pipeline & Streamlining Blueprint

How every model earns its keep, how output gets both **improved** and **fixed**,
and how the whole thing stays observable + improvable. Compiled 21 Jul 2026.

## The one-line shape
`INGEST → READ (cascade) → ANALYZE (score) → GENERATE (3D/reports/photoreal) →
LOG → REVIEW → IMPROVE → (loop)`

Every stage has ONE job, a typed output, and a place it's observed. No stage
blocks another; failures degrade gracefully, never crash the request.

---

## Stage 1 — INGEST (route by input, don't guess)
- Detect input type: layered CAD PDF / flat PDF / photo-scan / DXF-DWG.
- Route: CAD → vector engine; flat/photo → straight to the ML reader.
- Cap size, reject junk early (413/415/422).
- **Value:** each input goes to the reader that's actually best for it.

## Stage 2 — READ (vector-first cascade, ML fixes failures)
- **Vector parser** runs first — exact, no GPU, best on clean CAD.
- Health check (`plan_health`): envelope sane? rooms? doors?
- If healthy → done. If flagged/failed → **ML reader** (CubiCasa demo / TF2
  commercial) runs on the raster, and the higher-scoring scene wins.
- **This is how output is BOTH improved and fixed:** good readings are kept
  untouched (never worse); bad ones are rescued by the model. Tag `meta.reader`.
- *Optional cross-check:* if vector and ML disagree wildly, mark low-confidence
  for review instead of silently trusting one.

## Stage 3 — ANALYZE (extract value + score)
- `pipeline.analyze` → one block: quality_score (0-100), needs_review, room
  count + types, doors/windows, carpet/built-up area, warnings.
- **Value:** every plan comes out measured and triaged, not a black box.

## Stage 4 — GENERATE (the deliverables)
- **3D GLB** (walls/rooms/openings/furniture) — the walkable model.
- **RERA area statement** (Excel) — the B2B document.
- **Photoreal** (Visualize) — SDXL conditioned on a **G-buffer** rendered from
  the 3D scene: depth (volume) + **segmentation** (what each surface is) +
  canny (edges). This is where the moat lives — see below.
- **Value per model:** SDXL paints; ControlNets *lock the geometry* so the
  render matches the real plan; the segmentation map is the unique signal only
  Drishti can produce.

## Stage 5 — LOG (the flywheel)
- Every parse (scene + analysis) → Supabase, fire-and-forget.
- **Value:** this is the dataset. It powers the review dashboard now and any
  future fine-tune later. Nothing is thrown away.

## Stage 6 — REVIEW → IMPROVE (close the loop)
- Dashboard reads the log: plans sorted by quality_score, a "needs_review"
  queue, reader used, per-plan numbers.
- A teammate opens it, sees the week's failures, and that IS the to-do list.
- Fixes feed back into the engine (a new general rule) or the corpus.
- **Value:** the product measurably improves over time, by a team, not by luck.

---

## How each model's MAX value is extracted
| Model | Job | Value lever |
|-------|-----|-------------|
| Vector parser | read clean CAD exactly | primary; free; deterministic |
| CubiCasa / TF2 | read what vector can't (photos, messy CAD) | fallback only on failures — pure upside |
| SDXL | paint photoreal | conditioned, not free-hand |
| ControlNet depth | lock 3D volume/perspective | rendered from real geometry |
| **ControlNet segmentation** | lock WHAT each surface is | **the moat — only Drishti has perfect labels** |
| ControlNet canny | crisp edges | cheap extra fidelity |
| SVD (optional) | walkthrough video | shareable output |

## The moat, concretely (Stage 4 detail)
Drishti built the scene, so its GLB meshes are NAMED (`floor`, `wall_N`,
`glass_N`, `furn_*`). We render a **segmentation pass** — each mesh flat-coloured
by its class — and feed it to a segmentation ControlNet alongside depth
(multi-ControlNet). SDXL then paints floor-as-floor, window-as-glass,
bed-as-bed, with no bleed. A photo-based competitor must *guess* that map with
another model; we KNOW it exactly. That's a structural advantage, and it
compounds: better conditioning → better renders → better logged data.

## Streamlining rules (keep it clean as it grows)
1. **One reader at a time** (vector + one ML model) — never run all readers.
2. **One generator per task** — SDXL + one ControlNet stack; the 12 GB GPU
   can't hold everything, and doesn't need to.
3. **Every stage degrades gracefully** — an analysis or render failure never
   breaks the parse.
4. **Everything scored + logged** — if it's not measured, it can't be improved.
5. **Improvements are general rules, validated on the corpus** (batch_eval),
   never per-plan hacks.
6. **Model-agnostic seams** — swap CubiCasa↔TF2, or any ControlNet, by config.

## Build status
Stages 1-5 built. Stage 6 (review dashboard) is the next surface. The
segmentation moat (Stage 4) is being wired now.
