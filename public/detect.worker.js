/* Wall detection in a background thread — keeps the UI from freezing.
   Loads OpenCV.js here (off the main thread) and runs Hough detection. */
importScripts('https://docs.opencv.org/4.x/opencv.js')

let ready = false
const queue = []
function onReady(cb) {
  const cv = self.cv
  if (cv && cv.Mat) return cb()
  if (cv && typeof cv.then === 'function') return cv.then(cb)
  cv.onRuntimeInitialized = cb
}
onReady(() => { ready = true; flush() })
self.onmessage = (e) => { queue.push(e.data); flush() }
function flush() { if (!ready) return; while (queue.length) process(queue.shift()) }

function collapse(segs, PERP, DOOR, MIN) {
  segs = segs.slice().sort((a, b) => a.p - b.p)
  const clusters = []
  for (const s of segs) {
    const last = clusters[clusters.length - 1]
    if (last && s.p - last[last.length - 1].p <= PERP) last.push(s)
    else clusters.push([s])
  }
  const out = []
  for (const cl of clusters) {
    const p = cl.reduce((t, s) => t + s.p, 0) / cl.length
    const iv = cl.map((s) => [s.a, s.b]).sort((a, b) => a[0] - b[0])
    let ca = iv[0][0], cb = iv[0][1]
    for (let i = 1; i < iv.length; i++) {
      const a = iv[i][0], b = iv[i][1]
      if (a <= cb + DOOR) cb = Math.max(cb, b)
      else { out.push({ p, a: ca, b: cb }); ca = a; cb = b }
    }
    out.push({ p, a: ca, b: cb })
  }
  return out.filter((r) => r.b - r.a >= MIN)
}

// --- Phase 1: detection algorithm selector ---------------------------------
// 'morph' = morphological wall-band extraction (new default).
// 'hough' = original Hough-line core, kept as an internal fallback for instant revert.
const ALGO = 'morph'

// Turn horizontal/vertical wall BANDS into centerline runs, reusing the exact
// {p,a,b} shape collapse() consumes: p = band midline (perpendicular position),
// [a,b] = span along the wall. Centerline = bounding-box midline (no skeleton needed).
function collectRuns(cv, bandMask, axis, out) {
  const labels = new cv.Mat(), stats = new cv.Mat(), cents = new cv.Mat()
  const n = cv.connectedComponentsWithStats(bandMask, labels, stats, cents, 8, cv.CV_32S)
  for (let i = 1; i < n; i++) {
    const x = stats.intAt(i, cv.CC_STAT_LEFT), y = stats.intAt(i, cv.CC_STAT_TOP)
    const w = stats.intAt(i, cv.CC_STAT_WIDTH), h = stats.intAt(i, cv.CC_STAT_HEIGHT)
    if (axis === 'h') out.push({ p: y + h / 2, a: x, b: x + w }) // horizontal wall
    else out.push({ p: x + w / 2, a: y, b: y + h })              // vertical wall
  }
  labels.delete(); stats.delete(); cents.delete()
}

// Morphological wall-band extraction. Directional OPEN keeps only long runs in one
// orientation (so short furniture/text/dimension strokes vanish); perpendicular CLOSE
// fuses the two lines of a double-line wall into one solid band. Each band's centerline
// becomes a run. Diagonals are intentionally dropped in Phase 1 (handled in a later phase).
function wallRunsMorph(cv, mask, mpp) {
  const OPEN_LEN = Math.max(20, Math.round(0.5 / mpp)) // min wall length to survive (px)
  const CLOSE_TH = Math.max(3, Math.round(0.30 / mpp)) // double-line fuse gap, perpendicular (px)
  const Hs = [], Vs = []

  const hk = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(OPEN_LEN, 1))
  const hck = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(1, CLOSE_TH))
  const hBand = new cv.Mat()
  cv.morphologyEx(mask, hBand, cv.MORPH_OPEN, hk)   // keep long horizontal runs
  cv.morphologyEx(hBand, hBand, cv.MORPH_CLOSE, hck) // fuse the pair vertically
  collectRuns(cv, hBand, 'h', Hs)

  const vk = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(1, OPEN_LEN))
  const vck = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(CLOSE_TH, 1))
  const vBand = new cv.Mat()
  cv.morphologyEx(mask, vBand, cv.MORPH_OPEN, vk)
  cv.morphologyEx(vBand, vBand, cv.MORPH_CLOSE, vck)
  collectRuns(cv, vBand, 'v', Vs)

  hk.delete(); hck.delete(); vk.delete(); vck.delete(); hBand.delete(); vBand.delete()
  return { Hs, Vs, diag: [] }
}

