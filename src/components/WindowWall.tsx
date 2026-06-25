import * as THREE from 'three'
import { ROOM, WINDOW } from '../constants'

// The back wall, but with a rectangular hole for a window. You can't easily "cut"
// a hole in a single box, so we build the wall from FOUR slabs around the opening:
// left, right, below (under the sill) and above (the header). A bright plane fills
// the gap to read as sky, and a light shines in for a soft daylight shaft.
function WallSlab({ position, size }: { position: [number, number, number]; size: [number, number, number] }) {
  return (
    <mesh position={position} castShadow receiveShadow>
      <boxGeometry args={size} />
      <meshStandardMaterial color="#e8e4dc" side={THREE.BackSide} />
    </mesh>
  )
}

export default function WindowWall() {
  const { width: W, height: H, depth: D, wallThickness: T } = ROOM
  const { width: w, height: h, sill } = WINDOW
  const z = -D / 2                 // back wall sits at -depth/2
  const side = (W - w) / 2         // width of the left/right pieces
  const top = H - (sill + h)       // height of the piece above the window

  return (
    <group>
      {/* left of opening */}
      <WallSlab position={[-(W + w) / 4, H / 2, z]} size={[side, H, T]} />
      {/* right of opening */}
      <WallSlab position={[(W + w) / 4, H / 2, z]} size={[side, H, T]} />
      {/* below the window (sill) */}
      <WallSlab position={[0, sill / 2, z]} size={[w, sill, T]} />
      {/* above the window (header) */}
      <WallSlab position={[0, sill + h + top / 2, z]} size={[w, top, T]} />

      {/* "Sky" pane filling the opening — emissive so it glows like bright daylight. */}
      <mesh position={[0, sill + h / 2, z]}>
        <planeGeometry args={[w, h]} />
        <meshStandardMaterial emissive="#bfe3ff" emissiveIntensity={1.4} color="#bfe3ff" />
      </mesh>

      {/* A light just OUTSIDE the window, aimed inward, for a soft daylight shaft. */}
      <pointLight position={[0, sill + h / 2, z - 0.6]} intensity={6} distance={9} color="#dff0ff" />
    </group>
  )
}
