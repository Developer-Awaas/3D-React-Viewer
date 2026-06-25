import { SEGMENTS, WALL_HEIGHT, WALL_T } from '../floorplan'

// For each segment we compute: its length, its midpoint (where the box centre
// goes), and its angle in the floor plane (how to rotate the box). This is the
// core 2D->3D math.
export default function WallsFromPlan() {
  return (
    <group>
      {SEGMENTS.map(([x1, z1, x2, z2], i) => {
        const dx = x2 - x1
        const dz = z2 - z1
        const length = Math.hypot(dx, dz)
        const midX = (x1 + x2) / 2
        const midZ = (z1 + z2) / 2
        // A box's length runs along its local X axis. atan2(dz, dx) is the segment's
        // heading; we rotate by the negative of it so local X lines up with the wall.
        const rotY = -Math.atan2(dz, dx)
        return (
          <mesh key={i} position={[midX, WALL_HEIGHT / 2, midZ]} rotation={[0, rotY, 0]} castShadow receiveShadow>
            {/* length along X, height along Y, thickness along Z */}
            <boxGeometry args={[length + WALL_T, WALL_HEIGHT, WALL_T]} />
            <meshStandardMaterial color="#e9e5dd" />
          </mesh>
        )
      })}
    </group>
  )
}
