# Drishti 3D — Production Migration Roadmap

**Goal:** converge on a *single* production codebase. **React Viewer** (`3D React Viewer/`, OneDrive) is the production application and the migration **target**. **Project Viewer** (`3D Project viewer/drishti/`) is the architectural **reference** and the migration **source**. At the end of this roadmap, every valuable module from Project Viewer lives inside React Viewer (or has been deliberately dropped), and the Project Viewer repo is archived.

> Naming rule kept throughout: *React Viewer* = production/target, *Project Viewer* = reference/source. Files are never mixed; each migration item states why it crosses over.

---

## 1. Method — how items are ranked

Each candidate is scored on four axes, Low / Medium / High:

- **Business value (BV):** how much it moves Drishti toward reliable, automatic, semantic 2D→3D on real CAD plans.
- **Implementation effort (Eff):** engineering work to land it in production quality inside React Viewer.
- **Dependencies (Dep):** what must exist first (other items, a runtime decision, a library).
- **Risk:** likelihood of breaking things, blocking on unknowns, or needing rework. Includes "is it even runnable in the browser."

A rough **priority** is derived as high BV + low Eff + low Risk + few Deps first.

---

## 2. Module-by-module inventory

### 2a. Project Viewer (reference) → what migrates into React Viewer

| # | Project Viewer module | What it does | Target in React Viewer | Migrate? |
|---|---|---|---|---|
| M1 | `parser/SCHEMA.md` + `scene.json` | Semantic data contract: walls (ext/int), openings (window/door + hinge/swing + along/z), columns, ducts, furniture, meta/scale/warnings | Becomes the **canonical internal data model** for Convert, replacing flat `plan.json` and superseding `pipeline/SCHEMA.md` | **Yes — keystone** |
| M2 | `viewer/src/geometry.ts` (`wallBoxes`) | Tiles a wall into solid boxes that skip opening voids; door hinge side handled | New geometry util feeding `TraceScene`; gives React Viewer **real doors/windows** | **Yes** |
| M3 | `viewer/src/Scene.tsx` | Renders walls + openings + columns + ducts + furniture from `scene.json`; ext/int thickness; furniture colour map | Upgrade `TraceScene` / new `SceneView` to render semantic elements, not just flat wall lines | **Yes** |
| M4 | `parser/build_model.py` | **Vector CAD-layer reader** (PyMuPDF): reads PDF by layer → wall mask → contours → shapely polygons → extruded GLB; scale from column box | The robust "read the plan" engine. Must be re-homed as an **offline/server parsing step that emits `scene.json`** (cannot run in-browser as-is) | **Yes — highest value, highest risk** |
| M5 | `parser/parse_plan.py` (raster path) | OpenCV walls with **thickness→ext/int** classification; **column vs duct** detection; shared-schema assembly | Port the *classification ideas* into React Viewer's in-browser `detect.worker.js` (which today only emits undifferentiated wall lines) | **Yes (ideas, not file)** |
| M6 | `parser/parse_plan.py` / `parse_scale.py` (OCR) | Auto-scale by OCR-ing dimension text (`12'5" x 10'0"`) and pairing with room pixel width | Optional **auto-scale** in Convert via Tesseract.js, replacing the manual "building width (m)" input | **Yes (later)** |
| M7 | Units & coordinate convention | Feet, z-up, origin bottom-left, plan-Z→three-Y at render | Not a file — a **reconciliation task** vs React Viewer's metres/Y-up/origin-centred. Pick one canon | **Yes — decision** |
| M8 | `tools/scene_to_glb.py`, `tools/render_preview.py` | Offline `scene.json`→GLB and matplotlib preview | Low priority; React Viewer renders live in R3F and can export GLB client-side | **Optional** |
| — | `viewer/src/App.tsx`, `Scene` shell, floor buttons | Bare R3F shell, 3 floor-colour buttons | **Do not migrate** — React Viewer's UI is strictly superior | No |

### 2b. React Viewer (production) cleanup needed to reach one clean codebase

These are not migrations *from* the reference, but are required for a single, maintainable final codebase.

