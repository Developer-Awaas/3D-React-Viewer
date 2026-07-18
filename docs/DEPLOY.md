# Deploying Drishti v1 (≈20 minutes)

Two pieces: the **API** (FastAPI, Docker, vector-only) on Render, and the
**app** (Vite/React) on Vercel. The bundled sample building works even
before the API is up, so deploy the frontend first if you like.

## 0. Push the repo to GitHub (one time)

```bash
cd "D:\3D React Viewer"
git add -A
git commit -m "v1: engine + visual pass + deploy pack"
git push origin main
```

`plans/` (client drawings) and `server/venv` are gitignored — verify with
`git status` that no PDF from plans/ is staged.

## 1. API on Render

1. https://dashboard.render.com -> **New -> Blueprint** -> pick the repo.
   Render reads `render.yaml` and builds `server/Dockerfile` (slim image,
   **no torch** — photos/scans answer with the friendly beta message; CAD
   PDFs get the full engine).
2. When it's live, note the URL, e.g. `https://drishti-api.onrender.com`.
3. Check `https://<api-url>/health` -> `{"ok": true, ...}`.

(Railway works the same: New Project -> Deploy from repo -> root `server/`.)

## 2. App on Vercel

1. https://vercel.com/new -> import the repo (framework auto-detected via
   `vercel.json`).
2. Project -> Settings -> Environment Variables:
   - `VITE_API_BASE` = `https://drishti-api.onrender.com`  (no trailing slash)
3. Deploy. Note the URL, e.g. `https://drishti.vercel.app`.

## 3. Connect them

Render -> drishti-api -> Environment -> set
`ALLOWED_ORIGINS=https://drishti.vercel.app` (comma-separate to also keep
localhost) -> Save (auto-redeploys). This is CORS — uploads fail without it.

## 4. Smoke test (2 min)

- Open the Vercel URL -> landing loads -> **Open App**.
- **Try a sample** -> the 2BHK appears (proves frontend + bundle).
- Upload a CAD PDF -> model appears (proves API + CORS).
- Upload a JPG photo -> friendly "beta" message, not a crash (proves scope).
- Browser Back returns to the landing.

## Notes

- Free/starter Render instances sleep; first request after idle takes ~30 s.
  The sample button keeps the demo instant regardless.
- To enable the photo/scan beta on a GPU box later: install
  `requirements.txt` (torch) + the CubiCasa repo + weights, and deploy
  `server/` unchanged — `main.py` detects perception automatically.
- Env knobs: `INFER_TIMEOUT_S`, `MAX_CONCURRENT_INFER`, `ALLOWED_ORIGINS`,
  `VITE_API_BASE` (frontend, build-time).
