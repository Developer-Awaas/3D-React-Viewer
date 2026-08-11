"""Plan Doctor — the self-checking agent that runs on EVERY parse.

Three jobs (designed with Saswat, 22 Jul 2026):
 1. RULES (always on, pure, unit-tested): ~15 deterministic checks over the
    finished scene. Each failure carries a LAYMAN explanation of what went
    wrong and why the numbers moved (e.g. "efficiency is 0% because no rooms
    were detected — the wall lines on this sheet don't close").
 2. LEARNING LOG: every diagnosis is appended to docs/LEARNINGS.md, tagged by
    failure pattern. Claude reads this file at the start of each session, and
    batch_eval grows a case from every new pattern — that's the auto-learn
    loop. Fire-and-forget: logging can never break a parse.
 3. LLM SECOND OPINION (optional, parallel, NEVER blocking or overriding the
    rules): when ANTHROPIC_API_KEY + LLM_DOCTOR=1 are set, a small model gets
    the same facts and writes a friendlier paragraph into the learning log.
    The rules verdict stays authoritative — an LLM may phrase, not decide.

Efficiency is NON-NEGOTIABLE: when carpet is 0 the diagnosis explains it and
`efficiency_display` tells the UI to show "needs review" instead of a silent 0%.
"""
import json
import logging
import os
import time

log = logging.getLogger("drishti.doctor")

# universal sanity bands (phase-1 ground truth; golden corpus + user-feedback
# button come next per the phased plan)
EFF_LO, EFF_HI = 55.0, 90.0          # healthy carpet/super band for Indian flats
ENV_LO, ENV_HI = 12.0, 400.0         # plausible building side, ft
DOOR_LO, DOOR_HI = 2.0, 4.5          # plausible door leaf width, ft
TINY_ROOM_SQFT = 15.0
ROOM_DIM_OK, ROOM_DIM_FAIL = 90.0, 80.0   # R-2 median match bands

TRUSTED_SCALES = {"dimension_text", "cad_units", "room_dim_text"}


def _issue(issues, level, tag, message):
    issues.append({"level": level, "tag": tag, "message": message})


