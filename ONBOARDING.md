# Onboarding this repo for Sutra — plain English

**What it is:** Drishti, the Awaas floor-plan-to-3D app. Upload a CAD PDF of a
building plan, it reads the walls/doors/rooms and builds a walkable 3D model,
plus an area statement, a Vastu report and a rough cost estimate.

**Stack:** React + TypeScript + Vite (frontend, `npm`) talking to a FastAPI
Python backend (`server/`) that does the actual PDF reading with OpenCV /
Shapely / PyMuPDF. No database required for the main path — there's an
*optional* Supabase connection used only to log parses for later ML training.

## Can Sutra run and screenshot it on this Mac?

**Partly.**

- The **frontend** (`npm install && npm run dev`) runs on any Mac, no GPU, no
  network beyond npm's own install. Sutra can screenshot the upload page fine.
- The **backend** core parser also runs fine on CPU (the team's own working
  notes confirm this on a Mac with no CUDA) — but seeing the app actually
  *work* end to end (upload → 3D view) needs the backend running too, and its
  install is heavy: `pip install -r server/requirements.txt` pulls in torch,
  OpenCV, trimesh — multi-GB, several minutes.
- Two backend features are **not** usable on a MacBook: the photo/scan ML
  fallback (needs separately-downloaded CubiCasa/TF2 model weights) and the
  photoreal render feature (SDXL + ControlNet — needs a real GPU, explicitly
  documented in `docs/DEPLOY-GPU.md` as a separate GPU-box deploy). Neither is
  on the main CAD-PDF path, so their absence doesn't block the core product.

## Test database needed?

**No database is required to build or test this app.** The only database
integration is **optional, off by default**: Supabase parse-logging.

- Env var names it reads (not values): `SUPABASE_URL`, `SUPABASE_KEY`,
  `SUPABASE_TABLE` (default `parses`), `SUPABASE_BUCKET` (default `plans`).
- It is OFF unless **both** `SUPABASE_URL` and `SUPABASE_KEY` are set — leave
  them blank for Sutra's test env file and the app behaves exactly the same.
- If anyone ever wants this enabled for a test run, it needs its **own**
  disposable Supabase project (table + storage bucket defined in
  `server/schema.sql`), never the team's real one. `SUPABASE_KEY` is
  documented in the repo's own `.env.example` as the **service-role** key —
  that's a secret that must stay server-side, never shipped to the frontend.

## Checks available today

| check | command | notes |
|---|---|---|
| frontend build + typecheck | `npm run build` | `tsc && vite build`, offline |
| frontend tests | `npm run test` | vitest, 32 tests, fast |
| backend tests | `cd server && pytest` | ~520 tests in `server/tests/`, CPU-only, no network |
| backend scorecard | `python server/batch_eval.py plans` | runs the parser on the sample PDFs in `plans/` against `plans/ground_truth.json` |

A standalone typecheck is already implicit in `npm run build` (`tsc && vite
build`); no script was added here, since this pass is scoped to read-only
review of this particular repo (no edits to existing files).

**Missing:** no linter is configured for either the frontend (no ESLint
config in the repo) or the backend (no flake8/ruff config). Adding one wasn't
done here since it would mean installing a new dependency, which is out of
scope for this pass — flag it to the team if they want one.

## Security findings

- **No secrets found committed in the current code.** Only `.env.example`
  files exist (root: just `VITE_API_BASE`/`VITE_PITCHED_ROOF`; `server/`: a
  longer template) — both are examples with blank values, not real keys. Git
  history was not scanned in this pass (read-only, time-boxed); worth a
  proper `git log -p | grep` sweep separately if that matters to you.
- **No live keys in client code.** The frontend only reads `VITE_API_BASE`
  (just a URL) and `VITE_PITCHED_ROOF` (a flag) — no API keys anywhere in
  `src/`.
- **No service-role key in the browser.** `SUPABASE_KEY` is read only in
  `server/db.py`, `server/corpus_export.py` and `server/main.py` — all
  backend-only Python, never bundled into the frontend. The repo's own
  `.env.example` even comments "service role key (server-side only, NEVER in
  the frontend)," so the team is already aware.
- **RLS:** not applicable here — Supabase is used purely as an optional
  parse-log sink, not for app auth or multi-tenant data, and it's off by
  default.
- **Dependency risk:** `npm audit` / `pip-audit` were **not run** (both would
  need network access, which this pass avoided per instructions). Worth
  running once online, especially given `torch`, `opencv-python-headless` and
  `trimesh` are large, fast-moving packages.
- One **config** item worth a human look, not a secret leak: `REVIEW_TOKEN`
  gates a `/review` dashboard that shows "customer parse data" per the
  backend's own comment — make sure that's set to something real (or left
  unset, which restricts it to localhost) before any public deploy.

## Compute

- **Core parsing (the product's main job) is light enough for a MacBook
  Air** — it's pure CPU vector geometry (OpenCV/Shapely), no training, no GPU.
- **Heavy and explicitly GPU-only:** the photoreal render feature (SDXL +
  ControlNet). The repo's own `docs/DEPLOY-GPU.md` describes this as running
  on a separate GPU PC, reached from the public site over a tunnel — it is
  not expected to run on the Mac at all, and that's by design, not a gap.
- The optional ML fallback readers (CubiCasa/TF2) need their own downloaded
  model weights (hundreds of MB to a few GB) and are CPU-capable but slow;
  they're a fallback path for photo/scan input, not the main CAD-PDF flow.

## Top 5 risks before letting agents build on this repo

1. **The parser's working notes (`CLAUDE.md`) are the real spec, and they are
   huge and highly specific** — months of measured decisions, named
   constants, and a long list of fixes that were tried and *reverted*. An
   agent that edits `server/pdf_vector.py` without reading them first will
   very likely re-break something already fixed and re-learn a lesson that's
   already written down.
2. **The "golden corpus" is a deliberate ratchet, not a normal test suite.**
   `test_corpus_golden.py` / `test_area_compare.py` pin exact numbers from
   real sample plans. The team's own rule: a moved number must be explained
   in feet or rupees, never silently re-baselined to make a test pass. An
   agent that "fixes" a failing golden test by adjusting the expected value
   is doing the one thing explicitly forbidden.
3. **Supabase logging is off by default and should stay that way for
   automated runs.** It's easy to accidentally turn on by setting
   `SUPABASE_URL`/`SUPABASE_KEY` in a shared env file — don't, unless it's a
   disposable test project.
4. **No linter exists**, so style/quality regressions won't be caught
   automatically — code review (human or agent) needs to cover that gap.
5. **The backend install is heavy** (torch + OpenCV + trimesh, multi-GB).
   Budget for that before assuming a quick CI turnaround; it's also the
   reason the ML/render paths were explicitly left untested in this pass.
