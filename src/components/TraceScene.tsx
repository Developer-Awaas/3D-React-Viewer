import { useEffect, useState } from 'react'
import * as THREE from 'three'
import { Seg } from '../trace/useTrace'

function Wall({ seg, h, t }: { seg: Seg; h: number; t: number }) {
  const [x1, z1, x2, z2] = seg
  const dx = x2 - x1, dz = z2 - z1
  const len = Math.hypot(dx, dz)
  if (len < 1e-3) return null
  return (
    <mesh
      position={[(x1 + x2) / 2, h / 2, (z1 + z2) / 2]}
      rotation={[0, -Math.atan2(dz, dx), 0]}
      castShadow
      receiveShadow
    >
      <boxGeometry args={[len, h, t]} />
      <meshStandardMaterial color="#dcd7cd" />
    </mesh>
  )
}

export default function TraceScene({
  imageUrl, widthM, heightM, segments, start, onPick,
  ceiling = 2.5, thickness = 0.2,
}: {
  imageUrl: string | null
  widthM: number
  heightM: number
  segments: Seg[]
  start: [number, number] | null
  onPick: (x: number, z: number) => void
  ceiling?: number
  thickness?: number
}) {
  const [tex, setTex] = useState<THREE.Texture | null>(null)

  // Load the uploaded image (a blob URL) as a texture whenever it changes.
  useEffect(() => {
    if (!imageUrl) { setTex(null); return }
    new THREE.TextureLoader().load(imageUrl, (t) => {
      t.colorSpace = THREE.SRGBColorSpace
      setTex(t)
    })
  }, [imageUrl])

  return (
    <group>
      {/* The plan image, flat on the floor. Clicking it gives world coords in metres
          (the plane is sized in metres + centred at origin), which we hand to onPick. */}
      {tex && (
        <mesh
          rotation={[-Math.PI / 2, 0, 0]}
          position={[0, 0.01, 0]}
          onClick={(e) => { e.stopPropagation(); onPick(e.point.x, e.point.z) }}
        >
          <planeGeometry args={[widthM, heightM]} />
          <meshStandardMaterial map={tex} />
        </mesh>
      )}

      {/* live-generated walls */}
      {segments.map((s, i) => <Wall key={i} seg={s} h={ceiling} t={thickness} />)}

      {/* the "pen" position (where the next wall will start) */}
      {start && (
        <mesh position={[start[0], 0.06, start[1]]}>
          <sphereGeometry args={[0.12, 16, 16]} />
          <meshStandardMaterial color="#ff5577" emissive="#ff2255" emissiveIntensity={1.2} />
        </mesh>
      )}
    </group>
  )
}
