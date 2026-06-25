// Loads OpenCV.js (a ~8MB WebAssembly build) from the official CDN, once, and
// resolves when it's ready to use. We load it lazily so the app starts fast.
let pending: Promise<any> | null = null

export function loadOpenCV(): Promise<any> {
  const w = window as any
  if (w.cv && w.cv.Mat) return Promise.resolve(w.cv)   // already ready
  if (pending) return pending

  pending = new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = 'https://docs.opencv.org/4.x/opencv.js'
    s.async = true
    s.onload = () => {
      const cv = (window as any).cv
      if (!cv) return reject(new Error('OpenCV failed to load'))
      const finish = (m: any) => { (window as any).cv = m; resolve(m) }
      // OpenCV.js 4.x often returns `cv` as a Promise (thenable) — await it.
      if (typeof cv.then === 'function') { cv.then(finish); return }
      if (cv.Mat) return finish(cv)                     // already initialised
      cv.onRuntimeInitialized = () => finish(cv)        // older build: wait for wasm
    }
    s.onerror = () => reject(new Error('Could not download OpenCV.js'))
    document.body.appendChild(s)
  })
  return pending
}
