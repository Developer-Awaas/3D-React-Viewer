import { useLayoutEffect, useRef } from 'react'
import { useGLTF } from '@react-three/drei'
import * as THREE from 'three'

// Loads a .glb/.gltf model from a URL via drei's useGLTF (built on Three's
// GLTFLoader). useGLTF "suspends" while downloading, so it must be wrapped in
// <Suspense> by the parent. We auto-scale the model to a target footprint and
// drop it onto the floor, so we don't have to hand-tune numbers per model.
export default function Model({
  url,
  position = [0, 0, 0],
  rotationY = 0,
  targetSize = 1.9, // desired largest footprint dimension, in metres
}: {
  url: string
  position?: [number, number, number]
  rotationY?: number
  targetSize?: number
}) {
  const { scene } = useGLTF(url)
  const ref = useRef<THREE.Group>(null!)

  useLayoutEffect(() => {
    // 1) measure the raw model
    const box = new THREE.Box3().setFromObject(scene)
    const size = new THREE.Vector3()
    box.getSize(size)

    // 2) scale so its biggest horizontal dimension == targetSize
    const maxFootprint = Math.max(size.x, size.z) || 1
    ref.current.scale.setScalar(targetSize / maxFootprint)

    // 3) re-measure after scaling and lift it so its base rests on the floor
    const scaledBox = new THREE.Box3().setFromObject(ref.current)
    ref.current.position.y = position[1] - scaledBox.min.y

    // 4) make every part cast/receive shadows
    scene.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) {
        o.castShadow = true
        o.receiveShadow = true
      }
    })
  }, [scene, targetSize, position])

  return (
    <group ref={ref} position={position} rotation={[0, rotationY, 0]}>
      <primitive object={scene} />
    </group>
  )
}
