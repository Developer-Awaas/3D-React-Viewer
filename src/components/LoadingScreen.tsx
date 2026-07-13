import { useEffect, useRef, useState } from 'react'

// Drishti loading screen — the Lithos spotlight-reveal ideology, adapted:
// "drishti" means SIGHT. While the backend reads the drawing, a soft spotlight
// drifts across a dark blueprint and REVEALS the glowing structure hidden in
// it — a live metaphor for exactly what the engine is doing. The spotlight
// follows the cursor when the user moves it, and drifts on its own otherwise.
// No external images: both layers are drawn in code (a loading screen must
// never wait on a CDN). Palette = the app's slate + neon cyan.

const SPOTLIGHT_R = 260

const STAGES = [
  'Reading the architect’s layers…',
  'Listening to the dimension text…',
  'Raising the walls…',
  'Cutting doors at the lintel…',
  'Casting light into the rooms…',
]

// dark blueprint: faint slate grid on near-black
const BASE_BG = [
  'linear-gradient(rgba(148,163,184,0.07) 1px, transparent 1px)',
  'linear-gradient(90deg, rgba(148,163,184,0.07) 1px, transparent 1px)',
  'linear-gradient(rgba(148,163,184,0.04) 1px, transparent 1px)',
  'linear-gradient(90deg, rgba(148,163,184,0.04) 1px, transparent 1px)',
  'radial-gradient(ellipse at 50% 40%, #101b31 0%, #070d1a 70%)',
].join(',')
const BASE_SIZE = '96px 96px, 96px 96px, 24px 24px, 24px 24px, 100% 100%'

// revealed structure: the same drawing, alive — neon grid + glowing "walls"
const REVEAL_BG = [
  'linear-gradient(rgba(34,211,238,0.35) 2px, transparent 2px)',
  'linear-gradient(90deg, rgba(34,211,238,0.35) 2px, transparent 2px)',
  'linear-gradient(rgba(34,211,238,0.12) 1px, transparent 1px)',
  'linear-gradient(90deg, rgba(34,211,238,0.12) 1px, transparent 1px)',
  'radial-gradient(ellipse at 50% 40%, #0b2733 0%, #081420 70%)',
].join(',')
const REVEAL_SIZE = '96px 96px, 96px 96px, 24px 24px, 24px 24px, 100% 100%'

function RevealLayer({ x, y }: { x: number; y: number }) {
  // soft circular mask, same stops as the Lithos spec — pure CSS, no canvas,
  // so it costs almost nothing per frame.
  const mask =
    `radial-gradient(circle ${SPOTLIGHT_R}px at ${x}px ${y}px,` +
    ' rgba(255,255,255,1) 0%, rgba(255,255,255,1) 40%,' +
    ' rgba(255,255,255,0.75) 60%, rgba(255,255,255,0.4) 75%,' +
    ' rgba(255,255,255,0.12) 88%, rgba(255,255,255,0) 100%)'
  return (
    <div
      className="pointer-events-none absolute inset-0 z-30"
      style={{
        backgroundImage: REVEAL_BG,
        backgroundSize: REVEAL_SIZE,
        WebkitMaskImage: mask,
        maskImage: mask,
      }}
    />
  )
}

