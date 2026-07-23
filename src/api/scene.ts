// Step C: upload a floor plan -> the backend parses it (/scene) and builds a
// ready 3D model (/scene.glb). One call returns both: the meta (dimensions,
// scale source, wings, warnings) and a blob URL the viewer can load directly.
// Resolve the API base WITHOUT throwing at module-init: a top-level throw here
// white-screens the ENTIRE app (landing page included) if VITE_API_BASE is
// missing in a prod build. Instead return '' and fail loudly only when an API
// call is actually made (apiBase()), so the site still renders.
const API_BASE: string = (() => {
  const base = (import.meta as any).env?.VITE_API_BASE
  if (base) return base
  if ((import.meta as any).env?.PROD) return ''       // unset in prod -> see apiBase()
  return 'http://localhost:8000'
})()

function apiBase(): string {
  if (!API_BASE) {
    throw new Error('This site is not fully configured (VITE_API_BASE is not set). '
      + 'Please try again shortly.')
  }
  return API_BASE
}

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

// Plan Doctor verdict: the rules-based self-check that runs on every parse
export type Diagnosis = {
  grade: 'A' | 'B' | 'C' | 'D' | 'F'
  score: number
  headline: string
  issues: { level: 'ok' | 'warn' | 'fail'; tag: string; message: string }[]
  efficiency_display: string   // "72.4%" or "needs_review" — NEVER a silent 0%
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
  diagnosis?: Diagnosis
  raw?: any                 // full scene.json — sent back to /recompute (G7)
}

async function post(path: string, file: File, q: URLSearchParams, signal?: AbortSignal): Promise<Response> {
  const form = new FormData()
  form.append('image', file)
  const res = await fetch(`${apiBase()}${path}?${q}`, { method: 'POST', body: form, signal })
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
  return { ...planFromScene(scene), glbUrl: URL.createObjectURL(glb) }
}

/** Map a raw scene.json into the viewer's BuiltPlan shape (minus glbUrl). The
 *  raw scene is kept on `.raw` so /recompute (G7 corrections) can send it back. */
function planFromScene(scene: any): Omit<BuiltPlan, 'glbUrl'> {
  const ops: any[] = scene.openings ?? []
  return {
    meta: scene.meta,
    doors: ops.filter((o) => o.type === 'door').length,
    windows: ops.filter((o) => o.type === 'window').length,
    rooms: (scene.rooms ?? []) as Room[],
    areaStatement: scene.area_statement as AreaStatement | undefined,
    vastu: scene.vastu as VastuSummary | undefined,
    costInr: scene.boq?.cost_inr?.total_with_labour as number | undefined,
    diagnosis: scene.diagnosis as Diagnosis | undefined,
    raw: scene,
  }
}

export type Corrections = {
  true_width_ft?: number
  room_types?: Record<string, string>
  delete_rooms?: string[]
  loading_factor?: number
  north_deg?: number
}

/** G7: apply user corrections to a parsed plan and get fresh numbers back.
 *  No re-parse / no GPU — instant. Returns the updated plan (keeps the SAME
 *  glbUrl; scale corrections also return `scaleFactor` so the caller can
 *  scale the 3D model without a rebuild). */
export async function recomputePlan(
  plan: BuiltPlan, corr: Corrections,
): Promise<{ plan: BuiltPlan; scaleFactor?: number }> {
  const res = await fetch(`${apiBase()}/recompute`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scene: plan.raw, corrections: corr }),
    signal: AbortSignal.timeout(30_000),
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`recompute failed (${res.status}): ${detail.slice(0, 200)}`)
  }
  const scene = await res.json()
  const scaleFactor = scene.meta?.correction_info?.scale_factor as number | undefined
  return {
    plan: { ...planFromScene(scene), glbUrl: plan.glbUrl },
    scaleFactor,
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
