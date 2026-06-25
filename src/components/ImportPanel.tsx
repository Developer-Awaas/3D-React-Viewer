import { CSSProperties } from 'react'

const wrap: CSSProperties = {
  position: 'absolute', top: 70, left: 16, zIndex: 1,
  display: 'flex', flexDirection: 'column', gap: 8, padding: 12, maxWidth: 320,
  background: 'rgba(20,20,20,0.7)', borderRadius: 10, backdropFilter: 'blur(6px)', color: '#eee',
}
const btn: CSSProperties = {
  padding: '8px 12px', borderRadius: 8, cursor: 'pointer', textAlign: 'center',
  border: '1px solid #888', background: '#6cf', color: '#012', fontWeight: 700,
}

// Upload any plan/model. JPG/PNG/PDF -> auto-detected in the browser; GLB -> viewed.
export default function ImportPanel({
  onFile, status, count, widthM, setWidthM,
}: {
  onFile: (f: File) => void
  status: string
  count: number
  widthM: number
  setWidthM: (n: number) => void
}) {
  return (
    <div style={wrap}>
      <div style={{ fontSize: 13, opacity: 0.9 }}>
        Upload a plan (<b>JPG/PNG/PDF</b>) — walls are auto-detected here in your browser.
        A <b>.glb</b> opens directly in the viewer.
      </div>
      <label style={btn}>
        Upload file…
        <input type="file" accept=".jpg,.jpeg,.png,.pdf,.glb,.gltf" style={{ display: 'none' }}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f) }} />
      </label>
      <label style={{ fontSize: 13 }}>
        Building width (m):{' '}
        <input type="number" value={widthM} min={1} step={0.5}
          onChange={(e) => setWidthM(+e.target.value)} style={{ width: 64 }} />
      </label>
      <div style={{ fontSize: 12, opacity: 0.85 }}>{status}{count ? `  ·  ${count} walls` : ''}</div>
      <div style={{ fontSize: 11, opacity: 0.7 }}>
        First run downloads OpenCV (~8MB) — give it a few seconds.
      </div>
    </div>
  )
}
