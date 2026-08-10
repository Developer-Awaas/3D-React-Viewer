// ─────────────────────────────────────────────────────────────────────────────
// DEPTH LAYERS — the three flat surfaces that live at the bottom of the stage.
//
// THE BUG (fixed 2026-08-10): all three of them sat at exactly y = 0.
//   1. the big plot/ground plane          (App.tsx, plan + viewer modes)
//   2. drei's <ContactShadows> plane      (transparent, depthWrite=false)
//   3. the plan model's floor-slab UNDERSIDE — Model.tsx drops the loaded GLB
//      so its bounding-box min.y lands on y = 0, and the slab's bottom face IS
//      that min.y (server/scene_to_glb.py builds the slab from -0.25ft to 0ft).
// Three coplanar surfaces cannot be ordered by a depth buffer: which one wins a
// given pixel comes down to float rounding in the projection, so the pattern
// re-rolls every time the camera moves — the "flicker on orbit/zoom".
//
// THE FIX is two-part, because a vertical gap alone is not enough:
//   * A real vertical separation (below) gives the surfaces an unambiguous
//     order in world space — easy to see, easy to reason about.
//   * GROUND_DEPTH_BIAS additionally biases the ground plane in DEPTH-BUFFER
//     units. That matters because the depth resolution at distance z is roughly
//     z² / (near · 2^24): with the app's near = 0.1, one depth step is ~0.5 mm
//     at 30 m but ~6 mm at 100 m. A fixed millimetre gap therefore silently
//     dissolves as you zoom out — which is exactly when users reported the
//     worst flicker. polygonOffset is expressed in depth units, so it holds at
//     every zoom level and every grazing angle.
//
// Units are METRES (the app's world-unit convention, see constants.ts).
// These are RENDERING offsets only — no plan geometry, area or dimension is
// derived from them. MODEL_BASE_Y stays 0 on purpose, so the plan model, its
// camera framing, the room beacons and the roof all sit exactly where they did.
// ─────────────────────────────────────────────────────────────────────────────

/** Smallest separation we consider safe at the zoom levels the app allows. */
export const MIN_DEPTH_GAP = 0.005 // 5 mm

/** The plot/ground plane — sunk below everything else. */
export const GROUND_Y = -0.02

/** The contact-shadow plane — on the ground, under the building. */
export const CONTACT_SHADOW_Y = -0.01

/** Where the plan model's floor slab rests. Unchanged: this is the datum. */
export const MODEL_BASE_Y = 0

/**
 * Spread on the ground plane's material. Positive factor/units push the polygon
 * AWAY from the camera in depth-buffer units, so the ground always loses a
 * depth tie to whatever is drawn on top of it.
 */
export const GROUND_DEPTH_BIAS = {
  polygonOffset: true,
  polygonOffsetFactor: 1,
  polygonOffsetUnits: 1,
} as const

/**
 * Same trick, opposite sign, for COLUMNS (server/scene_to_glb.py builds them
 * 0 → wall_height_ft, exactly like the walls) — so a column embedded in a wall
 * has a top face coplanar with the wall's top face and the two flicker. There
 * is no vertical gap to give here: the two tops genuinely ARE at the same
 * height and moving either one would change the building. Negative offset
 * pulls the column TOWARDS the camera in depth-buffer units, so it wins the
 * tie at every zoom and every grazing angle. Free-standing columns share their
 * top with nothing, so the bias is a no-op for them.
 */
export const COLUMN_DEPTH_BIAS = {
  polygonOffset: true,
  polygonOffsetFactor: -1,
  polygonOffsetUnits: -1,
} as const

/** Bottom-to-top stack. Neighbouring layers must clear MIN_DEPTH_GAP. */
export const DEPTH_STACK = [GROUND_Y, CONTACT_SHADOW_Y, MODEL_BASE_Y] as const

/** Gaps between neighbouring layers, bottom-to-top. Pure, so it's testable. */
export function depthStackGaps(stack: readonly number[] = DEPTH_STACK): number[] {
  return stack.slice(1).map((y, i) => y - stack[i])
}
