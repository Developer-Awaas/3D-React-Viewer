// ── Floor-plan data ──────────────────────────────────────────────────────────
// This is the bridge from a 2D plan to 3D: the plan is described as a list of
// wall SEGMENTS in metres (start point -> end point), in the SAME coordinate
// system the plan image was drawn in (X: -5..5, Z: -4..4). To trace your own
// plan, you'd read coordinates off the drawing against its scale bar and list
// them here — that's the manual "develop the plan" step.

export const PLAN = {
  scale: 50,        // px per metre the image was drawn at
  imgW: 620,
  imgH: 520,
  // full image size in metres = underlay plane size (includes the margin)
  widthM: 620 / 50, // 12.4
  heightM: 520 / 50 // 10.4
}

export const WALL_HEIGHT = 2.5  // standard generated-wall height (metres)
export const WALL_T = 0.2

// [x1, z1, x2, z2] in metres. Gaps between segments = doorways/openings.
export const SEGMENTS: [number, number, number, number][] = [
  [-5, 4, -1, 4],  // front wall, left of entrance (gap x:-1..1 = doorway)
  [ 1, 4,  5, 4],  // front wall, right of entrance
  [ 5, 4,  5, -4], // right wall
  [ 5, -4, -5, -4],// back wall
  [-5, -4, -5, 4], // left wall
  [ 1, 4,  1, 0],  // interior partition (vertical)
  [ 1, 0,  5, 0],  // interior partition (horizontal)
]
