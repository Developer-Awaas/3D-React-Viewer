# Drishti — working agreement (read every session)

## Who does what
- Claude Code: builds, edits, runs tests. Never pushes. Never merges.
- Rahul: all git push, all merges, all deploys, all secrets.

## Before any change
1. Read CLAUDE.md, AWAAS-HANDOFF.md, MAC-BASELINE-10AUG.md.
2. Write a short plan first. Get it approved. Then build.
3. One cause per branch. Do not bundle unrelated fixes.

## After any change — all four, every time
- cd server && python -m pytest
- python server/batch_eval.py   (from repo root)
- npm run test
- npm run build

## Dry run — after building, before reporting (every task)

Run what you just wrote against the rest of the system and the remaining phase
plan, and report it as a short section, one line per finding:
- **Collisions** — does this break, or get broken by, another component or a
  later phase (0-7)?
- **Contradictions** — does it conflict with any rule in PLAN-READING-RULES.md?
- **Silent movement** — what totals, buckets or golden numbers could this move
  without a test noticing?
- **Assumptions** — what did you assume that the drawing or the spec does not
  actually state?

**Every finding carries a DATA POINT** — a number, a file:line, a measured
value. A verdict without one is an opinion and cannot be re-checked. A serious
collision means STOP and report, not work around.

## The corpus is the proof
- Any batch_eval number that moves must be explained in feet or rupees
  before the change is accepted.
- Never edit a golden test to make it pass.
- If a number moves unexpectedly: STOP and report. Do not continue.

## Hard rules
- Never touch LandingHero.tsx or landing.css.
- General rules only — no per-plan hacks.
- Report honestly what is proven vs assumed.
- Browser check anything visual. Source-level proof is not enough.

## Environment
- Mac runs everything except AI renders (needs NVIDIA).
- requirements.txt is a guide, not gospel — the old Windows box drifted.
  If a test behaves oddly, suspect versions before suspecting code.
- Frontend runs on 5174 here (5173 is taken). .env allows both.
