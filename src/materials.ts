// The floor finishes the user can pick from. Each is a simple PBR colour for now
// (a texture upgrade can come later). roughness/metalness change how light reflects:
//   roughness 0 = mirror-smooth, 1 = totally matte.  metalness ~0 for non-metals.
export type FloorKey = 'marble' | 'wood' | 'tile'

export const FLOOR_MATERIALS: Record<
  FloorKey,
  { label: string; color: string; roughness: number; metalness: number }
> = {
  marble: { label: 'Marble', color: '#ece9e4', roughness: 0.25, metalness: 0.05 },
  wood:   { label: 'Wood',   color: '#8a5a2b', roughness: 0.6,  metalness: 0.0  },
  tile:   { label: 'Tile',   color: '#8f9aa1', roughness: 0.4,  metalness: 0.05 },
}
