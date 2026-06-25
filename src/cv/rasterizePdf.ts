import * as pdfjsLib from 'pdfjs-dist'
// Vite resolves this worker file to a URL we can hand to pdf.js.
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

// Render page 1 of a PDF onto a canvas, so it can be treated like any image.
export async function rasterizePdf(file: File): Promise<HTMLCanvasElement> {
  const data = await file.arrayBuffer()
  const pdf = await pdfjsLib.getDocument({ data }).promise
  const page = await pdf.getPage(1)
  const viewport = page.getViewport({ scale: 2 }) // 2x for crisp lines
  const canvas = document.createElement('canvas')
  canvas.width = viewport.width
  canvas.height = viewport.height
  const ctx = canvas.getContext('2d')!
  await page.render({ canvasContext: ctx, viewport }).promise
  return canvas
}

// Draw any image File onto a canvas.
export function imageToCanvas(file: File): Promise<HTMLCanvasElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const c = document.createElement('canvas')
      c.width = img.naturalWidth
      c.height = img.naturalHeight
      c.getContext('2d')!.drawImage(img, 0, 0)
      resolve(c)
    }
    img.onerror = reject
    img.src = URL.createObjectURL(file)
  })
}
