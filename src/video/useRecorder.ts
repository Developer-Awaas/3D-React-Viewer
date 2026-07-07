import { useRef, useState, useCallback } from 'react'

// Records the WebGL <canvas> to a downloadable .webm clip.
// Pair with the GSAP camera fly-through to produce the walkthrough video.
// NOTE: not wired into the app yet - this is the building block for Step 4.
export function useRecorder() {
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const [recording, setRecording] = useState(false)

  const start = useCallback((canvas: HTMLCanvasElement, fps = 60) => {
    if (recorderRef.current) return
    const stream = canvas.captureStream(fps)
    const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
      ? 'video/webm;codecs=vp9'
      : 'video/webm'
    const rec = new MediaRecorder(stream, { mimeType: mime })
    chunksRef.current = []
    rec.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data) }
    rec.start()
    recorderRef.current = rec
    setRecording(true)
  }, [])

  const stop = useCallback((): Promise<Blob> => new Promise((resolve) => {
    const rec = recorderRef.current
    if (!rec) return resolve(new Blob())
    rec.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: 'video/webm' })
      recorderRef.current = null
      setRecording(false)
      resolve(blob)
    }
    rec.stop()
  }), [])

  const download = useCallback((blob: Blob, name = 'walkthrough.webm') => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = name; a.click()
    URL.revokeObjectURL(url)
  }, [])

  return { start, stop, download, recording }
}
