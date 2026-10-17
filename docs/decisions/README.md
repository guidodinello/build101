# Decisions

One short file per decision: `NNNN-short-title.md` (e.g. `0001-demo-channel.md`). Number sequentially from the highest existing file; the first is `0001`. Guidance on when a decision deserves a record: [ADR-FORMAT.md](../../.claude/skills/domain-modeling/ADR-FORMAT.md).

```md
# NNNN: Title

- Date: YYYY-MM-DD
- Status: proposed | accepted | superseded

## Context
## Decision
## Consequences
```

When an ADR is superseded, set its Status to `superseded`, add `- Superseded by: [NNNN](NNNN-short-title.md)` under it, and link back from the new ADR's Context.

## Index

| ADR | Title | Status | Date |
|---|---|---|---|
| [0001](0001-backend-python-fastapi.md) | Backend in Python + FastAPI | accepted | 2026-10-17 |
| [0002](0002-whatsapp-cloud-api-channel.md) | WhatsApp as the channel from day one | proposed | 2026-10-17 |
| [0003](0003-database-supabase-sqlalchemy.md) | Database on Supabase Postgres with SQLAlchemy and Alembic | proposed | 2026-10-17 |
| [0004](0004-frontend-nextjs-vercel.md) | Frontend in Next.js on Vercel | proposed | 2026-10-17 |
| [0005](0005-single-instance-in-process-jobs.md) | One backend instance with in-process jobs for the MVP | proposed | 2026-10-17 |
| [0006](0006-fixed-agent-catalog-brand-brain.md) | Fixed agent catalog personalized by a Brand Brain | proposed | 2026-10-17 |
| [0007](0007-approve-every-post.md) | Every post needs explicit approval | proposed | 2026-10-17 |
| [0008](0008-publishing-via-zernio.md) | Publish through Zernio | proposed | 2026-10-17 |
| [0009](0009-branded-templates-over-real-photos.md) | Branded HTML templates over the Owner's real photos | proposed | 2026-10-17 |
| [0010](0010-anthropic-sdk-own-orchestration.md) | Anthropic SDK with our own orchestration | proposed | 2026-10-17 |
| [0011](0011-hybrid-onboarding.md) | Hybrid onboarding (WhatsApp + magic-link web form) | proposed | 2026-10-17 |
| [0012](0012-catalog-content-dashboard-reels.md) | Catalog and content dashboard, with Reels from the Owner's videos | proposed | 2026-10-17 |
| [0013](0013-focus-marketing.md) | Focus the MVP on marketing and social media | proposed | 2026-10-17 |
| [0014](0014-whatsapp-cloud-api.md) | WhatsApp via the official Cloud API | proposed | 2026-10-17 |
| [0015](0015-instagram-login.md) | Connect Instagram through Instagram Login | proposed | 2026-10-17 |
| [0016](0016-demo-scope-one-post.md) | Demo scope is one post, from request to published | proposed | 2026-10-17 |
