# Drishti 3D — AI Perception Plan (2D plan → 3D model)

> **What this is:** the strategy for adding AI floor-plan recognition (CubiCasa-style)
> to the existing Drishti viewer. Written to be read by both non-engineers and Saswat.
> Decision-first; code comes after sign-off. **No existing code is abandoned.**
>
> Prepared: 2026-06-29.

---

## 0. TL;DR (read this if nothing else)

- **Keep the project. Improve one box.** Our architecture is already right
  (read plan → schema → build 3D → view). AI only upgrades the *"read the plan"* step.
- **No single model handles all our plan types.** We'll **route** each input to the
  best engine, and keep **manual Trace mode as the universal safety net**.
- **Fully-automatic is not realistic** for a customer product across messy inputs.
  The product model is **"AI draft + human fix"**, with a near-automatic fast path
  for clean inputs.
- **Start with a pretrained/hosted model (no GPU).** Measure on *our* plans. Only
  invest in training our own model if the numbers demand it.
- **Realistic timeline:** assisted prototype in ~2 weeks; reliable-on-our-plans in
  1–3 months.

---

## 1. The goal and the constraints

**Goal:** a real product where a user uploads a 2D floor plan and gets an explorable
3D model (+ a cinematic walkthrough video).

**Inputs we must accept (confirmed):**
1. Vector CAD PDFs (AutoCAD/Revit exports)
2. Clean raster images (sharp JPG/PNG)
3. Scanned / photographed plans (skewed, noisy)
4. Hand-drawn sketches

**Constraints:** in-house, browser-first feel, low/no recurring cost where possible,
must be reliable enough to put in front of customers.

---

## 2. What we already have (do NOT rebuild)

| Asset (in React Viewer) | Role | Keep? |
|---|---|---|
| `pipeline/builder.py` | Turns a plan (JSON) into a 3D `.glb` | **Keep** |
| `pipeline/SCHEMA.md` / reference `scene.json` | The data contract between "read" and "build" | **Keep (unify, see §6)** |
| R3F viewer + GSAP + camera rig | Renders + animates the 3D | **Keep** |
| Trace mode | Manual click-to-draw walls | **Keep — this is the safety net** |
| OpenCV.js in-browser detector | A rough automatic draft | **Keep as fallback** |
| `drishti` vector PDF parser (reference) | Reads CAD PDFs by layer; has real dimensions | **Promote to production for PDFs** |

The hard, valuable parts are done. AI is an *add-on*, not a restart.

---

## 3. CubiCasa — what it actually is (plain terms)

There are **two different "CubiCasa"** things:

- **CubiCasa the company (paid):** turns a *phone-camera walkthrough* into floor plans.
  It does **not** take our plan images/PDFs. Wrong tool for us → ignore.
- **CubiCasa5k the open model (free):** takes a *floor-plan image* and paints where the
  walls, rooms, doors and windows are. **This** is the relevant one.

**Honest accuracy expectations for the open model:**
- It's a smart **intern, not a finished worker**. Trained mostly on Finnish apartments.
- On **clean images similar to its training data:** finds most walls (~70–85%), rooms
  decent; **doors/windows less reliable** (small symbols).
- On **scanned / hand-drawn / very different styles:** noticeably worse.
- It outputs **pixels, not dimensions** — it never knows a wall is "3.2 m". **We must
  supply scale** separately. (Vector PDFs already contain real sizes; images need OCR
  of dimension text or a user-entered width.)
- **Conclusion:** great for a *draft a human checks*, not a reliable "upload → perfect 3D".

**Is cloning the pretrained model a good shortcut?** Partly. Pretrained weights exist
(skip training), but the code is old (Python 3.6 / PyTorch 1.0, unmaintained) and the
weights are tuned to their plans — likely needs **fine-tuning on our plans** for good
real-world results, which costs GPU + labelled data + time.

---

## 4. The key decision: a ROUTER, not one model

Send each input to the engine that's best at it:

```
            ┌──────────────────────────────┐
            │   1. INPUT ROUTER            │
            │   (what kind of plan is it?) │
            └──────────────────────────────┘
              │            │            │
     Vector PDF      Clean image    Scan / hand-drawn
              │            │            │
     ┌────────▼───┐  ┌─────▼──────┐  ┌──▼──────────────┐
     │ Vector     │  │ AI detector│  │ Cleanup → AI     │
     │ parser     │  │ (CubiCasa  │  │ (best effort)    │
     │ (drishti)  │  │  hosted)   │  │                  │
     │ +real dims │  │            │  │                  │
     └────────┬───┘  └─────┬──────┘  └──┬──────────────┘
              └────────────┼────────────┘
                           ▼
              ┌──────────────────────────┐
              │  scene.json (one schema) │  ◄── always editable in
              └──────────────────────────┘      MANUAL TRACE MODE
                           ▼
              builder.py → .glb → R3F viewer → walkthrough video
```

