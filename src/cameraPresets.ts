export interface CameraPreset {
  position: [number, number, number]
  target: [number, number, number]
}

// Camera viewpoints keyed by material preset (+ a 'default'). The GSAP rig tweens to these.
export const PRESETS: Record<string, CameraPreset> = {
  default: { position: [6, 5, 8], target: [0, 1.5, 0] },
  marble:  { position: [5.2, 3.8, 7], target: [0, 1.2, 0] },
  wood:    { position: [7, 3.6, 6], target: [0, 1.2, 0.4] },
  tile:    { position: [6, 6, 8.2], target: [0, 1, 0] },
}
