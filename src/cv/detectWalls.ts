import { loadOpenCV } from './loadOpenCV'

export type Seg = [number, number, number, number] // x1,z1,x2,z2 in metres

export type DetectResult = {
  segments: Seg[]
  widthM: number
  depthM: number
  underlay: string // data-URL of the (resized) plan, for the 3D underlay
}

type Run = { p: number; a: number; b: number }

// Cluster parallel edges + gap-aware merge (same logic as the Python pipeline).
function collapse(segs: Run[], PERP: number, DOOR: number, MIN: number): Run[] {
  segs = segs.slice().sort((x, y) => x.p - y.p)
  const clusters: Run[][] = []
  for (const s of segs) {
    const last = clusters[clusters.length - 1]
    if (last && s.p - last[last.length - 1].p <= PERP) last.push(s)
    else clusters.push([s])
  }
  const out: Run[] = []
  for (const cl of clusters) {
    const p = cl.reduce((t, s) => t + s.p, 0) / cl.length
    const iv = cl.map((s) => [s.a, s.b] as [number, number]).sort((x, y) => x[0] - y[0])
    let [ca, cb] = iv[0]
    for (let i = 1; i < iv.length; i++) {
      const [a, b] = iv[i]
      if (a <= cb + DOOR) cb = Math.max(cb, b)
      else { out.push({ p, a: ca, b: cb }); ca = a; cb = b }
    }
    out.push({ p, a: ca, b: cb })
  }
  return out.filter((r) => r.b - r.a >= MIN)
}

// Detect walls in a plan canvas, fully in-browser via OpenCV.js.
export async function detectWalls(srcCanvas: HTMLCanvasElement, realWidthM: number): Promise<DetectResult> {
  const cv = await loadOpenCV()

  // 1) read + downscale to a manageable width
  const src = cv.imread(srcCanvas)
  const W = 1400
  const H = Math.round((srcCanvas.height * W) / srcCanvas.width)
  const small = new cv.Mat()
  cv.resize(src, small, new cv.Size(W, H))

  // underlay image for the 3D scene
  const underCanvas = document.createElement('canvas')
  underCanvas.width = W; underCanvas.height = H
  cv.imshow(underCanvas, small)
  const underlay = underCanvas.toDataURL('image/png')

  // 2) grayscale -> threshold the dark ink
  const gray = new cv.Mat()
  cv.cvtColor(small, gray, cv.COLOR_RGBA2GRAY)
  const mask = new cv.Mat()
  cv.threshold(gray, mask, 115, 255, cv.THRESH_BINARY_INV)

  // 3) find straight segments
  const lines = new cv.Mat()
  cv.HoughLinesP(mask, lines, 1, Math.PI / 180, 90, Math.round(0.04 * W), 6)

  const Hs: Run[] = [], Vs: Run[] = []
  const diag: Seg[] = []
  const mpp = realWidthM / W
  const toM = (px: number, py: number): [number, number] => [(px - W / 2) * mpp, (py - H / 2) * mpp]

  for (let i = 0; i < lines.rows; i++) {
    const x1 = lines.data32S[i * 4], y1 = lines.data32S[i * 4 + 1]
    const x2 = lines.data32S[i * 4 + 2], y2 = lines.data32S[i * 4 + 3]
    const ang = (Math.abs(Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI)) % 180
    if (ang < 15 || ang > 165) Hs.push({ p: (y1 + y2) / 2, a: Math.min(x1, x2), b: Math.max(x1, x2) })
    else if (ang > 75 && ang < 105) Vs.push({ p: (x1 + x2) / 2, a: Math.min(y1, y2), b: Math.max(y1, y2) })
    else if (Math.hypot(x2 - x1, y2 - y1) > 0.12 * W) diag.push([...toM(x1, y1), ...toM(x2, y2)])
  }

  const PERP = 18, DOOR = Math.round(0.4 / mpp), MIN = Math.round(0.6 / mpp)
  const segments: Seg[] = []
  for (const r of collapse(Hs, PERP, DOOR, MIN)) segments.push([...toM(r.a, r.p), ...toM(r.b, r.p)])
  for (const r of collapse(Vs, PERP, DOOR, MIN)) segments.push([...toM(r.p, r.a), ...toM(r.p, r.b)])
  for (const d of diag) segments.push(d)

  // free memory (OpenCV.js Mats are not garbage-collected automatically)
  src.delete(); small.delete(); gray.delete(); mask.delete(); lines.delete()

  return { segments, widthM: W * mpp, depthM: H * mpp, underlay }
}
