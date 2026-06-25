import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Standard Vite + React setup. Nothing 3D-specific is needed here —
// react-three-fiber is just a React renderer, so plain Vite handles it.
export default defineConfig({
  plugins: [react()],
})
