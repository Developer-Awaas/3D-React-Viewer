import { useEffect, useRef, useState } from 'react';
import './landing.css';
import heroPlan from './assets/hero-plan.webp';
import hero3d from './assets/hero-3d.webp';
import AppSections from '../components/AppSections';

/**
 * Drishti landing hero.
 *
 * Base layer  : dark blueprint linework of a floor plan (what you upload).
 * Reveal layer: the same plan raised into 3D (what Drishti gives you),
 *               visible only inside a soft spotlight that trails the cursor —
 *               the cursor is Drishti's "sight" seeing the building in the plan.
 *
 * The spotlight mask is a pure CSS radial-gradient (no per-frame canvas
 * toDataURL), so it stays 60fps even on modest machines.
 *
 * Desktop (fine pointer + keyboard):
 *   · the native cursor is hidden over the hero and replaced by a small
 *     orange sight-dot; the smoothed spotlight trails it
 *   · Enter opens the app, arrow keys steer the spotlight, Esc closes menus
 *   · every control is focusable with a visible orange focus ring
 * Touch / idle: the spotlight drifts on its own so the effect always shows.
 */

const SPOTLIGHT_R = 260;

const gradientStops =
  'rgba(255,255,255,1) 0%, rgba(255,255,255,1) 40%, rgba(255,255,255,0.75) 60%, ' +
  'rgba(255,255,255,0.4) 75%, rgba(255,255,255,0.12) 88%, rgba(255,255,255,0) 100%';

/** Spotlight radius, clamped so it doesn't swallow small screens. */
function spotR(): number {
  return Math.min(SPOTLIGHT_R, Math.round(window.innerWidth * 0.42));
}

function RevealLayer({ image, x, y }: { image: string; x: number; y: number }) {
  const mask = `radial-gradient(circle ${spotR()}px at ${x}px ${y}px, ${gradientStops})`;
  return (
    <div
      className="dl-reveal"
      style={{
        backgroundImage: `url(${image})`,
        WebkitMaskImage: mask,
        maskImage: mask,
      }}
    />
  );
}

export interface LandingHeroProps {
  /** Called after the exit animation finishes — mount the app here. */
  onEnter: () => void;
}

