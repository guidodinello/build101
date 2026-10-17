# 0005: One backend instance with in-process jobs for the MVP

- Date: 2026-10-17
- Status: proposed

## Context

Generating a post takes 30–60 s (several LLM calls plus image generation), so WhatsApp webhooks must return immediately and the work must run in the background. A real queue (Redis + workers) adds infrastructure that a 2-person, 24h build can't afford to debug. See [architecture/overview.md](../architecture/overview.md#background-jobs).

## Decision

Run **exactly one backend container** (on Railway, [ADR 0017](0017-backend-host-railway.md)). Background jobs run in-process (`asyncio` tasks behind a small `JobRunner` that records each job in a `jobs` table), and messages from the same Business are serialized with an in-memory lock.

## Consequences

- No queue to operate; jobs are visible and debuggable in the database.
- A restart loses running jobs (they are marked failed at startup); no horizontal scaling.
- Job functions are plain `async def job(ctx, payload)` so they can move to a real queue (arq, or a Postgres-based queue) and the locks to Postgres advisory locks without rewriting them.
