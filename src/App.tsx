import { InputHTMLAttributes, ReactNode, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment, ContactShadows, Sky, useGLTF } from '@react-three/drei'
import { AnimatePresence, motion, type Variants } from 'framer-motion'
import Room from './components/Room'
import Lights from './components/Lights'
import PlanLights from './components/PlanLights'
import Furniture from './components/Furniture'
import Model from './components/Model'
import { ContactModal } from './components/AppSections'
import VisualizeButton from './components/VisualizeButton'
import GBufferBridge from './components/GBufferBridge'
import MeasureTool from './components/MeasureTool'
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
import { buildPlan, downloadAreaStatement, type BuiltPlan } from './api/scene'
import { roomView, roomWorldPoint, type FrameInfo } from './three/roomPoints'
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
// Hip roof fitted to the building footprint: ridge along the LONG axis, sloped
// trapezoid sides + triangular hip ends, plus a thin eave slab. Replaces the
// old 4-sided cone, which ballooned into a huge pyramid on elongated plans.
function HipRoof({ center, w, d }: { center: [number, number, number]; w: number; d: number }) {
  const rise = Math.min(w, d) * 0.35
  const geom = useMemo(() => {
    const hw = w / 2, hd = d / 2
    const alongX = w >= d
    const r = (Math.max(w, d) - Math.min(w, d)) / 2       // ridge half-length
    type V = [number, number, number]
    const R1: V = alongX ? [-r, rise, 0] : [0, rise, -r]
    const R2: V = alongX ? [r, rise, 0] : [0, rise, r]
    const A: V = [-hw, 0, -hd], B: V = [hw, 0, -hd]
    const C: V = [hw, 0, hd], D: V = [-hw, 0, hd]
    const tris: V[] = alongX
      ? [A, B, R2, A, R2, R1, C, D, R1, C, R1, R2, D, A, R1, B, C, R2]
      : [A, D, R2, A, R2, R1, C, B, R1, C, R1, R2, B, A, R1, D, C, R2]
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.Float32BufferAttribute(tris.flat(), 3))
    g.computeVertexNormals()
    return g
  }, [w, d, rise])
  return (
    <group position={center}>
      <mesh position={[0, 0.04, 0]} castShadow>
        <boxGeometry args={[w, 0.08, d]} />
        <meshStandardMaterial color="#cfc9bf" roughness={0.95} />
      </mesh>
      <mesh position={[0, 0.08, 0]} geometry={geom} castShadow>
        <meshStandardMaterial color="#d8d2c6" roughness={0.92} side={THREE.DoubleSide} />
      </mesh>
    </group>
  )
}

