# 0005: One backend instance with in-process jobs for the MVP

- Date: 2026-10-17
- Status: proposed

## Context

Generating a post takes 30–60 s (several LLM calls plus image generation), so WhatsApp webhooks must return immediately and the work must run in the background. A real queue (Redis + workers) adds infrastructure that a 2-person, 24h build can't afford to debug. See [architecture/overview.md](../architecture/overview.md#background-jobs).

## Decision

Run **exactly one backend container** (on Railway, [ADR 0017](0017-backend-host-railway.md)). Background jobs run in-process (`asyncio` tasks behind a small `JobRunner` that records each job in a `jobs` table), and messages from the same Business are serialized with an in-memory lock.

## Consequences

- No queue to operate; jobs are visible and debuggable in the database.
- A restart loses running jobs (they are marked failed at startup); no horizontal scaling. Amended 2026-10-20 ([#178](https://github.com/guidodinello/build101/issues/178)): a restart still stops running jobs, but they are no longer dropped silently. A job the shutdown cancels, or a dead process leaves `running`, starts over once if it is safe to repeat (the brand job, a photo analysis); interrupted again, or of another kind (the Instagram import), it fails, and a brand job then tells the Owner with Reintentar as an ordinary failure does. At startup a Business still stuck in `generating_brand` gets a new brand job. The count lives in `jobs.attempts`, so it survives the restart ([overview.md § Background jobs](../architecture/overview.md#background-jobs)).
- Job functions are plain `async def job(ctx, payload)` so they can move to a real queue (arq, or a Postgres-based queue) and the locks to Postgres advisory locks without rewriting them.