// Original Hough core (fallback), including the Ticket-2 small-blob cleanup. Mutates mask.
function wallRunsHough(cv, mask, W, H, mpp, toM) {
  const labels = new cv.Mat(), stats = new cv.Mat(), centroids = new cv.Mat()
  const nLabels = cv.connectedComponentsWithStats(mask, labels, stats, centroids, 8, cv.CV_32S)
  const MIN_AREA = Math.max(150, Math.round(0.0003 * W * H))
  const keep = new Uint8Array(nLabels)
  for (let i = 1; i < nLabels; i++) keep[i] = stats.intAt(i, cv.CC_STAT_AREA) >= MIN_AREA ? 1 : 0
  const lab = labels.data32S, md = mask.data
  for (let k = 0; k < lab.length; k++) if (keep[lab[k]] === 0) md[k] = 0
  labels.delete(); stats.delete(); centroids.delete()

  const lines = new cv.Mat()
  cv.HoughLinesP(mask, lines, 1, Math.PI / 180, 90, Math.round(0.04 * W), 6)
  const Hs = [], Vs = [], diag = []
  const d = lines.data32S
  for (let i = 0; i < lines.rows; i++) {
    const x1 = d[i*4], y1 = d[i*4+1], x2 = d[i*4+2], y2 = d[i*4+3]
    const ang = (Math.abs(Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI)) % 180
    if (ang < 15 || ang > 165) Hs.push({ p: (y1+y2)/2, a: Math.min(x1,x2), b: Math.max(x1,x2) })
    else if (ang > 75 && ang < 105) Vs.push({ p: (x1+x2)/2, a: Math.min(y1,y2), b: Math.max(y1,y2) })
    else if (Math.hypot(x2-x1, y2-y1) > 0.12 * W) diag.push([...toM(x1,y1), ...toM(x2,y2)])
  }
  lines.delete()
  return { Hs, Vs, diag }
}

function process(msg) {
  const cv = self.cv
  try {
    const { data, width, height, realWidthM } = msg
    const src = cv.matFromImageData({ data: new Uint8ClampedArray(data), width, height })
    const W = 1200, H = Math.round(height * 1200 / width)
    const small = new cv.Mat(); cv.resize(src, small, new cv.Size(W, H))
    const gray = new cv.Mat(); cv.cvtColor(small, gray, cv.COLOR_RGBA2GRAY)
    const mask = new cv.Mat(); cv.threshold(gray, mask, 115, 255, cv.THRESH_BINARY_INV)

    const mpp = realWidthM / W
    const toM = (px, py) => [(px - W / 2) * mpp, (py - H / 2) * mpp]

    // Pick the detection core; both return the same { Hs, Vs, diag } shape.
    const { Hs, Vs, diag } = ALGO === 'morph'
      ? wallRunsMorph(cv, mask, mpp)
      : wallRunsHough(cv, mask, W, H, mpp, toM)

    // Unchanged tail: cluster parallels + gap-aware merge + length filter -> metres.
    const PERP = 18, DOOR = Math.round(0.4 / mpp), MIN = Math.round(0.6 / mpp)
    const segments = []
    for (const r of collapse(Hs, PERP, DOOR, MIN)) segments.push([...toM(r.a, r.p), ...toM(r.b, r.p)])
    for (const r of collapse(Vs, PERP, DOOR, MIN)) segments.push([...toM(r.p, r.a), ...toM(r.p, r.b)])
    for (const dd of diag) segments.push(dd)

    src.delete(); small.delete(); gray.delete(); mask.delete()
    self.postMessage({ segments, widthM: W * mpp, depthM: H * mpp })
  } catch (err) {
    self.postMessage({ error: (err && err.message) || 'detection failed' })
  }
}
