-- Reading the Owner's Instagram through our own Meta app (ADR 0028)
alter table social_accounts
  add column access_token     text,
  add column token_expires_at timestamptz;

-- A Business can hold our Meta connection (reads) and a publishing provider's (Zernio) at once
alter table social_accounts drop constraint uq_social_accounts_business_id_platform;
alter table social_accounts
  add constraint uq_social_accounts_business_id_platform_provider unique (business_id, platform, provider);

-- The table holds access tokens: closed to Supabase's anon and authenticated roles. The backend
-- connects as the table owner, which RLS does not apply to.
alter table social_accounts enable row level security;

-- The Instagram media id of an imported image, so a second import skips it
alter table brand_assets add column external_id text;
create unique index uq_brand_assets_business_id_source_external_id
  on brand_assets (business_id, source, external_id) where external_id is not null;

alter table jobs drop constraint ck_jobs_kind;
alter table jobs add constraint ck_jobs_kind check (kind in ('analyze_asset','generate_brand',
  'generate_plan','generate_post','revise_post','redo_slides','publish_post','import_instagram'));
