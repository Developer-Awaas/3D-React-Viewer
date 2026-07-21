import type { CSSProperties } from 'react'
const wrap: CSSProperties = {
  position: 'absolute', top: 70, left: 16, zIndex: 1,
  display: 'flex', flexDirection: 'column', gap: 8, padding: 12, maxWidth: 300,
  background: 'rgba(20,20,20,0.7)', borderRadius: 10, backdropFilter: 'blur(6px)', color: '#eee',
}
const btn: CSSProperties = {
  padding: '6px 12px', borderRadius: 8, cursor: 'pointer',
  border: '1px solid #888', background: 'transparent', color: '#eee', fontWeight: 600,
}

export default function TracePanel({
  hasImage, widthM, setWidthM, count, onUpload, newWall, undo, clear, exportJSON,
}: {
  hasImage: boolean
  widthM: number
  setWidthM: (n: number) => void
  count: number
  onUpload: (f: File) => void
  newWall: () => void
  undo: () => void
  clear: () => void
  exportJSON: () => void
}) {
  return (
    <div style={wrap}>
      <label style={{ ...btn, textAlign: 'center', background: '#6cf', color: '#012' }}>
        {hasImage ? 'Replace plan…' : 'Upload plan…'}
        <input
          type="file" accept="image/*" style={{ display: 'none' }}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f) }}
        />
      </label>

      <label style={{ fontSize: 13 }}>
        Real width (m):{' '}
        <input
          type="number" value={widthM} min={1} step={0.5}
          onChange={(e) => setWidthM(+e.target.value)}
          style={{ width: 64 }}
        />
      </label>

      {hasImage && (
        <>
          <div style={{ fontSize: 12, lineHeight: 1.4, opacity: 0.85 }}>
            Click along a wall, point by point — connected clicks make a continuous wall.
            Press <b>New wall</b> to lift the pen and start a separate run (doorways).
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button style={btn} onClick={newWall}>New wall</button>
            <button style={btn} onClick={undo}>Undo</button>
            <button style={btn} onClick={clear}>Clear</button>
          </div>
          <button style={{ ...btn, background: '#fff', color: '#111' }} onClick={exportJSON}>
            Export plan.json ({count} walls)
          </button>
        </>
      )}
    </div>
  )
}
