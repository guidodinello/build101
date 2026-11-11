-- The agent run ledger (T10, #205): one agent_runs row per model call, with what it used and an
-- estimated cost, so the team can say what a Business, an agent or a Post costs. Rows are
-- written by app/llm/ledger.py and never updated.

-- The previous deployment keeps serving while this runs: fail the deploy fast rather than queue
-- the app's queries behind a lock wait
set local lock_timeout = '5s';

-- post_id has no foreign key: Posts live in memory until #181, with an 8-character id.
-- cost_usd is null when the call failed or its model or image size has no price
-- (app/llm/prices.py); input_tokens includes cache_read_tokens, output_tokens excludes
-- thought_tokens.
alter table agent_runs
  add column post_id        text,
  add column service_tier   text,
  add column thought_tokens int,
  add column image_size     text,
  add column image_count    int,
  add column video_seconds  int,
  add column cost_usd       numeric(12, 6);

create index ix_agent_runs_created_at on agent_runs (created_at);

-- The views run with the querying role's rights (security_invoker), so row level security on
-- agent_runs still closes them to Supabase's Data API roles (migration 0007).

-- Cost per Business per day, in the Business's timezone. Niche Report runs have no Business.
create view agent_run_costs_daily with (security_invoker = true) as
select
  r.business_id,
  (r.created_at at time zone b.timezone)::date as day,
  count(*) as runs,
  count(r.error) as failed_runs,
  count(*) filter (where r.error is null and r.cost_usd is null) as unpriced_runs,
  coalesce(sum(r.cost_usd), 0) as cost_usd
from agent_runs r
join businesses b on b.id = r.business_id
group by r.business_id, day;

-- Cost per Business per calendar month, in the Business's timezone
create view agent_run_costs_monthly with (security_invoker = true) as
select
  r.business_id,
  date_trunc('month', r.created_at at time zone b.timezone)::date as month,
  count(*) as runs,
  count(r.error) as failed_runs,
  count(*) filter (where r.error is null and r.cost_usd is null) as unpriced_runs,
  coalesce(sum(r.cost_usd), 0) as cost_usd
from agent_runs r
join businesses b on b.id = r.business_id
group by r.business_id, month;

-- Cost per agent and model per day (UTC), Niche Report runs included
create view agent_run_costs_by_agent with (security_invoker = true) as
select
  r.agent,
  r.model,
  (r.created_at at time zone 'UTC')::date as day,
  count(*) as runs,
  count(r.error) as failed_runs,
  coalesce(sum(r.cost_usd), 0) as cost_usd,
  round(avg(r.latency_ms)) as avg_latency_ms
from agent_runs r
group by r.agent, r.model, day;

-- The share of input tokens Gemini served from its implicit cache, per agent and model per day
-- (UTC). Null for a day whose calls reported no input tokens.
create view agent_run_cache_hits with (security_invoker = true) as
select
  r.agent,
  r.model,
  (r.created_at at time zone 'UTC')::date as day,
  coalesce(sum(r.input_tokens), 0) as input_tokens,
  coalesce(sum(r.cache_read_tokens), 0) as cache_read_tokens,
  round(
    coalesce(sum(r.cache_read_tokens), 0)::numeric / nullif(sum(r.input_tokens), 0), 4
  ) as cache_hit_rate
from agent_runs r
where r.error is null and r.input_tokens is not null
group by r.agent, r.model, day;
