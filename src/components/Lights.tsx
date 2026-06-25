import { ROOM } from '../constants'

const SHADOW_MAP = typeof window !== 'undefined' && window.innerWidth < 768 ? 2048 : 4096

// Size the shadow camera to just cover the room (+ a small margin). A TIGHT frustum
// means the shadow map's limited precision is spent only where it matters, which
// kills the shimmering "shadow acne" you saw on the floor.
const S = Math.max(ROOM.width, ROOM.depth) / 2 + 1 // ~3.5m for a 5x5 room

export default function Lights() {
  const { width: W, height: H, depth: D } = ROOM

  return (
    <>
      <hemisphereLight args={['#ffffff', '#b08d57', 0.6]} />
      <ambientLight intensity={0.15} />

      <directionalLight
        position={[W, H * 2.2, D * 0.8]}
        intensity={2.2}
        castShadow
        shadow-mapSize-width={SHADOW_MAP}
        shadow-mapSize-height={SHADOW_MAP}
        shadow-camera-near={0.5}
        shadow-camera-far={25}
        shadow-camera-left={-S}
        shadow-camera-right={S}
        shadow-camera-top={S}
        shadow-camera-bottom={-S}
        // normalBias is the key anti-shimmer setting: it offsets the shadow test
        // along each surface's normal, so flat lit areas stop self-shadowing.
        shadow-bias={-0.0001}
        shadow-normalBias={0.05}
      />
    </>
  )
}