def diagnose(scene):
    """Scene -> diagnosis dict. PURE (no I/O), safe on partial/malformed
    scenes (client-supplied via /recompute)."""
    if not isinstance(scene, dict):
        scene = {}
    meta = scene.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    # scale may arrive malformed (a string) from a client scene -> coerce
    scale_meta = meta.get("scale")
    if not isinstance(scale_meta, dict):
        scale_meta = {}
    rooms = scene.get("rooms", []) or []
    openings = scene.get("openings", []) or []
    stmt = scene.get("area_statement", {}) or {}
    issues = []

    # --- rooms & carpet (the efficiency chain) ---
    carpet_src = stmt.get("carpet_source")
    eff = float(stmt.get("efficiency_pct", 0) or 0)
    if not rooms:
        if carpet_src == "wall_interior":
            _issue(issues, "warn", "no_rooms_fallback",
                   "No individual rooms were detected, so carpet area was "
                   "estimated from the space enclosed by the walls. Room-wise "
                   "numbers and Vastu are unavailable for this plan.")
        else:
            _issue(issues, "fail", "no_rooms",
                   "No rooms were detected — the wall lines on this sheet "
                   "don't close into pockets (broken/fragmented linework or a "
                   "missing wall layer). Carpet area and efficiency cannot be "
                   "computed and show as 'needs review'.")
    if stmt and eff <= 0 and carpet_src == "none":
        _issue(issues, "fail", "efficiency_zero",
               "Efficiency reads 0% ONLY because carpet is unknown (see the "
               "room detection issue) — it is not a real 0%.")
    elif stmt and 0 < eff < EFF_LO:
        _issue(issues, "warn", "efficiency_low",
               f"Efficiency {eff:.0f}% is below the typical {EFF_LO:.0f}-"
               f"{EFF_HI:.0f}% band — some rooms were probably missed, so "
               "carpet is under-counted.")
    elif stmt and eff > EFF_HI:
        _issue(issues, "warn", "efficiency_high",
               f"Efficiency {eff:.0f}% is above the typical band — carpet may "
               "be over-counted (circulation included) or walls read too thin.")

    # --- R-8 / §0.1: the sheet's OWN printed area statement is ground truth.
    # This outranks every other accuracy signal here, because it comes from the
    # architect rather than from our own geometry. A parse that contradicts it
    # is wrong until proven otherwise, so a big gap is a FAIL, not a warning.
    cmp_ = scene.get("area_comparison") or {}
    if isinstance(cmp_, dict) and cmp_.get("rows"):
        worst = float(cmp_.get("worst_diff_pct", 0) or 0)
        detail = "; ".join(
            f"{r.get('label', r.get('figure'))} printed {r.get('printed_sqft')} vs "
            f"parsed {r.get('parsed_sqft')} sqft ({r.get('match_pct')}% match)"
            for r in cmp_["rows"])
        if cmp_.get("verdict") == "mismatch":
            _issue(issues, "fail", "printed_area_mismatch",
                   f"The sheet prints its own area statement and our numbers "
                   f"disagree with it by up to {worst:.0f}% — {detail}. The "
                   "printed figures are the architect's, so treat OUR areas as "
                   "wrong until the parse is checked.")
        elif cmp_.get("verdict") == "close":
            _issue(issues, "warn", "printed_area_close",
                   f"Our areas are within {worst:.0f}% of the sheet's own "
                   f"printed area statement — {detail}. Close, but worth a look "
                   "before quoting the numbers.")
        else:
            _issue(issues, "ok", "printed_area_verified",
                   f"Confirmed against the sheet's own printed area statement — "
                   f"{detail}. This is the strongest accuracy check available.")

    # --- R-2: the sheet PRINTS each room's size. Same authority as the printed
    # area statement above (§0.1) but room by room, so it localises the error:
    # a single bad room reads differently from every room being off together.
    try:
        import room_dims
        rsum = room_dims.summary(rooms)
    except Exception:
        rsum = None
    if rsum:
        med = float(rsum["median_match_pct"])
        n, off = rsum["rooms_checked"], rsum["rooms_off"]
        if med < ROOM_DIM_FAIL:
            _issue(issues, "fail", "room_dims_mismatch",
                   f"The sheet prints each room's size, and our measured rooms "
                   f"disagree: median match only {med:.0f}% across {n} room(s) "
                   f"({off} off by more than 20%). Either the scale is wrong or "
                   "rooms are merging into each other — room areas, carpet and "
                   "₹ cost are all affected.")
        elif med < ROOM_DIM_OK:
            _issue(issues, "warn", "room_dims_close",
                   f"Measured rooms are within {100 - med:.0f}% of the sizes "
                   f"printed on the sheet ({n} checked, {off} off by more than "
                   "20%) — close, but check the odd ones before quoting areas.")
        else:
            _issue(issues, "ok", "room_dims_verified",
                   f"Room sizes confirmed against the dimensions printed on the "
                   f"sheet: median match {med:.0f}% across {n} room(s).")

    # --- scale trust (every ft/sqft/₹ number scales with this) ---
    ssrc = scale_meta.get("source", "")
    if ssrc == "column_box_12in":
        _issue(issues, "warn", "scale_column_guess",
               "Scale was inferred by assuming the columns are 12 inches wide. "
               "If this plan uses 9-inch columns, every dimension is ~33% off — "
               "cross-check one known room size.")
    elif ssrc in ("assumed_width", "env_ppf", ""):
        _issue(issues, "warn", "scale_assumed",
               "No dimension text was found, so the drawing was scaled to an "
               "assumed overall width. All ft / sqft / cost numbers move with "
               "that guess — confirm the real plot width.")
    if scale_meta.get("needs_review"):
        sc = scale_meta
        _ov = sc.get("implied_oversize")
        _md = sc.get("door_median_ft")
        _corrected = "door_corrected" in str(sc.get("source", ""))
        if _corrected:
            _issue(issues, "ok", "scale_door_corrected",
                   f"Scale was auto-corrected from door widths (median door "
                   f"{_md} ft) — sizes should now be right; still worth a check.")
        else:
            _issue(issues, "fail", "scale_door_mismatch",
                   f"Sizes look off: the doors imply the plan is about "
                   f"{_ov}x wrong (median door reads {_md} ft, real doors are "
                   "~3 ft). Re-upload with the true plan width to fix every "
                   "measurement, or the areas/₹ cost will be off.")
    if scale_meta.get("envelope") == "overall_dimension_text":
        _issue(issues, "ok", "envelope_verified",
               "Plot size was taken from the architect's own overall dimension "
               "on the sheet (more trustworthy than raw linework).")

    # --- PHYSICS: the building cannot be bigger than the land it stands on.
    # Not a warning — a footprint above the plot is impossible, so something in
    # the reading is definitely wrong (§0.1). Skipped when the sheet states no
    # plot area: an unknown plot is not evidence of anything.
    fp_sqft = meta.get("footprint_sqft")
    plot_sqft = meta.get("plot_sqft")
    try:
        fp_sqft = float(fp_sqft) if fp_sqft else None
        plot_sqft = float(plot_sqft) if plot_sqft else None
    except (TypeError, ValueError):
        fp_sqft = plot_sqft = None
    if fp_sqft and plot_sqft and fp_sqft > plot_sqft:
        _issue(issues, "fail", "footprint_exceeds_plot",
               f"The building footprint reads {fp_sqft:.0f} sqft on a plot of "
               f"{plot_sqft:.0f} sqft — impossible, a building cannot be larger "
               "than its land. The wall reading has swallowed ground outside "
               "the building (setbacks, an adjacent drawing, or the plot line "
               "read as a wall); every area on this plan is unsafe.")

    # --- envelope sanity ---
    w = float(meta.get("plan_width_ft", 0) or 0)
    d = float(meta.get("plan_depth_ft", 0) or 0)
    if w and d and not (ENV_LO <= w <= ENV_HI and ENV_LO <= d <= ENV_HI):
        _issue(issues, "fail", "envelope_implausible",
               f"The building measures {w:.0f} x {d:.0f} ft — outside the "
               f"plausible {ENV_LO:.0f}-{ENV_HI:.0f} ft range. The scale "
               "detection almost certainly failed on this sheet.")

    # --- openings ---
    doors = [o for o in openings if o.get("type") == "door"]
    if not doors:
        _issue(issues, "warn", "no_doors",
               "No doors were found. Either the sheet has no door symbols/tags "
               "or they sit on an unusual layer — the 3D model will have "
               "sealed rooms.")
    else:
        widths = []
        for o in doors:
            a = o.get("along")
            if isinstance(a, (list, tuple)) and len(a) == 2:
                widths.append(abs(float(a[1]) - float(a[0])))
        if widths:
            widths.sort()
            med = widths[len(widths) // 2]
            if not (DOOR_LO <= med <= DOOR_HI):
                _issue(issues, "warn", "door_width_odd",
                       f"Typical door width came out {med:.1f} ft (normal is "
                       f"{DOOR_LO:.1f}-{DOOR_HI:.1f} ft) — a scale problem "
                       "is likely; treat all sizes with caution.")
    if not any(o.get("type") == "window" for o in openings):
        _issue(issues, "warn", "no_windows",
               "No windows were detected on this sheet (tags/symbols not "
               "found) — renders and Vastu light rules lose some accuracy.")

    # --- room quality ---
    if rooms:
        untyped = sum(1 for r in rooms if not r.get("type"))
        if untyped > len(rooms) / 2:
            _issue(issues, "warn", "rooms_unlabeled",
                   f"{untyped} of {len(rooms)} rooms have no name (labels are "
                   "images, not text, on this sheet) — Vastu and furniture "
                   "staging skip unnamed rooms. OCR (tesseract) helps here.")
        tiny = sum(1 for r in rooms
                   if float(r.get("area_sqft", 99) or 99) < TINY_ROOM_SQFT)
        if tiny:
            _issue(issues, "warn", "tiny_rooms",
                   f"{tiny} detected 'room(s)' are under {TINY_ROOM_SQFT:.0f} "
                   "sqft — likely wall pockets or shafts read as rooms; room "
                   "count may be inflated.")

    # --- silent analysis failures (blocks that vanished) ---
    for block, label in (("area_statement", "RERA area statement"),
                         ("vastu", "Vastu report"), ("boq", "cost estimate")):
        if block not in scene:
            _issue(issues, "warn", f"missing_{block}",
                   f"The {label} could not be computed for this plan (its "
                   "calculation hit an error and was skipped).")

    # --- reader provenance ---
    reader = meta.get("reader", "")
    if str(reader).startswith("ml:"):
        _issue(issues, "warn", "ml_reader",
               "This plan was read by the AI fallback (photo/scan path), which "
               "is less exact than CAD line reading — expect approximate walls.")

    # --- verdict ---
    fails = [i for i in issues if i["level"] == "fail"]
    warns = [i for i in issues if i["level"] == "warn"]
    if fails:
        grade = "D" if len(fails) == 1 else "F"
    elif len(warns) > 2:
        grade = "C"
    elif warns:
        grade = "B"
    else:
        grade = "A"
    score = max(0, 100 - 40 * len(fails) - 12 * len(warns))
    if fails:
        headline = fails[0]["message"]
    elif warns:
        headline = warns[0]["message"]
    else:
        headline = ("All checks passed: rooms, doors, scale and areas look "
                    "consistent for this plan.")
    return {
        "grade": grade,
        "score": score,
        "headline": headline,
        "issues": issues,
        "learn_tags": sorted({i["tag"] for i in issues if i["level"] != "ok"}),
        # NON-NEGOTIABLE efficiency contract for the UI: never a silent 0%
        # NON-NEGOTIABLE: never a silent 0% — a tiny positive eff that would
        # round to "0.0%" is treated as needs_review too
        "efficiency_display": ("needs_review" if (not stmt or eff < 0.05)
                               else f"{eff:.1f}%"),
    }


# --------------------------------------------------------------------------- #
# learning log (fire-and-forget; never raises into the request)
# --------------------------------------------------------------------------- #
def _learnings_path():
    return os.getenv("LEARNINGS_FILE") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "docs", "LEARNINGS.md")


