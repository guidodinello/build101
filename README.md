# build101

An AI marketing agency that lives in the small business owner's WhatsApp. The owner answers a few questions about their business. A team of specialized AI agents then plans, designs and publishes their Instagram content, and nothing goes out without the owner's "Aprobar".

> Status: **MVP in progress** (24h hackathon, 2 builders). Working end to end: onboarding (started from WhatsApp, finished in the web wizard), post and carousel creation from the chat with Gemini text and images, and approve-and-publish to Instagram through Zernio. Still to build: the dashboard, the WhatsApp simulator and the weekly plan. Start in [`docs/`](docs/README.md).

## Live

| What | Where |
|---|---|
| Frontend (Vercel) | <https://neitorai.vercel.app> |
| Backend (Railway) | <https://backend-production-6e67.up.railway.app> |
| WhatsApp bot (Kapso sandbox) | <https://wa.me/56920403095> |

## Repository layout

| Path | What lives there |
|---|---|
| [`docs/`](docs/) | Product, architecture, design and implementation docs ([reading order](docs/README.md)) |
| [`backend/`](backend/README.md) | FastAPI: Kapso WhatsApp channel, conversation orchestrator, agents, in-process jobs, Gemini text and image generation, carousels, onboarding, Zernio publishing, Alembic migrations |
| [`frontend/`](frontend/README.md) | Next.js: Neitor AI landing page (`/`), onboarding wizard (`/o/[token]`); dashboard and WhatsApp simulator are planned |
| [`.github/`](.github/) | Issue and PR templates, CI and Tenki review workflows, Dependabot |
| [`scripts/`](scripts/) | Repo tooling: the docs index check CI runs, Orca worktree setup |
| [`.claude/skills/`](.claude/skills/README.md) | Shared agent skills: workflow (grilling, domain modeling, tickets, PR review, docs), frontend, and infrastructure (Supabase, Railway, Vercel) |
| [`.claude/rules/`](.claude/rules/README.md) | Path-scoped agent rules (Python, database, Docker, CI) that load when matching files are touched |
| [`.claude/routines/`](.claude/routines/README.md) | Nightly cloud agents (issue fixer, product research, bug hunt) that open draft PRs |
| [`AGENTS.md`](AGENTS.md) | How we work: the shared workflow and conventions, for humans and any AI tool |

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.13 · FastAPI · SQLAlchemy 2 + asyncpg · Alembic · uv, on Railway ([ADR 0017](docs/decisions/0017-backend-host-railway.md)) |
| Frontend | Next.js 16 · React 19 · Tailwind 4 · shadcn/ui, on Vercel ([ADR 0004](docs/decisions/0004-frontend-nextjs-vercel.md)) |
| Text LLM | Gemini `gemini-3.8-flash` ([ADR 0023](docs/decisions/0023-gemini-text-llm.md)) |
| Images | Gemini `gemini-nano-banana-2.1` ([ADR 0018](docs/decisions/0018-ai-image-generation-service.md), [ADR 0019](docs/decisions/0019-image-provider-gemini.md)) |
| WhatsApp | Kapso ([ADR 0020](docs/decisions/0020-whatsapp-via-kapso.md)); voice notes via Kapso's transcript with Gemini as fallback ([ADR 0021](docs/decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md)) |
| Instagram publishing | Zernio ([ADR 0008](docs/decisions/0008-publishing-via-zernio.md)) |
| Database and files | Supabase Postgres + Storage ([ADR 0003](docs/decisions/0003-database-supabase-sqlalchemy.md)) |

Every decision and its status is in the [ADR index](docs/decisions/README.md).

## Run it locally

Full guide, env vars and accounts: [docs/implementation/setup.md](docs/implementation/setup.md).

```sh
# backend
cd backend && cp .env.example .env
uv sync && uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# frontend
cd frontend && cp .env.example .env.local
npm install && npm run dev
```

Checks before a PR: `uv run ruff check . && uv run pyright && uv run pytest` in `backend/`, `npm run typecheck && npm run lint && npm run build` in `frontend/`.

## How we work

Read [`AGENTS.md`](AGENTS.md): one workflow (capture, research, decide, plan, build, review, close the loop) that keeps what we learn in [`docs/`](docs/README.md). It applies whether you use Claude Code, another AI tool, or none.

For the MVP build, work from [docs/implementation/tasks.md](docs/implementation/tasks.md) (one task ≈ one small PR) and follow the [development workflow](docs/workflow.md).

## License

[AGPL-3.0](LICENSE). Contributions are licensed under the same terms ([ADR 0036](docs/decisions/0036-license-agpl-3.md)).
