"""INJECTION HARNESS — every plausibility check ships only after it catches
what it exists for (Rahul, 2 Sep 2026).

The corpus cannot validate a plausibility guard: all four sheets parse
correctly, so a guard that never fires looks identical to one that cannot fire.
This re-parses each sheet with `ppf_hint` deliberately wrong by a factor and
reports WHICH CHECK, if any, notices.

    python server/scale_injection.py [plans_dir ...]
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_eval as BE                                  # noqa: E402
from pdf_vector import parse                             # noqa: E402

FACTORS = (0.5, 2.0)


def caught_by(scene, err=None):
    """Every signal that noticed. Empty list = a confidently wrong parse."""
    if err:
        return [f"RAISES: {err}"]
    m = scene.get("meta", {}) or {}
    sc = m.get("scale", {}) or {}
    who = []
    if sc.get("implied_oversize"):
        who.append("door")
    if sc.get("tread_implied_oversize"):
        who.append("tread")
    if (m.get("plausibility") or {}).get("verdict") is False:
        who.append("room_median")
    if str((m.get("plausibility") or {}).get("builtup_why", "")).endswith(
            "This is not a floor"):
        who.append("builtup")
    who += [f for f in BE.health_flags({
        "width_ft": m.get("plan_width_ft", 0), "depth_ft": m.get("plan_depth_ft", 0),
        "rooms": len(scene.get("rooms") or []),
        "doors": sum(1 for o in (scene.get("openings") or [])
                     if o.get("type") == "door"),
        "scale_verified": scene.get("scale_verified"),
    }) if f != "scale_unverified"]                # not a scale-ERROR signal
    return who


def run(paths):
    rows, caught = [], 0
    for p in paths:
        try:
            base = parse(open(p, "rb").read(), None)["meta"]["scale"]["pt_per_ft"]
        except Exception as e:
            print(f"{os.path.basename(p)[:28]:<30} baseline RAISES: {e}")
            continue
        for f in FACTORS:
            try:
                sc = parse(open(p, "rb").read(), None, ppf_hint=base / f)
                who = caught_by(sc)
                med = (sc["meta"].get("plausibility") or {}).get("room_median_sqft")
                dm = (sc["meta"]["scale"] or {}).get("door_median_ft")
            except Exception as e:
                who, med, dm = caught_by(None, str(e)[:38]), None, None
            caught += bool(who)
            rows.append((os.path.basename(p)[:26], f, dm, med, who))
    print(f"{'sheet':<28}{'x':>5}{'door ft':>9}{'med room':>10}  caught by")
    for name, f, dm, med, who in rows:
        print(f"{name:<28}{f:>5.1f}{dm!s:>9}{med!s:>10}  "
              f"{', '.join(who) or '*** NOT CAUGHT ***'}")
    print(f"\n{caught}/{len(rows)} injected scale errors caught")
    return caught, len(rows)


if __name__ == "__main__":
    dirs = sys.argv[1:] or [os.path.join(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))), "plans")]
    files = [f for d in dirs for f in sorted(glob.glob(os.path.join(d, "*.pdf")))]
    run(files)
