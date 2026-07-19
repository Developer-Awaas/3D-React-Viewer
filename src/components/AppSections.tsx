import { ReactNode, useRef } from 'react'
import { motion, useInView, useScroll, useTransform } from 'framer-motion'

/* Scrollable story below the Plan → 3D viewer. Drishti's own identity
 * (orange accent, glass surfaces, Playfair italics) with cinematic craft:
 * pull-up word headings, a scroll-linked letter reveal, noise-textured
 * feature cards. All copy is REAL project data — engine steps, measured
 * accuracy, shipped features — not marketing filler. */

const EASE = [0.16, 1, 0.3, 1] as const

/* ---------- shared animation helpers ---------- */

function WordsPullUp({
  text, className = '', delay = 0,
}: { text: string; className?: string; delay?: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })
  return (
    <span ref={ref} className={`inline-flex flex-wrap ${className}`}>
      {text.split(' ').map((w, i) => (
        <motion.span
          key={i}
          initial={{ y: 20, opacity: 0 }}
          animate={inView ? { y: 0, opacity: 1 } : {}}
          transition={{ duration: 0.5, ease: EASE, delay: delay + i * 0.08 }}
          className="mr-[0.28em] inline-block"
        >
          {w}
        </motion.span>
      ))}
    </span>
  )
}

/* Paragraph whose letters brighten as you scroll through it (scroll-linked,
 * not time-linked — scrubbing back dims them again). */
function ScrollReveal({ text, className = '' }: { text: string; className?: string }) {
  const ref = useRef<HTMLParagraphElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start 0.85', 'end 0.35'] })
  const chars = text.split('')
  return (
    <p ref={ref} className={className}>
      {chars.map((c, i) => (
        <Char key={i} c={c} progress={scrollYProgress} range={[i / chars.length - 0.1, i / chars.length + 0.05]} />
      ))}
    </p>
  )
}
function Char({ c, progress, range }: { c: string; progress: any; range: [number, number] }) {
  const opacity = useTransform(progress, range, [0.18, 1])
  return <motion.span style={{ opacity }}>{c}</motion.span>
}

function FadeIn({ children, delay = 0, className = '' }: { children: ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 24, scale: 0.97 }}
      animate={inView ? { opacity: 1, y: 0, scale: 1 } : {}}
      transition={{ duration: 0.6, ease: EASE, delay }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

const Check = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"
    className="mt-0.5 shrink-0 text-neon">
    <path d="M20 6 9 17l-5-5" />
  </svg>
)

/* ---------- section data (real project facts) ---------- */

const STEPS = [
  ['01', 'Read the drawing', 'A CAD PDF is instructions, not pixels — every line, layer name and text string is read with its exact coordinates.'],
  ['02', 'Find the scale', 'Dimension texts like 12′-6″ are matched to the lines they measure; dozens of agreeing "votes" elect the true feet-per-point scale.'],
  ['03', 'Raise the walls', 'Wall centrelines become solid masonry bands, kept at the architect’s drawn positions and thicknesses — then extruded to 3 m.'],
  ['04', 'Cut doors & windows', 'Door swings snap into their wall gaps (a real lintel stays above), windows become glass at sill 3′ to head 7′.'],
  ['05', 'Furnish the rooms', 'Every enclosed space becomes a walk-inside room, and furniture symbols on the drawing return as 3D beds, sofas and counters at their true spots.'],
] as const

const STATS = [
  ['±2.5%', 'envelope accuracy', 'parsed footprint vs the client-confirmed plot dimensions of a real project sheet'],
  ['110+', 'automated tests', 'every real sheet’s numbers are pinned — a change that degrades accuracy fails the build'],
  ['6/6', 'demo doors snapped', 'the bundled sample runs through the same engine as your uploads — nothing staged'],
  ['0', 'plans stored', 'your PDF is parsed in memory and the result returned — drawings are never kept on the server'],
] as const

const CARDS = [
  {
    n: '01', t: 'Walk inside every room.',
    pts: ['One glowing beacon per detected room', 'Click it — or press 1–9 — to stand at eye level', 'The camera looks through the space, never into a wall'],
  },
  {
    n: '02', t: 'Furniture from your drawing.',
    pts: ['Beds, sofas, wardrobes, dining sets read from the furniture layer', 'Sanitary & kitchen fittings included', 'True positions and sizes — nothing invented'],
  },
  {
    n: '03', t: 'Take the model anywhere.',
    pts: ['Download a standard .glb of your building', 'Opens in Blender, Windows 3D Viewer, any glTF app', 'Named parts: walls, glass, columns, furniture'],
  },
  {
    n: '04', t: 'Photos & scans (beta).',
    pts: ['CAD-exported vector PDFs get the full engine', 'Photographed or scanned plans are answered honestly as beta', 'AI perception path is ready for a GPU host'],
  },
] as const

const FAQ = [
  ['What should I upload?', 'A PDF exported straight from AutoCAD (Plot → DWG to PDF). That keeps the vector geometry and live dimension text the engine reads. Photos and image-only scans are in beta.'],
  ['Why did my sheet build a different block than expected?', 'Sheets often hold several drawings. Drishti auto-picks the block with the most doors; use the Wing buttons in the sidebar to switch.'],
  ['Why does my plan show no furniture?', 'Furniture appears when the drawing has furniture / sanitary / kitchen layers. Sheets drawn without them still build perfectly — just unfurnished.'],
  ['The first upload takes long.', 'The free API server sleeps when idle and takes ~30 s to wake. The sample building needs no server at all — it loads instantly.'],
  ['Is my drawing kept anywhere?', 'No. Plans are parsed in memory, the 3D result is returned to your browser, and temporary files are deleted immediately after the response.'],
] as const

