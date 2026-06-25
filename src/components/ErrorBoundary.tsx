import { Component, ReactNode } from 'react'

// A class component (the one place React still uses classes). If anything inside
// it throws while rendering — e.g. the GLTF model fails to download — we show the
// `fallback` instead of crashing the entire scene.
export default class ErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode; onError?: () => void },
  { failed: boolean }
> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  componentDidCatch() {
    this.props.onError?.() // tell the parent so it can show a message
  }
  render() {
    if (this.state.failed) return this.props.fallback ?? null
    return this.props.children
  }
}
