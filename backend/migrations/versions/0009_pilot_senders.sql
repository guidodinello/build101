-- The closed pilot (#186): the WhatsApp numbers that may onboard, chat and publish. The team adds
-- and removes them by hand in the Supabase SQL editor, so no deploy is needed; the backend reads
-- the table at most once a minute. Digits only, with the country code: a delete by those digits
-- can't then miss a row written another way ('+598 99 ...') and leave the number in.
create table pilot_senders (
  phone       text not null,
  created_at  timestamptz not null default now(),
  constraint pilot_senders_pkey primary key (phone),
  constraint ck_pilot_senders_phone_digits check (phone ~ '^[0-9]{8,15}$')
);

-- Closed to Supabase's anon and authenticated roles like every table (migration 0007); the backend
-- connects as the table owner, which RLS does not apply to.
alter table pilot_senders enable row level security;
