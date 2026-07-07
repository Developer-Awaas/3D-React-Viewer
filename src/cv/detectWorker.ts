import { Seg } from './detectWalls'

export type DetectResult = { segments: Seg[]; widthM: number; depthM: number; underlay: string }

let worker: Worker | null = null
function getWorker() {
  if (!worker) worker = new Worker('/detect.worker.js') // classic worker from public/
  return worker
}

// Detect walls without blocking the UI: heavy OpenCV runs in the worker.
export function detectWallsWorker(canvas: HTMLCanvasElement, realWidthM: number): Promise<DetectResult> {
  const ctx = canvas.getContext('2d')!
  const img = ctx.getImageData(0, 0, canvas.width, canvas.height)
  const underlay = canvas.toDataURL('image/png') // cheap, do it before transferring the buffer
  return new Promise((resolve, reject) => {
    const w = getWorker()
    const cleanup = () => { w.removeEventListener('message', onmsg); w.removeEventListener('error', onerr) }
    const onmsg = (e: MessageEvent) => {
      cleanup()
      if (e.data?.error) reject(new Error(e.data.error))
      else resolve({ ...e.data, underlay })
    }
    const onerr = (e: ErrorEvent) => { cleanup(); reject(new Error(e.message || 'worker error')) }
    w.addEventListener('message', onmsg)
    w.addEventListener('error', onerr)
    w.postMessage({ data: img.data.buffer, width: canvas.width, height: canvas.height, realWidthM }, [img.data.buffer])
  })
}
