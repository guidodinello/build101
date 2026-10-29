# Docs

Everything needed to build the MVP: an AI marketing agency for small business owners that lives in WhatsApp.

## Reading order

**New to the project?** Read 1–3. **Implementing?** Read your task in [implementation/tasks.md](implementation/tasks.md) and the docs it links.

1. [idea.md](idea.md): problem, user, value proposition
2. [product/mvp.md](product/mvp.md): scope, priorities (MoSCoW), success criteria, demo fallbacks
3. [product/user-flows.md](product/user-flows.md): state machines and every flow, step by step
4. [product/conversation-design.md](product/conversation-design.md): bot persona, writing rules, copy deck, system prompt skeleton
5. [architecture/overview.md](architecture/overview.md): components, request lifecycle, jobs, deployment, repo layout
6. [architecture/agents.md](architecture/agents.md): Brand Brain, each agent's I/O, orchestrator tools, LLM conventions
7. [architecture/data-model.md](architecture/data-model.md): Postgres schema
8. [architecture/api.md](architecture/api.md): REST endpoints, webhooks, button IDs, internal interfaces
9. [architecture/integrations.md](architecture/integrations.md): WhatsApp (Kapso), Zernio, Gemini (text), image generation, Supabase
10. [design/web-app.md](design/web-app.md): onboarding wizard, dashboard, chat simulator
11. [implementation/plan.md](implementation/plan.md): 24h timeline, tracks, pre-hackathon checklist, risks
12. [implementation/tasks.md](implementation/tasks.md): task-by-task breakdown with acceptance criteria
13. [implementation/setup.md](implementation/setup.md): env vars, local run, deploy
14. [product/demo-script.md](product/demo-script.md): the 4-minute demo

## Folders

- **[product/](product/README.md)**: what the MVP does and how it behaves.
- **[architecture/](architecture/README.md)**: components, agents, data model, API and integrations.
- **[design/](design/README.md)**: web app design (the post templates are superseded by AI-generated images, [ADR 0018](decisions/0018-ai-image-generation-service.md)).
- **[implementation/](implementation/README.md)**: 24h plan, tasks and setup.
- **[operations/](operations/README.md)**: keeping production working for pilot Owners: the support runbook.
- **[research/](research/README.md)**: investigations behind the decisions.
- **[decisions/](decisions/README.md)**: ADRs.

## Other files

Every folder here has a `README.md` index; start from this page and follow the links. Conventions: [docs-index skill](../.claude/skills/docs-index/SKILL.md).

| Path | Purpose |
|---|---|
| [competitors.md](competitors.md) | Landscape summary and where the gap is (deep dives go in research/) |
| [open-questions.md](open-questions.md) | Risks and unknowns to resolve |
| [roadmap.md](roadmap.md) | Phases from hackathon demo to product, launch pricing |
| [demo-plan.md](demo-plan.md) | Early demo plan (superseded by product/demo-script.md) |
| [glossary.md](glossary.md) | Shared domain language (draft) |
| [workflow.md](workflow.md) | How we take a task to merged: Claude Code plan mode, auto mode, PR, Tenki review, merge |
| [research/](research/README.md) | Investigations, spikes, competitor/market/tech research |
| [decisions/](decisions/README.md) | Short records of decisions we made and why (ADRs) |
