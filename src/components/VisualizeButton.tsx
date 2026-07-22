import { useEffect, useState } from 'react'
import { renderImage, animateImage } from '../api/visualize'
import { captureGBuffer } from '../three/gbuffer'
import RenderLoading from './RenderLoading'
import { Button } from './ui/Button'

// detected room type (bedroom/kitchen/…) -> the Visualize room dropdown value
const TYPE_TO_ROOM: Record<string, string> = {
  bedroom: 'bedroom', kitchen: 'kitchen', bathroom: 'bathroom',
  living: 'living room', dining: 'living room', study: 'office',
}

// Drishti "Visualize" (Beta): a self-contained overlay. Grabs the current 3D
// view from the WebGL <canvas>, sends it to the backend for a photoreal render
// (SDXL + ControlNet), then optionally animates it into a short walkthrough.
//
// Only requirement in App.tsx: the <Canvas> must keep its draw buffer so we can
// screenshot it —  <Canvas ... gl={{ preserveDrawingBuffer: true }}>
//
// Drop in with:  {mode === 'plan' && pPlan && <VisualizeButton />}

const ROOMS = ['living room', 'bedroom', 'kitchen', 'bathroom', 'office'] as const
const STYLES = ['scandinavian', 'modern', 'warm minimal', 'luxury'] as const

function captureCanvas(): string | null {
  const c = document.querySelector('canvas') as HTMLCanvasElement | null
  if (!c) return null
  try {
    return c.toDataURL('image/png')
  } catch {
    return null // tainted/lost context
  }
}

type PackRoom = { id: string; type?: string }

