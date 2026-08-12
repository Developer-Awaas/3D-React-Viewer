import { useEffect, useMemo, useRef, useState } from 'react'
import type { Overlay } from '../api/scene'

// PHASE 0 instrument — the parsed geometry drawn over the original drawing.
//
// R-8 checks areas and R-2 checks room sizes; neither can show that a wall is
// in the wrong PLACE. Layers toggle client-side (instant, no round trip) and
// the composite downloads as a PNG for mark-up.
//
// Layers with no detector yet (railing, plot boundary, setback) are listed and
// shown as empty rather than hidden — an absent layer looks like a layer that
// found nothing, and the difference is the whole point of the instrument.

export default function WallOverlay({ data, onClose }: { data: Overlay; onClose: () => void }) {
  const names = useMemo(() => Object.keys(data.style), [data.style])
  const [on, setOn] = useState<Record<string, boolean>>(
    () => Object.fromEntries(names.map((n) => [n, n !== 'rejected'])))
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [img, setImg] = useState<HTMLImageElement | null>(null)
  const [solo, setSolo] = useState(false)   // click a layer chip to export it alone

  useEffect(() => {
    if (!data.page) return
    const i = new Image()
    i.onload = () => setImg(i)
    i.src = `data:image/png;base64,${data.page.png_b64}`
  }, [data.page])

  useEffect(() => {
    const c = canvasRef.current
    if (!c) return
    const w = data.page?.w ?? 1600
    const h = data.page?.h ?? 1200
    c.width = w
    c.height = h
    const ctx = c.getContext('2d')!
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, w, h)
    if (img) ctx.drawImage(img, 0, 0, w, h)
    for (const name of names) {
      if (!on[name]) continue
      const style = data.style[name]
      const shapes = data.layers[name] || []
      ctx.strokeStyle = style.colour
      ctx.lineWidth = style.width
      ctx.globalAlpha = name === 'rejected' ? 0.5 : 0.95
      for (const pts of shapes) {
        if (pts.length < 2) continue
        ctx.beginPath()
        ctx.moveTo(pts[0][0], pts[0][1])
        for (const p of pts.slice(1)) ctx.lineTo(p[0], p[1])
        if (style.kind !== 'line') ctx.closePath()
        ctx.stroke()
      }
    }
    ctx.globalAlpha = 1
  }, [img, on, data, names])

  // Export ONE layer over the drawing. All-layers-on is unreadable, and a
  // single layer is what you actually mark up and send back.
  const downloadLayer = (only?: string) => {
    const c = canvasRef.current
    if (!c) return
    if (only) {
      const w = data.page?.w ?? 1600, h = data.page?.h ?? 1200
      const tmp = document.createElement('canvas')
      tmp.width = w; tmp.height = h
      const ctx = tmp.getContext('2d')!
      ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, w, h)
      if (img) ctx.drawImage(img, 0, 0, w, h)
      const st = data.style[only]
      ctx.strokeStyle = st.colour; ctx.lineWidth = Math.max(st.width, 2)
      for (const pts of data.layers[only] || []) {
        if (pts.length < 2) continue
        ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1])
        for (const q of pts.slice(1)) ctx.lineTo(q[0], q[1])
        if (st.kind !== 'line') ctx.closePath()
        ctx.stroke()
      }
      tmp.toBlob((b) => {
        if (!b) return
        const url = URL.createObjectURL(b)
        const a = document.createElement('a')
        a.href = url; a.download = `overlay-${only}.png`; a.click()
        URL.revokeObjectURL(url)
      })
      return
    }
    c.toBlob((b) => {
      if (!b) return
      const url = URL.createObjectURL(b)
      const a = document.createElement('a')
      a.href = url
      a.download = 'wall-overlay.png'
      a.click()
      URL.revokeObjectURL(url)
    })
  }
  const download = () => downloadLayer()

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/90 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        <span className="mr-2 font-semibold text-white">Wall overlay</span>
        {names.map((n) => (
          <button key={n} onClick={() => (solo ? downloadLayer(n) : setOn((s) => ({ ...s, [n]: !s[n] })))}
            className={`rounded-full border px-2 py-1 ${on[n] ? 'border-white/40 text-white' : 'border-white/10 text-white/35'}`}>
            <span style={{ color: data.style[n].colour }}>■</span>{' '}
            {n.replace(/_/g, ' ')} ({data.counts[n] ?? 0})
            {data.not_yet_detected.includes(n) && <span className="text-amber-300"> · none yet</span>}
          </button>
        ))}
        <button onClick={download}
          className="rounded-full bg-neon px-3 py-1 font-semibold text-white">Download PNG</button>
        <button onClick={() => setSolo((v) => !v)}
          className={`rounded-full border px-3 py-1 ${solo ? 'border-neon text-neon' : 'border-white/20 text-white/70'}`}>
          {solo ? 'solo: click a layer to export it' : 'Export one layer'}
        </button>
        <button onClick={onClose} className="rounded-full border border-white/20 px-3 py-1 text-white/70">Close</button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto rounded-xl bg-white/5">
        <canvas ref={canvasRef} className="max-w-none" />
      </div>
    </div>
  )
}
