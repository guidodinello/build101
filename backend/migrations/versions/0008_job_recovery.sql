-- Recovering jobs a restart interrupts (#178). An interrupted job that is safe to repeat goes back
-- to the queue once, so the count has to survive the restart; and a Business stuck generating its
-- brand gets a new brand job at startup, unless its Owner already has a Reintentar to tap.

-- The previous deployment keeps serving while this runs: fail the deploy fast rather than queue
-- the app's queries behind a lock wait
set local lock_timeout = '5s';

alter table jobs
  add column attempts          int not null default 0,
  add column retry_offered_at  timestamptz,
  add constraint ck_jobs_attempts_not_negative check (attempts >= 0);

-- Every job claimed before this ran once
update jobs set attempts = 1 where started_at is not null;

-- Until now the runner sent the failure message with Reintentar for every failed brand job of a
-- WhatsApp Business (a failed send was only logged), except the ones it failed as stale
update jobs set retry_offered_at = jobs.finished_at
  from businesses
  where businesses.id = jobs.business_id
    and businesses.channel = 'whatsapp'
    and jobs.kind = 'generate_brand'
    and jobs.status = 'failed'
    and jobs.error is distinct from 'interrupted by a restart';