export default function VisualizeButton({
  roomType,
  rooms = [],
  enterRoom,
  style: styleProp,
  onStyleChange,
}: {
  roomType?: string
  rooms?: PackRoom[]
  enterRoom?: (i: number) => void
  /** controlled style: when provided, the SAME style also dresses the live 3D */
  style?: string
  onStyleChange?: (s: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState<'idle' | 'render' | 'animate'>('idle')
  const [room, setRoom] = useState<string>('living room')
  // when you walk into a detected room, auto-match the render's room type
  useEffect(() => {
    const mapped = roomType && TYPE_TO_ROOM[roomType]
    if (mapped) setRoom(mapped)
  }, [roomType])
  // controlled from App when provided (so the walkable 3D restyles too),
  // otherwise falls back to local state — the component works either way
  const [styleLocal, setStyleLocal] = useState<string>('scandinavian')
  const style = styleProp ?? styleLocal
  const setStyle = (s: string) => {
    setStyleLocal(s)
    onStyleChange?.(s)
  }
  const [img, setImg] = useState<string | null>(null)
  const [vid, setVid] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  // style grid: same geometry, all 4 styles at once (fixed seed → fair compare)
  const [grid, setGrid] = useState<{ style: string; img?: string; err?: string }[] | null>(null)

  const doRender = async () => {
    setErr(null); setVid(null)
    // depth pass from the 3D scene locks geometry best; fall back to a plain
    // screenshot (backend then uses Canny edges) if the G-buffer isn't ready.
    const gb = captureGBuffer()
    const shot = gb?.beauty ?? captureCanvas()
    if (!shot) {
      setErr('Could not capture the 3D view. Make sure the model is on screen.')
      return
    }
    setBusy('render')
    try {
      const { imageDataUrl } = await renderImage(shot, {
        roomType: room, style, depthDataUrl: gb?.depth, segDataUrl: gb?.seg,
      })
      setImg(imageDataUrl)
    } catch (e: any) {
      setErr(e?.message || 'render failed')
    } finally {
      setBusy('idle')
    }
  }

  // Listing Pack: fly into EVERY room, render each photoreal — the per-plan
  // deliverable (one still per room, labelled). Sequential: the GPU renders one
  // at a time anyway, and the camera needs to finish its glide before capture.
  const [pack, setPack] = useState<{ label: string; img?: string; err?: string }[] | null>(null)
  const doListingPack = async () => {
    if (!enterRoom || rooms.length === 0) return
    setErr(null); setImg(null); setVid(null); setGrid(null)
    const take = rooms.slice(0, 9)
    setPack(take.map((r, i) => ({ label: r.type ? `${r.type} ${i + 1}` : `room ${i + 1}` })))
    setBusy('render')
    for (let i = 0; i < take.length; i++) {
      enterRoom(i)
      await new Promise((res) => setTimeout(res, 1400))   // camera glide + settle
      const gb = captureGBuffer()
      const shot = gb?.beauty ?? captureCanvas()
      if (!shot) {
        setPack((p) => p && p.map((t, j) => (j === i ? { ...t, err: 'capture failed' } : t)))
        continue
      }
      try {
        const { imageDataUrl } = await renderImage(shot, {
          roomType: (take[i].type && TYPE_TO_ROOM[take[i].type!]) || 'living room',
          style, seed: 12345, depthDataUrl: gb?.depth, segDataUrl: gb?.seg,
        })
        setPack((p) => p && p.map((t, j) => (j === i ? { ...t, img: imageDataUrl } : t)))
      } catch (e: any) {
        setPack((p) => p && p.map((t, j) => (j === i ? { ...t, err: e?.message || 'failed' } : t)))
      }
    }
    setBusy('idle')
  }

  // Walkthrough: record the canvas while the camera glides through every room —
  // a true geometric walkthrough of the styled 3D, rendered in seconds on any
  // machine (no per-frame GPU diffusion). Downloads a .webm.
  const [walking, setWalking] = useState(false)
  // elapsed seconds while a render runs — honest feedback instead of a frozen label
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (busy !== 'render') { setElapsed(0); return }
    const t0 = Date.now()
    const iv = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000)
    return () => clearInterval(iv)
  }, [busy])
  const doWalkthrough = async () => {
    if (!enterRoom || rooms.length === 0 || walking) return
    const canvas = document.querySelector('canvas') as HTMLCanvasElement | null
    if (!canvas || !('captureStream' in canvas)) {
      setErr('Recording is not supported in this browser.')
      return
    }
    setErr(null)
    setWalking(true)
    try {
      const stream = canvas.captureStream(30)
      const mime = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm']
        .find((m) => MediaRecorder.isTypeSupported(m)) || 'video/webm'
      const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 8_000_000 })
      const chunks: Blob[] = []
      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data)
      const done = new Promise<void>((res) => { rec.onstop = () => res() })
      rec.start()
      for (let i = 0; i < Math.min(rooms.length, 9); i++) {
        enterRoom(i)
        await new Promise((r) => setTimeout(r, 2200))   // glide + linger per room
      }
      rec.stop()
      await done
      const url = URL.createObjectURL(new Blob(chunks, { type: mime }))
      const a = document.createElement('a')
      a.href = url
      a.download = 'drishti-walkthrough.webm'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setErr(e?.message || 'recording failed')
    } finally {
      setWalking(false)
    }
  }

  const GRID_SEED = 12345
  const doStyleGrid = async () => {
    setErr(null); setImg(null); setVid(null)
    // capture ONCE so every tile shares identical geometry — only style differs
    const gb = captureGBuffer()
    const shot = gb?.beauty ?? captureCanvas()
    if (!shot) {
      setErr('Could not capture the 3D view. Make sure the model is on screen.')
      return
    }
    setBusy('render')
    setGrid(STYLES.map((s) => ({ style: s })))
    // fire all 4; the backend semaphore runs them one at a time, each tile fills
    // in as it finishes
    await Promise.all(STYLES.map(async (s, i) => {
      try {
        const { imageDataUrl } = await renderImage(shot, {
          style: s, roomType: room, seed: GRID_SEED, depthDataUrl: gb?.depth,
        })
        setGrid((g) => g && g.map((t, j) => (j === i ? { ...t, img: imageDataUrl } : t)))
      } catch (e: any) {
        setGrid((g) => g && g.map((t, j) => (j === i ? { ...t, err: e?.message || 'failed' } : t)))
      }
    }))
    setBusy('idle')
  }

  const doAnimate = async () => {
    if (!img) return
    setErr(null); setBusy('animate')
    try {
      setVid(await animateImage(img))
    } catch (e: any) {
      setErr(e?.message || 'animate failed')
    } finally {
      setBusy('idle')
    }
  }

  return (
    <>
      {/* cinematic overlay while a single render runs */}
      <RenderLoading active={busy === 'render' && !grid && !pack} />
      {/* floating trigger (sits just above the controls hint, bottom-right) */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="absolute bottom-16 right-5 z-30 rounded-full bg-neon px-4 py-2.5 text-sm
                     font-semibold text-white shadow-glow hover:brightness-105"
        >
          ✨ Visualize <span className="ml-1 opacity-70">Beta</span>
        </button>
      )}

      {open && (
        <div
          style={{ background: 'rgba(15, 23, 42, 0.72)' }}
          className="glass-scroll absolute bottom-5 right-5 z-30 flex max-h-[calc(100vh-2.5rem)] w-[340px]
                     flex-col gap-3 overflow-y-auto rounded-2xl border border-white/10 p-5 shadow-2xl backdrop-blur-md"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">
              Visualize <span className="text-neon">Beta</span>
            </h2>
            <button onClick={() => setOpen(false)}
              className="rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground">Close</button>
          </div>

          <p className="text-[11px] leading-relaxed text-muted-foreground">
            Orbit to the angle you want, then render a photoreal version of this view.
            This is an <b>artistic impression</b> — furniture and finishes are AI-generated,
            not measured design.
          </p>

          <label className="text-xs text-muted-foreground">
            Room
            <select value={room} onChange={(e) => setRoom(e.target.value)}
              className="mt-1 h-8 w-full rounded-md border border-input bg-surface/60 px-2 text-sm text-foreground">
              {ROOMS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>

          <label className="text-xs text-muted-foreground">
            Style
            <select value={style} onChange={(e) => setStyle(e.target.value)}
              className="mt-1 h-8 w-full rounded-md border border-input bg-surface/60 px-2 text-sm text-foreground">
              {STYLES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>

          <Button className="w-full" disabled={busy !== 'idle'} onClick={doRender}>
            {busy === 'render' && !grid && !pack ? `Rendering… ${elapsed}s` : img ? 'Re-render' : 'Render photoreal view'}
          </Button>
          {busy === 'render' && !grid && !pack && (
            <p className="text-[10px] leading-relaxed text-muted-foreground/70">
              First render loads the AI model into the GPU — it can take a minute.
              After that: ~20–40s, and repeats are instant.
            </p>
          )}
          <button
            disabled={busy !== 'idle'}
            onClick={doStyleGrid}
            className="w-full rounded-md border border-input bg-surface/60 py-2 text-xs text-muted-foreground
                       hover:text-foreground disabled:opacity-50"
          >
            {busy === 'render' && grid ? 'Rendering 4 styles…' : '▦ Compare 4 styles'}
          </button>
          {rooms.length > 0 && enterRoom && (
            <button
              disabled={walking}
              onClick={doWalkthrough}
              className="w-full rounded-md border border-input bg-surface/60 py-2 text-xs text-muted-foreground
                         hover:text-foreground disabled:opacity-50"
            >
              {walking ? 'Recording walkthrough…' : `🎬 Record walkthrough (${Math.min(rooms.length, 9)} rooms)`}
            </button>
          )}
          {rooms.length > 0 && enterRoom && (
            <button
              disabled={busy !== 'idle'}
              onClick={doListingPack}
              className="w-full rounded-md border border-neon/40 bg-neon/10 py-2 text-xs font-medium
                         text-foreground hover:border-neon/70 hover:bg-neon/20 disabled:opacity-50"
            >
              {busy === 'render' && pack
                ? `Listing Pack… ${pack.filter((t) => t.img || t.err).length}/${pack.length}`
                : `🏠 Listing Pack (${Math.min(rooms.length, 9)} rooms)`}
            </button>
          )}

          {pack && (
            <div className="grid grid-cols-2 gap-2">
              {pack.map((t) => (
                <div key={t.label} className="relative overflow-hidden rounded-lg border border-white/10 bg-surface/40">
                  {t.img
                    ? <a href={t.img} download={`drishti-${t.label.replace(/\s+/g, '-')}.png`}>
                        <img src={t.img} alt={t.label} className="aspect-square w-full object-cover" />
                      </a>
                    : <div className="flex aspect-square items-center justify-center text-[10px] text-muted-foreground">
                        {t.err ? <span className="px-1 text-center text-red-300">⚠ {t.label}</span>
                               : <span className="animate-pulse">{t.label}…</span>}
                      </div>}
                  {t.img && (
                    <span className="absolute inset-x-0 bottom-0 bg-black/55 py-0.5 text-center text-[10px] capitalize text-white/90">
                      {t.label} · click to save
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          {grid && (
            <div className="grid grid-cols-2 gap-2">
              {grid.map((t) => (
                <button
                  key={t.style}
                  onClick={() => t.img && setImg(t.img)}
                  className="group relative flex aspect-square items-center justify-center overflow-hidden
                             rounded-lg border border-white/10 bg-surface/40 text-[10px] text-muted-foreground"
                >
                  {t.img
                    ? <img src={t.img} alt={t.style} className="h-full w-full object-cover" />
                    : t.err
                      ? <span className="px-1 text-center text-red-300">⚠ {t.style}</span>
                      : <span className="animate-pulse">{t.style}…</span>}
                  {t.img && (
                    <span className="absolute inset-x-0 bottom-0 bg-black/50 py-0.5 text-center capitalize text-white/90">
                      {t.style}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}

          {img && (
            <div className="flex flex-col gap-2">
              <img src={img} alt="photoreal render" className="w-full rounded-lg border border-white/10" />
              <div className="grid grid-cols-2 gap-2">
                <Button variant="secondary" disabled={busy !== 'idle'} onClick={doAnimate}>
                  {busy === 'animate' ? 'Animating… (~1–2min)' : '🎬 Animate'}
                </Button>
                <a href={img} download="drishti-render.png"
                  className="inline-flex h-9 items-center justify-center rounded-md border border-input
                             bg-surface/60 px-3 text-xs text-muted-foreground hover:text-foreground">
                  Download PNG
                </a>
              </div>
            </div>
          )}

          {vid && (
            <div className="flex flex-col gap-2">
              <video src={vid} controls autoPlay loop muted
                className="w-full rounded-lg border border-white/10" />
              <a href={vid} download="drishti-walkthrough.mp4"
                className="inline-flex h-9 items-center justify-center rounded-md border border-input
                           bg-surface/60 px-3 text-xs text-muted-foreground hover:text-foreground">
                Download .mp4
              </a>
            </div>
          )}

          {err && (
            <div className="rounded-lg border border-red-400/30 bg-red-500/10 p-2.5">
              <p className="text-xs leading-relaxed text-red-300">⚠ {err}</p>
              <p className="mt-1 text-[10px] text-red-200/60">
                Try again — if it repeats, check the backend window for the reason.
              </p>
            </div>
          )}
        </div>
      )}
    </>
  )
}
