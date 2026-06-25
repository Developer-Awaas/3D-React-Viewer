import { Suspense, useEffect, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment, ContactShadows } from '@react-three/drei'
import Room from './components/Room'
import Lights from './components/Lights'
import Furniture from './components/Furniture'
import Model from './components/Model'
import ErrorBoundary from './components/ErrorBoundary'
import CameraMarker from './components/CameraMarker'
import CameraRig, { View } from './components/CameraRig'
import FloorPlanUnderlay from './components/FloorPlanUnderlay'
import WallsFromPlan from './components/WallsFromPlan'
import AutoPlan from './components/AutoPlan'
import TraceScene from './components/TraceScene'
import TracePanel from './components/TracePanel'
import ViewerPanel from './components/ViewerPanel'
import ImportScene from './components/ImportScene'
import ImportPanel from './components/ImportPanel'
import { detectWalls, Seg } from './cv/detectWalls'
import { rasterizePdf, imageToCanvas } from './cv/rasterizePdf'
import { useTrace } from './trace/useTrace'
import { FLOOR_MATERIALS, FloorKey } from './materials'
import { MARKERS, OVERVIEW } from './scene'

const SOFA_URL =
  'https://cdn.jsdelivr.net/gh/KhronosGroup/glTF-Sample-Assets@main/Models/GlamVelvetSofa/glTF-Binary/GlamVelvetSofa.glb'

const TOP_VIEW: View = { position: [0, 16, 0.01], target: [0, 0, 0] } // look straight down for tracing

// Runs after a model finishes loading inside <Suspense> (signals "ready").
function ReadySignal({ onReady }: { onReady: () => void }) {
  useEffect(() => { onReady() }, [onReady])
  return null
}

type Mode = 'room' | 'plan' | 'trace' | 'auto' | 'viewer' | 'import'