| # | Item | Why |
|---|---|---|
| C1 | Delete dead/duplicate modules: `AutoPlan.tsx`, `FloorPlanUnderlay.tsx`, `WallsFromPlan.tsx`, `ImportPanel.tsx`, `ImportScene.tsx`, `TracePanel.tsx`, `ViewerPanel.tsx`, `floorplan.ts`, plus the unused main-thread `cv/detectWalls.ts` path + `loadOpenCV.ts`, and dead logic in `trace/useTrace.ts` | They're superseded and not imported; they confuse the "single codebase" and any schema migration |
| C2 | Reconcile the **two existing schemas**: React Viewer's own `pipeline/SCHEMA.md` (room-centric) vs the migrated `scene.json` (parse-centric). Unify to one | Two schemas in one repo is the exact fragmentation we're trying to end |
| C3 | Extract orchestration out of the monolithic `App.tsx` (Convert state machine, detection trigger) into hooks/modules | Makes the schema swap and the parser integration tractable and testable |

---

## 3. Ranked migration backlog (master table)

| Item | Summary | BV | Eff | Dep | Risk | Priority |
|---|---|----|----|----|----|----|
| M7 | Units/coords canon decision | High (enabler) | Low | none | Med (pervasive) | **P0** |
| M1 | `scene.json` as canonical data model | High | Med | M7 | Med | **P0** |
| C1 | Remove dead/duplicate modules | Med (hygiene) | Low | none | Low | **P0** |
| M2 | Opening-aware `wallBoxes` geometry | High | Low | M1 | Low | **P1** |
| M3 | Semantic renderer (cols/ducts/furniture/openings) | High | Med | M1, M2 | Low | **P1** |
| C2 | Unify the two schemas | Med | Med | M1 | Med | **P1** |
| C3 | De-monolith `App.tsx` | Med | Med | M1 | Low | **P1/2** |
| M5 | Raster ext/int + column/duct detection | Med | Med | M1, worker | Med | **P2** |
| M6 | OCR auto-scale (Tesseract.js) | Med | Med | M1, OCR lib | Med | **P2** |
| M4 | Vector CAD-layer parser → `scene.json` | **Very High** | High | M1, run-model decision | **High** | **P3** |
| M8 | Offline `scene_to_glb` / preview tools | Low | Low | M1 | Low | **P4 (opt)** |

Rationale for the ordering: the schema (M1) and the unit/coordinate canon (M7) gate everything, so they go first alongside cheap hygiene (C1). The pure-TypeScript wins (M2, M3) deliver visible product value — real doors, windows, columns, furniture — at low risk before any Python touches the browser. The hard, high-value bet (M4, the vector parser) is sequenced last because it depends on an unresolved runtime decision and is the largest source of risk.

---

## 4. Phased roadmap

### Phase 0 — Foundations & decisions (unblocks everything)
**Items:** M7, M1, C1.
**Work:** choose the canonical unit + coordinate system; define the `scene.json` TypeScript types in React Viewer as the single source of truth; delete dead modules.
**Exit criteria:** React Viewer compiles with one shared `Scene` type; no orphan files; a documented units/coords decision.

### Phase 1 — Semantic rendering (visible product value, no Python)
**Items:** M2, M3, plus C2/C3 as enablers.
**Work:** port `wallBoxes` (openings cut as voids); upgrade the Convert scene to render walls-by-thickness, columns, ducts, furniture, doors, windows from `scene.json`; map old flat segments into the new model.
**Exit criteria:** a hand-written or fixture `scene.json` renders in Convert with real openings and semantic elements; Convert's editor reads/writes the new model; export emits `scene.json`.

### Phase 2 — Detection upgrades (better in-browser drafts)
**Items:** M5, M6.
**Work:** extend `detect.worker.js` to classify ext/int by wall thickness and detect columns/ducts, emitting partial `scene.json` instead of flat lines; add optional Tesseract.js auto-scale from dimension text.
**Exit criteria:** uploading a clean raster plan yields a semantic draft (typed walls + columns) with scale auto-suggested; manual width remains as override.

