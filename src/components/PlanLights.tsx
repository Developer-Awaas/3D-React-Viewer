// Sun + sky sized for BUILDINGS (the room-scale <Lights /> shadow camera only
// covers ~3.5 m — a 14 m plan fell outside it, so plan shadows silently
// clipped). Frustum covers the whole scaled plan (targetSize 14 m + margin).
//
// Shadow settings tuned 2026-07-14 after the user's GPU showed heavy ACNE
// BANDING (stripes) across the ground that headless SwiftShader barely
// rendered: tighter frustum (S 18 -> 12, denser texels), normalBias up
// (0.06 -> 0.2 — the correct fix for banding on flat receivers), small
// depth bias, calmer intensities (the CDN HDR environment also lights the
// scene on machines where it loads).
import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

const SHADOW_MAP = typeof window !== 'undefined' && window.innerWidth < 768 ? 2048 : 4096
const S = 12 // half-extent of the shadow frustum, metres

// A soft "lantern" that rides with the camera: rooms sit in the sun's
// shadow, so walking inside was near-black. With distance falloff it lights
// whatever room you stand in and is negligible from aerial distance.
function CameraLantern() {
  const ref = useRef<THREE.PointLight>(null!)
  useFrame(({ camera }) => {
    ref.current.position.copy(camera.position)
    // real camera position, exposed for e2e tests (cheap, dev-tool friendly)
    ;(window as unknown as { __camPos?: number[] }).__camPos = camera.position.toArray()
  })
  return <pointLight ref={ref} intensity={14} distance={9} decay={1.6} color="#fff3e0" />
}

export default function PlanLights() {
  return (
    <>
      <CameraLantern />
      {/* cool sky above, warm ground bounce below */}
      <hemisphereLight args={['#dfeaff', '#8c7a5f', 0.5]} />
      <ambientLight intensity={0.12} />
      <directionalLight
        position={[14, 22, 9]}
        intensity={1.35}
        castShadow
        shadow-mapSize-width={SHADOW_MAP}
        shadow-mapSize-height={SHADOW_MAP}
        shadow-camera-near={1}
        shadow-camera-far={70}
        shadow-camera-left={-S}
        shadow-camera-right={S}
        shadow-camera-top={S}
        shadow-camera-bottom={-S}
        shadow-bias={-0.0001}
        shadow-normalBias={0.2}
      />
    </>
  )
}
