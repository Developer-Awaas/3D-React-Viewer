# F3 — Photoreal Render QA & Tuning Guide

Your first render worked. This is the checklist to judge quality and the exact
knobs to turn when something looks off. In layman's terms throughout.

## The 5-point QA check (do this per style, per room type)

1. **Geometry lock** — do walls/openings in the photo sit where they sit in the
   3D view? If the AI "moved a wall", the depth conditioning was weak.
2. **Style fidelity** — does "luxury" actually look luxury? Compare the 4-style
   grid (▦ Compare 4 styles) — same seed, same geometry, only style differs, so
   differences you see are pure style.
3. **Surface separation** — are wall/floor/window boundaries crisp? This is what
   the 5 GB seg model improves; re-check after the download completes.
4. **Artifacts** — melted furniture, doubled doors, text-like smudges. Usually
   fixed by a re-render (new seed) or slightly higher guidance.
5. **Consistency** — hit Re-render twice: results should stay in the same family
   (identical geometry, similar mood). Wild swings = conditioning too weak.

## The knobs (what they mean and when to turn them)

Per-request (the frontend sends defaults; can be changed in `VisualizeButton.tsx`
or by POSTing to `/visualize/render` directly):

| knob | default | plain-language meaning | turn it when |
|---|---|---|---|
| `steps` | 28 | how long the AI "develops" the photo | 20 = faster/rougher · 40 = slower/cleaner |
| `guidance` | 6.0 | how strictly it follows the text prompt | ↑7–8 if style ignored · ↓5 if images look "burnt" |
| `control_scale` | 0.7 | how strictly it follows YOUR geometry | ↑0.9 if walls drift · ↓0.5 if images look stiff/CG |

Backend env (`server/.env`):

| var | default | what it does |
|---|---|---|
| `RENDER_TIMEOUT_S` | 240 | give up after this many seconds (raise on first-ever run) |
| `MAX_CONCURRENT_RENDER` | 1 | renders at once — keep 1 on a 12 GB GPU |
| `SEG_CONTROLNET` | auto | seg model id; auto-enables once the 5 GB download is cached |
| `SVD_FRAMES` | 25 | video length in frames (25 ≈ 3–4 s) |
| `SVD_DECODE_CHUNK` | 4 | lower to 2 if Animate runs out of GPU memory |

## Rules of thumb

- Fix geometry problems with `control_scale`, style problems with `guidance`,
  quality problems with `steps`. One knob at a time.
- The render cache means a repeated identical request returns instantly — change
  the seed to force a genuinely new image.
- Eye-level room views photograph best; bird's-eye views of the whole plan will
  always look more "rendered" — that's a limit of how these models were trained.