def record(diagnosis, filename=None, duration_ms=None):
    """Append one line per parse to docs/LEARNINGS.md. Rotates at ~512 KB."""
    try:
        path = _learnings_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > 512 * 1024:
            os.replace(path, path + ".1")          # simple one-step rotation
        newfile = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as f:
            if newfile:
                f.write("# Drishti learning log (written by Plan Doctor — one "
                        "line per parse; Claude reads this each session)\n\n")
            f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} | "
                    f"{(filename or 'unnamed')[:60]} | grade {diagnosis['grade']}"
                    f" ({diagnosis['score']}/100) | "
                    f"tags: {', '.join(diagnosis['learn_tags']) or 'clean'} | "
                    f"{diagnosis['headline']}\n")
    except Exception as e:                          # logging must never hurt
        log.warning("learning log skipped: %s", e)


# --------------------------------------------------------------------------- #
# optional LLM second opinion — parallel, never blocking, never authoritative
# --------------------------------------------------------------------------- #
def llm_enabled():
    return (os.getenv("LLM_DOCTOR", "0").lower() in ("1", "true", "yes")
            and bool(os.getenv("ANTHROPIC_API_KEY")))


async def llm_second_opinion(diagnosis, meta, filename=None):
    """Ask a small Claude model to rephrase the rules' findings for a layman
    and suggest ONE improvement idea. Result is APPENDED to the learning log —
    it never changes the rules verdict and any failure is swallowed."""
    if not llm_enabled():
        return None
    try:
        import httpx
        prompt = (
            "You are the QA doctor for a floor-plan-to-3D product. Rules "
            "already ran; do NOT contradict them. In 2 short sentences of "
            "plain English: (1) explain to a non-technical founder why this "
            "parse got its grade, (2) suggest one concrete improvement. "
            f"Diagnosis: {json.dumps(diagnosis['issues'])[:2000]} "
            f"Grade: {diagnosis['grade']}. "
            f"Plan meta: {json.dumps({k: meta.get(k) for k in ('plan_width_ft', 'plan_depth_ft', 'reader', 'scale')})[:600]}")
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                         "anthropic-version": "2023-06-01"},
                json={"model": os.getenv("LLM_DOCTOR_MODEL", "claude-haiku-4-5"),
                      "max_tokens": 200,
                      "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json().get("content", []))
        if text:
            with open(_learnings_path(), "a", encoding="utf-8") as f:
                f.write(f"    - LLM 2nd opinion ({(filename or 'unnamed')[:40]}):"
                        f" {text.strip()[:500]}\n")
        return text
    except Exception as e:
        log.warning("llm second opinion skipped: %s", e)
        return None
