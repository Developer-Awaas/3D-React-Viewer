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

// ── Style palettes ──────────────────────────────────────────────────────────
// The SAME four styles the Visualize photo renders offer, expressed as real
// 3D material recipes — picking "Luxury" restyles the walkable model itself.
// Every texture below is parameterised by one of these palettes; nothing is
// hardcoded to a single look any more.
export type StylePalette = {
  /** wall paint */
  plasterBase: string
  plasterBlotch: string   // 'r,g,b' of the trowel blotches
  plasterTint: string     // material colour multiplier
  /** floor finish */
  floorTones: [string, string, string, string]
  grout: string
  vein: string            // 'rgba(...)' marbling stroke
  floorRoughness: number  // 0.2 = polished marble · 0.7 = matte terracotta
  floorMetalness: number
  floorTint: string
  /** columns / exposed structure */
  concreteBase: string
  concreteTint: string
}

export const STYLE_PALETTES: Record<string, StylePalette> = {
  scandinavian: {
    plasterBase: '#f1ede5', plasterBlotch: '175,168,152', plasterTint: '#faf7f1',
    floorTones: ['#e7d9bf', '#e2d3b7', '#ecdfc8', '#dccdb0'],
    grout: '#c9b795', vein: 'rgba(170,150,110,0.14)',
    floorRoughness: 0.55, floorMetalness: 0.02, floorTint: '#ffffff',
    concreteBase: '#b6b9bd', concreteTint: '#e9ebee',
  },
  modern: {
    plasterBase: '#d9dbde', plasterBlotch: '120,124,130', plasterTint: '#e6e8eb',
    floorTones: ['#4a4d52', '#43464b', '#515459', '#3c3f44'],
    grout: '#2e3134', vein: 'rgba(255,255,255,0.06)',
    floorRoughness: 0.32, floorMetalness: 0.08, floorTint: '#ffffff',
    concreteBase: '#7c8085', concreteTint: '#9aa0a6',
  },
  'warm minimal': {
    plasterBase: '#eadfce', plasterBlotch: '190,160,125', plasterTint: '#f4ebda',
    floorTones: ['#c98a63', '#c2825c', '#d0936c', '#bb7a55'],
    grout: '#96603f', vein: 'rgba(120,70,40,0.12)',
    floorRoughness: 0.7, floorMetalness: 0.0, floorTint: '#ffffff',
    concreteBase: '#b3a598', concreteTint: '#dcd1c4',
  },
  luxury: {
    plasterBase: '#f2ead9', plasterBlotch: '200,185,150', plasterTint: '#f9f2e3',
    floorTones: ['#efece6', '#eae6df', '#f3f0ea', '#e6e2da'],
    grout: '#cfc9bd', vein: 'rgba(140,130,110,0.3)',
    floorRoughness: 0.22, floorMetalness: 0.08, floorTint: '#ffffff',
    concreteBase: '#bdae94', concreteTint: '#dccfb4',
  },
}

export const DEFAULT_STYLE = 'scandinavian'
export const STYLE_KEYS = Object.keys(STYLE_PALETTES)

function palette(style: string): StylePalette {
  return STYLE_PALETTES[style] ?? STYLE_PALETTES[DEFAULT_STYLE]
}

function plasterTexture(p: StylePalette) {
  return canvasTex(256, 2.4, (ctx, s) => {
    ctx.fillStyle = p.plasterBase
    ctx.fillRect(0, 0, s, s)
    // soft trowel blotches
    for (let i = 0; i < 26; i++) {
      const g = ctx.createRadialGradient(
        Math.random() * s, Math.random() * s, 4,
        Math.random() * s, Math.random() * s, 30 + Math.random() * 60)
      g.addColorStop(0, `rgba(${p.plasterBlotch},${0.05 + Math.random() * 0.05})`)
      g.addColorStop(1, `rgba(${p.plasterBlotch},0)`)
      ctx.fillStyle = g
      ctx.fillRect(0, 0, s, s)
    }
    speckle(ctx, s, 2600, 0.05)
  })
}