**The Trace editor sits under everything** as the correction layer and the fallback for
inputs the AI can't handle (esp. hand-drawn).

---

## 5. Your two "advise me" questions — my recommendation

**Automation level → "AI draft + human fix".**
Promising fully-automatic across scans and hand-drawn plans will break customer trust.
Offer a **near-automatic fast path** for clean PDFs/images, and **draft+correct** for the
rest. The Trace editor is what makes this safe.

**Resources → pretrained/hosted first, measure, then decide.**
Don't buy a GPU or label data yet. Call a **hosted CubiCasa5k (e.g. Roboflow) via API**,
measure accuracy on *our real plans*, and only invest in fine-tuning if it underperforms
(probable for Indian/commercial/scanned styles). Decide with evidence.

---

## 6. Codebase changes (all additive, low risk)

**Phase 0 (do first — your roadmap already flags it):**
Unify the two schemas into **one `scene.json`** + pick one unit/coordinate convention.
Everything depends on this; getting it wrong causes silent geometry bugs.

**Then add:**
- `server/` — a small **FastAPI** backend (local in dev, same code deploys to cloud in
  prod). Endpoints: detect (image → `scene.json`) and build (`scene.json` → `.glb` via
  the existing `builder.py`). *(Scaffold already started.)*
- An **input router** (decides PDF vs image vs scan).
- **Hosted detector call** feeding `scene.json`.
- **Scale handling:** real dimensions from vector PDFs; OCR/user-input for images.
- **Video capture** in the browser (record the canvas during a GSAP camera fly-through).

**Untouched:** `builder.py`, the viewer, Trace mode, the UI. The dev→prod move is just
config (point the frontend at the deployed backend URL); no code rewrite.

**Architecture cut:** drop Python-OCC, Blender, Unreal, IFC from the original diagram —
they fight the "browser/in-house" goal and balloon scope. Trimesh + Three.js already
cover geometry + rendering.

---

## 7. Alternatives considered

| Option | Effort | Cost | Accuracy on our plans | Verdict |
|---|---|---|---|---|
| Hosted CubiCasa5k (Roboflow API) | Low | Low/usage | Medium (clean), low (messy) | **Start here** |
| Vision LLM (Claude/GPT vision) | Low | Usage | Medium, imprecise coords | Good for door-finding assist |
| Improve our OpenCV detector | Medium | Free | Low–medium | Keep as fallback |
| Train/fine-tune our own model | High | GPU + labelling | Best *if* done well | Only if measured need |
| Vector parser (drishti) for PDFs | Medium | Free | **High for CAD PDFs** | **Use for PDFs** |
| Paid service (e.g. GetFloorPlan) | Low | ~$/plan recurring | High | Backup / benchmark |

---

## 8. Phased roadmap & timeline

- **Weeks 1–2 — Prove it cheaply.** Backend + input router + hosted detector as an
  *assist* on top of Trace mode. Measure accuracy on 10–20 real plans.
  *Exit:* numbers that say "good enough on clean inputs?" yes/no.
- **Weeks 3–6 — Make it solid.** Production vector-PDF path; scale handling (real dims +
  OCR); polished draft→correct UX; near-automatic fast path for clean inputs.
  *Exit:* a customer can upload a clean plan and get a usable 3D with minor fixes.
- **Months 2–3+ — Only if needed.** Collect/label plans, fine-tune our own model for our
  styles (scanned/Indian/commercial). *Exit:* measurable accuracy lift on hard inputs.

---

## 9. How we test accuracy (and who's "responsible")

Grade it like a student against an answer key:
- **Ground-truth set:** plans where we already know correct walls/doors/room sizes.
- **Metrics:** % of walls found, % of doors/windows found, dimensional error in cm,
  plus an eyeball "does the 3D look right" check.
- **Human backstop:** Trace mode corrects whatever the AI misses — this is what makes it
  trustworthy enough to ship.
- **Owner:** define one person who runs this test set each time the model/router changes.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| AI weak on scanned/hand-drawn | Router + manual Trace fallback; set expectations |
| No real-world scale from images | OCR dimension text / user-entered width; PDFs carry real dims |
| Old CubiCasa code (Py3.6/Torch1.0) | Use hosted model first; containerise only if we self-host |
| Recurring API cost at scale | Measure usage; move to self-hosted/own model if volume justifies |
| Schema fragmentation | Phase 0 unification before any new feature |
| Over-engineering (Blender/Unreal) | Explicitly out of scope; lean Trimesh + Three.js |

---

## 11. Open decisions needed from you / Saswat

1. Sign-off to promote the `drishti` vector parser into production for PDFs.
2. Confirm "AI draft + human fix" as the product model (vs promising fully-automatic).
3. Confirm "hosted first, fine-tune later only if measured" resourcing.
4. Pick the canonical unit + coordinate system (metres, Y-up suggested).
5. Budget tolerance for per-plan API cost during the prototype.

---

*Next step after sign-off: Phase 0 (schema unification), then the Weeks 1–2 prototype.*
