import * as THREE from 'three'

// G-buffer capture: renders extra passes from the SAME live three.js scene so we
// can hand the generative backend real conditioning maps — DEPTH (3D volume) and
// SEGMENTATION (what each surface IS). Drishti can produce a PERFECT segmentation
// map because its GLB meshes are NAMED (floor / wall_N / glass_N / furn_*), which
// a photo-based competitor can only guess. That's the moat.
//
// A bridge component inside <Canvas> registers the live renderer/scene/camera via
// setGBufferSource(); UI outside the Canvas calls captureGBuffer().

type Source = { gl: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.Camera }

let source: Source | null = null

export function setGBufferSource(s: Source | null) {
  source = s
}

export type GBuffer = { beauty: string; depth: string; seg: string }

// semantic classes -> flat colours for the segmentation map. Distinct, saturated
// colours so a segmentation ControlNet (or regional masks) can separate them.
export const SEG_COLORS = {
  floor: '#3050c8',
  wall: '#c85050',
  window: '#50c8c8',
  column: '#9650c8',
  furniture: '#50c850',
  other: '#202020',
} as const

export type SegClass = keyof typeof SEG_COLORS

/** Map a GLB mesh name to its semantic class (pure — unit-tested). */
export function segClass(name: string): SegClass {
  const n = (name || '').toLowerCase()
  if (n.includes('glass') || n.includes('window')) return 'window'
  if (n.includes('floor')) return 'floor'
  if (n.includes('column')) return 'column'
  if (n.includes('furn')) return 'furniture'
  if (n.includes('wall')) return 'wall'
  return 'other'
}

// Render beauty, then a depth pass and a segmentation pass, then restore. Requires
// the Canvas to keep its draw buffer (gl={{ preserveDrawingBuffer: true }}).
// Returns PNG data URLs, or null if the scene isn't ready.
export function captureGBuffer(): GBuffer | null {
  if (!source) return null
  const { gl, scene, camera } = source
  // Crash-safe: EVERY temporary change (override material, background, per-mesh
  // swaps) is undone in `finally`, so an error mid-pass can never leave the
  // live scene looking like a depth/segmentation map.
  const prevOverride = scene.overrideMaterial
  const prevBg = scene.background
  const swapped: Array<[THREE.Mesh, THREE.Material | THREE.Material[]]> = []
  try {
    // 1) beauty
    gl.render(scene, camera)
    const beauty = gl.domElement.toDataURL('image/png')

    // 2) depth — via an override material on a black background
    scene.background = new THREE.Color(0x000000)
    scene.overrideMaterial = depthMaterial()
    gl.render(scene, camera)
    const depth = gl.domElement.toDataURL('image/png')
    scene.overrideMaterial = prevOverride

    // 3) segmentation — flat-colour each PLAN mesh by its class. Only meshes
    //    with standard materials are swapped: the Sky dome, shader effects and
    //    helper lines keep their own materials (swapping them breaks rendering).
    scene.traverse((o) => {
      const mesh = o as THREE.Mesh
      if (!mesh.isMesh || mesh.userData.measure) return
      const mat = mesh.material as THREE.Material
      if (Array.isArray(mesh.material)) return
      if (!(mat instanceof THREE.MeshStandardMaterial)
          && !(mat instanceof THREE.MeshBasicMaterial)) return
      swapped.push([mesh, mesh.material])
      mesh.material = segMaterial(segClass(mesh.name))
    })
    gl.render(scene, camera)
    const seg = gl.domElement.toDataURL('image/png')

    return { beauty, depth, seg }
  } catch {
    return null // tainted/lost context — finally still restores the scene
  } finally {
    scene.overrideMaterial = prevOverride
    scene.background = prevBg
    for (const [mesh, mat] of swapped) mesh.material = mat
    try { gl.render(scene, camera) } catch { /* repaint best-effort */ }
  }
}

let _depthMat: THREE.MeshDepthMaterial | null = null
function depthMaterial() {
  if (!_depthMat) {
    _depthMat = new THREE.MeshDepthMaterial({ depthPacking: THREE.BasicDepthPacking })
  }
  return _depthMat
}

const _segMats = new Map<SegClass, THREE.MeshBasicMaterial>()
function segMaterial(cls: SegClass) {
  let m = _segMats.get(cls)
  if (!m) {
    m = new THREE.MeshBasicMaterial({ color: SEG_COLORS[cls] })
    _segMats.set(cls, m)
  }
  return m
}
