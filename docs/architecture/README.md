# Architecture

How the MVP is built: components, agents, data, APIs and external integrations. These docs are the contracts the two build tracks implement against.

| File | What it covers | Date |
|---|---|---|
| [how-it-works.md](how-it-works.md) | How the built system fits together today: Kapso webhook to orchestrator, Gemini agents and tool loop, post generation, Zernio publishing, onboarding jobs, what is lost on restart | 2026-10-19 |
| [overview.md](overview.md) | System context, backend modules, request lifecycles (WhatsApp message, web upload), background jobs, deployment, security, repo layout | 2026-10-17 |
| [agents.md](agents.md) | Brand Brain schema, each specialist agent's input/output, orchestrator loop and tools, LLM conventions | 2026-10-17 |
| [data-model.md](data-model.md) | PostgreSQL schema and conventions, including the Catalog, Brand assets, Offers and post Variations | 2026-10-17 |
| [api.md](api.md) | REST endpoints (wizard, uploads, dashboard), webhooks, button IDs, internal module interfaces | 2026-10-17 |
| [integrations.md](integrations.md) | WhatsApp through Kapso (Meta Cloud API direct as plan B), Zernio (images and Reels), Gemini API (text), Supabase (incl. browser uploads), ffmpeg video processing, AI image generation (Gemini, OpenAI fallback) | 2026-10-17 |