export default function LandingHero({ onEnter }: LandingHeroProps) {
  const mouse = useRef({ x: -999, y: -999 });
  const smooth = useRef({ x: -999, y: -999 });
  const rafRef = useRef<number>(0);
  const lastInput = useRef<number>(0); // 0 = never touched -> auto drift
  const leavingRef = useRef(false);
  const [cursorPos, setCursorPos] = useState({ x: -999, y: -999 });
  const [rawPos, setRawPos] = useState({ x: -999, y: -999 });
  const [leaving, setLeaving] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  // pointer capability decides the cursor treatment + hint copy
  const [finePointer] = useState<boolean>(
    () => typeof window !== 'undefined' && window.matchMedia('(pointer: fine)').matches,
  );

  const enter = () => {
    if (leavingRef.current) return;
    leavingRef.current = true;
    setLeaving(true);
    window.setTimeout(() => onEnter(), 700);
  };

  // nav "How it works" / "Docs" now scroll DOWN the landing page (the story
  // sections live here, below the hero) instead of opening the app
  const scrollTo = (id: string) => {
    setMenuOpen(false);
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      mouse.current = { x: e.clientX, y: e.clientY };
      lastInput.current = performance.now();
    };
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (e.key === 'Escape') { setMenuOpen(false); return; }
      // Enter opens the app — unless focus sits on a control that
      // handles Enter itself (buttons would double-fire)
      if (e.key === 'Enter' && tag !== 'BUTTON' && tag !== 'INPUT' && tag !== 'A') {
        e.preventDefault();
        enter();
        return;
      }
      // arrow keys steer the spotlight — keyboard users get the reveal too
      const STEP = 64;
      const nudge: Record<string, [number, number]> = {
        ArrowLeft: [-STEP, 0], ArrowRight: [STEP, 0],
        ArrowUp: [0, -STEP], ArrowDown: [0, STEP],
      };
      if (nudge[e.key]) {
        e.preventDefault();
        const [dx, dy] = nudge[e.key];
        const base =
          mouse.current.x < 0
            ? { x: window.innerWidth / 2, y: window.innerHeight / 2 }
            : mouse.current;
        mouse.current = {
          x: Math.min(window.innerWidth, Math.max(0, base.x + dx)),
          y: Math.min(window.innerHeight, Math.max(0, base.y + dy)),
        };
        lastInput.current = performance.now();
      }
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('keydown', onKey);

    const start = performance.now();
    const loop = () => {
      const now = performance.now();
      // idle / touch: drift the spotlight along a slow lissajous path
      if (now - lastInput.current > 3500) {
        const t = (now - start) / 1000;
        const w = window.innerWidth;
        const h = window.innerHeight;
        mouse.current = {
          x: w * 0.5 + w * 0.26 * Math.sin(t * 0.45),
          y: h * 0.55 + h * 0.16 * Math.sin(t * 0.72 + 1.3),
        };
      }
      smooth.current.x += (mouse.current.x - smooth.current.x) * 0.1;
      smooth.current.y += (mouse.current.y - smooth.current.y) * 0.1;
      setCursorPos({ x: smooth.current.x, y: smooth.current.y });
      setRawPos({ x: mouse.current.x, y: mouse.current.y });
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);

    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('keydown', onKey);
      cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    // the landing is now a scrollable page: the hero fills the first screen,
    // and the story sections (how it works · accuracy · features · FAQ)
    // continue below. dl-page is the scroll container.
    <div className="dl-page" id="drishti-top">
    <div className={`dl-root${leaving ? ' dl-leaving' : ''}`}>
      {/* ---------- nav ---------- */}
      <nav className="dl-nav">
        <div className="dl-nav-brand">
          <svg width="26" height="26" viewBox="0 0 256 256" fill="none" aria-hidden="true">
            {/* isometric cube — a plan raised into 3D */}
            <path
              d="M128 18 L232 78 L232 178 L128 238 L24 178 L24 78 Z"
              stroke="#ffffff" strokeWidth="17" strokeLinejoin="round"
            />
            <path
              d="M24 78 L128 138 L232 78 M128 138 L128 238"
              stroke="#ffffff" strokeWidth="17" strokeLinejoin="round" strokeLinecap="round"
            />
          </svg>
          <span className="dl-wordmark dl-playfair">Drishti</span>
        </div>

        <div className="dl-nav-pill">
          <button className="dl-active" onClick={() => enter()}>Plan → 3D</button>
          <button onClick={() => enter()}>Viewer</button>
          <button onClick={() => scrollTo('drishti-story')}>How it works</button>
          <button onClick={() => scrollTo('drishti-docs')}>Docs</button>
        </div>

        <button className="dl-signup" onClick={() => enter()}>Open App</button>

        <button
          className="dl-burger"
          aria-label="Menu"
          onClick={() => setMenuOpen((v) => !v)}
        >
          <span /><span /><span />
        </button>
        {menuOpen && (
          <div className="dl-mobile-menu">
            <button onClick={() => enter()}>Plan → 3D</button>
            <button onClick={() => enter()}>Viewer</button>
            <button onClick={() => scrollTo('drishti-story')}>How it works</button>
            <button onClick={() => scrollTo('drishti-docs')}>Docs</button>
            <button onClick={() => enter()}>Open App</button>
          </div>
        )}
      </nav>

      {/* ---------- hero ---------- */}
      <section
        className={`dl-hero${finePointer ? ' dl-cursor-hide' : ''}`}
        style={{ height: '100dvh' }}
      >
        {/* base: the flat blueprint */}
        <div
          className="dl-base dl-zoom"
          style={{ backgroundImage: `url(${heroPlan})` }}
        />

        {/* reveal: the same plan, standing up in 3D */}
        <RevealLayer image={hero3d} x={cursorPos.x} y={cursorPos.y} />

        {/* soft accent ring hugging the spotlight */}
        <div
          className="dl-spot-ring"
          style={{
            left: cursorPos.x,
            top: cursorPos.y,
            width: spotR() * 2,
            height: spotR() * 2,
          }}
        />

        {/* the sight-dot that replaces the native cursor on desktop */}
        {finePointer && !leaving && rawPos.x >= 0 && (
          <div className="dl-cursor-dot" style={{ left: rawPos.x, top: rawPos.y }} />
        )}

        {/* heading */}
        <div className="dl-heading">
          <h1>
            <span
              className="dl-h1a dl-playfair dl-anim dl-reveal-anim"
              style={{ animationDelay: '0.25s' }}
            >
              Every plan holds
            </span>
            <span
              className="dl-h1b dl-anim dl-reveal-anim"
              style={{ animationDelay: '0.42s' }}
            >
              a building within
            </span>
          </h1>
          <div className="dl-hint dl-anim dl-fade" style={{ animationDelay: '1.4s' }}>
            {finePointer ? (
              <>move your cursor — see what Drishti sees · press <kbd>↵</kbd> to enter</>
            ) : (
              <>follow the light — tap “Convert a Plan” to begin</>
            )}
          </div>
        </div>

        {/* bottom-left copy */}
        <div className="dl-copy-left dl-anim dl-fade" style={{ animationDelay: '0.7s' }}>
          <p>
            A floor plan is a building compressed into lines — walls, doors,
            and rooms flattened onto a sheet, waiting for their third
            dimension.
          </p>
        </div>

        {/* bottom-right copy + CTA */}
        <div className="dl-copy-right dl-anim dl-fade" style={{ animationDelay: '0.85s' }}>
          <p>
            Drishti reads your CAD drawings layer by layer and raises them
            into true-to-scale, walk-through 3D. Upload a PDF and watch it
            stand up.
          </p>
          <button className="dl-cta" onClick={() => enter()}>
            Convert a Plan
          </button>
        </div>

        {/* scroll cue — the page continues below the hero */}
        <button
          className="dl-scrollcue dl-anim dl-fade"
          style={{ animationDelay: '1.6s' }}
          onClick={() => scrollTo('drishti-story')}
          aria-label="See how it works"
        >
          how it works <span className="dl-scrollcue-arrow">↓</span>
        </button>
      </section>
    </div>

      {/* ---------- story sections (moved here from the converter page) ---------- */}
      <AppSections onEnterApp={() => enter()} />
    </div>
  );
}
