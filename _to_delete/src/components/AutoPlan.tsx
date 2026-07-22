import { useEffect, useState } from 'react'
import { useTexture } from '@react-three/drei'

type Seg = [number, number, number, number]

function Wall({ seg, h = 2.5, t = 0.2 }: { seg: Seg; h?: number; t?: number }) {
  const [x1, z1, x2, z2] = seg
  const dx = x2 - x1, dz = z2 - z1
  const len = Math.hypot(dx, dz)
  if (len < 1e-3) return null
  return (
    <mesh position={[(x1 + x2) / 2, h / 2, (z1 + z2) / 2]} rotation={[0, -Math.atan2(dz, dx), 0]} castShadow receiveShadow>
      <boxGeometry args={[len, h, t]} />
      <meshStandardMaterial color="#dcd7cd" />
    </mesh>
  )
}

// Loads the AUTO-detected walls (public/auto_plan.json, produced by tools/auto_plan.py)
// and renders them in 3D over the source image — fully hands-off given a clean plan.
export default function AutoPlan() {
  const [data, setData] = useState<{ metresWide: number; metresDeep: number; ceilingHeight?: number; walls: Seg[] } | null>(null)
  useEffect(() => {
    fetch('/auto_plan.json').then((r) => r.json()).then(setData).catch(() => setData(null))
  }, [])
  const tex = useTexture('/plan.png')

  if (!data) return null
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]} receiveShadow>
        <planeGeometry args={[data.metresWide, data.metresDeep]} />
        <meshStandardMaterial map={tex} />
      </mesh>
      {data.walls.map((s, i) => <Wall key={i} seg={s} h={data.ceilingHeight ?? 2.5} />)}
    </group>
  )
}
