import { useEffect, useState } from 'react'
import * as THREE from 'three'
import { Seg } from '../cv/detectWalls'

function Wall({ seg, h = 2.5, t = 0.15 }: { seg: Seg; h?: number; t?: number }) {
  const [x1, z1, x2, z2] = seg
  const dx = x2 - x1, dz = z2 - z1
  const len = Math.hypot(dx, dz)
  if (len < 0.1) return null
  return (
    <mesh position={[(x1 + x2) / 2, h / 2, (z1 + z2) / 2]} rotation={[0, -Math.atan2(dz, dx), 0]} castShadow receiveShadow>
      <boxGeometry args={[len, h, t]} />
      <meshStandardMaterial color="#e7e2d8" />
    </mesh>
  )
}

// Renders the detected walls (live, from in-browser OpenCV) over the plan underlay.
export default function ImportScene({
  segments, underlay, widthM, depthM,
}: {
  segments: Seg[]
  underlay: string | null
  widthM: number
  depthM: number
}) {
  const [tex, setTex] = useState<THREE.Texture | null>(null)
  // cancel late loads + dispose the GPU texture on replace/unmount
  useEffect(() => {
    if (!underlay) { setTex(null); return }
    let cancelled = false
    let loaded: THREE.Texture | null = null
    new THREE.TextureLoader().load(underlay, (t) => {
      if (cancelled) { t.dispose(); return }
      t.colorSpace = THREE.SRGBColorSpace
      loaded = t
      setTex(t)
    })
    return () => { cancelled = true; loaded?.dispose() }
  }, [underlay])

  return (
    <group>
      {tex && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]} receiveShadow>
          <planeGeometry args={[widthM, depthM]} />
          <meshStandardMaterial map={tex} />
        </mesh>
      )}
      {segments.map((s, i) => <Wall key={i} seg={s} />)}
    </group>
  )
}
