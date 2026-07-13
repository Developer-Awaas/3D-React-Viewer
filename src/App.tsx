import { InputHTMLAttributes, ReactNode, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment, ContactShadows } from '@react-three/drei'
import { AnimatePresence, motion, type Variants } from 'framer-motion'
import Room from './components/Room'
import Lights from './components/Lights'
import Furniture from './components/Furniture'
import Model from './components/Model'
import ErrorBoundary from './components/ErrorBoundary'
import CameraMarker from './components/CameraMarker'
import CameraRig, { View } from './components/CameraRig'
import TraceScene from './components/TraceScene'
import { Seg } from './cv/detectWalls'
import { detectWallsWorker } from './cv/detectWorker'
import { rasterizePdf, imageToCanvas } from './cv/rasterizePdf'
import { FLOOR_MATERIALS, FloorKey } from './materials'
import { MARKERS } from './scene'
import { PRESETS } from './cameraPresets'
import { Button } from './components/ui/Button'
import { buildPlan, type BuiltPlan } from './api/scene'
import LoadingScreen from './components/LoadingScreen'
import LandingHero from './landing/LandingHero'

const SOFA_URL =
  'https://cdn.jsdelivr.net/gh/KhronosGroup/glTF-Sample-Assets@main/Models/GlamVelvetSofa/glTF-Binary/GlamVelvetSofa.glb'
const TOP_VIEW: View = { position: [0, 16, 0.01], target: [0, 0, 0] }

/* ---- motion constants (defined once, outside component) ---- */
const PILL_SPRING = { type: 'spring', stiffness: 380, damping: 32 } as const
const panelVariants: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
}

function ReadySignal({ onReady }: { onReady: () => void }) {
  useEffect(() => { onReady() }, [onReady])
  return null
}

type Mode = 'room' | 'convert' | 'plan' | 'viewer'
const PRIMARY_MODES: { id: Mode; label: string }[] = [
  { id: 'plan', label: 'Plan → 3D' },
]
const ADVANCED_MODES: { id: Mode; label: string }[] = [
  { id: 'room', label: 'Demo' },
  { id: 'convert', label: 'Convert' },
  { id: 'viewer', label: 'Viewer' },
]

/* ---------- small styled primitives ---------- */
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex items-center justify-between gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>{children}
    </label>
  )
}
function NumberInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input type="number" {...props}
    className="h-8 w-20 rounded-md border border-input bg-surface/60 px-2 text-sm text-foreground
               focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
}
function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props}
    className="h-9 w-full rounded-md border border-input bg-surface/60 px-3 text-sm text-foreground
               placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
}
function Upload({ onFile, accept, children }: { onFile: (f: File) => void; accept: string; children: ReactNode }) {
  return (
    <motion.label whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }} transition={{ duration: 0.15 }}
      className="inline-flex h-9 w-full cursor-pointer items-center justify-center gap-2 rounded-full
                 bg-neon px-4 text-sm font-semibold text-white shadow-glow hover:brightness-105">
      {children}
      <input type="file" accept={accept} className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.currentTarget.value = '' }} />
    </motion.label>
  )
}
function Status({ children }: { children: ReactNode }) {
  return <p className="text-xs leading-relaxed text-muted-foreground">{children}</p>
}

/* pill-button for tabs / material choices with a sliding shared-layout highlight */
function PillButton({
  active, layoutId, onClick, children,
}: { active: boolean; layoutId: string; onClick: () => void; children: ReactNode }) {
  return (
    <motion.button
      onClick={onClick} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }} transition={{ duration: 0.15 }}
      className={`relative rounded-full px-3 py-2 text-xs font-medium transition-colors ${
        active ? 'text-white' : 'text-muted-foreground hover:text-foreground'
      }`}
    >
      {active && <motion.span layoutId={layoutId} transition={PILL_SPRING}
        className="absolute inset-0 -z-0 rounded-full bg-neon shadow-glow" />}
      <span className="relative z-10">{children}</span>
    </motion.button>
  )
}

