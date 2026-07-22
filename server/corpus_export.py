"""Export the logged corpus into ML TRAINING PAIRS.

    python corpus_export.py [outdir]        (default ./corpus)

Pulls every logged parse from Supabase and writes, per plan:
    corpus/<id>.json    — the labels (full scene: walls, rooms, openings, meta)
    corpus/<id>.<ext>   — the original uploaded plan file (when STORE_UPLOADS
                          was on for that parse)
plus corpus/manifest.jsonl (one line per pair: id, files, metrics, quality).

This is the collection half of the ML flywheel: no training here — it just
turns everyday product usage into a dataset that's READY when you are.
Needs SUPABASE_URL + SUPABASE_KEY (service role) in env / server/.env.
"""
import json
import os
import sys


def _client():
    import httpx
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "")
    if not (url and key):
        sys.exit("set SUPABASE_URL and SUPABASE_KEY (see docs/SUPABASE.md)")
    return httpx.Client(base_url=url, timeout=30.0,
                        headers={"apikey": key, "Authorization": f"Bearer {key}"})


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "corpus"
    os.makedirs(outdir, exist_ok=True)
    table = os.environ.get("SUPABASE_TABLE", "parses")
    bucket = os.environ.get("SUPABASE_BUCKET", "plans")

    with _client() as c:
        rows, page, step = [], 0, 500
        while True:
            r = c.get(f"/rest/v1/{table}",
                      params={"select": "*", "order": "created_at.asc",
                              "limit": step, "offset": page * step})
            r.raise_for_status()
            batch = r.json()
            rows += batch
            if len(batch) < step:
                break
            page += 1
        print(f"{len(rows)} logged parses")

        manifest = []
        got_files = 0
        for row in rows:
            rid = row.get("id") or row.get("scene_hash") or f"row{len(manifest)}"
            label_path = os.path.join(outdir, f"{rid}.json")
            with open(label_path, "w") as f:
                json.dump(row.get("scene") or {}, f)
            entry = {"id": rid, "labels": os.path.basename(label_path),
                     "ok": row.get("ok"), "reader": (row.get("scene") or {})
                     .get("meta", {}).get("reader"),
                     "doors": row.get("doors"), "rooms": row.get("rooms"),
                     "filename": row.get("filename")}
            fp = row.get("file_path")
            if fp:
                fr = c.get(f"/storage/v1/object/{bucket}/{fp}")
                if fr.status_code == 200:
                    ext = os.path.splitext(fp)[1] or ".bin"
                    plan_path = os.path.join(outdir, f"{rid}{ext}")
                    with open(plan_path, "wb") as f:
                        f.write(fr.content)
                    entry["input"] = os.path.basename(plan_path)
                    got_files += 1
            manifest.append(entry)

        with open(os.path.join(outdir, "manifest.jsonl"), "w") as f:
            for e in manifest:
                f.write(json.dumps(e) + "\n")

    print(f"exported {len(manifest)} label sets, {got_files} with input files "
          f"-> {outdir}/ (manifest.jsonl)")
    print("pairs with BOTH input+labels are training-ready; label-only rows "
          "still document behaviour.")


if __name__ == "__main__":
    main()
