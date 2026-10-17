# build101

An AI marketing agency that lives in the small business owner's WhatsApp. The owner answers a few questions about their business. A team of specialized AI agents then plans, designs and publishes their Instagram content, and nothing goes out without the owner's "Aprobar".

> Status: **MVP specified, ready to build** (24h hackathon, 2 builders). Start in [`docs/`](docs/README.md).

## Repository layout

| Path | What lives there |
|---|---|
| [`docs/`](docs/) | Product, architecture, design and implementation docs ([reading order](docs/README.md)) |
| [`backend/`](backend/) | FastAPI: WhatsApp webhook, orchestrator, agents, jobs, renderer, publishing |
| [`frontend/`](frontend/) | Next.js: onboarding wizard, dashboard, WhatsApp simulator |
| [`.github/`](.github/) | Issue and PR templates, CI and Tenki review workflows, Dependabot |
| [`scripts/`](scripts/) | Repo tooling, e.g. the docs index check CI runs |
| [`.claude/skills/`](.claude/skills/) | Shared agent skills: grilling, domain modeling, issues, PR review, dependencies, docs conventions |
| [`.claude/rules/`](.claude/rules/) | Path-scoped agent rules (Python, database, Docker, CI) that load when matching files are touched |
| [`AGENTS.md`](AGENTS.md) | How we work: the shared workflow and conventions, for humans and any AI tool |

## Stack

Python 3.13 · FastAPI · Claude API (`claude-opus-5-5`) · WhatsApp Cloud API · Zernio (Instagram publishing) · Supabase (Postgres + Storage) · Playwright (image rendering) · Next.js · Tailwind · shadcn/ui · Vercel.

## How we work

Read [`AGENTS.md`](AGENTS.md): one workflow (capture, research, decide, plan, build, review, close the loop) that keeps what we learn in [`docs/`](docs/README.md). It applies whether you use Claude Code, another AI tool, or none.

For the MVP build, work from [docs/implementation/tasks.md](docs/implementation/tasks.md) (one task ≈ one small PR) and set up locally with [docs/implementation/setup.md](docs/implementation/setup.md).
