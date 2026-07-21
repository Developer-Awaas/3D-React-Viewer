import * as THREE from 'three'

// G-buffer capture: renders extra passes from the SAME live three.js scene so we
// can hand the generative backend a real DEPTH map (not just a screenshot).
// Depth locks the room's true 3D volume for depth-ControlNet — Drishti can do
// this because it built the scene. Segmentation (by mesh name) is the next pass
// to add here (Phase B.1).
//
// A bridge component inside <Canvas> registers the live renderer/scene/camera
// via setGBufferSource(); UI outside the Canvas calls captureGBuffer().

type Source = { gl: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.Camera }

let source: Source | null = null

export function setGBufferSource(s: Source | null) {
  source = s
}

export type GBuffer = { beauty: string; depth: string }

// Render the normal (beauty) frame, then a depth pass via an override material,
// then restore. Requires the Canvas to have gl={{ preserveDrawingBuffer: true }}
// so toDataURL() reads back the pixels. Returns PNG data URLs, or null if the
// scene isn't ready.
export function captureGBuffer(): GBuffer | null {
  if (!source) return null
  const { gl, scene, camera } = source
  try {
    // 1) beauty
    gl.render(scene, camera)
    const beauty = gl.domElement.toDataURL('image/png')

    // 2) depth — MeshDepthMaterial writes near→far as greyscale; ControlNet-depth
    //    wants near = bright, so we render with an inverted-tone depth material.
    const prevOverride = scene.overrideMaterial
    const prevBg = scene.background
    scene.background = new THREE.Color(0x000000)
    scene.overrideMaterial = depthMaterial()
    gl.render(scene, camera)
    const depth = gl.domElement.toDataURL('image/png')

    // 3) restore and repaint the beauty frame the user sees
    scene.overrideMaterial = prevOverride
    scene.background = prevBg
    gl.render(scene, camera)

    return { beauty, depth }
  } catch {
    return null // tainted/lost context
  }
}

let _depthMat: THREE.MeshDepthMaterial | null = null
function depthMaterial() {
  if (!_depthMat) {
    _depthMat = new THREE.MeshDepthMaterial({ depthPacking: THREE.BasicDepthPacking })
  }
  return _depthMat
}
