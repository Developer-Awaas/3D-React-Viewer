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

describe('segClass covers everything the scene builds', () => {
  it('classes door leaves and railings, which used to fall through to other', () => {
    expect(segClass('door_3')).toBe('door')
    expect(segClass('railing_0')).toBe('railing')
    expect(segClass('rail_w3_0')).toBe('railing')
  })
  it('classes the geometry added on 1 Sep 2026', () => {
    expect(segClass('stair_0_5')).toBe('stair')
    expect(segClass('terrace_0')).toBe('terrace')
    expect(segClass('duct_0_2')).toBe('column')
  })
  it('still classes the originals, and floor_open stays floor', () => {
    expect(segClass('floor_0')).toBe('floor')
    expect(segClass('floor_open_1')).toBe('floor')
    expect(segClass('wall_2_0')).toBe('wall')
    expect(segClass('column_7')).toBe('column')
    expect(segClass('glass_1')).toBe('window')
    expect(segClass('mystery')).toBe('other')
  })
})
