// Talks to the Drishti "Visualize" (Beta) backend endpoints (server/visualize.py).
// Dev default: http://localhost:8000.  Prod: set VITE_API_BASE.
// Resolve WITHOUT throwing at module-init (a top-level throw white-screens the
// whole app). '' in prod when unset -> apiBase() fails loud only on actual use.
const API_BASE: string = (() => {
  const base = (import.meta as any).env?.VITE_API_BASE
  if (base) return base
  if ((import.meta as any).env?.PROD) return ''
  return 'http://localhost:8000'
})()

function apiBase(): string {
  if (!API_BASE) throw new Error('Rendering is not configured (VITE_API_BASE is not set).')
  return API_BASE
}

export type RenderOpts = {
  roomType?: string
  style?: string
  prompt?: string
  seed?: number
  depthDataUrl?: string   // depth map rendered from the 3D scene -> depth ControlNet
  segDataUrl?: string     // segmentation map (surface classes) -> seg ControlNet (moat)
  signal?: AbortSignal    // caller's Cancel button (combined with the timeout)
}

// SDXL ~1-2 min, SVD a bit more on a 12 GB card; generous ceilings so a
// STALLED backend can never hang the UI forever (there was NO timeout before).
const RENDER_TIMEOUT_MS = 300_000
const ANIMATE_TIMEOUT_MS = 420_000

/** Timeout + optional user-cancel, combined into one AbortSignal. */
function guardSignal(timeoutMs: number, user?: AbortSignal): AbortSignal {
  return user ? AbortSignal.any([user, AbortSignal.timeout(timeoutMs)])
              : AbortSignal.timeout(timeoutMs)
}

function abortError(e: unknown, what: string): Error {
  if (e instanceof DOMException && e.name === 'TimeoutError')
    return new Error(`${what} timed out — the GPU box may be busy or offline. Try again.`)
  if (e instanceof DOMException && e.name === 'AbortError')
    return new Error(`${what} cancelled`)
  return e instanceof Error ? e : new Error(String(e))
}

/** data:image/png;base64,... -> a Blob we can POST as multipart form-data. */
function dataUrlToBlob(dataUrl: string): Blob {
  const [head, b64] = dataUrl.split(',')
  const mime = /:(.*?);/.exec(head)?.[1] ?? 'image/png'
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new Blob([bytes], { type: mime })
}

/** Eye-level screenshot (PNG data URL) -> photoreal furnished still (data URL). */
export async function renderImage(
  pngDataUrl: string,
  opts: RenderOpts = {},
): Promise<{ imageDataUrl: string; prompt: string }> {
  const form = new FormData()
  form.append('image', dataUrlToBlob(pngDataUrl), 'view.png')
  if (opts.depthDataUrl) form.append('depth', dataUrlToBlob(opts.depthDataUrl), 'depth.png')
  if (opts.segDataUrl) form.append('seg', dataUrlToBlob(opts.segDataUrl), 'seg.png')
  if (opts.roomType) form.append('room_type', opts.roomType)
  if (opts.style) form.append('style', opts.style)
  if (opts.prompt) form.append('prompt', opts.prompt)
  if (opts.seed != null) form.append('seed', String(opts.seed))
  let res: Response
  try {
    res = await fetch(`${apiBase()}/visualize/render`, {
      method: 'POST', body: form,
      signal: guardSignal(RENDER_TIMEOUT_MS, opts.signal),
    })
  } catch (e) {
    throw abortError(e, 'render')
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`render failed (${res.status}): ${detail.slice(0, 200)}`)
  }
  const j = await res.json()
  return { imageDataUrl: 'data:image/png;base64,' + j.image_base64, prompt: j.prompt }
}

/** Photoreal still (PNG data URL) -> short walkthrough .mp4 (data URL). */
export async function animateImage(
  pngDataUrl: string, seed = 12345, signal?: AbortSignal,
): Promise<string> {
  const form = new FormData()
  form.append('image', dataUrlToBlob(pngDataUrl), 'still.png')
  form.append('seed', String(seed))
  let res: Response
  try {
    res = await fetch(`${apiBase()}/visualize/animate`, {
      method: 'POST', body: form,
      signal: guardSignal(ANIMATE_TIMEOUT_MS, signal),
    })
  } catch (e) {
    throw abortError(e, 'animate')
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`animate failed (${res.status}): ${detail.slice(0, 200)}`)
  }
  const j = await res.json()
  return 'data:video/mp4;base64,' + j.video_base64
}

/** Is the Visualize backend up? Returns the backend name ('local'|'fal') or null. */
export async function visualizeHealth(): Promise<{ backend: string; cuda: boolean } | null> {
  try {
    const res = await fetch(`${apiBase()}/visualize/health`,
                            { signal: AbortSignal.timeout(8000) })  // never hang
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}
