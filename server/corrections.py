"""G7 user corrections — apply human fixes to an already-parsed scene, so a
wrong auto-number becomes a TRUSTED one without re-parsing the PDF (no GPU).

Three corrections, in priority order of value:
  1. true_width_ft — the real overall plan width. Rescales the whole scene so
     every ft / sqft / ₹ is right (the #1 fix; scale drives everything).
  2. room_types    — {room_id: "kitchen"|...|""}: set or clear a room's type
     (fixes Vastu + furniture + labels). "" clears it.
  3. delete_rooms  — [room_id, ...]: drop phantom rooms (shafts read as rooms)
     so carpet / efficiency stop being inflated.
  4. plot_area_sqft — the site area. The plot comes from the drawing or from
     the user, NEVER from the building's own envelope (21 Aug 2026).

Pure functions (no I/O, no GPU) -> fully unit-tested. The /recompute endpoint
calls apply_corrections() then re-runs area/vastu/boq/doctor on the result.
"""
import math

import pdf_vector

VALID_ROOM_TYPES = {
    "kitchen", "bedroom", "bathroom", "living", "dining", "study",
    "parking", "balcony", "lobby", "storage", "",
}


def apply_corrections(scene, corr):
    """Return (corrected_scene, info). Every bad input raises ValueError (the
    /recompute endpoint turns that into a clean 422 — never a 500). Mutates the
    scene the caller passes. `info` records what changed for transparency."""
    if not isinstance(scene, dict):
        raise ValueError("scene must be an object")
    if corr is None:
        corr = {}
    if not isinstance(corr, dict):
        raise ValueError("corrections must be an object")
    info = {"applied": []}
    meta = scene.setdefault("meta", {})
    if not isinstance(meta, dict):
        raise ValueError("scene.meta must be an object")
    scale = meta.get("scale")
    if not isinstance(scale, dict):
        scale = meta["scale"] = {}         # coerce a missing/malformed scale

    # 1) TRUE WIDTH -> rescale everything (reuses the G3 whole-scene rescaler)
    tw = corr.get("true_width_ft")
    if tw is not None:
        if isinstance(tw, bool) or not isinstance(tw, (int, float, str)):
            raise ValueError("true_width_ft must be a number")
        try:
            tw = float(tw)
        except (TypeError, ValueError):
            raise ValueError("true_width_ft must be a number")
        if not math.isfinite(tw) or not (0 < tw <= 2000):
            raise ValueError("true_width_ft must be in (0, 2000]")
        cur = float(meta.get("plan_width_ft", 0) or 0)
        if cur > 0:
            k = tw / cur
            if abs(k - 1.0) > 1e-4:
                pdf_vector._rescale_scene_ft(scene, k)
                # clear any G3 auto-flag: the human just gave the real number
                for key in ("needs_review", "suggested_factor",
                            "implied_oversize", "door_median_ft"):
                    scale.pop(key, None)
                scale["source"] = _mark(scale.get("source"), "user_width")
                scale["user_width_ft"] = round(tw, 3)
                info["applied"].append(f"rescaled x{k:.4f} to width {tw:g} ft")
                info["scale_factor"] = round(k, 6)

    # 2) ROOM TYPES -> set/clear
    types = corr.get("room_types") or {}
    if types:
        if not isinstance(types, dict):
            raise ValueError("room_types must be an object")
        by_id = {r.get("id"): r for r in scene.get("rooms", []) or []}
        changed = 0
        for rid, t in types.items():
            if t is None:
                t = ""
            if not isinstance(t, str):
                raise ValueError("room type must be a string")
            t = t.strip().lower()
            if t not in VALID_ROOM_TYPES:
                raise ValueError(f"invalid room type: {t!r}")
            r = by_id.get(rid)
            if r is None:
                continue
            if t:
                r["type"] = t
            else:
                r.pop("type", None)
            changed += 1
        if changed:
            info["applied"].append(f"retyped {changed} room(s)")

    # 4) PLOT AREA — user entry (21 Aug 2026, Rahul). The plot may come from
    # the drawing or from the user and from nowhere else: deriving it from the
    # building's own envelope made `footprint <= plot` self-referential.
    pa = corr.get("plot_area_sqft")
    if pa is not None:
        try:
            pa = float(pa)
        except (TypeError, ValueError):
            raise ValueError("plot_area_sqft must be a number")
        if not (pa > 0):
            raise ValueError("plot_area_sqft must be positive")
        meta["plot_sqft"] = round(pa, 1)
        meta["plot_source"] = "user"
        info["applied"].append(f"plot area set to {pa:.0f} sqft")

    # 3) DELETE phantom rooms
    dl = corr.get("delete_rooms")
    if dl and not isinstance(dl, (list, tuple)):
        # a bare string "r0" would iterate into {'r','0'} and delete the WRONG
        # rooms silently — require an explicit list
        raise ValueError("delete_rooms must be a list of room ids")
    dele = set(dl or [])
    if dele:
        rooms = scene.get("rooms", []) or []
        kept = [r for r in rooms if r.get("id") not in dele]
        removed = len(rooms) - len(kept)
        if removed:
            scene["rooms"] = kept
            info["applied"].append(f"deleted {removed} phantom room(s)")

    if info["applied"]:
        meta.setdefault("warnings", []).append(
            "user corrections applied: " + "; ".join(info["applied"]))
        scale["corrected"] = True

    # 6) §0.2 CONTRADICTS — the user answers "is there a wall here?"
    # CONFIRM closes the edge and the space counts; REJECT leaves it uncounted
    # and stops the prompt. Never auto-answered, and the answer travels with
    # the scene so /recompute does not ask twice.
    flags = meta.get("open_side_regions") or []
    conf = corr.get("confirm_open_sides")
    rej = corr.get("reject_open_sides")
    for key, val in (("confirmed", conf), ("rejected", rej)):
        if val is None:
            continue
        if not isinstance(val, (list, tuple)):
            raise ValueError(f"{key} open sides must be a list of indices")
        for i in val:
            try:
                i = int(i)
            except (TypeError, ValueError):
                raise ValueError("open-side index must be an integer")
            if not (0 <= i < len(flags)):
                raise ValueError(f"open-side index {i} out of range")
            flags[i]["answer"] = key
    for i, f in enumerate(flags):
        if f.get("answer") != "confirmed" or f.get("_applied"):
            continue
        b = f.get("bbox_ft") or []
        a = float(f.get("area_if_closed_sqft") or 0)
        if len(b) != 4 or a <= 0:
            continue
        # a confirmed space is COMMON when it holds the lift, stair or a duct;
        # otherwise it is ordinary floor. Decided from what is inside it, not
        # from a guess about what the space is for.
        cx, cy = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
        holds = any(r.get("type") in ("stairs", "lobby", "lift", "duct")
                    and b[0] <= (r.get("x") or 0) <= b[2]
                    and b[1] <= (r.get("y") or 0) <= b[3]
                    for r in (scene.get("rooms") or []))
        scene.setdefault("rooms", []).append({
            "id": f"osr{i}", "x": round(cx, 2), "y": round(cy, 2),
            "area_sqft": round(a, 1),
            "type": "lobby" if holds else None,
            "polygon_ft": [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]],
            "confirmed_open_side": f.get("open_side"), "_lab": -1})
        f["_applied"] = True
        info["applied"].append(
            f"confirmed the missing {f.get('open_side')} edge: a {a:.1f} sqft "
            f"space now encloses and counts"
            + (" as common area" if holds else ""))
    if rej:
        info["applied"].append(
            f"{len(rej)} open-side flag(s) rejected - left uncounted, not asked again")

    return scene, info


def _mark(source, tag):
    source = str(source or "")
    return source if tag in source else f"{source}+{tag}"
