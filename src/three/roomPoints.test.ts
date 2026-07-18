import { describe, expect, it } from 'vitest'
import { EYE_FT, FT, roomView, roomWorldPoint, type FrameInfo } from './roomPoints'

const FRAME: FrameInfo = {
  center: [0, 1.5, 0],
  size: [12, 3, 8],
  scale: 0.35,                 // Model shrank the building to fit the stage
  position: [-6, 0, -4],       // and slid it so its centre sits on origin
}

describe('roomWorldPoint', () => {
  it('applies feet->metres, model scale and group offset', () => {
    const p = roomWorldPoint({ x: 10, y: 20 }, FRAME, 5)
    expect(p[0]).toBeCloseTo(-6 + 0.35 * 10 * FT, 6)
    expect(p[1]).toBeCloseTo(0 + 0.35 * 5 * FT, 6)
    expect(p[2]).toBeCloseTo(-4 + 0.35 * 20 * FT, 6)
  })

  it('eye height scales WITH the building (small model = low eye)', () => {
    const big = roomWorldPoint({ x: 0, y: 0 }, { ...FRAME, scale: 1 })
    const small = roomWorldPoint({ x: 0, y: 0 }, { ...FRAME, scale: 0.2 })
    expect(small[1]).toBeLessThan(big[1])
    expect(big[1]).toBeCloseTo(EYE_FT * FT, 6)
  })
})

describe('roomView', () => {
  it('stands at eye height and looks toward the building centre', () => {
    const v = roomView({ x: 30, y: 20 }, FRAME)
    expect(v.position[1]).toBeCloseTo(0.35 * EYE_FT * FT, 6)
    // target must sit BETWEEN the eye and the centre (horizontally)
    const toCentre = Math.hypot(FRAME.center[0] - v.position[0], FRAME.center[2] - v.position[2])
    const toTarget = Math.hypot(v.target[0] - v.position[0], v.target[2] - v.position[2])
    expect(toTarget).toBeGreaterThan(0.3)
    expect(toTarget).toBeLessThan(toCentre + 1e-6)
    // and slightly below eye level, so the view reads natural
    expect(v.target[1]).toBeLessThan(v.position[1])
  })

  it('gazes toward the FARTHEST other beacon (through the building)', () => {
    const here = { x: 5, y: 5 }
    const near = { x: 8, y: 5 }
    const far = { x: 35, y: 22 }
    const v = roomView(here, FRAME, [near, far])
    const eye = roomWorldPoint(here, FRAME)
    const farW = roomWorldPoint(far, FRAME)
    // direction of target must match direction to the far beacon
    const want = Math.atan2(farW[2] - eye[2], farW[0] - eye[0])
    const got = Math.atan2(v.target[2] - v.position[2], v.target[0] - v.position[0])
    expect(got).toBeCloseTo(want, 5)
  })

  it('survives a room exactly at the centre (no NaN direction)', () => {
    const v = roomView(
      { x: (FRAME.center[0] - FRAME.position[0]) / (FRAME.scale * FT),
        y: (FRAME.center[2] - FRAME.position[2]) / (FRAME.scale * FT) },
      FRAME,
    )
    expect(Number.isFinite(v.target[0])).toBe(true)
    expect(Number.isFinite(v.target[2])).toBe(true)
  })
})
