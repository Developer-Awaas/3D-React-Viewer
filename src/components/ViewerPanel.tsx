import { CSSProperties, useState } from 'react'

const wrap: CSSProperties = {
  position: 'absolute', top: 70, left: 16, zIndex: 1,
  display: 'flex', flexDirection: 'column', gap: 8, padding: 12, maxWidth: 320,
  background: 'rgba(20,20,20,0.7)', borderRadius: 10, backdropFilter: 'blur(6px)', color: '#eee',
}
const btn: CSSProperties = {
  padding: '6px 12px', borderRadius: 8, cursor: 'pointer',
  border: '1px solid #888', background: 'transparent', color: '#eee', fontWeight: 600,
}

// HTML controls for loading a 3D model: paste a .glb/.gltf URL, or upload a file.
// This is where a third-party converter's output URL would be pasted.
export default function ViewerPanel({
  onLoadUrl, onUploadFile, status,
}: {
  onLoadUrl: (url: string) => void
  onUploadFile: (f: File) => void
  status: 'idle' | 'loading' | 'error'
}) {
  const [text, setText] = useState('')
  return (
    <div style={wrap}>
      <div style={{ fontSize: 13, opacity: 0.9 }}>
        Load any <b>.glb / .gltf</b> 3D model — e.g. the file a 2D→3D service returns.
      </div>

      <input
        type="text" placeholder="https://…/model.glb"
        value={text} onChange={(e) => setText(e.target.value)}
        style={{ padding: 6, borderRadius: 6, border: '1px solid #888', background: '#111', color: '#eee' }}
      />
      <button style={{ ...btn, background: '#6cf', color: '#012' }}
        onClick={() => text.trim() && onLoadUrl(text.trim())}>
        Load from URL
      </button>

      <label style={{ ...btn, textAlign: 'center' }}>
        Upload .glb file
        <input
          type="file" accept=".glb,.gltf,model/gltf-binary" style={{ display: 'none' }}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onUploadFile(f) }}
        />
      </label>

      <div style={{ fontSize: 12, opacity: 0.8 }}>
        {status === 'loading' && 'Loading model…'}
        {status === 'error' && '⚠ Could not load — check the URL is a .glb and allows CORS.'}
        {status === 'idle' && 'Drag to orbit · scroll to zoom.'}
      </div>
    </div>
  )
}
