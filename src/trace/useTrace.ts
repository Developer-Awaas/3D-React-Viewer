import { useCallback, useState } from 'react'

// One wall = [x1, z1, x2, z2] in metres.
export type Seg = [number, number, number, number]

// All the state + actions for tracing a plan. Kept in a custom hook so both the
// HTML panel and the 3D scene can share it (App calls this once and passes pieces
// to each). A "custom hook" is just a function starting with `use` that bundles
// related useState/useCallback logic for reuse.
export function useTrace() {
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [aspect, setAspect] = useState(1)      // image width / height
  const [widthM, setWidthM] = useState(12)     // real-world width of the plan (metres)
  const [segments, setSegments] = useState<Seg[]>([])
  const [start, setStart] = useState<[number, number] | null>(null) // current "pen" point

  // Read the uploaded file, learn its pixel aspect ratio, show it as the underlay.
  const onUpload = useCallback((file: File) => {
    const url = URL.createObjectURL(file) // a temporary in-browser URL for the file
    const img = new Image()
    img.onload = () => {
      setAspect(img.naturalWidth / img.naturalHeight)
      setImageUrl(url)
      setSegments([])
      setStart(null)
    }
    img.src = url
  }, [])

  // Each click: if the pen is already down, draw a wall from the pen to here, then
  // move the pen here. So clicking point-by-point traces connected walls.
  const addPoint = useCallback(
    (x: number, z: number) => {
      if (start) setSegments((s) => [...s, [start[0], start[1], x, z]])
      setStart([x, z])
    },
    [start]
  )

  const newWall = useCallback(() => setStart(null), []) // lift the pen (start a separate run)
  const clear = useCallback(() => { setSegments([]); setStart(null) }, [])
  const undo = useCallback(() => {
    setSegments((s) => {
      if (s.length === 0) { setStart(null); return s }
      const last = s[s.length - 1]
      setStart([last[0], last[1]]) // move pen back to the removed wall's start
      return s.slice(0, -1)
    })
  }, [])

  const heightM = widthM / aspect

  // Download the traced result as plan.json — the exact input format the renderer needs.
  const exportJSON = useCallback(() => {
    const data = {
      metresWide: +widthM.toFixed(3),
      metresDeep: +heightM.toFixed(3),
      ceilingHeight: 2.5,
      wallThickness: 0.2,
      walls: segments,
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'plan.json'
    a.click()
  }, [segments, widthM, heightM])

  return {
    imageUrl, aspect, widthM, setWidthM, heightM,
    segments, start, hasImage: !!imageUrl,
    onUpload, addPoint, newWall, undo, clear, exportJSON,
  }
}
