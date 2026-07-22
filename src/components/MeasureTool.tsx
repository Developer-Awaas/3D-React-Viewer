import { useEffect, useRef, useState } from 'react'
import { useThree } from '@react-three/fiber'
import { Html, Line } from '@react-three/drei'
import * as THREE from 'three'

// Click-to-measure: with measure mode on (M key), click two points on the model
// (or ground) and read the real distance in feet + metres. World distances are
// divided by the model's fit-to-stage scale, so the number is the BUILDING's
// true dimension — the thing an architect actually wants to check.
const FT = 0.3048

export default function MeasureTool({
  active,
  modelScale,          // frame.scale from Model's onFramed — world -> model metres
}: {
  active: boolean
  modelScale?: number
}) {
  const { gl, camera, scene } = useThree()
  const [pts, setPts] = useState<THREE.Vector3[]>([])
  const ray = useRef(new THREE.Raycaster())

  useEffect(() => {
    if (!active) {
      setPts([])
      return
    }
    const el = gl.domElement
    const onDown = (e: PointerEvent) => {
      if (e.button !== 0) return
      const r = el.getBoundingClientRect()
      const ndc = new THREE.Vector2(
        ((e.clientX - r.left) / r.width) * 2 - 1,
        -((e.clientY - r.top) / r.height) * 2 + 1,
      )
      ray.current.setFromCamera(ndc, camera)
      const hits = ray.current
        .intersectObjects(scene.children, true)
        .filter((h) => !(h.object as THREE.Object3D).userData.measure
                       && (h.object as THREE.Mesh).isMesh)
      if (!hits.length) return
      const p = hits[0].point.clone()
      setPts((prev) => (prev.length >= 2 ? [p] : [...prev, p]))
    }
    el.addEventListener('pointerdown', onDown)
    return () => el.removeEventListener('pointerdown', onDown)
  }, [active, gl, camera, scene])

  if (!active || pts.length === 0) return null
  const scale = modelScale || 1
  const worldDist = pts.length === 2 ? pts[0].distanceTo(pts[1]) : 0
  const metres = worldDist / scale                 // building metres
  const feet = metres / FT
  const mid = pts.length === 2
    ? pts[0].clone().add(pts[1]).multiplyScalar(0.5)
    : pts[0]

  return (
    <group>
      {pts.map((p, i) => (
        <mesh key={i} position={p} userData={{ measure: true }}>
          <sphereGeometry args={[0.06, 12, 12]} />
          <meshBasicMaterial color="#fb923c" depthTest={false} />
        </mesh>
      ))}
      {pts.length === 2 && (
        <>
          <Line points={[pts[0], pts[1]]} color="#fb923c" lineWidth={2}
                depthTest={false} userData={{ measure: true }} />
          <Html position={mid} center distanceFactor={8} zIndexRange={[30, 20]}>
            <div style={{
              background: 'rgba(15,23,42,0.85)', color: '#fff',
              border: '1px solid rgba(251,146,60,0.5)', borderRadius: 8,
              padding: '3px 8px', fontSize: 12, whiteSpace: 'nowrap',
              fontFamily: 'system-ui', pointerEvents: 'none',
            }}>
              {feet.toFixed(1)} ft <span style={{ opacity: 0.6 }}>({metres.toFixed(2)} m)</span>
            </div>
          </Html>
        </>
      )}
    </group>
  )
}