/* ---------- the sections ---------- */

export default function AppSections() {
  return (
    <div className="relative bg-background">
      {/* 1 · engine story */}
      <section id="drishti-story" className="bg-noise relative mx-auto max-w-6xl px-6 py-24 sm:py-32">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-neon">How it works</p>
        <h2 className="mt-3 max-w-3xl text-3xl leading-[1.02] text-foreground sm:text-4xl md:text-5xl">
          <WordsPullUp text="Your architect drew a building." />{' '}
          <span className="font-playfair italic text-neon">
            <WordsPullUp text="Drishti reads it back." delay={0.3} />
          </span>
        </h2>
        <ScrollReveal
          className="mt-8 max-w-2xl text-sm leading-relaxed text-foreground/80 sm:text-base"
          text="No AI guessing, no tracing by hand. The engine reads the same lines, layers and dimension texts a site engineer reads — and rebuilds them as real, measured 3D you can walk through."
        />
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map(([n, t, d], i) => (
            <FadeIn key={n} delay={i * 0.12}
              className="rounded-2xl border border-white/5 bg-surface-soft/40 p-5 backdrop-blur-sm">
              <span className="font-playfair text-2xl italic text-neon/80">{n}</span>
              <h3 className="mt-2 text-sm font-semibold text-foreground">{t}</h3>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{d}</p>
            </FadeIn>
          ))}
        </div>
      </section>

      {/* 2 · accuracy & trust */}
      <section className="relative border-y border-white/5 bg-[#0b1120] px-6 py-24 sm:py-28">
        <div className="mx-auto max-w-6xl">
          <h2 className="max-w-3xl text-3xl leading-[1.02] text-foreground sm:text-4xl md:text-5xl">
            <WordsPullUp text="Measured, tested," />{' '}
            <span className="text-muted-foreground"><WordsPullUp text="not imagined." delay={0.25} /></span>
          </h2>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STATS.map(([v, l, d], i) => (
              <FadeIn key={l} delay={i * 0.12}
                className="rounded-2xl border border-white/5 bg-surface/60 p-6">
                <div className="font-playfair text-4xl italic text-neon">{v}</div>
                <div className="mt-1 text-sm font-semibold text-foreground">{l}</div>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{d}</p>
              </FadeIn>
            ))}
          </div>
          <p className="mt-6 text-xs text-muted-foreground/70">
            Accuracy varies with how a sheet is drawn — dense multi-flat sheets snap fewer doors than clean single-flat plans.
            Every number above is enforced by the test suite on real client drawings.
          </p>
        </div>
      </section>

      {/* 3 · feature cards */}
      <section className="bg-noise relative mx-auto max-w-6xl px-6 py-24 sm:py-28">
        <h2 className="max-w-3xl text-2xl leading-tight text-foreground sm:text-3xl md:text-4xl">
          <WordsPullUp text="Built for people who build." />
        </h2>
        <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {CARDS.map((c, i) => (
            <FadeIn key={c.n} delay={i * 0.15}
              className="flex flex-col rounded-2xl border border-white/5 bg-surface-soft/50 p-5">
              <div className="flex items-baseline justify-between">
                <h3 className="text-sm font-semibold text-foreground">{c.t}</h3>
                <span className="ml-2 text-xs text-muted-foreground/60">{c.n}</span>
              </div>
              <ul className="mt-4 flex flex-col gap-2.5">
                {c.pts.map((p) => (
                  <li key={p} className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
                    <Check />{p}
                  </li>
                ))}
              </ul>
            </FadeIn>
          ))}
        </div>
      </section>

      {/* 4 · FAQ */}
      <section className="relative border-t border-white/5 bg-[#0b1120] px-6 py-24">
        <div className="mx-auto max-w-3xl">
          <h2 className="text-2xl leading-tight text-foreground sm:text-3xl">
            <WordsPullUp text="Good to know" />
          </h2>
          <div className="mt-8 flex flex-col gap-3">
            {FAQ.map(([q, a], i) => (
              <FadeIn key={q} delay={i * 0.08}>
                <details className="group rounded-xl border border-white/5 bg-surface/50 px-5 py-4">
                  <summary className="cursor-pointer list-none text-sm font-medium text-foreground marker:hidden">
                    <span className="mr-2 text-neon transition-transform group-open:rotate-90 inline-block">›</span>{q}
                  </summary>
                  <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{a}</p>
                </details>
              </FadeIn>
            ))}
          </div>
          <div className="mt-16 flex items-center justify-between border-t border-white/5 pt-6 text-xs text-muted-foreground/60">
            <span className="font-playfair italic">Drishti — every plan holds a building within</span>
            <button
              onClick={() => document.getElementById('drishti-viewer')?.scrollIntoView({ behavior: 'smooth' })}
              className="rounded-full border border-white/10 px-4 py-2 text-foreground/80 hover:border-neon/50 hover:text-foreground"
            >
              ↑ back to the viewer
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
