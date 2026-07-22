# Supabase parse logging — setup (10 min)

Every successful (and failed) parse is logged to a Postgres table: headline
metrics + the full scene JSON. This builds a data corpus for future ML and a
production error log. Logging is **off until you add keys**, so nothing breaks
if you skip this.

## 1. Create the project
1. Go to https://supabase.com → sign in → **New project**.
2. Name it (e.g. `drishti`), set a database password, pick a region near you.
3. Wait ~2 min for it to provision.

## 2. Create the table
1. In the project, open **SQL Editor** → **New query**.
2. Paste the entire contents of `server/schema.sql` and click **Run**.
3. You should see the `parses` table under **Table Editor**.

## 3. Get your keys
1. Open **Project Settings → API**.
2. Copy the **Project URL** (e.g. `https://abcdxyz.supabase.co`).
3. Copy the **`service_role`** key (NOT the `anon` key). This is server-side
   only — it must never appear in the frontend or a public repo.

## 4. Wire it into the backend
In `server/.env` (create it from `.env.example` if needed):
```
SUPABASE_URL=https://abcdxyz.supabase.co
SUPABASE_KEY=<your service_role key>
```
Restart uvicorn. That's it — the next upload writes a row.

On Render, set the same two vars under **Environment** (not in code).

## 5. Verify
Upload any plan, then in Supabase **Table Editor → parses** you'll see a row with
the envelope, door/window/room counts, scale source, warnings, timing, and the
full scene JSON.

## What's stored (one row per parse)
`filename, scene_hash, ok, error, width_ft_override, source, plan_width_ft,
plan_depth_ft, doors, windows, rooms, scale_source, ppf, wing_count,
duration_ms, warnings, scene(jsonb), created_at`.

`scene_hash` is a fingerprint of the result — re-uploading the same plan with the
same settings produces the same hash, so you can dedupe.

## Safety notes
- Row-level security is **enabled** with no public policies: even if the `anon`
  key leaks, the corpus can't be read by the public.
- Logging is fire-and-forget: a Supabase outage or a bad key can **never** slow
  down or fail a parse — errors are logged to the server console and swallowed.
- To turn logging off, blank out `SUPABASE_URL`/`SUPABASE_KEY` and restart.

## ML data pipeline (optional but recommended)
To also archive every uploaded plan FILE (the training input for the future
custom model), do two extra things:
1. In Supabase: **Storage -> New bucket** named `plans` (private).
2. In `server/.env` add: `STORE_UPLOADS=1`
From then on each parse stores the plan file + its labels. Build the
training-ready dataset anytime with:
```
python corpus_export.py          # -> corpus/ with (input, labels) pairs + manifest
```
Re-running schema.sql after updates is safe (`create table if not exists`); for
an existing table add the new column once:
```
alter table public.parses add column if not exists file_path text;
```
