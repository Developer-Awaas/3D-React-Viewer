import { useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

// A clickable "stand here for a photo" marker.
//   position — where the glowing sphere sits in the room
//   onSelect — called when clicked (App decides what view to fly to)
export default function CameraMarker({
  position,
  onSelect,
}: {
  position: [number, number, number]
  onSelect: () => void
}) {
  const ref = useRef<THREE.Mesh>(null!)
  const [hover, setHover] = useState(false)

  // useFrame runs ~60x/second. Here we make the marker gently pulse so it reads
  // as interactive. state.clock.elapsedTime is seconds since start.
  useFrame((state) => {
    const s = 1 + Math.sin(state.clock.elapsedTime * 3) * 0.12
    ref.current.scale.setScalar(s)
  })

  return (
    <mesh
      ref={ref}
      position={position}
      onClick={(e) => {
        e.stopPropagation() // don't let the click pass through to objects behind
        onSelect()
      }}
      onPointerOver={() => { setHover(true); document.body.style.cursor = 'pointer' }}
      onPointerOut={() => { setHover(false); document.body.style.cursor = 'auto' }}
    >
      <sphereGeometry args={[0.15, 24, 24]} />
      {/* emissive = the material glows on its own, independent of scene lights. */}
      <meshStandardMaterial
        color={hover ? '#fff7cc' : '#ffd84d'}
        emissive="#ffb300"
        emissiveIntensity={hover ? 2.2 : 1.3}
      />
    </mesh>
  )
}
