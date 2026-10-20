-- Close the public schema to Supabase's Data API (audit SEC-1). Supabase serves `public` through
-- PostgREST and GraphQL to its anon and authenticated roles, whose default privileges grant them
-- every new table; anyone with the publishable key could read and write every row. The backend
-- connects as the table owner, which neither row level security nor these revokes restrict.
--
-- Inner semicolons stay mid-line: the migration runner and tests/conftest.py split statements on a
-- semicolon at the end of a line.

-- Every table gets an ACCESS EXCLUSIVE lock while the previous deployment keeps serving: fail the
-- deploy fast rather than queue the app's queries behind a lock wait
set local lock_timeout = '5s';

-- Every table, alembic_version included. RLS with no policy denies every row to other roles
do $$ declare t text; begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t); end loop; end $$;

-- Plain Postgres (CI, local tests) has no Supabase roles, so their grants are only revoked where
-- they exist
do $$ declare statement text; begin
  if to_regrole('anon') is not null and to_regrole('authenticated') is not null then
    foreach statement in array array[
      'revoke all on all tables in schema public from anon, authenticated',
      'revoke all on all sequences in schema public from anon, authenticated',
      'revoke all on all functions in schema public from anon, authenticated',
      'alter default privileges in schema public revoke all on tables from anon, authenticated',
      'alter default privileges in schema public revoke all on sequences from anon, authenticated',
      'alter default privileges in schema public revoke all on functions from anon, authenticated'
    ] loop execute statement; end loop; end if; end $$;

-- Every role inherits PUBLIC's EXECUTE on new functions, and PostgREST serves functions in public
-- as RPC. A per-schema default can't narrow the global one, so the default is revoked globally
revoke execute on all functions in schema public from public;
alter default privileges revoke execute on functions from public;
