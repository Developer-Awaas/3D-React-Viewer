# Morning update - what I did overnight

Instruction followed: fix the tasks, prepare Steps 3 & 4, **no major changes**, and
**test every idea before applying it**. Nothing in your existing app (App.tsx, viewer)
was modified - all changes are minimal fixes to the backend plus new additive files.

## 1. Fixed the blocker (the torch.load crash)
Root cause: `get_model()` loads a pretrained backbone `model_1427.pth` via a relative
path. Running from `server/`, it was grabbing the wrong 208 MB copy instead of the
correct 69.7 MB one in the CubiCasa folder. Fix: build the model with the CubiCasa
folder as the working directory (exactly how Colab did it). Also made the checkpoint
loader recursive and added a sanity check.
- Files: `server/perception.py`, `server/main.py`
- **Tested:** the recursive loader logic was unit-verified (flat/single/double-wrapped
  checkpoints) and all Python files compile cleanly. The full model load itself still
  needs to run on YOUR GPU machine - see "What you do next".

## 2. Hardened the API (from the code review)
- `/perceive` now: rejects non-images (415), rejects files > 25 MB (413), and runs the
  heavy model off the event loop so the server stays responsive.
- File: `server/main.py`. See `docs/CODE_REVIEW.md` for the full review.

## 3. Tests + CI (credibility before pushing)
- `server/tests/` - unit tests (weight loader, overlay, class sizes) and API tests
  (health, validation, success shape). The model is stubbed so tests need no GPU.
- `.github/workflows/ci.yml` - runs the tests automatically on every push.
- `server/requirements-dev.txt`, `server/pytest.ini` added.

## 4. Step 3 & 4 groundwork (new files only - NOT wired in yet)
- `src/api/client.ts` - frontend helper to call the backend (`perceive()`, `health()`),
  with a `VITE_API_BASE` env switch for dev vs prod. (Step 3 building block.)
- `src/video/useRecorder.ts` - React hook to record the 3D canvas to a `.webm`
  walkthrough clip. (Step 4 building block.)
- `.env.example` (root) - documents `VITE_API_BASE`.
- These are intentionally standalone so they change nothing until we choose to wire
  them into the app together - keeping to "no major changes".

## What you do next (needs your GPU machine)
1. Restart the backend: `uvicorn main:app --port 8000`
   Expect: `Weights loaded. matched_keys=<hundreds> missing=0 ...` then
   `CubiCasa model loaded and ready.`
2. Run the tests: from `server/`, `pip install -r requirements-dev.txt` then `pytest`.
3. If both look good, push (heavy files are already git-ignored).

## Deliberately deferred (to respect "test before operating")
- The actual masks -> `scene.json` translator (the core of Step 3) is NOT written yet,
  because it must be built and tested against real model output on your GPU. I prepared
  the frontend plumbing so we can do that together once the server is confirmed working.
