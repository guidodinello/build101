# Architecture

How the MVP is built: components, agents, data, APIs and external integrations. These docs are the contracts the two build tracks implement against.

| File | What it covers | Date |
|---|---|---|
| [overview.md](overview.md) | System context, backend modules, request lifecycles (WhatsApp message, web upload), background jobs, deployment, security, repo layout | 2026-10-17 |
| [agents.md](agents.md) | Brand Brain schema, each specialist agent's input/output, orchestrator loop and tools, LLM conventions | 2026-10-17 |
| [data-model.md](data-model.md) | PostgreSQL schema and conventions, including the Catalog, Brand assets and Offers | 2026-10-17 |
| [api.md](api.md) | REST endpoints (wizard, uploads, dashboard), webhooks, button IDs, internal module interfaces | 2026-10-17 |
| [integrations.md](integrations.md) | WhatsApp Cloud API, Zernio (images and Reels), Claude API, Supabase (incl. browser uploads), ffmpeg video processing, the HTML renderer | 2026-10-17 |
