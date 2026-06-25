# How to commit (run these on YOUR Windows machine)

Git can't run from inside Cowork's sandbox because the OneDrive mount blocks the
rename/delete operations git needs. On your own machine it works normally.

## One-time cleanup
A broken `.git` folder got left behind. Delete it first, then start fresh.

**Option A — File Explorer:** turn on "Hidden items" (View menu), delete the `.git`
folder inside `3D React Viewer`.

**Option B — PowerShell** (open it in the project folder):
```powershell
cd "$env:USERPROFILE\OneDrive\Desktop\3D React Viewer"
Remove-Item -Recurse -Force .git
```

## First commit
```powershell
git init
git config user.email "awaas.ai.dev@gmail.com"
git config user.name "Dev_Awaas"
git add .
git commit -m "step 1: scaffold Vite+React+TS R3F viewer with OrbitControls + cube; add docs"
```

(If `git` isn't recognized, install Git for Windows from https://git-scm.com/download/win
and reopen the terminal.)

## After every future step
```powershell
git add .
git commit -m "step 2: room geometry"   # change the message per step
```
Small, frequent commits with clear messages — that's what the brief asks for.

## Optional: push to your own GitHub later
```powershell
git remote add origin https://github.com/<your-username>/drishti-sandbox.git
git branch -M main
git push -u origin main
```
