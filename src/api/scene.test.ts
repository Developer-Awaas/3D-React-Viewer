import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { buildPlan } from './scene'

// buildPlan is the frontend's contract with the backend: one call, two
// requests (/scene json + /scene.glb binary) -> meta + blob URL + counts.

const SCENE = {
  meta: {
    source: 'vector_pdf_layers',
    plan_width_ft: 40.5,
    plan_depth_ft: 28.5,
    scale: { source: 'column_box_12in', pt_per_ft: 10 },
    wing: { count: 1, index: 0, bbox_ft: null },
    warnings: [],
  },
  openings: [
    { type: 'door' }, { type: 'door' }, { type: 'window' },
  ],
  rooms: [{ id: 'r0', x: 10, y: 8, area_sqft: 120 }],
}

function okJson(body: unknown): Response {
  return { ok: true, json: async () => body } as unknown as Response
}
function okBlob(): Response {
  return { ok: true, blob: async () => new Blob(['glb']) } as unknown as Response
}

describe('buildPlan', () => {
  const calls: string[] = []

  beforeEach(() => {
    calls.length = 0
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      calls.push(String(url))
      if (String(url).includes('/scene.glb')) return okBlob()
      if (String(url).includes('/scene')) return okJson(SCENE)
      throw new Error('unexpected url ' + url)
    }))
    if (!URL.createObjectURL) {
      // node lacks createObjectURL — the contract is only that we pass the blob
      Object.assign(URL, { createObjectURL: () => 'blob:mock' })
    } else {
      vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock')
    }
  })

  afterEach(() => vi.unstubAllGlobals())

  it('returns meta, counts and a loadable url', async () => {
    const built = await buildPlan(new File(['%PDF'], 'p.pdf'))
    expect(built.meta.plan_width_ft).toBe(40.5)
    expect(built.doors).toBe(2)
    expect(built.windows).toBe(1)
    expect(built.rooms).toEqual([{ id: 'r0', x: 10, y: 8, area_sqft: 120 }])
    expect(built.glbUrl).toBeTruthy()
    expect(calls).toHaveLength(2)
  })

  it('passes width_ft and wing as query params', async () => {
    await buildPlan(new File(['%PDF'], 'p.pdf'), 42, 1)
    expect(calls[0]).toContain('width_ft=42')
    expect(calls[0]).toContain('wing=1')
  })

  it('omits width_ft when auto (0/undefined)', async () => {
    await buildPlan(new File(['%PDF'], 'p.pdf'), 0)
    expect(calls[0]).not.toContain('width_ft')
  })

  it('surfaces backend errors with status + detail', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: false, status: 503,
      text: async () => 'photo/scan engine is in beta',
    } as unknown as Response)))
    await expect(buildPlan(new File([''], 'x.jpg')))
      .rejects.toThrow(/503.*beta/s)
  })
})
