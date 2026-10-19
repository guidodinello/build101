-- Durable webhook dedupe (#105): one row per WhatsApp message id the webhook accepted.
-- messages.external_id can't serve: the webhook has no business_id yet and nothing writes messages.
create table inbound_deliveries (
  external_id  text not null,
  received_at  timestamptz not null default now(),
  constraint inbound_deliveries_pkey primary key (external_id)
);
create index ix_inbound_deliveries_received_at on inbound_deliveries (received_at);

-- Closed to Supabase's anon and authenticated roles; the backend connects as the table owner,
-- which RLS does not apply to (same as social_accounts, migration 0002).
alter table inbound_deliveries enable row level security;
