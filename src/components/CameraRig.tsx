import { useEffect, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'

// A "view" = where the camera sits + the point it looks at.
export type View = {
  position: [number, number, number]
  target: [number, number, number]
}

// CameraRig watches `view`. When it changes, it animates the real camera there by
// LERPing (linear-interpolating) a little closer every frame — a smooth glide
// instead of an instant jump. Renders nothing visible; it just drives the camera.
export default function CameraRig({ view }: { view: View | null }) {
  // Pull the live camera and the OrbitControls out of R3F's shared state.
  // (OrbitControls registered itself because we gave it `makeDefault` in App.)
  const { camera, controls } = useThree() as any

  const animating = useRef(false)
  const goalPos = useRef(new THREE.Vector3())
  const goalTarget = useRef(new THREE.Vector3())

  // When a new view is chosen, record the goal and start animating.
  useEffect(() => {
    if (!view) return
    goalPos.current.set(...view.position)
    goalTarget.current.set(...view.target)
    animating.current = true
    if (controls) controls.enabled = false // pause user input so it doesn't fight the glide
  }, [view, controls])

  useFrame(() => {
    if (!animating.current || !controls) return

    // 0.08 = how much of the remaining distance to close each frame (the "ease").
    camera.position.lerp(goalPos.current, 0.08)
    controls.target.lerp(goalTarget.current, 0.08)
    controls.update()

    // Close enough? Stop animating and hand control back to the user.
    const done =
      camera.position.distanceTo(goalPos.current) < 0.02 &&
      controls.target.distanceTo(goalTarget.current) < 0.02
    if (done) {
      animating.current = false
      controls.enabled = true
    }
  })

  return null
}
