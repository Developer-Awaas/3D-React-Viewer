// Step C: upload a floor plan -> the backend parses it (/scene) and builds a
// ready 3D model (/scene.glb). One call returns both: the meta (dimensions,
// scale source, wings, warnings) and a blob URL the viewer can load directly.
const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? 'http://localhost:8000'

export type SceneMeta = {
  source: string
  plan_width_ft: number
  plan_depth_ft: number
  scale: { source: string; pt_per_ft?: number }
  wing?: { count: number; index: number; bbox_ft?: number[] | null } | null
  warnings: string[]
}

export type BuiltPlan = {
  meta: SceneMeta
  glbUrl: string
  doors: number
  windows: number
}

async function post(path: string, file: File, q: URLSearchParams): Promise<Response> {
  const form = new FormData()
  form.append('image', file)
  const res = await fetch(`${API_BASE}${path}?${q}`, { method: 'POST', body: form })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`${path} failed (${res.status}): ${detail.slice(0, 200)}`)
  }
  return res
}

/** Parse a plan and build its 3D model on the backend. */
export async function buildPlan(file: File, widthFt?: number, wing?: number): Promise<BuiltPlan> {
  const q = new URLSearchParams()
  if (widthFt && widthFt > 0) q.set('width_ft', String(widthFt))
  if (wing !== undefined) q.set('wing', String(wing))
  const scene = await (await post('/scene', file, q)).json()
  const glb = await (await post('/scene.glb', file, q)).blob()
  const ops: any[] = scene.openings ?? []
  return {
    meta: scene.meta,
    glbUrl: URL.createObjectURL(glb),
    doors: ops.filter((o) => o.type === 'door').length,
    windows: ops.filter((o) => o.type === 'window').length,
  }
}