export default function App() {
  const [mode, setMode] = useState<Mode>('plan')
  // landing gate — the hero shows first; entering is remembered for this tab
  // session (add ?landing to the URL to force the hero back for demos)
  const [entered, setEntered] = useState<boolean>(() => {
    try {
      if (new URLSearchParams(window.location.search).has('landing')) return false
      return sessionStorage.getItem('drishti_entered') === '1'
    } catch { return false }
  })
  const enterApp = useCallback(() => {
    try { sessionStorage.setItem('drishti_entered', '1') } catch { /* ignore */ }
    setEntered(true)
  }, [])
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [floor, setFloor] = useState<FloorKey>('marble')
  const [view, setView] = useState<View | null>(null)

  // viewer
  const [modelUrl, setModelUrl] = useState<string | null>(null)
  const [vStatus, setVStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [urlText, setUrlText] = useState('')
  const loadUrl = (u: string) => { setVStatus('loading'); setModelUrl(u) }

  // convert = auto-detect a draft, then trace-fix
  const [cSegs, setCSegs] = useState<Seg[]>([])
  const [cUnder, setCUnder] = useState<string | null>(null)
  const [cDims, setCDims] = useState({ w: 12, d: 10 })
  const [cWidthM, setCWidthM] = useState(18)
  const [cStart, setCStart] = useState<[number, number] | null>(null)
  const [cSel, setCSel] = useState<number | null>(null) // selected wall index (click-to-delete)
  const [cStatus, setCStatus] = useState('Upload a plan to auto-detect a draft, then click to fix walls.')

  // plan -> 3D via the backend (Step C)
  const [pFile, setPFile] = useState<File | null>(null)
  const [pLoading, setPLoading] = useState(false)
  const [pPlan, setPPlan] = useState<BuiltPlan | null>(null)
  const [pWidthFt, setPWidthFt] = useState<number>(0) // 0 = let the backend decide
  const [pStatus, setPStatus] = useState('Upload a plan (PDF or image) — the backend parses it and builds real 3D.')

  const handlePlan = async (f: File, wing?: number) => {
    setPFile(f)
    setPLoading(true)
    setPStatus(wing === undefined ? 'Parsing plan + building 3D…' : `Building wing ${wing}…`)
    try {
      const built = await buildPlan(f, pWidthFt || undefined, wing)
      // swap in the new model FIRST, then release the old one's blob URL —
      // revoking before the rebuild finishes can break the model on screen
      const old = pPlan
      setPPlan(built)
      if (old) URL.revokeObjectURL(old.glbUrl)
      const m = built.meta
      setPStatus(`${m.plan_width_ft.toFixed(1)} × ${m.plan_depth_ft.toFixed(1)} ft · ` +
        `${built.doors} doors · ${built.windows} windows · scale: ${m.scale.source}`)
    } catch (e: any) {
      setPPlan(null)
      setPStatus('Error: ' + (e?.message || 'backend unreachable — is uvicorn running on :8000?'))
    } finally {
      setPLoading(false)
    }
  }

  // fit the camera to the built model's actual box (long thin plans otherwise
  // render tiny and off-centre with a fixed preset)
  const lastFrame = useRef<{ center: [number, number, number]; size: [number, number, number] } | null>(null)
  const framePlan = useCallback((info: { center: [number, number, number]; size: [number, number, number] }) => {
    lastFrame.current = info
    const [cx, cy, cz] = info.center
    const maxd = Math.max(info.size[0], info.size[2]) || 10
    setView({
      position: [cx + maxd * 0.75, cy + maxd * 0.95, cz + maxd * 0.75],
      target: [cx, cy, cz],
    })
  }, [])

  const pickMaterial = (k: FloorKey) => { setFloor(k); setView({ ...PRESETS[k] }) } // triggers GSAP tween

  const handleConvert = async (f: File) => {
    const ext = f.name.toLowerCase().split('.').pop() || ''
    if (ext === 'glb' || ext === 'gltf') { loadUrl(URL.createObjectURL(f)); setMode('viewer'); return }
    // guard: the in-browser detector chokes on CAD PDFs / big files. Send those
    // to the backend engine (Plan → 3D) instead of freezing the tab.
    if (ext === 'pdf' || f.size > 3 * 1024 * 1024) {
      setCStatus('This looks like a CAD or large file. Use the “Plan → 3D” tab — it runs the full backend engine and won’t freeze. Convert is best for simple photos/images.')
      return
    }
    try {
      setCStatus('Loading engine + reading plan…'); setCSegs([]); setCStart(null); setCSel(null)
      const canvas = ext === 'pdf' ? await rasterizePdf(f) : await imageToCanvas(f)
      setCStatus('Detecting walls… (first run downloads the engine, ~10–20s)')
      const r = await detectWallsWorker(canvas, cWidthM)
      setCSegs(r.segments); setCUnder(r.underlay); setCDims({ w: r.widthM, d: r.depthM })
      setCStatus(`Auto-detected ${r.segments.length} walls. Click along missing walls to add them — or Clear and trace fresh.`)
    } catch (e: any) {
      setCStatus('Error: ' + (e?.message || 'detection failed'))
    }
  }
  const addPoint = (x: number, z: number) => {
    if (cStart) setCSegs((s) => [...s, [cStart[0], cStart[1], x, z]])
    setCStart([x, z])
  }
  const newWall = () => setCStart(null)
  const undo = () => { setCSegs((s) => s.slice(0, -1)); setCSel(null) }
  const clearAll = () => { setCSegs([]); setCStart(null); setCSel(null) }
  const deleteSelected = () => {
    if (cSel === null) return
    setCSegs((s) => s.filter((_, i) => i !== cSel))
    setCSel(null)
  }
  const exportJSON = () => {
    const data = { metresWide: cDims.w, metresDeep: cDims.d, ceilingHeight: 2.5, wallThickness: 0.2, walls: cSegs }
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    a.download = 'plan.json'; a.click()
  }

  // desktop keyboard shortcuts: T = top view, F = re-frame the loaded plan
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (e.key === 't' || e.key === 'T') setView({ ...TOP_VIEW })
      if ((e.key === 'f' || e.key === 'F') && lastFrame.current) framePlan(lastFrame.current)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [framePlan])

  useEffect(() => {
    if (mode === 'convert') setView({ ...TOP_VIEW })
    else if (mode === 'room') setView({ ...PRESETS.default })
    else setView({ position: [7, 5, 9], target: [0, 1.5, 0] })  // plan + viewer
  }, [mode])

  // all hooks above have run — safe to branch
  if (!entered) return <LandingHero onEnter={enterApp} />

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-background">
      <LoadingScreen active={pLoading} />
      {/* ─────────── Glassmorphism sidebar ─────────── */}
      <aside
        style={{ background: 'rgba(15, 23, 42, 0.6)' }}
        className="glass-scroll absolute left-5 top-5 z-20 flex max-h-[calc(100vh-2.5rem)] w-[320px]
                   max-w-[calc(100vw-2.5rem)] flex-col overflow-y-auto rounded-2xl border border-white/10
                   shadow-2xl backdrop-blur-md"
      >
        <header className="flex items-center gap-3 px-6 pt-6">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-neon/15 text-neon shadow-glow">
            <svg width="18" height="18" viewBox="0 0 256 256" fill="none" stroke="currentColor" strokeWidth="20" strokeLinejoin="round" strokeLinecap="round">
              <path d="M128 18 L232 78 L232 178 L128 238 L24 178 L24 78 Z" />
              <path d="M24 78 L128 138 L232 78 M128 138 L128 238" />
            </svg>
          </div>
          <div className="leading-tight">
            <h1 className="font-playfair text-xl italic text-foreground">Drishti</h1>
            <p className="text-xs text-muted-foreground">every plan holds a building within</p>
          </div>
        </header>

        {/* Plan → 3D is the primary flow; Demo/Convert/Viewer live under Advanced */}
        <nav className="flex flex-wrap items-center gap-1 px-6 pt-5">
          {PRIMARY_MODES.map((m) => (
            <div key={m.id}>
              <PillButton active={mode === m.id} layoutId="tabPill" onClick={() => setMode(m.id)}>
                <span className="block w-full text-center">{m.label}</span>
              </PillButton>
            </div>
          ))}
          {showAdvanced && ADVANCED_MODES.map((m) => (
            <div key={m.id}>
              <PillButton active={mode === m.id} layoutId="tabPill" onClick={() => setMode(m.id)}>
                <span className="block w-full text-center">{m.label}</span>
              </PillButton>
            </div>
          ))}
          <button
            onClick={() => setShowAdvanced((v) => !v)}
            className="ml-auto rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
          >
            {showAdvanced ? 'Hide' : 'Advanced'}
          </button>
        </nav>

        {/* mode content */}
        <div className="p-6 pt-5">
          <AnimatePresence mode="wait">
            <motion.div
              key={mode} variants={panelVariants} initial="initial" animate="animate" exit="exit"
              transition={{ duration: 0.18, ease: 'easeOut' }} className="flex flex-col gap-5"
            >
              {mode === 'room' && (
                <>
                  <Status>A furnished demo room. Switch the floor finish — the camera glides to a matching angle.</Status>
                  <div className="grid grid-cols-3 gap-2">
                    {Object.entries(FLOOR_MATERIALS).map(([k, mat]) => (
                      <PillButton key={k} active={k === floor} layoutId="matPill" onClick={() => pickMaterial(k as FloorKey)}>
                        <span className="block w-full text-center">{mat.label}</span>
                      </PillButton>
                    ))}
                  </div>
                  <Button variant="secondary" className="w-full" onClick={() => setView({ ...PRESETS.default })}>Reset view</Button>
                </>
              )}

              {mode === 'convert' && (
                <>
                  <Status>1 · Upload a plan — it auto-detects a draft. 2 · Click along walls it missed. 3 · The 3D updates live.</Status>
                  <Field label="Building width (m)">
                    <NumberInput value={cWidthM} min={1} step={0.5} onChange={(e) => setCWidthM(+e.target.value)} />
                  </Field>
                  <Upload onFile={handleConvert} accept=".jpg,.jpeg,.png,.pdf,.glb,.gltf">Upload plan</Upload>
                  {cUnder && (
                    <div className="flex flex-col gap-2">
                      <div className="grid grid-cols-3 gap-2">
                        <Button size="sm" variant="outline" onClick={newWall}>New wall</Button>
                        <Button size="sm" variant="outline" onClick={undo}>Undo</Button>
                        <Button size="sm" variant="outline" onClick={clearAll}>Clear</Button>
                      </div>
                      <Button size="sm" variant="destructive" className="w-full"
                        disabled={cSel === null} onClick={deleteSelected}>
                        {cSel === null ? 'Click a wall to select' : 'Delete selected wall'}
                      </Button>
                      <Button variant="secondary" className="w-full" onClick={exportJSON}>Export plan.json</Button>
                    </div>
                  )}
                  <Status>{cStatus}{cSegs.length ? ` · ${cSegs.length} walls` : ''}</Status>
                </>
              )}

              {mode === 'plan' && (
                <>
                  <Status>Upload a floor plan — the backend reads the CAD geometry, finds walls, doors and scale, and returns a real 3D model.</Status>
                  <Field label="Width override (ft)">
                    <NumberInput value={pWidthFt || ''} min={0} step={1} placeholder="auto"
                      onChange={(e) => setPWidthFt(+e.target.value || 0)} />
                  </Field>
                  <Upload onFile={(f) => handlePlan(f)} accept=".pdf,.png,.jpg,.jpeg">Upload plan</Upload>
                  {pPlan?.meta.wing && pPlan.meta.wing.count > 1 && pFile && (
                    <div className="grid grid-cols-3 gap-2">
                      {Array.from({ length: pPlan.meta.wing.count }, (_, i) => (
                        <Button key={i} size="sm"
                          variant={pPlan.meta.wing!.index === i ? 'secondary' : 'outline'}
                          onClick={() => handlePlan(pFile, i)}>
                          Wing {i}
                        </Button>
                      ))}
                    </div>
                  )}
                  <Status>{pStatus}</Status>
                  {pPlan && pPlan.meta.warnings.length > 0 && (
                    <details className="text-xs text-muted-foreground">
                      <summary className="cursor-pointer">{pPlan.meta.warnings.length} parser notes</summary>
                      <ul className="mt-1 list-disc pl-4">
                        {pPlan.meta.warnings.map((w, i) => <li key={i}>{w}</li>)}
                      </ul>
                    </details>
                  )}
                </>
              )}

              {mode === 'viewer' && (
                <>
                  <Status>Load any .glb / .gltf 3D model — paste a URL or upload a file.</Status>
                  <TextInput placeholder="https://…/model.glb" value={urlText} onChange={(e) => setUrlText(e.target.value)} />
                  <Button className="w-full" onClick={() => urlText.trim() && loadUrl(urlText.trim())}>Load from URL</Button>
                  <Upload onFile={(f) => loadUrl(URL.createObjectURL(f))} accept=".glb,.gltf">Upload .glb</Upload>
                  <Status>
                    {vStatus === 'loading' && 'Loading model…'}
                    {vStatus === 'error' && '⚠ Could not load — check the URL is a .glb and allows CORS.'}
                    {vStatus === 'idle' && 'Drag to orbit · scroll to zoom.'}
                  </Status>
                </>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </aside>

      {/* ─────────── 3D scene ─────────── */}
      <Canvas shadows camera={{ position: PRESETS.default.position, fov: 50 }} className="!absolute inset-0">
        <Lights />

        {mode === 'room' && (
          <>
            <Room floor={floor} windowWall />
            <Furniture />
            <Suspense fallback={null}>
              <ErrorBoundary fallback={null}>
                <Model url={SOFA_URL} position={[-1.4, 0.002, -0.4]} rotationY={Math.PI / 2} targetSize={1.9} />
              </ErrorBoundary>
            </Suspense>
            {MARKERS.map((m) => (
              <CameraMarker key={m.id} position={m.spot} onSelect={() => setView({ ...m.view })} />
            ))}
          </>
        )}

        {mode === 'convert' && (
          <TraceScene imageUrl={cUnder} widthM={cDims.w} heightM={cDims.d}
            segments={cSegs} start={cStart} onPick={addPoint}
            selected={cSel} onSelect={setCSel} />
        )}

        {mode === 'plan' && (
          <>
            {/* HDR comes from a CDN — if it can't load (offline demo), keep the app alive */}
            <ErrorBoundary fallback={null}>
              <Suspense fallback={null}><Environment preset="apartment" /></Suspense>
            </ErrorBoundary>
            <ContactShadows position={[0, 0, 0]} opacity={0.55} scale={40} blur={2.2} far={12} />
            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
              <planeGeometry args={[60, 60]} />
              <meshStandardMaterial color="#d9d6d0" roughness={0.95} />
            </mesh>
            {pPlan && (
              <Suspense fallback={null}>
                <ErrorBoundary key={pPlan.glbUrl} fallback={null}
                  onError={() => setPStatus('⚠ The 3D model failed to render — try rebuilding, another wing, or a smaller plan.')}>
                  <Model key={pPlan.glbUrl} url={pPlan.glbUrl} targetSize={14} position={[0, 0, 0]} center onFramed={framePlan} />
                </ErrorBoundary>
              </Suspense>
            )}
          </>
        )}

        {mode === 'viewer' && (
          <>
            <ErrorBoundary fallback={null}>
              <Suspense fallback={null}><Environment preset="apartment" /></Suspense>
            </ErrorBoundary>
            <ContactShadows position={[0, 0, 0]} opacity={0.55} scale={30} blur={2.2} far={12} />
            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
              <planeGeometry args={[40, 40]} />
              <meshStandardMaterial color="#d9d6d0" roughness={0.95} />
            </mesh>
            {modelUrl && (
              <Suspense fallback={null}>
                <ErrorBoundary key={modelUrl} fallback={null} onError={() => setVStatus('error')}>
                  <Model key={modelUrl} url={modelUrl} targetSize={6} position={[0, 0, 0]} />
                  <ReadySignal onReady={() => setVStatus('idle')} />
                </ErrorBoundary>
              </Suspense>
            )}
          </>
        )}

        <CameraRig view={view} />
        <OrbitControls makeDefault enableDamping target={[0, 1.5, 0]} />
      </Canvas>

      {/* ── empty state: nothing loaded yet in Plan → 3D ── */}
      {mode === 'plan' && !pPlan && !pLoading && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
          <p className="font-playfair px-6 text-center text-2xl italic text-white/25 sm:text-3xl">
            upload a plan — watch it stand up
          </p>
        </div>
      )}

      {/* ── meta HUD: the built plan's numbers, landing-style glass pill ── */}
      {mode === 'plan' && pPlan && (
        <motion.div
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
          className="absolute bottom-5 left-1/2 z-20 -translate-x-1/2 whitespace-nowrap rounded-full
                     border border-white/10 bg-black/50 px-5 py-2.5 text-xs text-white/80 backdrop-blur-md"
        >
          <span className="font-medium text-white">
            {pPlan.meta.plan_width_ft.toFixed(1)} × {pPlan.meta.plan_depth_ft.toFixed(1)} ft
          </span>
          <span className="mx-2 text-white/30">·</span>{pPlan.doors} doors
          <span className="mx-2 text-white/30">·</span>{pPlan.windows} windows
          <span className="mx-2 text-white/30">·</span>scale: {pPlan.meta.scale.source}
          {pPlan.meta.wing && pPlan.meta.wing.count > 1 && (
            <><span className="mx-2 text-white/30">·</span>wing {pPlan.meta.wing.index + 1}/{pPlan.meta.wing.count}</>
          )}
        </motion.div>
      )}

      {/* ── desktop controls hint ── */}
      <div className="pointer-events-none absolute bottom-5 right-5 z-20 hidden text-[11px] tracking-wide text-white/35 md:block">
        drag to orbit · scroll to zoom ·{' '}
        <span className="rounded border border-white/20 px-1">T</span> top view ·{' '}
        <span className="rounded border border-white/20 px-1">F</span> frame plan
      </div>
    </div>
  )
}
