-- The brand summary and WhatsApp's 24 h window (#204). Free-form messages reach the Owner only
-- within 24 h of their last message, so the backend records when that was, and a summary that
-- can't go out yet waits, unsent, until the Owner's next message.

-- The previous deployment keeps serving while this runs: fail the deploy fast rather than queue
-- the app's queries behind a lock wait
set local lock_timeout = '5s';

alter table businesses add column last_inbound_at timestamptz;

alter table brand_brains add column summary_sent_at timestamptz;

-- Every summary written before this went out when its version was saved: none is left pending
update brand_brains set summary_sent_at = created_at;
