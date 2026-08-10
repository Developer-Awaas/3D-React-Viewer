import { describe, expect, it } from 'vitest'
import {
  COLUMN_DEPTH_BIAS,
  CONTACT_SHADOW_Y,
  DEPTH_STACK,
  GROUND_DEPTH_BIAS,
  GROUND_Y,
  MIN_DEPTH_GAP,
  MODEL_BASE_Y,
  depthStackGaps,
} from './depthLayers'

// Regression guard for the z-fighting fix (2026-08-10). The ground plane, the
// contact-shadow plane and the plan model's floor slab all used to sit at
// exactly y = 0, so the depth buffer could not order them and the surfaces
// flickered on every orbit/zoom. If anyone collapses them back together, or
// shaves the separation down to something the depth buffer can't resolve when
// the camera is far out, these tests fail instead of the bug coming back.
describe('depth layers', () => {
  it('never puts two surfaces on the same plane', () => {
    expect(new Set(DEPTH_STACK).size).toBe(DEPTH_STACK.length)
  })

  it('stacks ground -> contact shadow -> model floor, bottom to top', () => {
    expect(GROUND_Y).toBeLessThan(CONTACT_SHADOW_Y)
    expect(CONTACT_SHADOW_Y).toBeLessThan(MODEL_BASE_Y)
    expect(depthStackGaps().every((g) => g > 0)).toBe(true)
  })

  it('leaves every neighbouring pair at least MIN_DEPTH_GAP apart', () => {
    for (const gap of depthStackGaps()) expect(gap).toBeGreaterThanOrEqual(MIN_DEPTH_GAP)
  })

  it('keeps the model floor on y=0 so framing/beacons/roof do not move', () => {
    expect(MODEL_BASE_Y).toBe(0)
  })

  it('biases the ground plane AWAY from the camera so it loses depth ties', () => {
    expect(GROUND_DEPTH_BIAS.polygonOffset).toBe(true)
    expect(GROUND_DEPTH_BIAS.polygonOffsetFactor).toBeGreaterThan(0)
    expect(GROUND_DEPTH_BIAS.polygonOffsetUnits).toBeGreaterThan(0)
  })

  // Columns are built 0 -> wall height, exactly like the walls, so one embedded
  // in a wall shares its top face plane. No vertical gap is possible there
  // (moving either top would change the building), so the ONLY separation is
  // the depth bias — and its sign is the whole fix: it must pull the column
  // TOWARDS the camera, the opposite of the ground plane.
  it('biases columns TOWARDS the camera so they win the tie with wall tops', () => {
    expect(COLUMN_DEPTH_BIAS.polygonOffset).toBe(true)
    expect(COLUMN_DEPTH_BIAS.polygonOffsetFactor).toBeLessThan(0)
    expect(COLUMN_DEPTH_BIAS.polygonOffsetUnits).toBeLessThan(0)
    expect(COLUMN_DEPTH_BIAS.polygonOffsetFactor)
      .toBeLessThan(GROUND_DEPTH_BIAS.polygonOffsetFactor)
  })

  it('reports gaps for an arbitrary stack (pure helper)', () => {
    expect(depthStackGaps([0, 0.5, 2])).toEqual([0.5, 1.5])
  })
})
