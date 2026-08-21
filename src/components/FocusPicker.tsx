import { ReactNode } from 'react'
import { useThree } from '@react-three/fiber'
import type { View } from './CameraRig'

/**
 * DOUBLE-CLICK TO FOCUS (20 Aug 2026).
 *
 * OrbitControls zooms toward a FIXED target, so on a 95 ft plan the far east
 * and west rooms could never be reached: the dolly runs into the centre of the
 * building and stops. Double-clicking any surface re-targets the orbit centre
 * to the point under the pointer and pulls the camera in along its CURRENT
 * view direction, so zoom, orbit and pan all work from there.
 *
 * Wraps its children in a group: r3f pointer events bubble up the React tree,
 * so one handler here covers every mesh inside without touching them.
 */
export default function FocusPicker({
  onFocus, distance = 5, children,
}: { onFocus: (v: View) => void; distance?: number; children: ReactNode }) {
  const { camera } = useThree()
  return (
    <group
      onDoubleClick={(e) => {
        e.stopPropagation()
        const p = e.point
        // keep the direction the user is already looking from; only the
        // DISTANCE is normalised, so a double-click never spins the model
        const dir = camera.position.clone().sub(p)
        const len = dir.length() || 1
        dir.multiplyScalar(Math.min(distance, len) / len)
        const pos = p.clone().add(dir)
        onFocus({ position: [pos.x, pos.y, pos.z], target: [p.x, p.y, p.z] })
      }}
    >
      {children}
    </group>
  )
}