export default function App() {
  const [mode, setMode] = useState<Mode>('room')
  const [floor, setFloor] = useState<FloorKey>('marble')
  const [view, setView] = useState<View | null>(null)
  const trace = useTrace()

  // GLB Viewer state: which model URL to show + a simple load status for the panel.
  const [modelUrl, setModelUrl] = useState<string | null>(null)
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const loadUrl = (u: string) => { setStatus('loading'); setModelUrl(u) }
  const uploadFile = (f: File) => { setStatus('loading'); setModelUrl(URL.createObjectURL(f)) }

  // ── Import mode: in-browser auto-convert (opencv.js) ──
  const [impSegs, setImpSegs] = useState<Seg[]>([])
  const [impUnder, setImpUnder] = useState<string | null>(null)
  const [impDims, setImpDims] = useState({ w: 12, d: 10 })
  const [impWidthM, setImpWidthM] = useState(18)
  const [impStatus, setImpStatus] = useState('Upload a plan to begin.')

  const handleImport = async (f: File) => {
    const ext = f.name.toLowerCase().split('.').pop() || ''
    if (ext === 'glb' || ext === 'gltf') {            // a 3D model -> view it
      loadUrl(URL.createObjectURL(f)); setMode('viewer'); return
    }
    try {
      setImpStatus('Loading OpenCV + reading plan…'); setImpSegs([])
      const canvas = ext === 'pdf' ? await rasterizePdf(f) : await imageToCanvas(f)
      setImpStatus('Detecting walls…')
      const r = await detectWalls(canvas, impWidthM)
      setImpSegs(r.segments); setImpUnder(r.underlay); setImpDims({ w: r.widthM, d: r.depthM })
      setImpStatus(`Done — ${r.segments.length} walls detected.`)
    } catch (e: any) {
      setImpStatus('Error: ' + (e?.message || 'detection failed'))
    }
  }

  // Fly to a sensible camera when entering each mode.
  useEffect(() => {
    if (mode === 'trace') setView({ ...TOP_VIEW })
    else if (mode === 'room') setView({ ...OVERVIEW })
    else if (mode === 'viewer') setView({ position: [7, 5, 9], target: [0, 1.5, 0] })
    else setView({ position: [11, 13, 15], target: [0, 0, 0] }) // plan / auto / import: high view
  }, [mode])

  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh' }}>
      {/* ── TOP UI PANEL ── */}
      <div style={{
        position: 'absolute', top: 16, left: 16, zIndex: 2,
        display: 'flex', gap: 8, padding: 8, flexWrap: 'wrap', maxWidth: '92vw',
        background: 'rgba(20,20,20,0.6)', borderRadius: 10, backdropFilter: 'blur(6px)',
      }}>
        {(['room', 'plan', 'trace', 'auto', 'viewer', 'import'] as Mode[]).map((m) => (
          <button key={m} onClick={() => setMode(m)} style={{
            padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
            border: mode === m ? '2px solid #6cf' : '1px solid #888',
            background: mode === m ? '#6cf' : 'transparent',
            color: mode === m ? '#012' : '#eee', fontWeight: 700,
          }}>{m === 'room' ? 'Demo Room' : m === 'plan' ? 'Floor Plan' : m === 'trace' ? 'Trace' : m === 'auto' ? 'Auto (CV)' : m === 'viewer' ? 'GLB Viewer' : 'Import (auto)'}</button>
        ))}

        {mode === 'room' && (
          <>
            <span style={{ width: 1, background: '#666', margin: '0 2px' }} />
            {Object.entries(FLOOR_MATERIALS).map(([k, mat]) => {
              const active = k === floor
              return (
                <button key={k} onClick={() => setFloor(k as FloorKey)} style={{
                  padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
                  border: active ? '2px solid #fff' : '1px solid #888',
                  background: active ? '#fff' : 'transparent',
                  color: active ? '#111' : '#eee', fontWeight: 600,
                }}>{mat.label}</button>
              )
            })}
            <button onClick={() => setView({ ...OVERVIEW })} style={{
              padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
              border: '1px solid #888', background: 'transparent', color: '#eee', fontWeight: 600,
            }}>Reset view</button>
          </>
        )}
      </div>

      {/* ── TRACE CONTROLS (only in trace mode) ── */}
      {mode === 'trace' && (
        <TracePanel
          hasImage={trace.hasImage}
          widthM={trace.widthM}
          setWidthM={trace.setWidthM}
          count={trace.segments.length}
          onUpload={trace.onUpload}
          newWall={trace.newWall}
          undo={trace.undo}
          clear={trace.clear}
          exportJSON={trace.exportJSON}
        />
      )}

      {/* ── VIEWER CONTROLS (only in viewer mode) ── */}
      {mode === 'viewer' && (
        <ViewerPanel onLoadUrl={loadUrl} onUploadFile={uploadFile} status={status} />
      )}

      {/* ── IMPORT CONTROLS (only in import mode) ── */}
      {mode === 'import' && (
        <ImportPanel onFile={handleImport} status={impStatus} count={impSegs.length}
          widthM={impWidthM} setWidthM={setImpWidthM} />
      )}

      {/* ── 3D SCENE ── */}
      <Canvas shadows camera={{ position: OVERVIEW.position, fov: 50 }} style={{ width: '100%', height: '100%' }}>
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

        {mode === 'plan' && (
          <>
            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
              <planeGeometry args={[16, 14]} />
              <meshStandardMaterial color="#cfcfcf" />
            </mesh>
            <Suspense fallback={null}><FloorPlanUnderlay /></Suspense>
            <WallsFromPlan />
          </>
        )}

        {mode === 'trace' && (
          <TraceScene
            imageUrl={trace.imageUrl}
            widthM={trace.widthM}
            heightM={trace.heightM}
            segments={trace.segments}
            start={trace.start}
            onPick={trace.addPoint}
          />
        )}

        {mode === 'auto' && (
          <Suspense fallback={null}><AutoPlan /></Suspense>
        )}

        {mode === 'import' && (
          <ImportScene segments={impSegs} underlay={impUnder} widthM={impDims.w} depthM={impDims.d} />
        )}

        {mode === 'viewer' && (
          <>
            {/* HDR image-based lighting for realistic reflections + soft shadow */}
            <Suspense fallback={null}><Environment preset="apartment" /></Suspense>
            <ContactShadows position={[0, 0, 0]} opacity={0.55} scale={30} blur={2.2} far={12} />
            {/* ground for shadows */}
            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
              <planeGeometry args={[40, 40]} />
              <meshStandardMaterial color="#d9d6d0" roughness={0.95} />
            </mesh>
            {modelUrl && (
              // key={modelUrl} remounts cleanly each time a new model is loaded,
              // which also resets the ErrorBoundary if the previous load failed.
              <Suspense fallback={null}>
                <ErrorBoundary key={modelUrl} fallback={null} onError={() => setStatus('error')}>
                  <Model key={modelUrl} url={modelUrl} targetSize={6} position={[0, 0, 0]} />
                  <ReadySignal onReady={() => setStatus('idle')} />
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
