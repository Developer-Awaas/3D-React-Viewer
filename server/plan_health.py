"""Decision logic for the vector-first / ML-fallback cascade — designed so the
cascade can only make output BETTER, never worse.

Rules:
  * A HEALTHY vector result (passes the checks) is returned as-is; the ML model
    never even runs, so a good reading is never degraded.
  * Only when the vector result is unhealthy (tiny envelope / no rooms / no
    doors / parse failed) does the ML reader run, and it wins ONLY if it scores
    strictly higher. Ties go to vector (it's exact on clean CAD).

Pure functions, fully unit-tested.
"""


# E6 plausibility guards: a reader that HALLUCINATES tiny shafts as rooms must
# not win best-of by sheer count. Rooms below the floor don't count toward
# health or score; the room reward is capped at a count real plans never
# exceed. A MISSING area is treated as plausible (the vector path always has
# areas; ML rooms may not), so every pre-existing decision is unchanged.
MIN_ROOM_SQFT = 8.0
ROOM_SCORE_CAP = 25
DOOR_SCORE_CAP = 40


def _dims(scene):
    m = (scene or {}).get("meta", {}) or {}
    return (float(m.get("plan_width_ft", 0) or 0),
            float(m.get("plan_depth_ft", 0) or 0))


def plausible_room_count(scene):
    """Rooms that aren't implausibly tiny (junk pockets/shafts). A room with no
    area counts as plausible."""
    n = 0
    for r in (scene.get("rooms", []) or []):
        a = r.get("area_sqft")
        if a is None or float(a or 0) >= MIN_ROOM_SQFT:
            n += 1
    return n


def health_flags(scene):
    """'This reading probably failed' flags, usable on ANY plan without ground
    truth. Empty list = looks healthy."""
    if not scene:
        return ["no_scene"]
    w, d = _dims(scene)
    rooms = plausible_room_count(scene)
    doors = sum(1 for o in (scene.get("openings", []) or [])
                if o.get("type") == "door")
    flags = []
    if min(w, d) < 12:
        flags.append("envelope_tiny")
    if max(w, d) > 600:
        flags.append("envelope_huge")
    if rooms == 0:
        flags.append("no_rooms")
    if doors == 0:
        flags.append("no_doors")
    return flags


def is_healthy(scene):
    return scene is not None and not health_flags(scene)


def score_scene(scene):
    """Higher = better. Rewards PLAUSIBLE rooms + doors (both capped so a noisy
    over-detecting reader can't win best-of by inventing count); each health
    flag is a big penalty so a flagged scene always loses to an unflagged one."""
    if not scene:
        return -1e9
    rooms = min(plausible_room_count(scene), ROOM_SCORE_CAP)
    doors = min(sum(1 for o in (scene.get("openings", []) or [])
                    if o.get("type") == "door"), DOOR_SCORE_CAP)
    return rooms * 2 + doors - 100 * len(health_flags(scene))


def better_scene(vector_scene, ml_scene):
    """Pick the better reading. ML wins ONLY if it scores strictly higher than
    vector; ties and near-misses keep vector (exact on clean CAD). Either may be
    None."""
    if ml_scene is None:
        return vector_scene
    if vector_scene is None:
        return ml_scene
    return ml_scene if score_scene(ml_scene) > score_scene(vector_scene) else vector_scene
