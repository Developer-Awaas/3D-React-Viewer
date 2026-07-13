#!/usr/bin/env python3
"""Corpus batch evaluator (corpus-hardening step).

Runs every plan in plans/ through the /scene pipeline (vector CAD PDFs via
pdf_vector; raster images via CubiCasa when torch is available), then writes
per-plan artifacts to the output dir:

    <name>.scene.json   the scene the API would return
    <name>.png          top-down preview (walls / doors / windows / columns)
    scorecard.md        one table row per plan + warnings, vs INDEX.txt

Run from repo root or tools/:  python tools/batch_eval.py
Options: --plans DIR (default <repo>/plans)  --out DIR (default <repo>/out/batch)
Raster plans are skipped gracefully where torch/CubiCasa is not installed.
"""
import argparse
import json
import os
import sys
import traceback


def _require(mod, hint):
    """Fail fast with a human message instead of a raw ImportError traceback."""
    try:
        __import__(mod)
    except ImportError:
        sys.exit(
            f"\n[batch_eval] missing dependency '{mod}'.\n"
            f"  Fix: activate the venv first, then install deps:\n"
            f"    server\\venv\\Scripts\\activate    (Windows)\n"
            f"    pip install -r server/requirements.txt -r server/requirements-dev.txt\n"
            f"  ({hint})\n")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "server"))

# make the CubiCasa repo importable no matter where this script is run from
# (perception.py defaults to the RELATIVE path ./CubiCasa5k, which only works
# when the CWD is server/ - that broke the raster path from the repo root)
_CUBI = os.environ.get("CUBICASA_REPO") or os.path.join(REPO, "server", "CubiCasa5k")
os.environ.setdefault("CUBICASA_REPO", _CUBI)
if os.path.isdir(_CUBI) and _CUBI not in sys.path:
    sys.path.insert(0, _CUBI)

PLAN_EXTS = (".pdf", ".png", ".jpg", ".jpeg", ".webp")


def read_index(plans_dir):
    """INDEX.txt -> {filename_lower: raw_line}."""
    idx = {}
    p = os.path.join(plans_dir, "INDEX.txt")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            line = line.strip()
            if "|" in line and not line.lower().startswith(("one line", "filename")):
                idx[line.split("|", 1)[0].strip().lower()] = line
    return idx


def build_scene(path):
    """One plan file -> (scene_dict|None, status_string). Mirrors main._scene_from_upload."""
    raw = open(path, "rb").read()
    is_pdf = path.lower().endswith(".pdf")
    if is_pdf:
        import pdf_vector
        if pdf_vector.is_vector_plan(raw):
            return pdf_vector.parse(raw, None), "vector"
        try:
            import fitz
            doc = fitz.open(stream=raw, filetype="pdf")
            raw = doc[0].get_pixmap(dpi=200).tobytes("png")
        except Exception as e:
            return None, "flat PDF, could not rasterize: %s" % e
    try:
        import perception, openings, scene_builder
        segs, boxes, w, h = perception.detections(raw)
        segs, ops = openings.attach_openings(segs, boxes, openings.default_tol(w))
        return scene_builder.scene_from_segments(segs, w, h,
                scene_builder.DEFAULT_WIDTH_FT, openings=ops), "raster"
    except ImportError as e:
        return None, "raster path skipped (needs torch/CubiCasa: %s)" % e


def counts(scene):
    ops = scene.get("openings", [])
    doors = [o for o in ops if o["type"] == "door"]
    snapped = sum(1 for o in doors if o.get("snapped"))
    return {
        "walls": len(scene.get("walls", [])) + len(scene.get("walls_poly", [])),
        "doors": len(doors),
        "doors_snapped": snapped,
        "windows": sum(1 for o in ops if o["type"] == "window"),
        "columns": len(scene.get("columns", [])),
    }


def _poly_patch(ax, outer, holes, **kw):
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    verts, codes = [], []
    for ring in [outer] + list(holes or []):
        if len(ring) < 3:
            continue
        verts += [tuple(p) for p in ring] + [tuple(ring[0])]
        codes += [Path.MOVETO] + [Path.LINETO] * (len(ring) - 1) + [Path.CLOSEPOLY]
    if verts:
        ax.add_patch(PathPatch(Path(verts, codes), **kw))