### Phase 3 — Vector CAD-layer parsing (the robustness leap)
**Items:** M4 (after the run-model decision in §6).
**Work:** re-home the PyMuPDF layer reader as a clean, path-independent module that outputs `scene.json` (strip the hard-coded absolute paths; make scale deterministic). Wire it into React Viewer via the chosen runtime (offline CLI, local helper, or server endpoint).
**Exit criteria:** a real vector PDF (e.g. "TYPICAL FLOOR PLAN") produces a `scene.json` that renders in Convert without hand-tracing; trace-fix is used only for corrections.

### Phase 4 — Consolidation & retirement
**Items:** M8 (optional), final cleanup.
**Work:** fold any remaining useful offline tooling; unify docs; archive the Project Viewer repo with a pointer to its migrated modules.
**Exit criteria:** single repo, single schema, single viewer, single parser pipeline; Project Viewer is read-only/archived.

---

## 5. Schema & units reconciliation (the keystone detail)

Three things must be decided once and applied everywhere, because every other item depends on them:

1. **Canonical schema:** adopt Project Viewer's `scene.json` (richer: axis, ext/int thickness, openings with `along`/`z`/hinge/swing, columns, ducts, furniture, meta/scale/warnings) as the canonical model, and migrate React Viewer's room-centric `pipeline/SCHEMA.md` concepts (rooms, per-room walls) into it rather than keeping both.
2. **Units:** React Viewer is **metres**; Project Viewer is **feet**. Pick one as the stored unit (recommend metres for the app, with feet/inches only as a display + input format), and define a single conversion boundary.
3. **Coordinates:** React Viewer uses origin-centred, Y-up; Project Viewer stores origin-bottom-left, z-up and maps z→Y at render. Choose one storage convention and one render mapping, documented in the `scene.json` types.

Getting these wrong is the most likely cause of silent geometry bugs, so they are Phase 0, not later.

---

## 6. Open decisions (blocking — needed before Phase 3, ideally Phase 0)

1. **Where does the vector parser run?** It is Python (PyMuPDF/OpenCV/shapely/trimesh) and cannot run in the browser as-is. Options: (a) offline CLI that the user runs to produce `scene.json`, (b) a local helper/service the app calls, (c) a hosted endpoint, (d) long-term port to WASM/JS. This decision gates M4 and shapes the product's "in-house, client-side" positioning.
2. **Canonical units & coordinates** (see §5) — owner decision, low effort, high blast radius.
3. **Team ownership:** Project Viewer is the senior's code. Confirm sign-off to absorb and then archive it, and who owns the parser module post-migration.
4. **Scale strategy:** keep manual width, OCR auto-scale, or parser-derived scale as primary? Affects M6 vs M4 emphasis.

---

## 7. Risk register

| Risk | Where | Mitigation |
|---|---|---|
| Python parser can't run client-side | M4 | Resolve run-model decision (§6.1) before Phase 3; keep raster worker as browser fallback |
| `build_model.py` has hard-coded absolute paths + provisional (column-derived) scale | M4 | Refactor to a path-independent module with deterministic, text-derived scale before integration |
| Unit/coord mismatch causes silent geometry errors | M1, M2, M3 | Decide canon in Phase 0; add fixture `scene.json` + golden-render tests |
| Two schemas linger and re-fragment the repo | C2 | Make schema unification an explicit Phase 1 exit criterion |
| OneDrive sync serves stale/truncated files to tooling | whole React Viewer repo | "Always keep on this device"; consider moving the production repo off a sync-root, or verify via the editor not raw FS |
| `App.tsx` monolith makes schema swap risky | C3 | Extract Convert state machine early (Phase 1) |
| Scope creep into full ML auto-detection | beyond M4 | Explicitly out of this roadmap; trace-fix remains the correctness backstop |

---

## 8. Definition of done (single final codebase)

- One repo (React Viewer) containing: one `scene.json` schema, one semantic renderer (openings, columns, ducts, furniture), one detection path (in-browser raster worker) plus one re-homed vector parser emitting the same schema, and the existing premium UI + GLB viewer.
- No dead/duplicate modules; `App.tsx` orchestration extracted into hooks/modules.
- A documented units/coordinate canon and a single conversion boundary.
- Project Viewer archived, with a migration note mapping each of its modules (M1–M8) to its new home.

---

*Prepared as a read-only planning artifact. No application code was modified. Next step is to confirm the open decisions in §6, especially the parser run-model and the units canon, before starting Phase 0.*
