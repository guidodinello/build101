# 0004: Frontend in Next.js on Vercel

- Date: 2026-10-17
- Status: proposed

## Context

The Owner lives in WhatsApp, but some steps need a web page: the onboarding form (uploads, colors, questionnaire), the Instagram connect hand-off, a read-only dashboard, and a WhatsApp simulator for development and as the demo fallback. See [design/web-app.md](../design/web-app.md).

## Decision

Next.js (App Router, TypeScript) with Tailwind CSS and shadcn/ui, deployed on Vercel. It talks to the FastAPI backend over REST; it never talks to the database directly.

## Consequences

- Fits the shared frontend skills in [`.claude/skills/`](../../.claude/skills/README.md) (shadcn, Next.js, Vercel React best practices).
- Two languages in the repo (Python backend, TypeScript frontend); each build track owns one.
- REST types in `frontend/lib/api.ts` were written by hand from [architecture/api.md](../architecture/api.md) for the hackathon; [ADR 0034](0034-zod-api-response-schemas.md) replaced them with Zod schemas that also check each response at runtime.
