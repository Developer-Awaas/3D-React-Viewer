"""Corpus evaluation harness — run the parser across a whole folder of plans and
score it, so generalization is MEASURED, not guessed. This is the "improve with
time" backbone: run it before and after any engine change to catch regressions
and track progress across many real plans.

Usage:
    python batch_eval.py [PLANS_DIR] [--save]

- PLANS_DIR defaults to ./plans (or $DRISHTI_PLANS_DIR, or $PLANS_DIR). Parses
  every *.pdf. The corpus is confidential and gitignored, so a repo copy
  without it just scores zero plans - this script reports, it does not gate;
  the pytest golden suite is the gate and fails loudly instead.
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
    # COLD-SHEET GUARD: a guessed scale is a REFUSAL, not a warning - every
    # ft/sqft/rupee in the row above scales with it (2 Sep 2026, Rahul).
    if m.get("scale_verified") is False:
        flags.append("scale_unverified")
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


def carpet_r2_verdict(prev, cur, carpet_tol=0.5, r2_tol=0.5):
    """CARPET RISING WHILE R-2 FALLS IS A REGRESSION (24 Aug 2026, Rahul).

    Found the hard way: the seal split took FLOOR PLAN's carpet 1191.1 -> 1328.1
    (+137) and its R-2 median 98.0 -> 94.6 in the same run. Carpet alone reads
    as a win — 137 sqft of floor we were not counting before. Read together
    with R-2 it is the opposite: the rooms did not come back, the rooms we
    already had GREW PAST THEIR PRINTED DIMENSIONS. Coverage and accuracy move
    TOGETHER when the parse improves; when they move APART, a boundary moved.

    `prev` / `cur` are dicts carrying `carpet_sqft` and `r2_median`. Returns a
    short verdict string, or None when the rule does not apply (a figure
    missing, or neither moved beyond its tolerance). Pure -> unit-tested.

    THE MIRROR CASE — carpet FALLING while R-2 RISES — is UNVERIFIED, neither
    an improvement nor a regression (Rahul, 25 Aug 2026). It is genuinely both
    readings at once: the sign-flipped phenomenon (rooms shrinking inside their
    printed dimensions) AND what an honest correction looks like when we stop
    counting space we never had — which is exactly the 20 Aug footprint fix,
    where losing 2.6 sqft was the wall material we had been claiming at twice
    its drawn thickness. NEITHER READING CAN BE CHOSEN FROM THE NUMBERS ALONE,
    so it is flagged for a human, the same way a blind instrument is: said out
    loud, never silently scored either way.

    Verdicts are prefixed `REGRESSION:` or `UNVERIFIED:` so a caller can route
    them without re-parsing the sentence.
    """
    def _d(k):
        a, b = (prev or {}).get(k), (cur or {}).get(k)
        return None if a is None or b is None else b - a
    dc, dr = _d("carpet_sqft"), _d("r2_median")
    if dc is None or dr is None:
        return None
    if dc > carpet_tol and dr < -r2_tol:
        return (f"REGRESSION: carpet +{dc:.1f} sqft while R-2 {dr:+.1f} — "
                "rooms grew past their printed dimensions; carpet alone would "
                "have called this a win")
    if dc < -carpet_tol and dr > r2_tol:
        return (f"UNVERIFIED: carpet {dc:.1f} sqft while R-2 {dr:+.1f} — this "
                "is EITHER rooms shrinking inside their printed dimensions OR "
                "an honest correction that stops counting space we never had. "
                "The numbers cannot tell these apart. A human must rule.")
    return None


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
        # READ BEFORE ANY NUMBER IN THIS ROW (standing protocol, 2 Sep 2026)
        "scale_verified": scene.get("scale_verified"),
        "typed_rooms": sum(1 for r in scene.get("rooms", []) if r.get("type")),
        # columns + footprint are REPORTED because they moved unseen: a scale
        # change on 11 Aug silently took FLOOR PLAN from 26 columns to 0 and
        # nothing here would have shown it (12 Aug)
        "columns": len(scene.get("columns", [])),
        "footprint_sqft": m.get("footprint_sqft"),
        # THE PHYSICS CHECK, SAID OUT LOUD. `plot_source` names where the plot
        # came from — printed statement, user entry, or "unknown", in which
        # case the check is BLIND and reports so rather than passing.
        "plot_sqft": m.get("plot_sqft"),
        "plot_source": m.get("plot_source"),
        "footprint_pct_of_plot": (round(100.0 * m["footprint_sqft"] / m["plot_sqft"], 1)
                                  if m.get("footprint_sqft") and m.get("plot_sqft")
                                  else None),
        # M-1 (19 Aug): the model's own wall material / the measured pair
        # rectangles. Printed because the 3D can be incoherent while every
        # other number holds — that is exactly how the stacked-sheet build
        # of 19 Aug passed the whole judged set.
        "m1": (m.get("wall_face_quality") or {}).get("material_ratio"),
        "furniture": len(scene.get("furniture", [])),
        "wings": m.get("wing", {}).get("count", 1),
        "scale": m.get("scale", {}).get("source"),
        "mode": m.get("source"),
        # CARPET AND R-2 ARE EMITTED TOGETHER because they must be READ
        # together (24 Aug 2026): carpet rising while R-2 falls is a
        # regression, and neither number can show that on its own. See
        # carpet_r2_verdict.
        "carpet_sqft": _carpet_sqft(scene),
        # R-2 IS A QUARTET, NEVER A MEDIAN ALONE (standing rule, 25 Aug 2026).
        # Three times the median stayed still while the parse changed under it:
        # a DELETED room left the sample (17 Aug), a MERGED blob matched no
        # printed dimension (22 Aug), and a REMOVED blob moved it 0.6 while
        # `worst` went 0.0 -> 57.2 (25 Aug). A median that cannot move is not
        # evidence of stability.
        **_r2_quartet(scene),
        # WHICH CODE PATH RAN — three absolute floors switch branches with no
        # other trace, so a run diff can say "this plan changed ROUTE" rather
        # than only "these numbers moved".
        "route": m.get("route"),
    }


def _carpet_sqft(scene):
    try:
        import area_statement
        st = area_statement.compute_area_statement(scene, 1.30)
        return (st.get("carpet_area") or {}).get("sqft")
    except Exception:
        return None


def _r2_quartet(scene):
    """R-2's four numbers, always together: median, sample size, how many are
    off, and the worst. Reporting the median alone has hidden a real change
    three times."""
    try:
        import room_dims
        s = room_dims.summary(scene.get("rooms", [])) or {}
    except Exception:
        s = {}
    return {"r2_median": s.get("median_match_pct"),
            "r2_checked": s.get("rooms_checked"),
            "r2_off": s.get("rooms_off"),
            "r2_worst": s.get("worst_match_pct")}


def evaluate(plans_dir, ground_truth=None):
    import pdf_vector
    results = []
    for path in sorted(glob.glob(os.path.join(plans_dir, "*.pdf"))):
        name = os.path.basename(path)
        row = {"plan": name}
        try:
            scene = pdf_vector.parse(open(path, "rb").read())
            # USER-ENTRY PLOT (28 Aug 2026, Rahul). `footprint <= plot` is our
            # only physics check and it is BLIND wherever a sheet prints no
            # plot area — including neelachala FIRST FLOOR, the sheet with the
            # largest footprint. Rahul supplied 11,500 sqft for that site on
            # 21 Aug and it lives in ground_truth.json.
            #
            # IT IS APPLIED HERE, IN THE EVAL, AND NOT IN THE PARSER, ON
            # PURPOSE. The parser must never read its own ground-truth file:
            # that is how `footprint <= plot` became self-referential in the
            # first place (it fell back to the building's own envelope, 21
            # Aug). The eval may legitimately read its own truth file; a real
            # user supplies the same figure through
            # `corrections.plot_area_sqft` on /recompute, which is the path
            # this reuses unchanged.
            _plot = ((ground_truth or {}).get("plans", {})
                     .get(name, {}).get("plot_sqft"))
            if _plot and not (scene.get("meta") or {}).get("plot_sqft"):
                import corrections
                scene, _ = corrections.apply_corrections(scene,
                                                         {"plot_area_sqft": _plot})
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
    print(f"\n{'plan':<42} {'envelope':>14} {'dr':>3} {'wn':>3} {'rm':>3} {'ty':>3} "
          f"{'col':>4} {'foot':>6} {'M-1':>5} flags")
    print("-" * 104)
    healthy = 0
    for r in results:
        if not r.get("ok"):
            print(f"{r['plan']:<42} {'FAILED':>14}  {r.get('error','')[:30]}")
            continue
        env = f"{r['width_ft']:.0f}x{r['depth_ft']:.0f}ft"
        flags = ",".join(r["flags"]) or "ok"
        if flags == "ok":
            healthy += 1
        foot = f"{r['footprint_sqft']:.0f}" if r.get("footprint_sqft") else "-"
        print(f"{r['plan']:<42} {env:>14} {r['doors']:>3} {r['windows']:>3} "
              f"{r['rooms']:>3} {r['typed_rooms']:>3} {r.get('columns', 0):>4} "
              f"{foot:>6} {(f'{r['m1']:.2f}' if r.get('m1') else '-'):>5} {flags}")
    print("-" * 104)
    print(f"{healthy}/{len(results)} plans clean (no health flags)\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    plans_dir = args[0] if args else (os.getenv("DRISHTI_PLANS_DIR")
                                       or os.getenv("PLANS_DIR", "plans"))
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
