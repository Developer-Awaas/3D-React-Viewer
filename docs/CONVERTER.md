# Building a 2D→3D floor-plan converter — fully local, no API

Everything here runs on your own machine: OpenCV (Python) for reading the image and
React Three Fiber for the 3D. No paid service, no cloud model.

## The core idea
A 3D engine can't "see" a picture. So the whole job is: turn a wall image into a
list of wall lines in metres, then extrude each line into a box. Two halves:

  A. EXTRACT  (image -> wall segments)   -> tools/auto_plan.py  (OpenCV)
  B. RENDER   (segments -> 3D walls)     -> the React app (modes: Floor Plan / Auto)

## A. EXTRACT — the OpenCV pipeline (tools/auto_plan.py)
1. Read image, convert to grayscale.
2. Threshold the DARK pixels — walls are thick black lines  ->  binary mask.
3. HoughLinesP — find straight segments in the mask.
4. Snap each segment to horizontal/vertical; merge collinear/overlapping pieces
   into one wall per line (kills the duplicates from thick strokes).
5. Scale: metres-per-pixel = realBuildingWidth / imagePixelWidth.
6. Convert endpoints to metres, centred on the image middle (origin).
7. Write public/auto_plan.json + tools/auto_preview.png (red overlay to inspect).

Run it:
    python tools/auto_plan.py public/plan.png 12.4
        (args: image path, real building width in metres)

## B. RENDER — segments to 3D (already in the app)
For each [x1,z1,x2,z2]:
    length = distance(p1,p2)
    centre = midpoint(p1,p2)
    angle  = atan2(dz,dx)
    -> a box of [length, WALL_HEIGHT, thickness] at centre, rotated -angle about Y.
Open the app, pick "Auto (CV)" to see auto_plan.json rendered in 3D over the image.

## Status: implemented in tools/auto_plan.py
Steps 1-3 below are now built in: small-blob cleaning (removes text/scale bar/icons),
parallel-edge clustering (a thick wall = ONE line), gap-aware merge (keeps doorways),
length filter, and 0.1 m grid snapping. On the clean sample it now finds exactly the
7 real walls with the front doorway preserved. Remaining ideas (openings as door frames,
floors/ceilings, ML for stylised plans) are still open.

## What to MODIFY to make extraction better (the real work)
The naive pipeline grabs text, furniture and scale bars as "walls". Improvements,
all still local:

1. CLEAN THE INPUT (biggest win, least code)
   - Feed a plain line drawing: black walls on white, no furniture/labels/colour.
   - Or pre-clean: keep only near-black pixels AND drop tiny blobs:
       mask = (gray < 80)
       remove components smaller than N pixels (cv2.connectedComponentsWithStats)
     This deletes text and small icons, keeping long wall strokes.

2. ISOLATE WALLS BY THICKNESS / LENGTH
   - Real walls are long and thick. After Hough, drop segments shorter than, say,
     0.5 m. Raise minLineLength. Furniture edges are short -> filtered out.

3. SNAP + CLOSE THE GEOMETRY
   - Snap endpoints to a grid (e.g. nearest 0.1 m) so walls meet cleanly.
   - Join endpoints that are within a few cm so rooms form closed loops.

4. DERIVE OPENINGS (doors/windows)
   - A gap in an otherwise straight wall run = a doorway. Detect gaps and either
     leave them or place a door frame.

5. ADD FLOORS / CEILINGS
   - Once rooms are closed loops, fill each loop with a floor polygon (THREE.Shape
     + ShapeGeometry) for a solid room, not just walls.

6. WANT REAL HANDS-OFF ON MESSY PLANS?  (still local, heavier)
   - Train / run a small segmentation model (U-Net style) that outputs a wall mask,
     ignoring furniture and text. Runs locally with onnxruntime / tensorflow.js —
     no external API. This is the only thing that reliably handles stylised plans.

## The honest tiering
- Clean CAD line plans          -> steps 1-3 above, hands-off today.
- Lightly stylised plans        -> steps 1-5 + manual fixes via the Trace tool.
- Heavily furnished/colour plans -> step 6 (a local ML model) or human tracing.
