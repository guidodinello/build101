-- The weekly Niche Report of each niche (ADR 0025), written by the generate_niche_report job and
-- read by every Business in that niche. app/agents/data/niches.py holds the niches, so niche_id
-- is a plain text key, not a foreign key

create table niche_reports (
  id           uuid primary key default gen_random_uuid(),
  niche_id     text not null,                         -- app/agents/data/niches.py, e.g. 'curated-wood-furniture-uy'
  week_start   date not null,                         -- Monday, in the niche's timezone
  report       jsonb not null,                        -- NicheReport (agents.md § Niche Analyst)
  created_at   timestamptz not null default now(),
  constraint uq_niche_reports_niche_id_week_start unique (niche_id, week_start)
);

-- A generate_niche_report job has no Business (jobs.business_id is null): payload {"niche_id": ...}
alter table jobs drop constraint ck_jobs_kind;
alter table jobs add constraint ck_jobs_kind check (kind in ('analyze_asset','generate_brand',
  'generate_plan','generate_post','revise_post','redo_slides','publish_post','import_instagram',
  'generate_niche_report'));
