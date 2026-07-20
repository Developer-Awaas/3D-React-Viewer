import * as THREE from 'three'

// Visual pass for backend-built plans (Wed of launch week).
//
// The GLB that /scene.glb returns has NO texture coordinates (walls are
// extruded prisms), so regular texture mapping would smear. boxUV() generates
// box-projected UVs per face from the dominant normal axis — a CPU-side
// "triplanar" that is exact for axis-aligned masonry and shader-free, so it
// can never break on a three.js upgrade. Textures are drawn procedurally on
// canvases: zero downloads, zero new bundle assets, works offline.
//
// Mesh roles come from NODE NAMES baked by server/scene_to_glb.py:
//   floor · wall_* / wall_p* · column_* · glass_* · furn_*

function canvasTex(
  size: number,
  repeatMetres: number,
  draw: (ctx: CanvasRenderingContext2D, s: number) => void,
): THREE.CanvasTexture {
  const c = document.createElement('canvas')
  c.width = c.height = size
  draw(c.getContext('2d')!, size)
  const t = new THREE.CanvasTexture(c)
  t.wrapS = t.wrapT = THREE.RepeatWrapping
  t.colorSpace = THREE.SRGBColorSpace
  t.anisotropy = 8
  // UVs are in model metres -> one texture tile every `repeatMetres`
  t.repeat.set(1 / repeatMetres, 1 / repeatMetres)
  return t
}

function speckle(ctx: CanvasRenderingContext2D, s: number, n: number, alpha: number) {
  for (let i = 0; i < n; i++) {
    const a = alpha * (0.4 + Math.random() * 0.6)
    ctx.fillStyle = Math.random() < 0.5 ? `rgba(0,0,0,${a})` : `rgba(255,255,255,${a})`
    ctx.fillRect(Math.random() * s, Math.random() * s, 1 + Math.random(), 1 + Math.random())
  }
}

function plasterTexture() {
  return canvasTex(256, 2.4, (ctx, s) => {
    ctx.fillStyle = '#ece7dd'
    ctx.fillRect(0, 0, s, s)
    // soft trowel blotches
    for (let i = 0; i < 26; i++) {
      const g = ctx.createRadialGradient(
        Math.random() * s, Math.random() * s, 4,
        Math.random() * s, Math.random() * s, 30 + Math.random() * 60)
      g.addColorStop(0, `rgba(180,170,150,${0.05 + Math.random() * 0.05})`)
      g.addColorStop(1, 'rgba(180,170,150,0)')
      ctx.fillStyle = g
      ctx.fillRect(0, 0, s, s)
    }
    speckle(ctx, s, 2600, 0.05)
  })
}

function floorTexture() {
  // 600 mm vitrified tiles, 2x2 per texture -> tile every 0.6 m
  return canvasTex(512, 1.2, (ctx, s) => {
    const half = s / 2
    for (let ty = 0; ty < 2; ty++)
      for (let tx = 0; tx < 2; tx++) {
        const tones = ['#ded8cc', '#d9d3c6', '#e2dcd0', '#d6d0c3']
        ctx.fillStyle = tones[(tx + ty * 2 + Math.floor(Math.random() * 2)) % 4]
        ctx.fillRect(tx * half, ty * half, half, half)
        // faint marbling
        ctx.strokeStyle = 'rgba(160,150,130,0.16)'
        ctx.lineWidth = 1
        for (let k = 0; k < 5; k++) {
          ctx.beginPath()
          const x0 = tx * half + Math.random() * half
          const y0 = ty * half + Math.random() * half
          ctx.moveTo(x0, y0)
          ctx.bezierCurveTo(
            x0 + 40 - Math.random() * 80, y0 + 40 - Math.random() * 80,
            x0 + 80 - Math.random() * 160, y0 + 80 - Math.random() * 160,
            x0 + 60 - Math.random() * 120, y0 + 60 - Math.random() * 120)
          ctx.stroke()
        }
      }
    // grout lines
    ctx.strokeStyle = '#b3ac9d'
    ctx.lineWidth = 3
    ctx.strokeRect(0, 0, s, s)
    ctx.beginPath()
    ctx.moveTo(half, 0); ctx.lineTo(half, s)
    ctx.moveTo(0, half); ctx.lineTo(s, half)
    ctx.stroke()
    speckle(ctx, s, 1200, 0.03)
  })
}

function concreteTexture() {
  return canvasTex(256, 1.5, (ctx, s) => {
    ctx.fillStyle = '#a9adb2'
    ctx.fillRect(0, 0, s, s)
    speckle(ctx, s, 3200, 0.07)
  })
}

