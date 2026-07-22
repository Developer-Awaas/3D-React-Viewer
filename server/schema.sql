-- Drishti parse log — run once in the Supabase SQL editor (see docs/SUPABASE.md).
-- Stores one row per parse: headline metrics + the full scene JSON, so the data
-- doubles as a training corpus and a production error log.

create table if not exists public.parses (
  id                uuid primary key default gen_random_uuid(),
  created_at        timestamptz not null default now(),
  filename          text,
  scene_hash        text,                 -- sha256 of the scene JSON; dedupes re-uploads
  ok                boolean not null default true,
  error             text,                 -- populated when a parse fails
  width_ft_override real,
  source            text,                 -- vector_pdf_layers | vector_pdf_geometry | cad | raster
  plan_width_ft     real,
  plan_depth_ft     real,
  doors             int,
  windows           int,
  rooms             int,
  scale_source      text,                 -- dimension_text | column_box_12in | assumed_width | cad_units
  ppf               real,                 -- points per foot
  wing_count        int,
  duration_ms       int,
  warnings          jsonb,
  file_path         text,                 -- Supabase Storage path of the uploaded plan (STORE_UPLOADS=1)
  scene             jsonb                 -- the full canonical scene (walls, openings, rooms, meta)
);

create index if not exists parses_created_at_idx on public.parses (created_at desc);
create index if not exists parses_scene_hash_idx on public.parses (scene_hash);
create index if not exists parses_source_idx     on public.parses (source);

-- The backend writes with the SERVICE ROLE key (server-side only, never shipped
-- to the browser), which bypasses row-level security. Enable RLS so that even if
-- the anon key leaks, the public cannot read the corpus.
alter table public.parses enable row level security;
-- (No anon policies added on purpose: anon/public gets no access.)
