import { useThree } from '@react-three/fiber'
import { useEffect } from 'react'
import { setGBufferSource } from '../three/gbuffer'

// Lives INSIDE <Canvas>. Publishes the live renderer/scene/camera to the
// gbuffer module so the Visualize button (outside the Canvas) can capture a
// depth pass. Unregisters on unmount so a stale scene is never captured.
export default function GBufferBridge() {
  const gl = useThree((s) => s.gl)
  const scene = useThree((s) => s.scene)
  const camera = useThree((s) => s.camera)
  useEffect(() => {
    setGBufferSource({ gl, scene, camera })
    return () => setGBufferSource(null)
  }, [gl, scene, camera])
  return null
}
