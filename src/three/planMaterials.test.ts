import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import { boxUV, DEFAULT_STYLE, STYLE_KEYS, STYLE_PALETTES } from './planMaterials'

// boxUV is the maths that lets textures sit correctly on walls that ship
// with NO texture coordinates: per face, project UVs from the dominant
// normal axis (a CPU-side triplanar).

describe('boxUV', () => {
  it('adds a uv attribute sized to the de-indexed positions', () => {
    const g = boxUV(new THREE.BoxGeometry(2, 3, 1))
    expect(g.index).toBeNull() // de-indexed for per-face UVs
    expect(g.attributes.uv).toBeDefined()
    expect(g.attributes.uv.count).toBe(g.attributes.position.count)
  })

  it('projects top faces from X/Z and side faces from the wall plane', () => {
    const g = boxUV(new THREE.BoxGeometry(2, 2, 2))
    const pos = g.attributes.position
    const nor = g.attributes.normal
    const uv = g.attributes.uv
    for (let f = 0; f + 2 < pos.count; f += 3) {
      const ny = Math.abs(nor.getY(f))
      const nx = Math.abs(nor.getX(f))
      const nz = Math.abs(nor.getZ(f))
      for (let v = f; v < f + 3; v++) {
        if (ny >= nx && ny >= nz) {
          // floor/ceiling: uv = (x, z)
          expect(uv.getX(v)).toBeCloseTo(pos.getX(v), 5)
          expect(uv.getY(v)).toBeCloseTo(pos.getZ(v), 5)
        } else if (nx >= nz) {
          // x-facing wall: uv = (z, y) — v tracks HEIGHT so bands stay level
          expect(uv.getX(v)).toBeCloseTo(pos.getZ(v), 5)
          expect(uv.getY(v)).toBeCloseTo(pos.getY(v), 5)
        } else {
          // z-facing wall: uv = (x, y)
          expect(uv.getX(v)).toBeCloseTo(pos.getX(v), 5)
          expect(uv.getY(v)).toBeCloseTo(pos.getY(v), 5)
        }
      }
    }
  })

  it('computes flat normals so masonry edges stay crisp', () => {
    const g = boxUV(new THREE.BoxGeometry(1, 1, 1))
    const nor = g.attributes.normal
    // every face's three vertex normals must be identical (flat shading)
    for (let f = 0; f + 2 < nor.count; f += 3) {
      for (const axis of ['getX', 'getY', 'getZ'] as const) {
        expect(nor[axis](f + 1)).toBeCloseTo(nor[axis](f), 5)
        expect(nor[axis](f + 2)).toBeCloseTo(nor[axis](f), 5)
      }
    }
  })

  it('handles geometry that arrives without normals (old GLBs)', () => {
    const raw = new THREE.BoxGeometry(1, 2, 3).toNonIndexed()
    raw.deleteAttribute('normal')
    const g = boxUV(raw)
    expect(g.attributes.normal).toBeDefined()
    expect(g.attributes.uv.count).toBe(g.attributes.position.count)
  })
})

// The 4 Visualize styles must each map to a COMPLETE 3D material recipe —
// a missing field would silently render black/default surfaces.
describe('STYLE_PALETTES', () => {
  const HEX = /^#[0-9a-f]{6}$/i
  const RGB = /^\d{1,3},\d{1,3},\d{1,3}$/
  const RGBA = /^rgba\(\d{1,3},\d{1,3},\d{1,3},0?\.\d+\)$/

  it('covers exactly the 4 photo-render styles, incl. the default', () => {
    expect(STYLE_KEYS.sort()).toEqual(
      ['luxury', 'modern', 'scandinavian', 'warm minimal'])
    expect(STYLE_KEYS).toContain(DEFAULT_STYLE)
  })

  it.each(Object.entries(STYLE_PALETTES))('%s palette is complete and valid', (_k, p) => {
    expect(p.plasterBase).toMatch(HEX)
    expect(p.plasterTint).toMatch(HEX)
    expect(p.plasterBlotch).toMatch(RGB)
    expect(p.floorTones).toHaveLength(4)
    for (const t of p.floorTones) expect(t).toMatch(HEX)
    expect(p.grout).toMatch(HEX)
    expect(p.vein).toMatch(RGBA)
    expect(p.floorTint).toMatch(HEX)
    expect(p.concreteBase).toMatch(HEX)
    expect(p.concreteTint).toMatch(HEX)
    expect(p.floorRoughness).toBeGreaterThan(0)
    expect(p.floorRoughness).toBeLessThanOrEqual(1)
    expect(p.floorMetalness).toBeGreaterThanOrEqual(0)
    expect(p.floorMetalness).toBeLessThan(0.5) // floors are stone/wood, not chrome
  })

  it('styles are visually distinct (different floor tones)', () => {
    const firstTones = Object.values(STYLE_PALETTES).map((p) => p.floorTones[0])
    expect(new Set(firstTones).size).toBe(firstTones.length)
  })
})
