# Code Review - Perception Backend (server/)

Reviewed before first push. Scope: `server/` (main.py, perception.py) + tests.

## Summary
The service is small, single-purpose, and mirrors the validated Colab inference.
Loads the model once at startup, auto-detects GPU/CPU, and is memory-safe. Below are
the findings and what was fixed in this pass.

## Fixed in this pass
| # | Severity | Finding | Fix |
|---|----------|---------|-----|
| 1 | High | `get_model()` loaded the wrong `model_1427.pth` (relative path resolved from `server/`, picking a 208 MB stray copy instead of the 69.7 MB backbone) -> startup crash | `load_model()` now `chdir`s into the CubiCasa repo around `get_model()`, then restores cwd; paths made absolute |
| 2 | Medium | Checkpoint is multiply-wrapped; single `["model_state"]` extraction failed | Recursive `_extract_weights()` digs to the real tensor dict (unit-tested) |
| 3 | Medium | Heavy inference ran on the async event loop, blocking the server | `/perceive` now runs `perception.detect` via `run_in_threadpool` |
| 4 | Medium | No input validation on upload | Reject non-images (415) and files > 25 MB (413) |
| 5 | Low | `strict=False` could silently load a mismatched model | Raise if `matched_keys == 0` |

## Recommendations (not blocking - noted for later)
- **Thread-safety of `load_model()`**: the global `_MODEL` is set without a lock. In
  practice the model is warmed at startup so requests never race, but add a
  `threading.Lock` if you ever remove the startup warm-up.
- **Error detail leakage**: `/perceive` returns the raw exception string. Fine for dev;
  sanitize the message in production.
- **Pin dependency versions** in `requirements.txt` for reproducible builds.
- **Config**: keep `CUBICASA_REPO`/`CUBICASA_WEIGHTS` in `.env` (already done); make sure
  the stray top-level `server/floortrans/` copy is removed later to avoid confusion.

## Tests added
- `tests/test_perception.py` - recursive weight extraction (flat/single/double/none),
  overlay PNG validity, class-list vs split sizes.
- `tests/test_api.py` - `/health`, empty-file 400, non-image 415, success JSON shape
  (model stubbed, so no GPU/weights needed).
- `.github/workflows/ci.yml` - runs the tests on every push/PR (installs CPU torch).
