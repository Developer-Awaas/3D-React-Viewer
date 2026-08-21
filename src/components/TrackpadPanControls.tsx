import { useEffect } from 'react'
import { useThree } from '@react-three/fiber'
import { isTrackpadPan, panBy } from './TrackpadPan'

/** Wires the two-finger trackpad gesture to PAN instead of dolly. */
export default function TrackpadPanControls() {
  const { camera, controls, gl } = useThree() as any
  useEffect(() => {
    if (!controls || !gl?.domElement) return
    const el = gl.domElement as HTMLElement
    const onWheel = (e: WheelEvent) => {
      if (!isTrackpadPan(e)) return          // pinch / mouse wheel -> OrbitControls zooms
      e.preventDefault()
      e.stopPropagation()
      panBy(camera, controls, -e.deltaX, e.deltaY)
    }
    // capture, so this runs BEFORE OrbitControls' own wheel listener
    el.addEventListener('wheel', onWheel, { passive: false, capture: true })
    const noMenu = (e: Event) => e.preventDefault()   // right-drag pan without the menu
    el.addEventListener('contextmenu', noMenu)
    return () => {
      el.removeEventListener('wheel', onWheel, { capture: true } as any)
      el.removeEventListener('contextmenu', noMenu)
    }
  }, [camera, controls, gl])
  return null
}
