// Talks to the Drishti perception backend (server/).
// Dev default: http://localhost:8000.  Prod: set VITE_API_BASE to the deployed URL.
// NOTE: not wired into the app yet - this is the building block for Step 3.
const API_BASE: string = (() => {
  const base = (import.meta as any).env?.VITE_API_BASE
  if (base) return base
  // never silently point a production build at localhost — fail loud at init
  if ((import.meta as any).env?.PROD) {
    throw new Error('VITE_API_BASE is not set — configure it in your deployment environment')
  }
  return 'http://localhost:8000'
})()

export type Perception = {
  device: string
  width: number
  height: number
  rooms_found: string[]
  icons_found: string[]
  rooms_overlay_png_base64: string
  icons_overlay_png_base64: string
}

/** Send a floor-plan image to the backend and get back what the model detected. */
export async function perceive(file: File): Promise<Perception> {
  const form = new FormData()
  form.append('image', file)
  const res = await fetch(`${API_BASE}/perceive`, { method: 'POST', body: form })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`perceive failed (${res.status}): ${detail}`)
  }
  return res.json()
}

/** Is the backend up and the model loaded? */
export async function health(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`)
    return res.ok && !!(await res.json()).ok
  } catch {
    return false
  }
}