/** Box-projected UVs from each face's dominant normal axis (in model metres). */
export function boxUV(geo: THREE.BufferGeometry): THREE.BufferGeometry {
  const g = geo.index ? geo.toNonIndexed() : geo
  // recompute on the de-indexed geometry = flat per-face normals: crisp
  // masonry edges (the exporter's smoothed normals shade boxes "rounded")
  g.computeVertexNormals()
  const p = g.attributes.position
  const n = g.attributes.normal
  const uv = new Float32Array(p.count * 2)
  for (let f = 0; f + 2 < p.count; f += 3) {
    const nx = Math.abs(n.getX(f))
    const ny = Math.abs(n.getY(f))
    const nz = Math.abs(n.getZ(f))
    for (let v = f; v < f + 3; v++) {
      let u: number, w: number
      if (ny >= nx && ny >= nz) { u = p.getX(v); w = p.getZ(v) }        // floor/top
      else if (nx >= nz) { u = p.getZ(v); w = p.getY(v) }               // x-facing wall
      else { u = p.getX(v); w = p.getY(v) }                             // z-facing wall
      uv[v * 2] = u
      uv[v * 2 + 1] = w
    }
  }
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2))
  return g
}

type PlanMaterials = {
  plaster: THREE.MeshStandardMaterial
  floor: THREE.MeshStandardMaterial
  concrete: THREE.MeshStandardMaterial
  glass: THREE.MeshStandardMaterial
}
let cached: PlanMaterials | null = null

function materials(): PlanMaterials {
  if (cached) return cached
  cached = {
    // envMapIntensity lets the CDN environment ground each surface: matte
    // walls barely reflect, tiled floor + glass pick up more sheen. Reads as
    // "lit by a real room" instead of flat paint.
    plaster: new THREE.MeshStandardMaterial({
      map: plasterTexture(), color: '#f4efe6', roughness: 0.92, metalness: 0.0,
      envMapIntensity: 0.55,
    }),
    floor: new THREE.MeshStandardMaterial({
      map: floorTexture(), color: '#ffffff', roughness: 0.5, metalness: 0.04,
      envMapIntensity: 1.25,
    }),
    concrete: new THREE.MeshStandardMaterial({
      map: concreteTexture(), color: '#e2e5e9', roughness: 0.85, metalness: 0.0,
      envMapIntensity: 0.7,
    }),
    glass: new THREE.MeshStandardMaterial({
      color: '#a8cfe3', transparent: true, opacity: 0.38,
      roughness: 0.12, metalness: 0.0, side: THREE.DoubleSide,
      depthWrite: false, envMapIntensity: 1.6,
      // small emissive floor so panes read as glass even if the HDR
      // environment fails to load (offline demo) — never black
      emissive: '#5f7f96', emissiveIntensity: 0.35,
    }),
  }
  return cached
}

/** Dispose a replaced material (and any textures it owns) — GPU leak guard. */
function disposeMaterial(mat: THREE.Material | THREE.Material[]) {
  for (const m of Array.isArray(mat) ? mat : [mat]) {
    if (!m) continue
    for (const v of Object.values(m)) {
      if (v instanceof THREE.Texture) v.dispose()
    }
    m.dispose()
  }
}

/** Swap the flat vertex-colour GLB materials for the PBR set, by mesh name. */
export function applyPlanMaterials(root: THREE.Object3D) {
  const m = materials()
  root.traverse((o) => {
    const mesh = o as THREE.Mesh
    if (!mesh.isMesh) return
    const name = (mesh.name || mesh.parent?.name || '').toLowerCase()
    const oldMaterial = mesh.material
    if (name.includes('glass')) {
      // the exporter writes glass boxes without NORMALs — without this the
      // lighting math goes NaN and the pane renders solid black
      if (!mesh.geometry.attributes.normal) mesh.geometry.computeVertexNormals()
      mesh.material = m.glass
      if (oldMaterial !== mesh.material) disposeMaterial(oldMaterial)
      mesh.castShadow = false
      mesh.receiveShadow = false
      return
    }
    const oldGeometry = mesh.geometry
    mesh.geometry = boxUV(mesh.geometry)
    if (mesh.geometry !== oldGeometry) oldGeometry.dispose() // old indexed copy
    if (name.includes('floor')) mesh.material = m.floor
    else if (name.includes('column')) mesh.material = m.concrete
    else if (name.includes('furn')) {
      // keep the furniture's baked colour but give it a sane finish
      mesh.material = new THREE.MeshStandardMaterial({
        vertexColors: true, roughness: 0.7, metalness: 0.0,
      })
    } else mesh.material = m.plaster
    if (oldMaterial !== mesh.material) disposeMaterial(oldMaterial)
    mesh.castShadow = !name.includes('floor')
    mesh.receiveShadow = true
  })
}
