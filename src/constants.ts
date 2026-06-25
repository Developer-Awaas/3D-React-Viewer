// ─────────────────────────────────────────────────────────────────────────────
// ROOM DIMENSIONS — single source of truth.
// Change a number here and the whole room updates. Keeping measurements in named
// constants (not sprinkled through the code) is exactly what the brief asks for.
// Units are METRES by our own convention (Three.js itself is unitless).
// ─────────────────────────────────────────────────────────────────────────────
export const ROOM = {
  width: 5,          // size along the X axis (left ↔ right)
  depth: 5,          // size along the Z axis (front ↔ back)
  height: 3,         // size along the Y axis (floor ↔ ceiling)
  wallThickness: 0.1 // how thick the floor/walls/ceiling slabs are
}

// The ceiling closes the box, which is realistic but hides the interior when you
// orbit from above. We're building an open-top "doll-house" view so you can see
// the floor materials and shadows. Flip to `true` to seal the room.
export const INCLUDE_CEILING = false

// Window opening cut into the back wall (used by the demo scene).
export const WINDOW = {
  width: 1.8,      // opening width (X)
  height: 1.3,     // opening height (Y)
  sill: 0.9,       // height of the window's bottom edge above the floor
}
