import { useEffect, useRef } from 'react'
import { useThree } from '@react-three/fiber'
import gsap from 'gsap'
import type { Vector3 } from 'three'

export type View = { position: [number, number, number]; target: [number, number, number] }

// Ultra-smooth camera transitions: tween camera.position AND controls.target together
// with GSAP (0.8s, power3.out), updating controls every tick. Any in-flight tween is killed.
export default function CameraRig({ view }: { view: View | null }) {
  const { camera, controls } = useThree() as any
  const tween = useRef<gsap.core.Tween | null>(null)

  useEffect(() => {
    if (!view || !controls) return
    tween.current?.kill()
    const t = controls.target as Vector3
    const o = {
      px: camera.position.x, py: camera.position.y, pz: camera.position.z,
      tx: t.x, ty: t.y, tz: t.z,
    }
    tween.current = gsap.to(o, {
      px: view.position[0], py: view.position[1], pz: view.position[2],
      tx: view.target[0], ty: view.target[1], tz: view.target[2],
      duration: 0.8, ease: 'power3.out',
      onUpdate() {
        camera.position.set(o.px, o.py, o.pz)
        controls.target.set(o.tx, o.ty, o.tz)
        controls.update()
      },
    })
    return () => { tween.current?.kill() }
  }, [view, controls, camera])

  return null
}
