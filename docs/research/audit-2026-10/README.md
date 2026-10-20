# Product and codebase audit (2026-10-19)

An audit of Neitor AI's product and code, read at commit `dc0bc01` on 2026-10-19. It covers 12 dimensions and holds 225 verified findings: 3 critical, 27 high, 110 medium and 85 low. An independent adversarial reviewer checked every finding against the code and the cited sources; "adjusted" means the reviewer corrected its severity or details, and the docs already show the corrected version. Findings are recommendations, not decisions: anything that changes what we build goes through an ADR ([decisions/](../../decisions/README.md)) and issues. The new unknowns the audit raised are in [open-questions.md](../../open-questions.md#from-the-2026-10-19-audit).

Each finding has an id whose prefix names its doc (COST, MOD, AIQ, PRD, GRW, ARCH, BUG, SEC, FE, OPS, DOC, GAP), a severity, an effort (S is under half a day, M is 1-2 days, L is about a week, XL is more than a week), a confidence level, inline evidence and, where findings overlap, links to the related ids in other docs.

Start at [summary.md](summary.md): the cross-dimension synthesis with the executive summary, the P0 and P1 fix lists, a digest of each dimension and the 2-week, 30-day and 90-day roadmap.

| If you want… | Start at |
|---|---|
| What blocks the pilot, and the prioritized plan | [summary.md](summary.md), then the [production readiness checklist](platform-ops.md#production-readiness-checklist) in platform-ops.md |
| Cost per Owner, gross margin and the levers that cut it | [unit-economics.md](unit-economics.md) |
| Which model each agent should run on, before the 2027-01-01 Gemini price change | [models.md](models.md) |
| Orchestrator and agent quality, factual guarantees, an eval harness | [ai-quality.md](ai-quality.md) |
| What the Owner experiences, MVP gaps and new features | [product.md](product.md) |
| Competitors, pricing and packaging, go-to-market and metrics | [growth-pricing-market.md](growth-pricing-market.md) |
| Durable state, the job runner, configuration and code health | [backend-architecture.md](backend-architecture.md) |
| Concrete bugs, with the scenario in which an Owner hits each one | [bugs-reliability.md](bugs-reliability.md) |
| Supabase access, privacy law (Ley 18.331, URCDP), Meta and WhatsApp policy | [security-privacy.md](security-privacy.md) |
| The landing, the onboarding wizard and the Takumi render route | [frontend.md](frontend.md) |
| Hosting plans, deploys, monitoring, backups, CI and tests | [platform-ops.md](platform-ops.md) |
| Where docs contradict the code, ADR hygiene, the PR and review process | [docs-process.md](docs-process.md) |
| One Instagram connection (Zernio or our Meta app), third-party terms, legal entity and IVA | [cross-cutting-gaps.md](cross-cutting-gaps.md) |
| Which findings are fixed or in flight since the audit | [status.md](status.md) |
| What is still unknown and needs a decision or a check | [open-questions.md](../../open-questions.md#from-the-2026-10-19-audit) |

| File | What it covers | Findings | Date |
|---|---|---|---|
| [summary.md](summary.md) | Cross-dimension synthesis: executive summary, P0 and P1 fix lists, a digest of each dimension, roadmap and how the audit was done. Start here | 225 (merged) | 2026-10-19 |
| [status.md](status.md) | Which findings the PRs merged or opened after the audit fixed, partly fixed or have in flight, and what remains of each | 38 of 225 | 2026-10-20 |
| [unit-economics.md](unit-economics.md) | COST: cost per Owner (text models, scene images, WhatsApp messages, Zernio, platform plans), gross margin at the ADR 0031 prices, savings levers, Zernio or our own Meta app | 17 (2 high, 8 medium, 7 low) | 2026-10-19 |
| [models.md](models.md) | MOD: the model for each agent, scene images and voice transcription, compared on price, quality, latency and migration risk | 17 (1 high, 8 medium, 8 low) | 2026-10-19 |
| [ai-quality.md](ai-quality.md) | AIQ: the Orchestrator and its agents (prompt quality, factual guarantees, evals, traceability, latency, model cost), plus a proposed eval harness | 21 (2 high, 12 medium, 7 low) | 2026-10-19 |
| [product.md](product.md) | PRD: the Owner's experience from the first WhatsApp message to a published Post, MVP scope against the code, new features for the persona | 24 (2 critical, 2 high, 14 medium, 6 low) | 2026-10-19 |
| [growth-pricing-market.md](growth-pricing-market.md) | GRW: positioning against competitors (Postou.ai, Pomelli, Meta Business Agent), pricing and packaging, go-to-market, retention, attribution and platform risk | 19 (3 high, 12 medium, 4 low) | 2026-10-19 |
| [backend-architecture.md](backend-architecture.md) | ARCH: backend structure, durability, configuration, data model and code health, with a phased path to durable state | 19 (3 high, 9 medium, 7 low) | 2026-10-19 |
| [bugs-reliability.md](bugs-reliability.md) | BUG: concrete backend bugs and reliability failures, the scenario in which an Owner hits each one, and the fix | 20 (3 high, 7 medium, 10 low) | 2026-10-19 |
| [security-privacy.md](security-privacy.md) | SEC: security checks, cost of abuse, and the compliance requirements of Ley 18.331, Meta Platform Terms and WhatsApp policy | 19 (3 high, 4 medium, 12 low) | 2026-10-19 |
| [frontend.md](frontend.md) | FE: the public landing, the onboarding wizard (`/o/[token]`) and the Takumi render route | 19 (2 high, 9 medium, 8 low) | 2026-10-19 |
| [platform-ops.md](platform-ops.md) | OPS: hosting, deploys, durability, monitoring, backups, environments, CI and tests, with a production readiness checklist | 17 (1 critical, 4 high, 10 medium, 2 low) | 2026-10-19 |
| [docs-process.md](docs-process.md) | DOC: how well `docs/`, the ADRs, agent instructions and the engineering workflow match the running system, and what a pilot still needs | 21 (1 high, 12 medium, 8 low) | 2026-10-19 |
| [cross-cutting-gaps.md](cross-cutting-gaps.md) | GAP: what fell between the other dimensions, such as one Instagram connection, third-party terms, Meta's messaging rules, legal entity, IVA and consent | 12 (1 high, 5 medium, 6 low) | 2026-10-19 |
