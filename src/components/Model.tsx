import { useLayoutEffect, useRef } from 'react'
import { useGLTF } from '@react-three/drei'
import * as THREE from 'three'
import { applyPlanMaterials } from '../three/planMaterials'

// Loads a .glb/.gltf model from a URL via drei's useGLTF (built on Three's
// GLTFLoader). useGLTF "suspends" while downloading, so it must be wrapped in
// <Suspense> by the parent. We auto-scale the model to a target footprint and
// drop it onto the floor, so we don't have to hand-tune numbers per model.
export default function Model({
  url,
  position = [0, 0, 0],
  rotationY = 0,
  targetSize = 1.9, // desired largest footprint dimension, in metres
  center = false,   // horizontally centre the model on `position` (plans)
  plan = false,     // backend-built plan: swap in PBR materials by mesh name
  onFramed,         // fires after scale+placement with the final box info
}: {
  url: string
  position?: [number, number, number]
  rotationY?: number
  targetSize?: number
  center?: boolean
  plan?: boolean
  onFramed?: (info: {
    center: [number, number, number]
    size: [number, number, number]
    scale: number                       // transform the group applied —
    position: [number, number, number]  // needed to map plan-feet points
  }) => void                            // (room beacons) into world space
}) {
  const { scene } = useGLTF(url)
  const ref = useRef<THREE.Group>(null!)

  // Keep the latest onFramed WITHOUT making it an effect dependency.
  // CRASH FIX: `position` is written inline in the parent (`position={[0,0,0]}`),
  // so its ARRAY IDENTITY changes on every parent render. With `position` and
  // `onFramed` in the dep list, the effect re-fired each render, called
  // onFramed -> setView -> re-render -> new array -> effect again… an infinite
  // loop that crashed the app ("Maximum update depth exceeded") right after a
  // plan finished loading. We depend on the primitive coordinates instead, and
  // read the callback through a ref.
  const onFramedRef = useRef(onFramed)
  onFramedRef.current = onFramed
  const [px, py, pz] = position

  useLayoutEffect(() => {
    // 1) measure the raw model
    const box = new THREE.Box3().setFromObject(scene)
    const size = new THREE.Vector3()
    box.getSize(size)

    // 2) scale so its biggest horizontal dimension == targetSize
    const maxFootprint = Math.max(size.x, size.z) || 1
    ref.current.scale.setScalar(targetSize / maxFootprint)

    // 3) re-measure after scaling; lift base to the floor and (for plans)
    //    slide it so its X/Z centre sits on `position` rather than its corner.
    const scaledBox = new THREE.Box3().setFromObject(ref.current)
    const c = new THREE.Vector3()
    scaledBox.getCenter(c)
    ref.current.position.y = py - scaledBox.min.y
    if (center) {
      ref.current.position.x = px - c.x
      ref.current.position.z = pz - c.z
    }

    // 4) materials + shadows. Plans get the PBR set (plaster walls, tiled
    //    floor, glass windows — assigned by mesh name); other models just
    //    get shadow flags.
    if (plan) {
      applyPlanMaterials(scene)
    } else {
      scene.traverse((o) => {
        if ((o as THREE.Mesh).isMesh) {
          o.castShadow = true
          o.receiveShadow = true
        }
      })
    }

    // 5) report the final placed box so the parent can frame the camera to it
    if (onFramedRef.current) {
      const finalBox = new THREE.Box3().setFromObject(ref.current)
      const fc = new THREE.Vector3()
      const fs = new THREE.Vector3()
      finalBox.getCenter(fc)
      finalBox.getSize(fs)
      const gp = ref.current.position
      onFramedRef.current({
        center: [fc.x, fc.y, fc.z],
        size: [fs.x, fs.y, fs.z],
        scale: ref.current.scale.x,
        position: [gp.x, gp.y, gp.z],
      })
    }
  }, [scene, targetSize, px, py, pz, center, plan])

  return (
    <group ref={ref} position={position} rotation={[0, rotationY, 0]}>
      <primitive object={scene} />
    </group>
  )
}
