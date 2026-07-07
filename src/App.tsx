import { InputHTMLAttributes, ReactNode, Suspense, useEffect, useState } from 'react'
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
import { MARKERS, OVERVIEW } from './scene'
import { PRESETS } from './cameraPresets'
import { Button } from './components/ui/Button'

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

type Mode = 'room' | 'convert' | 'viewer'
const MODES: { id: Mode; label: string }[] = [
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
      className="inline-flex h-9 w-full cursor-pointer items-center justify-center gap-2 rounded-lg
                 bg-neon px-4 text-sm font-semibold text-slate-900 shadow-glow hover:brightness-105">
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
      className={`relative rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
        active ? 'text-slate-900' : 'text-muted-foreground hover:text-foreground'
      }`}
    >
      {active && <motion.span layoutId={layoutId} transition={PILL_SPRING}
        className="absolute inset-0 -z-0 rounded-lg bg-neon shadow-glow" />}
      <span className="relative z-10">{children}</span>
    </motion.button>
  )
}

export default function App() {
  const [mode, setMode] = useState<Mode>('room')
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

  const pickMaterial = (k: FloorKey) => { setFloor(k); setView({ ...PRESETS[k] }) } // triggers GSAP tween

  const handleConvert = async (f: File) => {
    const ext = f.name.toLowerCase().split('.').pop() || ''
    if (ext === 'glb' || ext === 'gltf') { loadUrl(URL.createObjectURL(f)); setMode('viewer'); return }
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

  useEffect(() => {
    if (mode === 'convert') setView({ ...TOP_VIEW })
    else if (mode === 'room') setView({ ...PRESETS.default })
    else setView({ position: [7, 5, 9], target: [0, 1.5, 0] })
  }, [mode])

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-background">
      {/* ─────────── Glassmorphism sidebar ─────────── */}
      <aside
        style={{ background: 'rgba(15, 23, 42, 0.6)' }}
        className="glass-scroll absolute left-5 top-5 z-20 flex max-h-[calc(100vh-2.5rem)] w-[320px]
                   max-w-[calc(100vw-2.5rem)] flex-col overflow-y-auto rounded-2xl border border-white/10
                   shadow-2xl backdrop-blur-md"
      >
        <header className="flex items-center gap-3 px-6 pt-6">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-neon/15 text-neon shadow-glow">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 9l9-6 9 6v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9z" /><path d="M9 21V12h6v9" />
            </svg>
          </div>
          <div className="leading-tight">
            <h1 className="text-sm font-semibold tracking-tight text-foreground">Drishti 3D</h1>
            <p className="text-xs text-muted-foreground">2D → 3D converter</p>
          </div>
        </header>

        {/* mode tabs */}
        <nav className="flex gap-1 px-6 pt-5">
          {MODES.map((m) => (
            <div key={m.id} className="flex-1">
              <PillButton active={mode === m.id} layoutId="tabPill" onClick={() => setMode(m.id)}>
                <span className="block w-full text-center">{m.label}</span>
              </PillButton>
            </div>
          ))}
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

        {mode === 'viewer' && (
          <>
            <Suspense fallback={null}><Environment preset="apartment" /></Suspense>
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
    </div>
  )
}
