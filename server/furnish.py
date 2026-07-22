"""Room typing + conservative auto-staging of furniture.

Two pure, unit-tested pieces used by the parser:
  * classify_room_type(text)  -> a room type from its label text (Indian plans
    almost always label rooms: "Bed Room", "C. Bath", "Kitchen", "Pooja").
  * stage_room(type, x0,y0,x1,y1) -> a few sensible furniture footprints placed
    INSIDE the room, used only when the room has little/no drawn furniture.

Both are pure (no I/O, no drawing) so every case is testable. Staging is
deliberately conservative: 1-2 key pieces per room, always fully inside the
room box, and nothing at all for spaces that should stay empty (parking,
balcony, stairs).
"""

# order matters: more specific keywords first (bath before generic, etc.)
_ROOM_KEYWORDS = (
    ("bathroom", ("bath", "toilet", "w.c", "wc", "washroom", "powder", "latrine")),
    ("kitchen",  ("kitchen", "kitch", "pantry")),
    ("bedroom",  ("bed", "master", "guest room", "kids", "child")),
    ("dining",   ("dining", "dinning")),
    ("living",   ("living", "drawing", "hall", "lounge", "family")),
    ("pooja",    ("pooja", "puja", "prayer", "mandir", "temple")),
    ("study",    ("study", "office", "work room")),
    ("parking",  ("parking", "garage", "car park", "porch")),
    ("balcony",  ("balcony", "verandah", "veranda", "terrace", "sit out",
                  "sitout", "ots", "open to sky", "deck")),
    ("store",    ("store", "storage", "utility", "wash area", "dry")),
    ("stairs",   ("stair", "staircase", "steps", "lift", "elevator")),
    ("lobby",    ("lobby", "foyer", "passage", "corridor", "entrance", "entry")),
)


def classify_room_type(text):
    """Room type from label text, or None if no keyword matches."""
    t = (text or "").lower()
    for rtype, kws in _ROOM_KEYWORDS:
        if any(k in t for k in kws):
            return rtype
    return None


# rooms that are furnished when empty; the rest (parking/balcony/stairs/lobby/
# store/pooja) stay empty on purpose
STAGEABLE = {"bedroom", "living", "dining", "kitchen", "bathroom", "study"}

# plausible carpet-area band (sqft) per type — a "bathroom" of 454 sqft is a
# mis-label (usually a merged/poorly-sealed region), so we don't stage it
_AREA_SQFT = {
    "bathroom": (12, 90),
    "bedroom": (55, 340),
    "kitchen": (22, 240),
    "living": (75, 800),
    "dining": (45, 500),
    "study": (28, 240),
}


def plausible_area(rtype, area_sqft):
    """Is this room's area sensible for the claimed type? Guards against staging
    furniture into a mis-typed / merged region."""
    lo, hi = _AREA_SQFT.get(rtype, (0.0, 1e18))
    return lo <= float(area_sqft or 0) <= hi


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def stage_room(rtype, x0, y0, x1, y1, margin=0.6):
    """Return default furniture [{type,x,y,w,d}] (feet, origin bottom-left) for a
    room of the given type, placed inside [x0,y0,x1,y1]. Empty if the room is too
    small or should not be furnished."""
    w, d = x1 - x0, y1 - y0
    if rtype not in STAGEABLE or w < 3.2 or d < 3.2:
        return []
    ix0, iy0, ix1, iy1 = x0 + margin, y0 + margin, x1 - margin, y1 - margin
    iw, idp = ix1 - ix0, iy1 - iy0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    out = []

    def add(t, fw, fd, fx, fy):
        fw = _clamp(fw, 0.5, iw)
        fd = _clamp(fd, 0.5, idp)
        fx = _clamp(fx, ix0, ix1 - fw)
        fy = _clamp(fy, iy0, iy1 - fd)
        out.append({"type": t, "x": round(fx, 2), "y": round(fy, 2),
                    "w": round(fw, 2), "d": round(fd, 2), "staged": True})

    if rtype == "bedroom":
        bw, bd = min(5.0, iw), min(6.5, idp)          # double bed against a wall
        add("bed", bw, bd, cx - bw / 2, iy0)
    elif rtype == "living":
        sw = min(6.0, iw)
        add("sofa", sw, 2.2, cx - sw / 2, iy0)         # sofa along one wall
    elif rtype == "dining":
        add("table", min(4.0, iw), min(3.0, idp), cx - 2.0, cy - 1.5)
    elif rtype == "kitchen":
        add("counter", iw, 2.0, ix0, iy0)              # counter along the wall
    elif rtype == "bathroom":
        add("commode", 1.5, 2.0, ix0, iy0)
        if iw > 3.5:
            add("basin", 1.2, 1.0, ix1 - 1.2, iy0)
    elif rtype == "study":
        add("table", min(3.5, iw), 2.0, ix0, iy0)
    return out