def render_preview(scene, out_png, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, ax = plt.subplots(figsize=(14, 10))
    for w in scene.get("walls_poly", []):
        _poly_patch(ax, w["outer"], w.get("holes"), facecolor="#3f3a33",
                    edgecolor="none", zorder=2)
    for w in scene.get("walls", []):
        ax.add_patch(Rectangle((w["x0"], w["y0"]), w["x1"] - w["x0"], w["y1"] - w["y0"],
                     facecolor="#3f3a33", edgecolor="none", zorder=2))
    wall_by_id = {w["id"]: w for w in scene.get("walls", [])}
    for o in scene.get("openings", []):
        col = "#e07b28" if o["type"] == "door" else "#2f7fd0"
        if o.get("footprint"):
            x0, y0, x1, y1 = o["footprint"]
        elif o.get("wall") in wall_by_id:
            w = wall_by_id[o["wall"]]
            a, b = o["along"]
            if w["axis"] == "x":
                x0, x1, y0, y1 = a, b, w["y0"], w["y1"]
            else:
                x0, x1, y0, y1 = w["x0"], w["x1"], a, b
        else:
            continue
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor="none",
                     edgecolor=col, linewidth=2.0, zorder=4))
    for c in scene.get("columns", []):
        ax.add_patch(Rectangle((c["x"], c["y"]), c["w"], c["d"],
                     facecolor="#8a8f96", edgecolor="none", zorder=3))
    ax.set_title(title, fontsize=11)
    ax.set_aspect("equal")
    ax.autoscale_view()
    mw = scene["meta"].get("plan_width_ft", 0)
    md = scene["meta"].get("plan_depth_ft", 0)
    ax.set_xlim(-2, (mw or 40) + 2)
    ax.set_ylim(-2, (md or 40) + 2)
    ax.set_xlabel("ft (doors=orange, windows=blue, columns=gray)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


def main():
    _require("fitz", "PyMuPDF - reads the PDF geometry")
    _require("cv2", "opencv - wall morphology")
    _require("matplotlib", "renders the preview PNGs")
    ap = argparse.ArgumentParser()
    ap.add_argument("--plans", default=os.path.join(REPO, "plans"))
    ap.add_argument("--out", default=os.path.join(REPO, "out", "batch"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    index = read_index(args.plans)

    rows = ["| plan | route | size (ft) | scale | walls | doors (snapped) | windows | cols | warnings |",
            "|---|---|---|---|---|---|---|---|---|"]
    notes = []
    files = sorted(f for f in os.listdir(args.plans)
                   if f.lower().endswith(PLAN_EXTS))
    if not files:
        print("no plan files in", args.plans)
        return
    for f in files:
        name = os.path.splitext(f)[0]
        print("=== %s" % f)
        try:
            scene, route = build_scene(os.path.join(args.plans, f))
        except Exception as e:
            traceback.print_exc()
            rows.append("| %s | ERROR | - | - | - | - | - | - | %s |" % (f, e))
            continue
        if scene is None:
            rows.append("| %s | SKIP | - | - | - | - | - | - | %s |" % (f, route))
            print("   ", route)
            continue
        c = counts(scene)
        meta = scene["meta"]
        sc = meta.get("scale", {})
        size = "%.1f x %.1f" % (meta.get("plan_width_ft", 0), meta.get("plan_depth_ft", 0))
        warn = "; ".join(meta.get("warnings", []))
        rows.append("| %s | %s | %s | %s | %d | %d (%d) | %d | %d | %s |" % (
            f, route, size, sc.get("source", "?"),
            c["walls"], c["doors"], c["doors_snapped"], c["windows"], c["columns"], warn))
        exp = index.get(f.lower())
        if exp:
            notes.append("- **%s** expected: `%s`" % (f, exp))
        json.dump(scene, open(os.path.join(args.out, name + ".scene.json"), "w"), indent=1)
        title = "%s | %s | %s ft | scale=%s | walls=%d doors=%d windows=%d" % (
            f, route, size, sc.get("source", "?"), c["walls"], c["doors"], c["windows"])
        try:
            render_preview(scene, os.path.join(args.out, name + ".png"), title)
        except Exception:
            traceback.print_exc()
        print("    %s ft, walls=%d doors=%d(snap %d) windows=%d cols=%d" % (
            size, c["walls"], c["doors"], c["doors_snapped"], c["windows"], c["columns"]))

    md = "# Batch scorecard\n\n" + "\n".join(rows)
    if notes:
        md += "\n\n## Ground truth (INDEX.txt)\n\n" + "\n".join(notes)
    open(os.path.join(args.out, "scorecard.md"), "w").write(md + "\n")
    print("\nwrote", os.path.join(args.out, "scorecard.md"))


if __name__ == "__main__":
    main()
