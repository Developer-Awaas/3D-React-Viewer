import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// Standard React 18 entry point. Everything 3D lives inside <App />.
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
