# GUIDE — Understanding this project from zero

Written assuming you've never touched React. Read top to bottom once; after that, keep it
open beside the code. The goal (and what Saswat is really testing): **you can explain every
line, not just run it.**

---

## Part 1 — The mental model

### What is React?
React builds a webpage out of **components** — reusable functions that return a description
of "what should be on screen." When data changes, React re-runs the function and updates only
what changed. You write what the screen *should look like* for a given state; React figures
out the DOM updates.

### What is Three.js?
A JavaScript library that draws 3D graphics in the browser using your GPU (via WebGL). You
build a **scene** containing **meshes** (objects), **lights**, and a **camera**, then it
renders frames.

### What is React Three Fiber (R3F)?
Normally Three.js is written with imperative code (`const cube = new THREE.Mesh(...)`,
`scene.add(cube)`). R3F lets you write that **same Three.js as React components** instead:

```jsx
<mesh>
  <boxGeometry args={[1,1,1]} />
  <meshStandardMaterial color="orange" />
</mesh>
```

That JSX is *exactly* equivalent to:
```js
const mesh = new THREE.Mesh(
  new THREE.BoxGeometry(1,1,1),
  new THREE.MeshStandardMaterial({ color: "orange" })
);
scene.add(mesh);
```
**This single equivalence is the most important thing to understand.** Every R3F tag is a
Three.js class; the `args` array is the constructor arguments.

---

## Part 2 — Reading the actual files

### `index.html` — the page shell
A nearly empty HTML page with one `<div id="root">`. React injects the entire app into that
div. The `<script src="/src/main.tsx">` line is the starting gun.

### `src/main.tsx` — the entry point
```tsx
ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
```
Plain English: "Find the root div, and render my `<App>` component inside it." `<StrictMode>`
is a dev-only helper that warns about mistakes — it never ships to users.

### `src/App.tsx` — the scene (the important file)
```tsx
<Canvas shadows camera={{ position: [4, 3, 6], fov: 50 }}>
```
- `<Canvas>` is R3F's root. **Inside it = 3D world. Outside it = normal HTML.** This split
  is why the material-panel buttons (Step 4) will live *outside* the Canvas — they're HTML.
- `camera={{ position: [4,3,6] }}` — where you're viewing from. The three numbers are
  **[x, y, z]**: x = right, y = up, z = toward you. So [4,3,6] = a bit right, a bit up,
  pulled back.
- `fov: 50` — field of view in degrees, like a camera lens. Bigger = wider/more distorted.

```tsx
<mesh position={[0, 0.5, 0]} castShadow>
  <boxGeometry args={[1, 1, 1]} />
  <meshStandardMaterial color="orange" />
</mesh>
```
- A **mesh = shape + surface**. `<boxGeometry>` is the shape; `<meshStandardMaterial>` is how
  it reacts to light (PBR = physically based, looks realistic).
- `args={[1,1,1]}` = width, height, depth → a 1-metre cube. Change these and the cube resizes.
- `position={[0, 0.5, 0]}` — **why 0.5 and not 0?** Three.js positions an object by its
  *center*. The cube is 1 m tall, so its center must sit 0.5 m up for its bottom to rest on
  the floor (y=0). At y=0 it would sink half-underground.
- `castShadow` — this object is allowed to throw a shadow (matters once lighting is real).

```tsx
<OrbitControls makeDefault enableDamping />
```
- From **drei**. Gives mouse/touch camera control: drag = rotate, scroll/pinch = zoom,
  right-drag/two-finger = pan.
- `makeDefault` registers it as *the* active controls, so the Step 5 camera animation can
  grab and steer it. `enableDamping` adds a smooth glide when you let go.

### `src/index.css`
Resets margins and makes html/body/#root fill 100% so the canvas can be truly full-window.

---

## Part 3 — Coordinate cheat-sheet (you'll use this constantly)
```
        y (up)
        |
        |____ x (right)
       /
      z (toward you)
```
- Floor is the **x–z plane** at y=0. "Tall" = the y axis.
- Distances are in **metres** by our convention. A 5x5 m room spans x:[-2.5, 2.5], z:[-2.5, 2.5].

---

## Part 4 — How to explain Step 1 to Saswat (script)
> "I scaffolded a Vite + React + TypeScript app and added react-three-fiber. The `<Canvas>`
> component is the boundary between normal HTML and the 3D scene. Inside it I put one mesh —
> a box geometry with a standard PBR material — plus basic lights and drei's OrbitControls
> for rotate/zoom/pan. Each R3F tag maps directly to a Three.js class, and the `args` array
> is that class's constructor arguments. I positioned the cube at y=0.5 because Three.js
> places objects by their center, so half its height lifts it to rest on the floor."

If you can say that unprompted, you've passed Step 1.

---

## Part 5 — Working efficiently with Claude (and not getting lost)
1. **Start each session by pasting `docs/CONTEXT.md`.** That restores my memory of the project
   instantly — you never re-explain.
2. **Go one step at a time.** Ask for Step N only; read it; make sure you can explain it;
   then ask for Step N+1. The brief is testing understanding, not speed.
3. **When code appears, ask "explain line X"** for anything fuzzy *before* moving on. Cheaper
   than debugging confusion later.
4. **Commit after each step** with a short message (`git commit -m "step 2: room geometry"`).
   Small commits = your progress is legible and easy to roll back.
5. **Keep CONTEXT.md updated** — tick the step checkbox and add a progress-log line. Future-you
   and Saswat both benefit.
6. **If stuck >1 hour, ask Saswat** (the brief says so explicitly). Asking costs nothing.
