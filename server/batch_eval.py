"""Corpus evaluation harness — run the parser across a whole folder of plans and
score it, so generalization is MEASURED, not guessed. This is the "improve with
time" backbone: run it before and after any engine change to catch regressions
and track progress across many real plans.

Usage:
    python batch_eval.py [PLANS_DIR] [--save]

- PLANS_DIR defaults to ./plans (or $PLANS_DIR). Parses every *.pdf.
- Prints a per-plan scorecard + health flags that catch likely failures on ANY
  plan (no ground truth needed): implausible envelope, zero rooms, zero doors.
- If plans/ground_truth.json exists, also checks door counts where a number is
  given.
- --save writes a timestamped JSON so runs can be diffed over time.

The scoring helpers are pure so they are unit-tested.
"""
import glob
import json
import os
import sys


# ---- pure scoring (unit-tested) ----

def health_flags(m):
    """Heuristic 'this parse probably failed' flags that work on any plan without
    ground truth. Returns a list of short flag strings (empty = looks healthy)."""
    flags = []
    w, d = m.get("width_ft", 0) or 0, m.get("depth_ft", 0) or 0
    small = min(w, d)
    if small < 12:
        flags.append("envelope_tiny")           # e.g. picked a detail block
    if max(w, d) > 600:
        flags.append("envelope_huge")
    if m.get("rooms", 0) == 0:
        flags.append("no_rooms")                 # open envelope / unsealed
    if m.get("doors", 0) == 0:
        flags.append("no_doors")
    return flags


def door_score(actual, expected):
    """Recall vs an expected door count. Returns (ratio, ok) or (None, None) if
    expected isn't a usable number."""
    try:
        exp = int(expected)
    except (TypeError, ValueError):
        return None, None
    if exp <= 0:
        return None, None
    ratio = round(actual / exp, 2)
    return ratio, ratio >= 0.8


# ---- runner (I/O) ----

def parse_metrics(scene):
    m = scene.get("meta", {})
    ops = scene.get("openings", [])
    return {
        "width_ft": round(m.get("plan_width_ft", 0), 1),
        "depth_ft": round(m.get("plan_depth_ft", 0), 1),
        "doors": sum(1 for o in ops if o.get("type") == "door"),
        "windows": sum(1 for o in ops if o.get("type") == "window"),
        "rooms": len(scene.get("rooms", [])),
        "typed_rooms": sum(1 for r in scene.get("rooms", []) if r.get("type")),
        "furniture": len(scene.get("furniture", [])),
        "wings": m.get("wing", {}).get("count", 1),
        "scale": m.get("scale", {}).get("source"),
        "mode": m.get("source"),
    }


def evaluate(plans_dir, ground_truth=None):
    import pdf_vector
    results = []
    for path in sorted(glob.glob(os.path.join(plans_dir, "*.pdf"))):
        name = os.path.basename(path)
        row = {"plan": name}
        try:
            scene = pdf_vector.parse(open(path, "rb").read())
            row.update(parse_metrics(scene))
            row["flags"] = health_flags(row)
            row["ok"] = True
        except Exception as e:
            row["ok"] = False
            row["error"] = f"{type(e).__name__}: {e}"
            row["flags"] = ["parse_failed"]
        gt = (ground_truth or {}).get("plans", {}).get(name, {})
        if gt and row.get("ok"):
            ratio, ok = door_score(row["doors"], gt.get("doors_expected"))
            if ratio is not None:
                row["door_recall"] = ratio
        results.append(row)
    return results


def _print(results):
    print(f"\n{'plan':<42} {'envelope':>14} {'dr':>3} {'wn':>3} {'rm':>3} {'ty':>3} flags")
    print("-" * 92)
    healthy = 0
    for r in results:
        if not r.get("ok"):
            print(f"{r['plan']:<42} {'FAILED':>14}  {r.get('error','')[:30]}")
            continue
        env = f"{r['width_ft']:.0f}x{r['depth_ft']:.0f}ft"
        flags = ",".join(r["flags"]) or "ok"
        if flags == "ok":
            healthy += 1
        print(f"{r['plan']:<42} {env:>14} {r['doors']:>3} {r['windows']:>3} "
              f"{r['rooms']:>3} {r['typed_rooms']:>3} {flags}")
    print("-" * 92)
    print(f"{healthy}/{len(results)} plans clean (no health flags)\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    plans_dir = args[0] if args else os.getenv("PLANS_DIR", "plans")
    gt_path = os.path.join(plans_dir, "ground_truth.json")
    gt = json.load(open(gt_path)) if os.path.exists(gt_path) else None
    results = evaluate(plans_dir, gt)
    _print(results)
    if "--save" in sys.argv:
        import time
        out = os.path.join(plans_dir, f"eval_{time.strftime('%Y%m%d_%H%M%S')}.json")
        json.dump(results, open(out, "w"), indent=1)
        print(f"saved -> {out}")


if __name__ == "__main__":
    main()