export default function LoadingScreen({ active }: { active: boolean }) {
  const mouse = useRef({ x: -999, y: -999, moved: false })
  const smooth = useRef({ x: -999, y: -999 })
  const rafRef = useRef(0)
  const [pos, setPos] = useState({ x: -999, y: -999 })
  const [stage, setStage] = useState(0)

  useEffect(() => {
    if (!active) return
    setStage(0)
    const onMove = (e: MouseEvent) => {
      mouse.current = { x: e.clientX, y: e.clientY, moved: true }
    }
    window.addEventListener('mousemove', onMove)

    const t0 = performance.now()
    smooth.current = { x: window.innerWidth / 2, y: window.innerHeight / 2 }
    const loop = (now: number) => {
      const t = (now - t0) / 1000
      // cursor leads when it has moved; otherwise the light drifts on its own
      const tx = mouse.current.moved
        ? mouse.current.x
        : window.innerWidth / 2 + window.innerWidth * 0.28 * Math.sin(t * 0.45)
      const ty = mouse.current.moved
        ? mouse.current.y
        : window.innerHeight / 2 + window.innerHeight * 0.2 * Math.sin(t * 0.3 + 1.3)
      smooth.current.x += (tx - smooth.current.x) * 0.1
      smooth.current.y += (ty - smooth.current.y) * 0.1
      setPos({ x: smooth.current.x, y: smooth.current.y })
      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)

    const stageTimer = setInterval(
      () => setStage((s) => Math.min(s + 1, STAGES.length - 1)),
      1700,
    )
    return () => {
      window.removeEventListener('mousemove', onMove)
      cancelAnimationFrame(rafRef.current)
      clearInterval(stageTimer)
      mouse.current.moved = false
    }
  }, [active])

  if (!active) return null

  return (
    <section
      className="fixed inset-0 z-[90] overflow-hidden bg-black tracking-[-0.02em]"
      style={{ height: '100dvh', fontFamily: "'Inter', sans-serif" }}
    >
      {/* base blueprint, slow Ken Burns drift */}
      <div
        className="hero-zoom absolute inset-0 z-10"
        style={{ backgroundImage: BASE_BG, backgroundSize: BASE_SIZE }}
      />
      {/* the revealed structure inside the moving spotlight */}
      <RevealLayer x={pos.x} y={pos.y} />

      {/* wordmark, top-left — same placement language as the app header */}
      <div className="absolute left-5 top-5 z-50 flex items-center gap-3 sm:left-8 sm:top-6">
        <div className="grid h-9 w-9 place-items-center rounded-lg bg-neon/15 text-neon shadow-glow">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 9l9-6 9 6v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9z" /><path d="M9 21V12h6v9" />
          </svg>
        </div>
        <span className="font-playfair text-2xl italic text-white">Drishti</span>
      </div>

      {/* heading — blur-rise, staggered */}
      <div className="pointer-events-none absolute left-0 right-0 top-[26%] z-50 flex flex-col items-center px-5 text-center">
        <h1 className="text-white leading-[0.95]">
          <span
            className="hero-anim hero-reveal font-playfair block text-4xl italic font-normal sm:text-6xl md:text-7xl"
            style={{ letterSpacing: '-0.05em', animationDelay: '0.25s' }}
          >
            Every line holds
          </span>
          <span
            className="hero-anim hero-reveal -mt-1 block text-4xl font-light sm:text-6xl md:text-7xl"
            style={{ letterSpacing: '-0.08em', animationDelay: '0.42s' }}
          >
            a home within
          </span>
        </h1>

        {/* cycling stage caption */}
        <p
          key={stage}
          className="hero-anim hero-fade mt-6 text-sm text-white/70 sm:text-base"
          style={{ animationDelay: '0.1s' }}
        >
          {STAGES[stage]}
        </p>

        {/* indeterminate shimmer bar */}
        <div className="hero-anim hero-fade mt-5 h-[2px] w-56 overflow-hidden rounded-full bg-white/10 sm:w-72"
             style={{ animationDelay: '0.6s' }}>
          <div className="load-sweep h-full w-1/3 rounded-full bg-neon shadow-glow" />
        </div>
      </div>

      {/* bottom-left note */}
      <div className="hero-anim hero-fade absolute bottom-14 left-10 z-50 hidden max-w-[280px] sm:block md:left-14"
           style={{ animationDelay: '0.7s' }}>
        <p className="text-sm leading-relaxed text-white/60">
          Drishti reads the drawing the way a mason would — walls by their
          thickness, scale from the architect’s own dimensions, doors cut at
          the lintel.
        </p>
      </div>

      {/* bottom-right hint */}
      <div className="hero-anim hero-fade absolute bottom-10 right-5 z-50 max-w-full sm:bottom-14 sm:right-10 md:right-14 sm:max-w-[260px]"
           style={{ animationDelay: '0.85s' }}>
        <p className="load-pulse text-xs leading-relaxed text-white/50 sm:text-sm">
          Move your cursor — the light shows what the engine sees.
        </p>
      </div>
    </section>
  )
}
