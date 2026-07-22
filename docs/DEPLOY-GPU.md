# Go-live: Vercel frontend + YOUR GPU backend (tunnel)

The launch architecture you chose: the public website runs on Vercel; the
backend (parser + CubiCasa/TF2 + SDXL photoreal) runs on YOUR GPU PC, exposed
through a secure tunnel. Strangers upload on the site → your GPU does the work.

## 0. Prerequisites
- Repo pushed to GitHub (branch merged to main, or deploy the branch).
- Backend runs locally: `run_backend_gpu.bat` → http://localhost:8000/health ok.
- Windows power settings: disable Sleep (the site dies when the PC sleeps).

## 1. Tunnel — give your PC a public URL (Cloudflare, free)
1. Install: `winget install Cloudflare.cloudflared`
2. Quick start (new URL each run — fine for testing):
   ```
   cloudflared tunnel --url http://localhost:8000
   ```
   It prints `https://<random>.trycloudflare.com` — that's your public API URL.
3. Stable URL (recommended for launch): create a free Cloudflare account, add a
   domain (or use their dashboard "Tunnels" → create tunnel → route a hostname
   like `api.yourdomain.com` → service `http://localhost:8000`). Install the
   connector command it gives you; run it as a service so it survives reboots.

## 2. Frontend — Vercel
1. vercel.com → Add New Project → import the GitHub repo (auto-detects Vite).
2. Environment variable (Project → Settings → Environment Variables):
   ```
   VITE_API_BASE = https://<your-tunnel-url>
   ```
   (No trailing slash. This is baked at BUILD time — changing it later needs a
   redeploy.)
3. Deploy → you get `https://<app>.vercel.app`.

## 3. CORS — let the site call your PC
On the GPU PC, in `server/.env` (or run_backend_gpu.bat):
```
ALLOWED_ORIGINS=https://<app>.vercel.app,http://localhost:5173
```
Restart the backend. (Trailing-slash tolerant, comma-separated.)

## 4. Protection (already built — just confirm)
- Rate limit: RATE_LIMIT_PER_MIN (default 30/client/min) 429s abusers.
- Concurrency: MAX_CONCURRENT_INFER / MAX_CONCURRENT_RENDER = 1 queue jobs.
- Timeouts return clean 504s; uploads capped at 25 MB.

## 5. Smoke test (in order)
1. `https://<tunnel>/health` in a browser → `{"ok": true, ...}`.
2. Open the Vercel site → Try a sample (works even if the API is down).
3. Upload a CAD PDF → 3D + RERA card appear.
4. Walk into a room → Visualize → photoreal render (GPU busy on your PC).
5. `https://<tunnel>/review` → dashboard (needs Supabase keys set).

## 6. Honest operational notes
- Site's heavy features live and die with your PC + internet. For a demo/low
  traffic this is normal early-stage practice; when traffic grows, rent a GPU
  host and change ONE value (VITE_API_BASE or the tunnel target).
- Fallback option: also deploy the slim CPU backend to Render (render.yaml,
  free) and point VITE_API_BASE at it when your PC is off — CAD parsing works,
  photoreal/photo features answer with the friendly beta message.
- Keep STORE_UPLOADS in mind: if on, users' plans are archived to your
  Supabase — say so in a privacy note before public launch.