function floorTexture(p: StylePalette) {
  // 600 mm vitrified tiles, 2x2 per texture -> tile every 0.6 m
  return canvasTex(512, 1.2, (ctx, s) => {
    const half = s / 2
    for (let ty = 0; ty < 2; ty++)
      for (let tx = 0; tx < 2; tx++) {
        const tones = p.floorTones
        ctx.fillStyle = tones[(tx + ty * 2 + Math.floor(Math.random() * 2)) % 4]
        ctx.fillRect(tx * half, ty * half, half, half)
        // faint marbling
        ctx.strokeStyle = p.vein
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
    ctx.strokeStyle = p.grout
    ctx.lineWidth = 3
    ctx.strokeRect(0, 0, s, s)
    ctx.beginPath()
    ctx.moveTo(half, 0); ctx.lineTo(half, s)
    ctx.moveTo(0, half); ctx.lineTo(s, half)
    ctx.stroke()
    speckle(ctx, s, 1200, 0.03)
  })
}

function concreteTexture(p: StylePalette) {
  return canvasTex(256, 1.5, (ctx, s) => {
    ctx.fillStyle = p.concreteBase
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
// One material set PER STYLE, built lazily and kept for the session (max 4
// small sets — canvas textures, tiny). `managed` marks OUR shared materials so
// a re-style never disposes a set another style is still using.
const styleCache = new Map<string, PlanMaterials>()
const managed = new WeakSet<THREE.Material>()

function materials(style: string): PlanMaterials {
  const key = STYLE_PALETTES[style] ? style : DEFAULT_STYLE
  const hit = styleCache.get(key)
  if (hit) return hit
  const p = palette(key)
  const built: PlanMaterials = {
    // envMapIntensity lets the CDN environment ground each surface: matte
    // walls barely reflect, tiled floor + glass pick up more sheen. Reads as
    // "lit by a real room" instead of flat paint.
    plaster: new THREE.MeshStandardMaterial({
      map: plasterTexture(p), color: p.plasterTint, roughness: 0.92, metalness: 0.0,
      envMapIntensity: 0.55,
    }),
    floor: new THREE.MeshStandardMaterial({
      map: floorTexture(p), color: p.floorTint,
      roughness: p.floorRoughness, metalness: p.floorMetalness,
      envMapIntensity: 1.25,
    }),
    concrete: new THREE.MeshStandardMaterial({
      map: concreteTexture(p), color: p.concreteTint, roughness: 0.85, metalness: 0.0,
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
  for (const m of Object.values(built)) managed.add(m)
  styleCache.set(key, built)
  return built
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

/** Dispose a replaced material UNLESS it's one of our shared style sets. */
function disposeIfOwnedByMesh(mat: THREE.Material | THREE.Material[]) {
  if (!Array.isArray(mat) && managed.has(mat)) return
  disposeMaterial(mat)
}

/**
 * Swap the flat vertex-colour GLB materials for the PBR set, by mesh name.
 * Safe to call again with a different `style` — meshes keep their box-projected
 * UVs (userData guard) and simply pick up the new style's material set, so
 * switching styles is instant.
 */
export function applyPlanMaterials(root: THREE.Object3D, style: string = DEFAULT_STYLE) {
  const m = materials(style)
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
      if (oldMaterial !== mesh.material) disposeIfOwnedByMesh(oldMaterial)
      mesh.castShadow = false
      mesh.receiveShadow = false
      return
    }
    if (!mesh.userData.uvBoxed) {
      const oldGeometry = mesh.geometry
      mesh.geometry = boxUV(mesh.geometry)
      if (mesh.geometry !== oldGeometry) oldGeometry.dispose() // old indexed copy
      mesh.userData.uvBoxed = true
    }
    if (name.includes('floor')) mesh.material = m.floor
    else if (name.includes('column')) mesh.material = m.concrete
    else if (name.includes('furn') || name.includes('door')) {
      // furniture AND door leaves (D1): keep the baked wood colour but give it
      // a sane wood finish, created once per mesh and reused across re-styles.
      // Without this a 'door_*' mesh falls through to plaster and reads as a
      // wall slab instead of a door.
      if (!mesh.userData.furnMat) {
        mesh.material = new THREE.MeshStandardMaterial({
          vertexColors: true, roughness: 0.6, metalness: 0.0,
        })
        mesh.userData.furnMat = true
      }
    } else mesh.material = m.plaster
    if (oldMaterial !== mesh.material) disposeIfOwnedByMesh(oldMaterial)
    mesh.castShadow = !name.includes('floor')
    mesh.receiveShadow = true
  })
}
