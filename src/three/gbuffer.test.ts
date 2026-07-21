import { describe, it, expect } from 'vitest'
import { segClass, SEG_COLORS } from './gbuffer'

describe('segClass', () => {
  it('maps GLB mesh names to semantic classes', () => {
    expect(segClass('floor')).toBe('floor')
    expect(segClass('wall_3')).toBe('wall')
    expect(segClass('glass_0')).toBe('window')
    expect(segClass('WindowPane')).toBe('window')
    expect(segClass('column')).toBe('column')
    expect(segClass('furn_bed_1_frame')).toBe('furniture')
    expect(segClass('something_else')).toBe('other')
    expect(segClass('')).toBe('other')
  })
  it('window beats wall when a name contains both hints', () => {
    // glass panes sit "in windows in walls" — must classify as window
    expect(segClass('glass_wall_0')).toBe('window')
  })
  it('every class has a distinct colour', () => {
    const vals = Object.values(SEG_COLORS)
    expect(new Set(vals).size).toBe(vals.length)
  })
})
