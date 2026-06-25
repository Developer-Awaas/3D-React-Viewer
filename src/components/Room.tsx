import * as THREE from 'three'
import { ROOM, INCLUDE_CEILING } from '../constants'
import { FLOOR_MATERIALS, FloorKey } from '../materials'
import WindowWall from './WindowWall'

function Slab({
  position, size, color, cutaway = false,
}: {
  position: [number, number, number]
  size: [number, number, number]
  color: string
  cutaway?: boolean
}) {
  return (
    <mesh position={position} castShadow receiveShadow>
      <boxGeometry args={size} />
      <meshStandardMaterial color={color} side={cutaway ? THREE.BackSide : THREE.FrontSide} />
    </mesh>
  )
}

// `floor` = selected material; `windowWall` = replace the plain back wall with the
// windowed one (used by the demo scene).
export default function Room({
  floor,
  windowWall = false,
}: {
  floor: FloorKey
  windowWall?: boolean
}) {
  const { width: W, depth: D, height: H, wallThickness: T } = ROOM
  const floorMat = FLOOR_MATERIALS[floor]

  return (
    <group>
      {/* FLOOR — material from current selection */}
      <mesh position={[0, -T / 2, 0]} receiveShadow castShadow>
        <boxGeometry args={[W, T, D]} />
        <meshStandardMaterial color={floorMat.color} roughness={floorMat.roughness} metalness={floorMat.metalness} />
      </mesh>

      {/* BACK wall: either the windowed version or a plain slab */}
      {windowWall ? (
        <WindowWall />
      ) : (
        <Slab cutaway position={[0, H / 2, -D / 2]} size={[W, H, T]} color="#e8e4dc" />
      )}

      {/* FRONT + SIDE walls (cutaway so you can see in) */}
      <Slab cutaway position={[0, H / 2, D / 2]}  size={[W, H, T]} color="#e8e4dc" />
      <Slab cutaway position={[-W / 2, H / 2, 0]} size={[T, H, D]} color="#ded9d0" />
      <Slab cutaway position={[W / 2, H / 2, 0]}  size={[T, H, D]} color="#ded9d0" />

      {INCLUDE_CEILING && <Slab cutaway position={[0, H + T / 2, 0]} size={[W, T, D]} color="#f2f0ec" />}
    </group>
  )
}
