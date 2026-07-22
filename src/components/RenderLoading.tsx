import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

// Cinematic overlay while a photoreal render runs — same mood as the landing
// loader ("Raising the walls…"): Playfair italic headline, staged engine copy,
// a thin track with a glowing orange runner. Pure presentation; the render
// itself is untouched.
const STAGES: [number, string, string][] = [
  // [starts at second, headline, sub copy]
  [0, 'Reading the depth…', 'Every wall’s true distance, straight from your 3D scene.'],
  [6, 'Locking the geometry…', 'ControlNet pins the render to the real plan — nothing drifts.'],
  [14, 'Choosing materials…', 'Floors, plaster, glass — painted where they belong.'],
  [24, 'Lighting the room…', 'Daylight, shadows and reflections settle in.'],
  [36, 'Developing the photo…', 'Final denoising passes — almost there.'],
  [55, 'First render warms the GPU…', 'Loading the model into memory — one-time wait.'],
]

export default function RenderLoading({ active, label = 'photoreal render' }: {
  active: boolean
  label?: string
}) {
  const [t, setT] = useState(0)
  useEffect(() => {
    if (!active) { setT(0); return }
    const t0 = Date.now()
    const iv = setInterval(() => setT((Date.now() - t0) / 1000), 250)
    return () => clearInterval(iv)
  }, [active])

  const stage = [...STAGES].reverse().find(([s]) => t >= s) ?? STAGES[0]
  // honest-but-smooth progress: eases toward 95% over ~45s, never fakes done
  const pct = Math.min(95, 100 * (1 - Math.exp(-t / 18)))

  return (
    <AnimatePresence>
      {active && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: 0.35 }}
          className="pointer-events-none absolute inset-0 z-[25] flex flex-col items-center
                     justify-center bg-[#0a1020]/80 backdrop-blur-[3px]"
        >
          {/* faint blueprint grid, echoing the landing */}
          <div
            aria-hidden
            className="absolute inset-0 opacity-[0.07]"
            style={{
              backgroundImage:
                'linear-gradient(rgba(251,146,60,.6) 1px, transparent 1px),' +
                'linear-gradient(90deg, rgba(251,146,60,.6) 1px, transparent 1px)',
              backgroundSize: '56px 56px',
            }}
          />
          <AnimatePresence mode="wait">
            <motion.p
              key={stage[1]}
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.45 }}
              className="font-playfair px-6 text-center text-3xl italic text-white sm:text-4xl"
            >
              {stage[1]}
            </motion.p>
          </AnimatePresence>
          <AnimatePresence mode="wait">
            <motion.p
              key={stage[2]}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.45, delay: 0.1 }}
              className="mt-3 max-w-md px-6 text-center text-xs leading-relaxed text-white/50"
            >
              {stage[2]}
            </motion.p>
          </AnimatePresence>

          {/* track + glowing runner, like the landing's underline */}
          <div className="relative mt-8 h-[2px] w-56 overflow-hidden rounded bg-white/10">
            <motion.div
              className="absolute inset-y-0 left-0 rounded bg-neon shadow-glow"
              animate={{ width: `${pct}%` }}
              transition={{ ease: 'easeOut', duration: 0.3 }}
            />
          </div>
          <p className="mt-3 text-[11px] tracking-wide text-white/35">
            {Math.floor(t)}s · {label}
          </p>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
