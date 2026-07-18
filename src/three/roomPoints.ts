import type { Room } from '../api/scene'

// Walk-inside maths. The backend gives room points in PLAN FEET (origin
// bottom-left). The GLB maps feet -> metres (x, height, y->Z) and Model.tsx
// then scales + repositions the whole group to fit the stage — so a room
// point must go through the same transform to land in world space.

export const FT = 0.3048
export const EYE_FT = 5.2 // standing eye height, scales with the building

export type FrameInfo = {
  center: [number, number, number]
  size: [number, number, number]
  scale: number                       // group scale Model applied
  position: [number, number, number]  // group position Model applied
}

export type View = { position: [number, number, number]; target: [number, number, number] }

/** Plan-feet point -> world position at a given height (feet). */
export function roomWorldPoint(
  room: Pick<Room, 'x' | 'y'>,
  f: FrameInfo,
  heightFt = EYE_FT,
): [number, number, number] {
  return [
    f.position[0] + f.scale * room.x * FT,
    f.position[1] + f.scale * heightFt * FT,
    f.position[2] + f.scale * room.y * FT,
  ]
}

/** Camera view standing IN the room at eye height. Gaze: toward the
 * FARTHEST other room beacon — that direction runs through the building's
 * open spaces (doorway sightlines), instead of nose-first into the nearest
 * wall. Falls back to the building centre when it's the only room.
 * Dragging the orbit target (~1.5 m ahead) then feels like looking around. */
export function roomView(
  room: Pick<Room, 'x' | 'y'>,
  f: FrameInfo,
  others: Pick<Room, 'x' | 'y'>[] = [],
): View {
  const eye = roomWorldPoint(room, f, EYE_FT)
  let dx: number
  let dz: number
  let far: Pick<Room, 'x' | 'y'> | null = null
  let best = 0
  for (const o of others) {
    const d = Math.hypot(o.x - room.x, o.y - room.y)
    if (d > best) { best = d; far = o }
  }
  if (far) {
    const p = roomWorldPoint(far, f, EYE_FT)
    dx = p[0] - eye[0]
    dz = p[2] - eye[2]
  } else {
    dx = f.center[0] - eye[0]
    dz = f.center[2] - eye[2]
  }
  const L = Math.hypot(dx, dz)
  if (L < 1e-3) { dx = 1; dz = 0 } else { dx /= L; dz /= L }
  const ahead = 1.5 * f.scale + 0.4   // look distance scales with the model
  return {
    position: eye,
    target: [eye[0] + dx * ahead, eye[1] - 0.08, eye[2] + dz * ahead],
  }
}
