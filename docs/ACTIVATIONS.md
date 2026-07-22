# F6 — User-Side Activations Checklist

Everything the code already supports but that needs YOUR machine or YOUR
accounts to switch on. Work top to bottom; each item says how to verify.

## 1. Model downloads (in progress today)
- [ ] **Seg ControlNet (5 GB)** — finishes on its own during renders. Verify:
      restart the backend, run a render, log should say seg conditioning is on;
      renders get crisper wall/floor boundaries. No config needed (auto-enables).
- [ ] **SVD video model (4.51 GB)** — wait for the download to complete, then
      press **Animate** again. The earlier 504 was just a timeout while the
      model was still downloading.

## 2. Git push (do today)
- [ ] From `D:\3D React Viewer`: `git add -A` → `git commit -m "style-3D, RERA fallback, contact + signature"` → `git push`
      Verify: the commit shows on GitHub.

## 3. Supabase (unlocks logging dashboard + corpus growth)
- [ ] Create a free project at supabase.com → Project Settings → API.
- [ ] Put in `server\.env`:
      `SUPABASE_URL=https://<your-project>.supabase.co`
      `SUPABASE_KEY=<service_role key>`
      optional: `STORE_UPLOADS=1` (archives every uploaded plan for the corpus)
- [ ] Restart backend. Verify: upload a plan, then open `http://localhost:8000/review`
      — the parse appears in the dashboard.

## 4. Tesseract OCR (labels rooms on scanned plans)
- [ ] Install: https://github.com/UB-Mannheim/tesseract/wiki (Windows installer,
      keep default path). Then `pip install pytesseract` in the venv.
- [ ] Restart backend. Verify: a scanned/photo plan now shows room names.

## 5. DWG support (optional)
- [ ] Install ODA File Converter (free) and set `DWG_CONVERTER` in `server\.env`
      to its exe path. Verify: upload a `.dwg` directly.

## 6. Go live (when you're ready — full steps in docs/DEPLOY-GPU.md)
- [ ] Cloudflare Tunnel on your machine exposes the backend.
- [ ] Vercel hosts the frontend (`npm run build` output).
- [ ] Set the tunnel URL as the API base + CORS origin.

## Licensing reminders before anything commercial
- CubiCasa reader: **CC BY-NC — demo only**, must be off/replaced in a paid product.
- TF2DeepFloorplan: GPL-3.0 — SaaS use likely fine; confirm with a lawyer.
- SVD (video): Stability Community License — free below revenue cap; check terms.
