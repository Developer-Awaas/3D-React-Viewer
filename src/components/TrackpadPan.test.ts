import { describe, it, expect } from 'vitest'
import { isTrackpadPan } from './TrackpadPan'

const W = (o: Partial<WheelEvent>) => o as WheelEvent

describe('two-finger trackpad drag = pan, everything else = zoom', () => {
  it('pinch (ctrlKey) stays a zoom', () => {
    expect(isTrackpadPan(W({ ctrlKey: true, deltaX: 0, deltaY: -6 }))).toBe(false)
  })
  it('a mouse wheel notch stays a zoom', () => {
    // mice send coarse discrete steps with no horizontal component
    expect(isTrackpadPan(W({ ctrlKey: false, deltaX: 0, deltaY: 100 }))).toBe(false)
    expect(isTrackpadPan(W({ ctrlKey: false, deltaX: 0, deltaY: -120 }))).toBe(false)
  })
  it('a two-finger drag pans', () => {
    expect(isTrackpadPan(W({ ctrlKey: false, deltaX: 0, deltaY: 3.5 }))).toBe(true)
    expect(isTrackpadPan(W({ ctrlKey: false, deltaX: -12, deltaY: 0 }))).toBe(true)
    // horizontal component means trackpad even when the step looks coarse
    expect(isTrackpadPan(W({ ctrlKey: false, deltaX: 60, deltaY: 90 }))).toBe(true)
  })
})
