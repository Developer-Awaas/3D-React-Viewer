"""Streamlined analysis pipeline — one coherent, observable pass over a parsed
scene that EXTRACTS VALUE and SCORES it, so a team can manage/triage/improve.

`analyze(scene)` runs the value-extraction stages (health, envelope, rooms,
openings, furniture, area statement) and returns ONE structured block plus a
0-100 quality score and a `needs_review` flag. Attach it to the scene response
and log it (Supabase) — that single object is what a dashboard / reviewer reads.

Pure (no I/O), so it's fully unit-tested and safe to run on every parse.
"""
from collections import Counter


def _quality_score(scene, flags):
    """0-100 confidence that this reading is good. Starts at 100, subtracts for
    each health problem and weak signal, so plans that need attention rank low."""
    meta = scene.get("meta", {}) or {}
    score = 100
    score -= 25 * len(flags)                         # each health flag is serious
    if meta.get("scale", {}).get("source") in ("assumed_width", None):
        score -= 15                                  # scale is a guess
    rooms = scene.get("rooms", []) or []
    if not rooms:
        score -= 15
    typed = sum(1 for r in rooms if r.get("type"))
    if rooms and typed == 0:
        score -= 10                                  # rooms found but none labelled
    doors = sum(1 for o in (scene.get("openings", []) or []) if o.get("type") == "door")
    if doors == 0:
        score -= 10
    return max(0, min(100, score))


def analyze(scene, loading_factor=1.30):
    """Scene dict -> one structured analysis block (value extracted + scored)."""
    import area_statement
    import plan_health

    meta = scene.get("meta", {}) or {}
    rooms = scene.get("rooms", []) or []
    ops = scene.get("openings", []) or []
    flags = plan_health.health_flags(scene)
    types = Counter(r.get("type") for r in rooms if r.get("type"))
    area = area_statement.compute_area_statement(scene, loading_factor)

    return {
        "reader": meta.get("reader"),
        "quality_score": _quality_score(scene, flags),
        "needs_review": bool(flags),
        "health": {"ok": not flags, "flags": flags},
        "envelope_ft": [round(meta.get("plan_width_ft", 0) or 0, 1),
                        round(meta.get("plan_depth_ft", 0) or 0, 1)],
        "scale": meta.get("scale", {}),
        "rooms": {"count": len(rooms), "typed": dict(types)},
        "openings": {
            "doors": sum(1 for o in ops if o.get("type") == "door"),
            "windows": sum(1 for o in ops if o.get("type") == "window"),
        },
        "furniture": len(scene.get("furniture", []) or []),
        "area": {
            "carpet_sqft": area["carpet_area"]["sqft"],
            "built_up_sqft": area["built_up_area"]["sqft"],
            "super_built_up_sqft": area["super_built_up_area"]["sqft"],
            "efficiency_pct": area["efficiency_pct"],
        },
        "warnings": meta.get("warnings", []),
    }
