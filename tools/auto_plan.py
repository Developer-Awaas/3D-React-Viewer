#!/usr/bin/env python3
"""
Auto-detect walls from a 2D floor-plan image -> plan.json (no clicking, no API).

Local OpenCV pipeline:
  1. grayscale + threshold dark pixels (walls are thick black lines)
  2. CLEAN: drop small connected blobs -> removes text, scale bars, icons
  3. HoughLinesP -> straight segments
  4. cluster parallel edges (so a thick wall = ONE line) and merge collinear pieces,
     but keep gaps wider than a door -> openings are preserved
  5. length filter + snap endpoints to a 0.1 m grid; scale px -> metres (origin centre)

Usage: python tools/auto_plan.py <image> <building_width_metres>
"""
import sys, json, cv2, numpy as np

img_path = sys.argv[1]; width_m = float(sys.argv[2])
img  = cv2.imread(img_path)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
H, W = gray.shape
mpp  = width_m / W

# 1) mask
mask = (gray < 80).astype(np.uint8)

# 2) clean: keep large blobs only
n, lbl, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
min_area = max(800, int(0.0015 * W * H))
clean = np.zeros_like(mask)
for i in range(1, n):
    if stats[i, cv2.CC_STAT_AREA] >= min_area:
        clean[lbl == i] = 255

# 3) segments
lines = cv2.HoughLinesP(clean, 1, np.pi/180, threshold=80,
                        minLineLength=int(0.05*W), maxLineGap=12)
lines = [] if lines is None else [l[0] for l in lines]

# split into horizontal / vertical (perp = the fixed coordinate, a/b = the span)
H_segs, V_segs = [], []   # (perp, a, b)
for x1, y1, x2, y2 in lines:
    if abs(x2-x1) >= abs(y2-y1):
        a, b = sorted((x1, x2)); H_segs.append(((y1+y2)/2, a, b))
    else:
        a, b = sorted((y1, y2)); V_segs.append(((x1+x2)/2, a, b))

PERP_SNAP = max(8, int(1.4 * 10))        # px: edges this close = same wall (thick stroke)
DOOR_GAP  = max(12, int(0.4 / mpp))      # px: gaps wider than ~0.4 m are kept as openings
MIN_LEN   = int(0.5 / mpp)               # px: ignore runs shorter than 0.5 m

def collapse(segs):
    """Cluster by perpendicular position, then merge spans but keep door-sized gaps."""
    segs = sorted(segs, key=lambda s: s[0])
    clusters, runs = [], []
    for perp, a, b in segs:
        if clusters and perp - clusters[-1][-1][0] <= PERP_SNAP:
            clusters[-1].append((perp, a, b))
        else:
            clusters.append([(perp, a, b)])
    for cl in clusters:
        perp = sum(p for p, _, _ in cl) / len(cl)
        intervals = sorted((a, b) for _, a, b in cl)
        cur_a, cur_b = intervals[0]
        for a, b in intervals[1:]:
            if a <= cur_b + DOOR_GAP:                 # overlap / small gap -> same wall
                cur_b = max(cur_b, b)
            else:                                     # big gap -> opening; emit + restart
                runs.append((perp, cur_a, cur_b)); cur_a, cur_b = a, b
        runs.append((perp, cur_a, cur_b))
    return [(perp, a, b) for perp, a, b in runs if (b - a) >= MIN_LEN]

GRID = 0.1
def to_m(px, py):
    mx = round(((px - W/2)*mpp) / GRID) * GRID
    mz = round(((py - H/2)*mpp) / GRID) * GRID
    return [round(mx, 2), round(mz, 2)]

walls = []
for y, x0, x1 in collapse(H_segs): walls.append([*to_m(x0, y), *to_m(x1, y)])
for x, y0, y1 in collapse(V_segs): walls.append([*to_m(x, y0), *to_m(x, y1)])

out = {"metresWide": round(width_m,3), "metresDeep": round(H*mpp,3),
       "ceilingHeight": 2.5, "wallThickness": 0.2, "walls": walls}
json.dump(out, open("public/auto_plan.json","w"), indent=2)

prev = img.copy()
for wx1,wz1,wx2,wz2 in walls:
    p1=(int(wx1/mpp+W/2),int(wz1/mpp+H/2)); p2=(int(wx2/mpp+W/2),int(wz2/mpp+H/2))
    cv2.line(prev,p1,p2,(0,0,255),3)
cv2.imwrite("tools/auto_preview.png", prev)
print(f"detected {len(walls)} walls -> public/auto_plan.json  (preview: tools/auto_preview.png)")
