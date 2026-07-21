// Talks to the Drishti "Visualize" (Beta) backend endpoints (server/visualize.py).
// Dev default: http://localhost:8000.  Prod: set VITE_API_BASE.
const API_BASE: string = (() => {
  const base = (import.meta as any).env?.VITE_API_BASE
  if (base) return base
  // never silently point a production build at localhost — fail loud at init
  if ((import.meta as any).env?.PROD) {
    throw new Error('VITE_API_BASE is not set — configure it in your deployment environment')
  }
  return 'http://localhost:8000'
})()

export type RenderOpts = {
  roomType?: string
  style?: string
  prompt?: string
  seed?: number
  depthDataUrl?: string   // depth map rendered from the 3D scene -> depth ControlNet
  segDataUrl?: string     // segmentation map (surface classes) -> seg ControlNet (moat)
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
  const res = await fetch(`${API_BASE}/visualize/render`, { method: 'POST', body: form })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`render failed (${res.status}): ${detail.slice(0, 200)}`)
  }
  const j = await res.json()
  return { imageDataUrl: 'data:image/png;base64,' + j.image_base64, prompt: j.prompt }
}

/** Photoreal still (PNG data URL) -> short walkthrough .mp4 (data URL). */
export async function animateImage(pngDataUrl: string, seed = 12345): Promise<string> {
  const form = new FormData()
  form.append('image', dataUrlToBlob(pngDataUrl), 'still.png')
  form.append('seed', String(seed))
  const res = await fetch(`${API_BASE}/visualize/animate`, { method: 'POST', body: form })
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
    const res = await fetch(`${API_BASE}/visualize/health`)
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}
