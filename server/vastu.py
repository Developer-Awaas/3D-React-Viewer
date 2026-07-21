"""Vastu analysis — score room placement against classical Vastu Shastra zones.

Pure geometry over the parsed scene: each room's position (relative to the plan
centre, rotated by the plan's North) falls in one of 9 zones (N, NE, E, SE, S,
SW, W, NW, CENTER/Brahmasthan). Each room type has ideal / acceptable / avoid
zones from standard residential Vastu practice:

  kitchen   ideal SE (Agneya), ok NW            avoid NE
  bedroom   ideal SW, ok S/W                    avoid NE
  bathroom  ideal NW, ok W/S                    avoid NE + CENTER
  pooja     ideal NE, ok E/N                    avoid S/SW
  living    ideal NE/N/E, ok CENTER
  dining    ideal W, ok E/S
  study     ideal W/SW, ok N/E
  stairs    ideal SW/S/W                        avoid NE + CENTER
  store     ideal SW/W
  parking/balcony/lobby: neutral (not scored)

`north_deg` = compass North's direction on the sheet, degrees clockwise from
"up" (0 = top of the plan is North, 90 = right edge is North, ...). Drawings
usually put North up, so 0 is the default; the user can correct it.

This is guidance, not doctrine — output carries a disclaimer. Pure + tested.
"""
import math

_IDEAL, _OK, _AVOID = 1.0, 0.6, 0.0
_NEUTRAL = {"parking", "balcony", "lobby", None}

_RULES = {
    "kitchen":  ({"SE"}, {"NW"}, {"NE"}),
    "bedroom":  ({"SW"}, {"S", "W"}, {"NE"}),
    "bathroom": ({"NW"}, {"W", "S"}, {"NE", "CENTER"}),
    "pooja":    ({"NE"}, {"E", "N"}, {"S", "SW"}),
    "living":   ({"NE", "N", "E"}, {"CENTER"}, set()),
    "dining":   ({"W"}, {"E", "S"}, set()),
    "study":    ({"W", "SW"}, {"N", "E"}, set()),
    "stairs":   ({"SW", "S", "W"}, set(), {"NE", "CENTER"}),
    "store":    ({"SW", "W"}, set(), set()),
}

_SECTORS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def zone_of(x, y, w, d, north_deg=0.0, center_frac=0.33):
    """Which Vastu zone the point (x, y) falls in, on a plan of w x d ft with
    origin bottom-left. north_deg rotates the compass (0 = +y is North)."""
    cx, cy = w / 2.0, d / 2.0
    dx, dy = x - cx, y - cy
    if abs(dx) <= (w * center_frac / 2) and abs(dy) <= (d * center_frac / 2):
        return "CENTER"
    ang = math.degrees(math.atan2(dx, dy))       # 0 = +y ("up"), clockwise +
    ang = (ang - north_deg) % 360                 # rotate so 0 = true North
    idx = int(((ang + 22.5) % 360) // 45)
    return _SECTORS[idx]


def analyze(scene, north_deg=0.0):
    """Scene -> Vastu report: per-room zone + verdict and an overall 0-100
    score. Rooms without a type (or neutral types) aren't scored."""
    meta = scene.get("meta", {}) or {}
    w = float(meta.get("plan_width_ft", 0) or 0)
    d = float(meta.get("plan_depth_ft", 0) or 0)
    rooms = scene.get("rooms", []) or []
    verdicts, scores = [], []
    for r in rooms:
        rtype = r.get("type")
        if rtype in _NEUTRAL or rtype not in _RULES or w <= 0 or d <= 0:
            continue
        z = zone_of(float(r.get("x", 0)), float(r.get("y", 0)), w, d, north_deg)
        ideal, ok, avoid = _RULES[rtype]
        if z in ideal:
            s, verdict = _IDEAL, "ideal"
        elif z in ok:
            s, verdict = _OK, "acceptable"
        elif z in avoid:
            s, verdict = _AVOID, "avoid"
        else:
            s, verdict = 0.4, "neutral"
        scores.append(s)
        rec = None
        if verdict == "avoid":
            rec = f"{rtype} in {z} is discouraged; ideal zone: {'/'.join(sorted(ideal))}"
        verdicts.append({"room": r.get("id"), "type": rtype, "zone": z,
                         "verdict": verdict, **({"advice": rec} if rec else {})})
    score = round(100 * sum(scores) / len(scores), 1) if scores else None
    return {
        "north_deg": north_deg,
        "score": score,
        "rooms_scored": len(scores),
        "verdicts": verdicts,
        "disclaimer": ("Indicative Vastu guidance from detected room positions; "
                       "verify North direction and consult a Vastu practitioner "
                       "for decisions."),
    }
