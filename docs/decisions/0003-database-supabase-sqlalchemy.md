# 0003: Database on Supabase Postgres with SQLAlchemy and Alembic

- Date: 2026-10-17
- Status: proposed

## Context

[ADR 0001](0001-backend-python-fastapi.md) left the database and ORM open. The MVP needs relational state (businesses, posts, plans, conversation history, jobs), file storage for logos, photos and rendered posts, and a free tier that two people can set up in minutes for a 24h hackathon. The data model is in [architecture/data-model.md](../architecture/data-model.md).

## Decision

- **PostgreSQL on Supabase** (free tier), plus **Supabase Storage** for files (private `assets` bucket, public `renders` bucket).
- **SQLAlchemy 2 (async) + asyncpg** in the backend; the backend is the only database client: it connects as the table owner, and every table has RLS on, with no policies and no grants for Supabase's Data API roles (amended 2026-10-20 by migration `0007`, was "service role key, RLS off for the demo": Supabase serves `public` to anyone with the publishable key whether or not a client uses it; 2026-10-19 audit, finding SEC-1). The service role key is only for Storage.
- **Alembic** migrations from the first commit; the schema in data-model.md is the initial migration. Schema conventions follow [`.claude/rules/database.md`](../../.claude/rules/database.md).
- UUID primary keys, because row IDs travel in WhatsApp button payloads and web URLs, where sequential IDs would be guessable; table volumes are tiny.

## Consequences

- One vendor for database and storage; Supabase Auth and RLS remain available if a client ever talks to the database directly (it would first need RLS policies and grants for its role; amended 2026-10-20, was "turn RLS on first").
- Connect through the **session pooler** (the transaction pooler breaks asyncpg prepared statements unless the statement cache is disabled).
- Moving off Supabase later is a plain Postgres dump plus replacing the storage client.
