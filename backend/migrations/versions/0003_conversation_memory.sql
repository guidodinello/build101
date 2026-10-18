-- The orchestrator's memory (ADR 0030): its history, a summary of the turns cut from it, and
-- the facts the Owner asked it to keep.

create table conversation_steps (
  id           bigint generated always as identity primary key,
  business_id  uuid not null constraint conversation_steps_business_id_fkey references businesses(id) on delete cascade,
  step         jsonb not null,                        -- one Interactions API step, resent unchanged (thought signatures included)
  created_at   timestamptz not null default now()
);
create index ix_conversation_steps_business_id_id on conversation_steps (business_id, id);

-- What the orchestrator keeps of the steps compacted out of conversation_steps
alter table businesses add column conversation_summary text;

create table owner_notes (
  id           uuid primary key default gen_random_uuid(),
  business_id  uuid not null constraint owner_notes_business_id_fkey references businesses(id) on delete cascade,
  text         text not null,
  created_at   timestamptz not null default now(),
  archived_at  timestamptz,
  constraint ck_owner_notes_text_not_blank check (length(trim(text)) > 0)
);
create index ix_owner_notes_business_id on owner_notes (business_id) where archived_at is null;