function Upload({ onFile, accept, children }: { onFile: (f: File) => void; accept: string; children: ReactNode }) {
  return (
    <motion.label whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }} transition={{ duration: 0.15 }}
      className="inline-flex h-9 w-full cursor-pointer items-center justify-center gap-2 rounded-full
                 bg-neon px-4 text-sm font-semibold text-white shadow-glow hover:brightness-105
                 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background">
      {children}
      {/* sr-only (not `hidden`) keeps the input focusable, so the upload is keyboard-reachable */}
      <input type="file" accept={accept} className="sr-only"
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
    // push a history entry so the browser BACK button returns to the landing
    // hero instead of leaving the site (entering is otherwise just state)
    try { window.history.pushState({ drishtiApp: true }, '') } catch { /* ignore */ }
    setEntered(true)
  }, [])

  // browser Back -> show the landing again; Forward -> re-enter the app
  useEffect(() => {
    const onPop = (e: PopStateEvent) => {
      const inApp = Boolean((e.state as { drishtiApp?: boolean } | null)?.drishtiApp)
      try {
        if (inApp) sessionStorage.setItem('drishti_entered', '1')
        else sessionStorage.removeItem('drishti_entered')
      } catch { /* ignore */ }
      setEntered(inApp)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  // page refreshed mid-app (entered restored from sessionStorage): make sure
  // there is still a landing entry underneath for Back to land on
  useEffect(() => {
    if (entered && !window.history.state?.drishtiApp) {
      try { window.history.pushState({ drishtiApp: true }, '') } catch { /* ignore */ }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [floor, setFloor] = useState<FloorKey>('marble')
  const [view, setView] = useState<View | null>(null)

  // viewer
  const [modelUrl, setModelUrl] = useState<string | null>(null)
  const [vStatus, setVStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [urlText, setUrlText] = useState('')
  const loadUrl = (u: string) => {
    // release the previous model's blob URL (and its GLTF cache entry) so
    // repeated uploads don't leak memory
    if (modelUrl && modelUrl !== u && modelUrl.startsWith('blob:')) {
      useGLTF.clear(modelUrl)
      URL.revokeObjectURL(modelUrl)
    }
    setVStatus('loading'); setModelUrl(u)
  }

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
  // shared style: the Visualize panel's style choice ALSO re-dresses the
  // walkable 3D's materials live (floors, walls, columns) — same palette
  const [vizStyle, setVizStyle] = useState('scandinavian')
  // founders popup, reachable from the sidebar in every app mode
  const [contactOpen, setContactOpen] = useState(false)
  const [pStatus, setPStatus] = useState('Upload a plan (PDF, image, or CAD .dxf/.dwg) — the backend parses it and builds real 3D.')

  // bundled demo building: built by tools/make_sample_plan.py through the
  // REAL engine; loads straight from public/ with NO backend needed, so the
  // first-visit wow works even while the API is cold or down
  // request sequencing: each build gets an id; a finished build whose id no
  // longer matches lost the race — its state updates are dropped and its blob
  // URL revoked, so a stale slow response can't overwrite a newer plan
  const planReqId = useRef(0)

  const loadSample = async () => {
    const id = ++planReqId.current // invalidate any in-flight build
    setPFile(null)
    setPLoading(true)
    setPStatus('Loading the sample building…')
    try {
      const m = await (await fetch('/sample.meta.json')).json()
      // re-check AFTER the await: if the user uploaded a real plan while the
      // sample was fetching, that newer request owns the UI — don't clobber it
      if (id !== planReqId.current) return
      const old = pPlan
      setPPlan({ meta: m.meta, glbUrl: '/sample.glb', doors: m.doors,
                 windows: m.windows, rooms: m.rooms ?? [] })
      if (old) URL.revokeObjectURL(old.glbUrl)
      setPStatus(`Sample 2BHK · ${m.meta.plan_width_ft.toFixed(1)} × ` +
        `${m.meta.plan_depth_ft.toFixed(1)} ft — parsed by the same engine. ` +
        'Now try your own CAD PDF.')
    } catch {
      if (id === planReqId.current) setPStatus('Could not load the sample building.')
    } finally {
      if (id === planReqId.current) setPLoading(false)
    }
  }

  const handlePlan = async (f: File, wing?: number, northDeg?: number) => {
    const id = ++planReqId.current
    setPFile(f)
    setPLoading(true)
    setPStatus(wing === undefined ? 'Parsing plan + building 3D…' : `Building wing ${wing}…`)
    try {
      const built = await buildPlan(f, pWidthFt || undefined, wing,
                                    northDeg ?? pNorthDeg)
      if (id !== planReqId.current) { // a newer request won — drop this result
        URL.revokeObjectURL(built.glbUrl)
        return
      }
      // swap in the new model FIRST, then release the old one's blob URL —
      // revoking before the rebuild finishes can break the model on screen
      const old = pPlan
      setPPlan(built)
      if (old) URL.revokeObjectURL(old.glbUrl)
      const m = built.meta
      setPStatus(`${m.plan_width_ft.toFixed(1)} × ${m.plan_depth_ft.toFixed(1)} ft · ` +
        `${built.doors} doors · ${built.windows} windows · scale: ${m.scale.source}`)
    } catch (e: any) {
      if (id !== planReqId.current) return // stale failure — a newer request owns the UI
      setPPlan(null)
      setPStatus('Error: ' + (e?.message ||
        (import.meta.env.DEV
          ? 'backend unreachable — is uvicorn running on :8000?'
          : 'could not reach the server — please try again in a moment.')))
    } finally {
      if (id === planReqId.current) setPLoading(false)
    }
  }

  // fit the camera to the built model's actual box (long thin plans otherwise
  // render tiny and off-centre with a fixed preset). The frame info also
  // carries the model's scale/offset — needed to place room beacons.
  const lastFrame = useRef<FrameInfo | null>(null)
  const [frame, setFrame] = useState<FrameInfo | null>(null)
  const [roofOn, setRoofOn] = useState(false)  // R toggles a roof slab over the plan
  const [areaBusy, setAreaBusy] = useState(false)
  const [currentRoomType, setCurrentRoomType] = useState<string | undefined>(undefined)
  const [measureOn, setMeasureOn] = useState(false)   // M: click-to-measure
  const [pNorthDeg, setPNorthDeg] = useState(0)       // Vastu compass: sheet-North
  const framePlan = useCallback((info: FrameInfo) => {
    lastFrame.current = info
    setFrame(info)
    const [cx, cy, cz] = info.center
    const maxd = Math.max(info.size[0], info.size[2]) || 10
    setView({
      position: [cx + maxd * 0.75, cy + maxd * 0.95, cz + maxd * 0.75],
      target: [cx, cy, cz],
    })
  }, [])

  // walk inside: fly the camera to eye height in room N (beacon click / keys 1-9)
  const enterRoom = useCallback((n: number) => {
    const f = lastFrame.current
    const room = pPlan?.rooms?.[n]
    if (f && room) {
      setView(roomView(room, f, pPlan!.rooms.filter((_, i) => i !== n)))
      setCurrentRoomType(room.type)   // so Visualize can auto-match the room
    }
  }, [pPlan])

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

  // desktop keyboard shortcuts: T = top view, F = re-frame, R = roof, 1-9 = enter room
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null
      const tag = el?.tagName
      // don't hijack typing/select interaction (e.g. type-ahead "m" in the
      // Visualize dropdowns used to toggle measure mode)
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el?.isContentEditable) return
      if (e.key === 't' || e.key === 'T') setView({ ...TOP_VIEW })
      if ((e.key === 'f' || e.key === 'F') && lastFrame.current) framePlan(lastFrame.current)
      if (e.key === 'r' || e.key === 'R') setRoofOn((v) => !v)
      if (e.key === 'm' || e.key === 'M') setMeasureOn((v) => !v)
      if (/^[1-9]$/.test(e.key)) enterRoom(Number(e.key) - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [framePlan, enterRoom])

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
                    <NumberInput value={cWidthM} min={1} step={0.5} onChange={(e) => {
                      // guard: an emptied field parses to NaN — keep the last valid width
                      const v = +e.target.value
                      if (Number.isFinite(v) && v > 0) setCWidthM(v)
                    }} />
                  </Field>
                  <Upload onFile={handleConvert} accept=".jpg,.jpeg,.png,.glb,.gltf">Upload plan</Upload>
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
                  <Status>Upload any floor plan — CAD files (DWG/DXF) are read in real units for exact scale; CAD-exported PDFs read by layer. Photos &amp; scans are beta.</Status>
                  <Field label="Width override (ft)">
                    <NumberInput value={pWidthFt || ''} min={0} step={1} placeholder="auto"
                      onChange={(e) => setPWidthFt(+e.target.value || 0)} />
                  </Field>
                  <Upload onFile={(f) => handlePlan(f)} accept=".pdf,.png,.jpg,.jpeg,.dxf,.dwg">Upload plan</Upload>
                  <div className="grid grid-cols-2 gap-2">
                    <Button size="sm" variant="secondary" onClick={loadSample}>✨ Try a sample</Button>
                    <a href="/sample-plan.pdf" download
                       className="inline-flex h-8 items-center justify-center rounded-md border border-input
                                  bg-surface/60 px-2 text-xs text-muted-foreground hover:text-foreground">
                      Sample PDF ↓
                    </a>
                  </div>
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

          {/* contact stays reachable inside the app (story/FAQ live on the
              landing page only) — opens the same founders popup */}
          <button
            onClick={() => setContactOpen(true)}
            className="mt-4 w-full rounded-md border border-white/10 py-1.5 text-[11px]
                       text-muted-foreground transition-colors hover:border-neon/50 hover:text-foreground"
          >
            ✉ Contact founders
          </button>
        </div>
      </aside>

      <ContactModal open={contactOpen} onClose={() => setContactOpen(false)} />

      {/* ─────────── 3D scene ─────────── */}
      <Canvas
        shadows="soft"
        dpr={[1, 2]}
        gl={{ antialias: true, toneMappingExposure: 1.08, preserveDrawingBuffer: true }}
        camera={{ position: PRESETS.default.position, fov: 50 }}
        className="!absolute inset-0"
      >
        {/* plan mode needs a building-sized sun; the room lights' shadow
            camera (~3.5 m) silently clipped shadows on 14 m plans */}
        {mode === 'plan' ? <PlanLights /> : <Lights />}

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
            {/* self-contained sky shader (no downloads) + distance fog: the
                model sits in a world instead of a void */}
            <Sky distance={450000} sunPosition={[14, 22, 9]} turbidity={5.5} rayleigh={1.1} />
            <fog attach="fog" args={['#cfd9e4', 45, 160]} />
            {/* HDR comes from a CDN — if it can't load (offline demo), keep the app alive */}
            <ErrorBoundary fallback={null}>
              <Suspense fallback={null}><Environment preset="apartment" /></Suspense>
            </ErrorBoundary>
            <ContactShadows position={[0, 0, 0]} opacity={0.5} scale={44} blur={2.4} far={12} />
            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
              <planeGeometry args={[400, 400]} />
              <meshStandardMaterial color="#ccd3da" roughness={1} />
            </mesh>
            {pPlan && (
              <Suspense fallback={null}>
                <ErrorBoundary key={pPlan.glbUrl} fallback={null}
                  onError={() => setPStatus('⚠ The 3D model failed to render — try rebuilding, another wing, or a smaller plan.')}>
                  <Model key={pPlan.glbUrl} url={pPlan.glbUrl} targetSize={14} position={[0, 0, 0]} center plan styleKey={vizStyle} onFramed={framePlan} />
                </ErrorBoundary>
              </Suspense>
            )}
            {/* roof (press R): a HIP roof fitted to the building's footprint —
                ridge along the long axis, 45°-style hip ends, slight eave
                overhang. Off by default so the rooms stay visible. */}
            {pPlan && frame && roofOn && (
              <HipRoof
                center={[frame.center[0], frame.position[1] + frame.size[1], frame.center[2]]}
                w={frame.size[0] * 1.05}
                d={frame.size[2] * 1.05}
              />
            )}
            {/* walk-inside beacons: one per detected room — click to step in */}
            {pPlan && frame && pPlan.rooms.map((r, i) => (
              <CameraMarker key={r.id}
                position={roomWorldPoint(r, frame, 4.6)}
                onSelect={() => enterRoom(i)} />
            ))}
            {/* M: click two points -> real distance in ft/m */}
            <MeasureTool active={measureOn} modelScale={frame?.scale} />
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
        <GBufferBridge />
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

      {/* ── RERA area statement card (top-right) ── */}
      {mode === 'plan' && pPlan?.areaStatement && (
        <motion.div
          initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
          style={{ background: 'rgba(15, 23, 42, 0.6)' }}
          className="absolute right-5 top-5 z-20 w-56 rounded-2xl border border-white/10 p-4 text-xs
                     text-white/80 shadow-2xl backdrop-blur-md"
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="font-semibold text-white">Area statement</span>
            <span className="text-[10px] text-neon">RERA</span>
          </div>
          {([
            ['Carpet', pPlan.areaStatement.carpet_area],
            ['Built-up', pPlan.areaStatement.built_up_area],
            ['Super built-up', pPlan.areaStatement.super_built_up_area],
          ] as const).map(([label, pair]) => (
            <div key={label} className="flex items-baseline justify-between py-0.5">
              <span className="text-white/60">{label}</span>
              <span className="font-medium text-white">
                {pair.sqft.toLocaleString()} <span className="text-white/40">sqft</span>
              </span>
            </div>
          ))}
          <div className="mt-1 flex items-baseline justify-between border-t border-white/10 pt-1.5 text-white/60">
            <span>Efficiency</span>
            {/* NON-NEGOTIABLE: a failed room detection must never show as a
                silent 0% — the Plan Doctor downgrades it to "needs review" */}
            {pPlan.diagnosis?.efficiency_display === 'needs_review' || !(pPlan.areaStatement.efficiency_pct > 0)
              ? <span className="text-amber-300">needs review</span>
              : <span>{pPlan.areaStatement.efficiency_pct}%</span>}
          </div>
          {pPlan.diagnosis && (
            <div className="py-0.5 text-white/60">
              <div className="flex items-baseline justify-between">
                <span>Plan check</span>
                <span className={
                  pPlan.diagnosis.grade === 'A' ? 'text-emerald-300'
                    : pPlan.diagnosis.grade === 'B' ? 'text-emerald-200'
                    : pPlan.diagnosis.grade === 'C' ? 'text-amber-300' : 'text-red-300'
                }>
                  {pPlan.diagnosis.grade} · {pPlan.diagnosis.score}/100
                </span>
              </div>
              {pPlan.diagnosis.grade !== 'A' && (
                <div className="text-[10px] leading-snug text-white/35">
                  {pPlan.diagnosis.headline}
                </div>
              )}
            </div>
          )}
          {pPlan.vastu?.score != null && (
            <div className="flex items-baseline justify-between py-0.5 text-white/60">
              <span>Vastu <span className="text-white/30">({pPlan.vastu.rooms_scored} rooms)</span></span>
              <span className={pPlan.vastu.score >= 70 ? 'text-emerald-300' : pPlan.vastu.score >= 45 ? 'text-amber-300' : 'text-red-300'}>
                {pPlan.vastu.score}/100
              </span>
            </div>
          )}
          {pPlan.vastu && pFile && (
            <div className="flex items-center justify-between py-0.5 text-white/60">
              <span>North on sheet</span>
              <div className="flex gap-1">
                {([['↑', 0], ['→', 90], ['↓', 180], ['←', 270]] as const).map(([arrow, deg]) => (
                  <button
                    key={deg}
                    title={`North points ${arrow} (${deg}°)`}
                    onClick={() => {
                      if (deg === pNorthDeg) return
                      setPNorthDeg(deg)
                      handlePlan(pFile, undefined, deg)   // re-read with the new compass
                    }}
                    className={`h-6 w-6 rounded border text-xs leading-none
                      ${pNorthDeg === deg
                        ? 'border-neon/70 bg-neon/20 text-white'
                        : 'border-white/15 text-white/50 hover:border-neon/40 hover:text-white'}`}
                  >
                    {arrow}
                  </button>
                ))}
              </div>
            </div>
          )}
          {pPlan.costInr != null && pPlan.costInr > 0 && (
            <div className="py-0.5 text-white/60">
              <div className="flex items-baseline justify-between">
                <span>Walls &amp; finishes cost</span>
                <span className="text-white">₹{Math.round(pPlan.costInr / 1000).toLocaleString()}k</span>
              </div>
              {/* honest scope: this is NOT total construction cost (~half) */}
              <div className="text-[10px] leading-snug text-white/30">
                masonry + plaster + paint + flooring only — excludes RCC structure,
                doors/windows, electrical &amp; plumbing
              </div>
            </div>
          )}
          <button
            disabled={areaBusy || !pFile}
            onClick={async () => {
              if (!pFile) return
              setAreaBusy(true)
              try { await downloadAreaStatement(pFile, pWidthFt || undefined, pPlan.areaStatement!.loading_factor) }
              catch { /* surfaced by the button label reset */ }
              finally { setAreaBusy(false) }
            }}
            className="mt-3 w-full rounded-lg border border-neon/40 bg-neon/10 py-2 text-xs font-medium
                       text-white hover:border-neon/70 hover:bg-neon/20 disabled:opacity-50"
          >
            {areaBusy ? 'Preparing…' : '⬇ Download Excel'}
          </button>
        </motion.div>
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

      {/* ── Visualize (Beta): photoreal render of the current view (GPU backend) ── */}
      {mode === 'plan' && pPlan && (
        <VisualizeButton roomType={currentRoomType} rooms={pPlan.rooms} enterRoom={enterRoom}
          style={vizStyle} onStyleChange={setVizStyle} />
      )}

      {/* ── desktop controls hint ── */}
      <div className="pointer-events-none absolute bottom-5 right-5 z-20 hidden text-[11px] tracking-wide text-white/35 md:block">
        drag to orbit · scroll to zoom ·{' '}
        <span className="rounded border border-white/20 px-1">T</span> top view ·{' '}
        <span className="rounded border border-white/20 px-1">F</span> frame plan
        {mode === 'plan' && pPlan && (
          <>
            {' '}· <span className={`rounded border px-1 ${roofOn ? 'border-neon/60 text-neon' : 'border-white/20'}`}>R</span> roof
            {' '}· <span className={`rounded border px-1 ${measureOn ? 'border-neon/60 text-neon' : 'border-white/20'}`}>M</span> measure
          </>
        )}
        {mode === 'plan' && (pPlan?.rooms.length ?? 0) > 0 && (
          <> · <span className="rounded border border-white/20 px-1">1–{Math.min(9, pPlan!.rooms.length)}</span> step inside · click a beacon</>
        )}
      </div>
    </div>
  )
}
