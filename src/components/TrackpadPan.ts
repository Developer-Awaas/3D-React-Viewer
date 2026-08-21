import { Vector3 } from 'three'
import type { PerspectiveCamera } from 'three'

/**
 * TWO-FINGER TRACKPAD DRAG = PAN (20 Aug 2026).
 *
 * On a Mac a two-finger drag IS the scroll gesture, and OrbitControls maps
 * every wheel event to DOLLY — so the trackpad could only zoom toward the
 * fixed orbit centre, which is exactly what put the far rooms out of reach.
 * A pinch arrives as a wheel event with ctrlKey set, so the two gestures are
 * separable and the mapping becomes the familiar one: two fingers pan, pinch
 * zooms, scroll wheel still zooms.
 *
 * Telling a MOUSE wheel from a trackpad drag has no API: mice send coarse
 * discrete steps (|deltaY| >= 40, deltaX exactly 0), trackpads send fine
 * fractional deltas and usually some deltaX. That heuristic is the only
 * signal browsers expose.
 */
export function isTrackpadPan(e: WheelEvent): boolean {
  if (e.ctrlKey) return false                 // pinch-zoom
  return e.deltaX !== 0 || Math.abs(e.deltaY) < 40
}

/** Pan controls.target + camera by a screen-space delta, in world units. */
export function panBy(camera: PerspectiveCamera, controls: any, dx: number, dy: number) {
  const t = controls.target as Vector3
  const dist = camera.position.distanceTo(t)
  // world units per pixel at the TARGET's depth, so a pan tracks the surface
  // under the fingers instead of drifting with distance
  const k = (2 * dist * Math.tan((camera.fov * Math.PI) / 360)) /
    (controls.domElement?.clientHeight || 800)
  const right = new Vector3().setFromMatrixColumn(camera.matrix, 0)
  const up = new Vector3().setFromMatrixColumn(camera.matrix, 1)
  const move = right.multiplyScalar(-dx * k).add(up.multiplyScalar(dy * k))
  camera.position.add(move)
  t.add(move)
  controls.update()
}
