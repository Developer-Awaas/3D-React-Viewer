import { useTexture } from '@react-three/drei'
import { PLAN } from '../floorplan'

// Loads /plan.png (served from the public/ folder) and lays it flat on the ground.
// A plane is born standing up in the XY plane, so we rotate it -90° about X to make
// it lie down facing the sky. Sized to the full image's real-world dimensions so it
// lines up with the generated walls.
export default function FloorPlanUnderlay() {
  const tex = useTexture('/plan.png')
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]} receiveShadow>
      <planeGeometry args={[PLAN.widthM, PLAN.heightM]} />
      <meshStandardMaterial map={tex} />
    </mesh>
  )
}
