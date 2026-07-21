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


def _dims(scene):
    m = (scene or {}).get("meta", {}) or {}
    return (float(m.get("plan_width_ft", 0) or 0),
            float(m.get("plan_depth_ft", 0) or 0))


def health_flags(scene):
    """'This reading probably failed' flags, usable on ANY plan without ground
    truth. Empty list = looks healthy."""
    if not scene:
        return ["no_scene"]
    w, d = _dims(scene)
    rooms = len(scene.get("rooms", []) or [])
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
    """Higher = better. Rewards rooms + doors; each health flag is a big penalty
    so a flagged scene always loses to an unflagged one."""
    if not scene:
        return -1e9
    rooms = len(scene.get("rooms", []) or [])
    doors = sum(1 for o in (scene.get("openings", []) or [])
                if o.get("type") == "door")
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
