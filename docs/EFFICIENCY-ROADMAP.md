# Efficiency & accuracy roadmap — architect analysis (23 Jul 2026)

"Efficiency %" = carpet ÷ super built-up. It reads 0% ONLY when **rooms = 0**,
and rooms = 0 whenever the wall lines don't close into pockets. So the biggest
lever on the number is ROOM-DETECTION robustness, not the area math. Gaps below
are ranked by impact on that number and on overall accuracy.

## The pipeline (where each gap sits)
INGEST → **READ (parse walls/rooms/openings)** → **ANALYZE (area/vastu/boq)** →
GENERATE (3D + render) → LOG/LEARN (Plan Doctor).

---

## G1 — Wall-gap healing for fragmented plans  ★ highest impact
How it works now: rooms are found as enclosed pockets inside the wall mask. On
clean CAD this works; on fragmented sheets (343) or missing-wall-layer sheets
(BRICK WORK) the walls have gaps, no pocket forms, rooms = 0 → efficiency 0%.
There is envelope sealing (DRISHTI_SEAL) but walls_poly stays UNSEALED to
protect stairs, so room-detection still leaks.
Improve: a room-detection-only "gap bridge" — morphological close + snap wall
endpoints within a small tolerance (e.g. ≤ 6 in) to seal hairline gaps, run on
a SEPARATE mask used only for rooms (stairs stay safe). Corpus-gate hard: must
lift 343/BRICK WORK to rooms > 0 without changing the 5 clean plans. Effort: M.

## G2 — OCR room labels not active
How it works now: room typing reads live PDF text. Many CAD exports OUTLINE
text (letters become linework) → no readable label → untyped rooms → Vastu &
furniture skip them. OCR (tesseract) code EXISTS but (a) tesseract isn't
installed on the box, (b) it only runs when ZERO live labels are found.
Improve: install tesseract (user-side, 5 min) + let OCR fill the rooms that
live text missed even when some labels exist (additive, not all-or-nothing).
Effort: S (code) + user install.

## G3 — Scale auto-correction
How it works now: when there's no dimension text, scale is guessed from
"columns = 12 inch". A 9-inch-column plan is then ~33% off, so every ft/sqft/₹
is wrong. A door-width sanity check exists but only WARNS.
Improve: cross-check the guessed scale against median door width (~2.5–3.5 ft);
if it disagrees, auto-correct the scale (or return needs_review) instead of
shipping a silently-wrong number. Effort: S–M.

## G4 — Fixture furniture from ML icons  ★ cheap win, data already computed
How it works now: CubiCasa detects Toilet, Sink, Bathtub, Closet, Fireplace
icons — we use ONLY Door/Window and throw the rest away. Bathrooms/kitchens on
the photo path come out empty.
Improve: now that E5 opened the room pipe, map those icons to furniture pieces
and stage them (toilet→commode, sink→basin…). Pure win, no new model. Effort: S.

## G5 — Cross-reader opening fusion
How it works now: best-of picks ONE reader and discards the other's doors/
windows entirely (E5 fused room-TYPES, not openings).
Improve: union doors/windows across CubiCasa + tf2 with agreement voting, so a
door found by either reader survives. Effort: M.

## G6 — Server-side depth + segmentation render feed (the "moat")
How it works now: SDXL renders use depth/seg maps ONLY if the frontend uploads
them; otherwise it falls back to Canny edges (weaker geometry lock). No server
generates the maps from the 3D scene.
Improve: render depth + surface-class maps from the GLB server-side and feed
ControlNet directly — crisper, geometry-locked renders every time. Effort: L.

## G7 — User correction / editing  ★ turns a wrong auto-number into a trusted one
How it works now: if the parser mis-types a room or guesses scale wrong, the
user can't fix it — the wrong number ships.
Improve: a lightweight "correct this" layer — set true plan width, rename a
room, delete a phantom room — re-runs area/vastu/boq from the corrected scene.
Also the best ground-truth signal for the learning loop. Effort: M (UI + a
recompute endpoint).

## G8 — Multi-floor stacking
How it works now: one upload = one floor. A G+3 building can't be assembled.
Improve: upload N floors, stack them at wall height, unified walkthrough.
Effort: L. (v2 candidate.)

## G9 — Feedback button (Plan Doctor phase 2)
"Looks right / looks wrong" per parse → real ground truth into LEARNINGS.md,
beyond the sanity bands. Effort: S. (Already planned.)

## G11 — E4 parse-once cache (performance, not accuracy)
/scene and /scene.glb each re-parse the same PDF. Cache by upload hash → ~2×
faster uploads. Effort: M. Deferred to post-launch.

---

## Recommended build order (accuracy-first)
1. **G1 wall-gap healing** — kills the 0% swings at the root. (corpus-gated)
2. **G4 fixture furniture** — cheap, visible, data already there.
3. **G3 scale auto-correct** — stops silently-wrong numbers.
4. **G2 OCR activation** — recover typed rooms on outlined-text plans.
5. G5 opening fusion · G7 user correction · G6 server seg/depth · G8 multi-floor.
Each ships tested + corpus-gated; the Plan Doctor grade is the before/after meter.
