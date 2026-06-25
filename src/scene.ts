import { View } from './components/CameraRig'

// Each marker = a glowing pin in the room + the camera view clicking it flies to.
export type Marker = { id: string; spot: [number, number, number]; view: View }

export const OVERVIEW: View = { position: [6, 5, 8], target: [0, 1.5, 0] }

export const MARKERS: Marker[] = [
  { id: 'sofa',   spot: [1.6, 0.18, 1.4],  view: { position: [1.6, 1.5, 1.4],  target: [-1.4, 0.7, -0.4] } },
  { id: 'window', spot: [-1.4, 0.18, 0.8], view: { position: [-1.4, 1.5, 0.8], target: [0, 1.4, -2.5] } },
  { id: 'corner', spot: [-1.9, 0.18, 1.9], view: { position: [-1.9, 1.7, 1.9], target: [0, 1.0, 0] } },
]
