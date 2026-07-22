// Step C: upload a floor plan -> the backend parses it (/scene) and builds a
// ready 3D model (/scene.glb). One call returns both: the meta (dimensions,
// scale source, wings, warnings) and a blob URL the viewer can load directly.
const API_BASE: string = (() => {
  const base = (import.meta as any).env?.VITE_API_BASE
  if (base) return base
  // never silently point a production build at localhost — fail loud at init
  if ((import.meta as any).env?.PROD) {
    throw new Error('VITE_API_BASE is not set — configure it in your deployment environment')
  }
  return 'http://localhost:8000'
})()

export type SceneMeta = {
  source: string
  plan_width_ft: number
  plan_depth_ft: number
  scale: { source: string; pt_per_ft?: number }
  wing?: { count: number; index: number; bbox_ft?: number[] | null } | null
  warnings: string[]
}

export type Room = { id: string; x: number; y: number; area_sqft: number; type?: string }

export type AreaPair = { sqft: number; sqm: number }
export type AreaStatement = {
  carpet_area: AreaPair
  built_up_area: AreaPair
  super_built_up_area: AreaPair
  wall_and_circulation?: AreaPair
  loading_factor: number
  efficiency_pct: number
}

export type VastuSummary = {
  score: number | null
  rooms_scored: number
  verdicts: { room: string; type: string; zone: string; verdict: string; advice?: string }[]
}

export type BuiltPlan = {
  meta: SceneMeta
  glbUrl: string
  doors: number
  windows: number
  rooms: Room[]
  areaStatement?: AreaStatement
  vastu?: VastuSummary
  costInr?: number          // BOQ total incl. labour (budgeting estimate)
}

async function post(path: string, file: File, q: URLSearchParams, signal?: AbortSignal): Promise<Response> {
  const form = new FormData()
  form.append('image', file)
  const res = await fetch(`${API_BASE}${path}?${q}`, { method: 'POST', body: form, signal })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`${path} failed (${res.status}): ${detail.slice(0, 200)}`)
  }
  return res
}

// generous ceiling: Render free tier cold starts + big-plan parsing both fit
const BUILD_TIMEOUT_MS = 180_000

/** Parse a plan and build its 3D model on the backend. */
export async function buildPlan(
  file: File, widthFt?: number, wing?: number, northDeg?: number,
): Promise<BuiltPlan> {
  const q = new URLSearchParams()
  if (widthFt && widthFt > 0) q.set('width_ft', String(widthFt))
  if (wing !== undefined) q.set('wing', String(wing))
  if (northDeg) q.set('north_deg', String(northDeg))  // Vastu compass (0 = top of sheet)
  // both uploads in parallel, sharing one timeout signal — no more unbounded
  // sequential hangs when the backend stalls
  const signal = AbortSignal.timeout(BUILD_TIMEOUT_MS)
  let sceneRes: Response, glbRes: Response
  try {
    ;[sceneRes, glbRes] = await Promise.all([
      post('/scene', file, q, signal),
      post('/scene.glb', file, q, signal),
    ])
  } catch (e: any) {
    if (e?.name === 'TimeoutError' || (e?.name === 'AbortError' && signal.aborted)) {
      throw new Error('The backend took too long to respond (over 3 minutes) — it may be waking from a cold start. Please try again.')
    }
    throw e
  }
  const scene = await sceneRes.json()
  const glb = await glbRes.blob()
  const ops: any[] = scene.openings ?? []
  return {
    meta: scene.meta,
    glbUrl: URL.createObjectURL(glb),
    doors: ops.filter((o) => o.type === 'door').length,
    windows: ops.filter((o) => o.type === 'window').length,
    rooms: (scene.rooms ?? []) as Room[],
    areaStatement: scene.area_statement as AreaStatement | undefined,
    vastu: scene.vastu as VastuSummary | undefined,
    costInr: scene.boq?.cost_inr?.total_with_labour as number | undefined,
  }
}

/** Download the RERA area-statement spreadsheet for a plan (re-parses server-side). */
export async function downloadAreaStatement(
  file: File, widthFt?: number, loadingFactor = 1.3, project = '',
): Promise<void> {
  const q = new URLSearchParams()
  if (widthFt && widthFt > 0) q.set('width_ft', String(widthFt))
  if (loadingFactor) q.set('loading_factor', String(loadingFactor))
  if (project) q.set('project', project)
  const res = await post('/area-statement.xlsx', file, q, AbortSignal.timeout(BUILD_TIMEOUT_MS))
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'area-statement.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}
