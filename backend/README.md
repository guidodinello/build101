# Backend

FastAPI service: WhatsApp webhook, conversation routing, orchestrator + specialist agents (Gemini, [ADR 0023](../docs/decisions/0023-gemini-text-llm.md)), background jobs, AI image generation for Posts and carousels (Gemini, [ADR 0018](../docs/decisions/0018-ai-image-generation-service.md), [ADR 0019](../docs/decisions/0019-image-provider-gemini.md), [ADR 0022](../docs/decisions/0022-carousels-in-mvp.md)) and publishing (Zernio).

- Architecture: [docs/architecture/overview.md](../docs/architecture/overview.md)
- Agents: [docs/architecture/agents.md](../docs/architecture/agents.md)
- API: [docs/architecture/api.md](../docs/architecture/api.md)
- Setup: [docs/implementation/setup.md](../docs/implementation/setup.md)

Stack: **Python + FastAPI**, uv project rooted here ([ADR 0001](../docs/decisions/0001-backend-python-fastapi.md)), with SQLAlchemy 2 (async) + asyncpg, Pydantic v2, `google-genai` and Supabase ([ADR 0003](../docs/decisions/0003-database-supabase-sqlalchemy.md)).

Commands run from this folder (`uv run ruff check .`, `uv run pytest tests/ -v`); see [`.claude/rules/python.md`](../.claude/rules/python.md).

## What exists today

- `app/main.py`: `/health` (`uv run uvicorn app.main:app --reload`).
- `app/imagegen/`: `ImageGenPort` with the Gemini and mock adapters, selected by `IMAGE_GEN`.
- `app/media/images.py`: reference photo normalization and the 1080×1350 resize.
- `app/carousel/`: carousel schemas, slide prompts and `CarouselGenerator` (cover first, other slides anchored on it).
- `app/channels/`: `ChannelPort` with the Kapso adapter, `POST /webhooks/whatsapp` (signature check, dedupe, background handling) and an echo handler until the conversation router (T23) exists.

Generate a carousel from a copy + brief spec without the database or the agents:

```bash
cp .env.example .env   # set IMAGE_GEN=gemini and GEMINI_API_KEY for real calls
uv run python -m app.carousel.cli --spec tests/fixtures/carousel_spec.json \
  --photos ~/demo/photo1.jpg ~/demo/photo2.jpg --out out/carousel [--slides 1]
```

It writes `slide-N.jpg`, each slide's prompt and a `report.json` with latency, raw size and token usage per call. Live tests run with `uv run pytest -m live` (skipped without `GEMINI_API_KEY`).

Write this week's Niche Report ([ADR 0025](../docs/decisions/0025-weekly-niche-report.md)) for a Business in a known niche; set `NICHE_REPORT_PATH=out/niche-report.json` and post generation gets its insights as trend notes:

```bash
uv run python -m app.agents.niche_cli --niche curated-wood-furniture-uy --name "Roble & Co" \
  --category "muebles de madera maciza" --about "Mesas y aparadores a medida" --out out/niche-report.json
```

It needs `GEMINI_API_KEY` from a project with billing (Google Search grounding isn't on the free tier) and takes 30–100 s.

## Deploy

The backend runs on Railway ([ADR 0017](../docs/decisions/0017-backend-host-railway.md)): project `build101`, service `backend`, environment `production`, one replica in `us-east4-eqdc4a` (Virginia; Railway has no South America region). The image is built from [`Dockerfile`](Dockerfile): two stages, uv with `--frozen`, non-root, one uvicorn worker on `0.0.0.0:$PORT` ([ADR 0005](../docs/decisions/0005-single-instance-in-process-jobs.md)).

### How it deploys

- **Push to `main`** builds and deploys the service from the connected GitHub repo.
- **Manual deploy** from the repo root, with the service linked (`railway link`): `railway up --service backend --detach`. Run it from the repo root and not from `backend/`: the service's root directory is `/backend`, so Railway expects the repo layout in the upload.
- Each deploy runs the pre-deploy command, then starts the container; Railway switches traffic only after `/health` answers.

### Service settings

Railway "Config as Code" files (`railway.json`, `railway.toml`) are deprecated and unavailable to new services, so the settings live in the service, not in the repo. They are applied with the Railway CLI or dashboard and must match this table:

| Setting | Value |
|---|---|
| Source | GitHub `guidodinello/build101`, branch `main` |
| Root directory | `/backend` |
| Builder / Dockerfile | Dockerfile, `Dockerfile` |
| Pre-deploy command | `alembic upgrade head` (timeout 300 s) |
| Healthcheck | `/health`, timeout 60 s |
| Restart policy | on failure, up to 10 retries |
| Region / replicas | `us-east4-eqdc4a` × 1 |
| Domain | Railway-generated (`*.up.railway.app`) |

### Environment variables

Set on the service (`railway variable set KEY --stdin --service backend`, value on stdin so it never lands in shell history). Names are in [`.env.example`](.env.example); the values that differ from local:

| Variable | Production value |
|---|---|
| `ENV` | `prod` |
| `PUBLIC_BACKEND_URL` | the Railway domain (`https://<service>.up.railway.app`); the app refuses to start without it while `INBOUND_HANDLER=chat` |
| `DATABASE_URL` | Supabase **session pooler**, port 5432, `postgresql+asyncpg://` (the transaction pooler breaks asyncpg prepared statements, see [ADR 0003](../docs/decisions/0003-database-supabase-sqlalchemy.md)) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | the project URL and its legacy `service_role` JWT (the code sends it as `apikey` and as a Bearer token) |
| `FRONTEND_URL`, `FRONTEND_ORIGINS` | the Vercel domain, `https://build101-khaki.vercel.app` (no `localhost` in production CORS) |
| `WHATSAPP_BOT_NUMBER` | `56920403095`, the shared Kapso sandbox number (only answers phones with an active sandbox session) |
| `ENABLE_DEV_ENDPOINTS`, `DEV_TOKEN` | unset (dev endpoints off) |

Everything else (`GEMINI_*`, `KAPSO_*`, `ZERNIO_*`, `PUBLISHER`, `IMAGE_GEN`, ...) carries the same value as local. Without `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `GEMINI_API_KEY` the app still boots but the job runner is off (the startup log says so).

### Migrations

`alembic upgrade head` runs as the pre-deploy command in a separate container with the service variables. A failing migration fails the deploy and the previous deployment keeps serving. It reads `DATABASE_URL` through the app settings, so `app` must stay importable from the image working directory (`/app`).

### Logs and checks

- `railway logs --service backend` (deploy logs) and `railway logs --service backend --build` (build logs).
- `curl -sS https://<service>.up.railway.app/health` returns `{"status":"ok"}`.
- Pre-deploy output shows up in the deploy logs of the new deployment; `Running upgrade ...` lines appear only when a migration was pending.
- uvicorn and the app log to stderr, so Railway tags every line `level=error`, including the normal `INFO` ones. It is known noise: read the message text, not the Railway level.

### Rollback

Redeploy the previous deployment from the Railway dashboard (service, Deployments, the earlier one, Redeploy) or revert on `main`. A rollback does not undo migrations: an Alembic `downgrade` has to be run by hand against the database.

### One instance

State kept in memory is lost on every deploy or restart: running jobs (the job runner marks jobs stuck for more than 5 minutes as failed), the webhook dedupe store, served post images (`/media/*.jpg`) and the in-memory photo and post stores. The orchestrator's history, its conversation summary and the Owner's notes are in Postgres ([ADR 0028](../docs/decisions/0028-orchestrator-memory-and-context.md)), and so are the chat photos once kept as Brand assets. Keep one replica ([ADR 0005](../docs/decisions/0005-single-instance-in-process-jobs.md)).

### Switching WhatsApp between Railway and local development

Kapso calls `https://<service>.up.railway.app/webhooks/whatsapp` through a "Message received" webhook on the number. **Each Kapso webhook has its own signing secret**: after creating or replacing a webhook, set that webhook's secret as `KAPSO_WEBHOOK_SECRET` wherever that backend runs (Railway variable on stdin, or `backend/.env` locally). A mismatched secret gives 401s on every delivery.

Point the number at one backend at a time: two backends would both answer the Owner, and the dedupe store is per process. The `simulator` channel is not built yet (T21), so developing against real WhatsApp locally means toggling:

1. In the Kapso dashboard, pause the Railway webhook.
2. Start a tunnel to the local backend (cloudflared or ngrok), set `PUBLIC_BACKEND_URL` in `backend/.env` to the tunnel URL, and enable (or create) a webhook on the tunnel URL `/webhooks/whatsapp`.
3. Put that webhook's secret in `backend/.env` as `KAPSO_WEBHOOK_SECRET`.
4. To go back: pause the tunnel webhook and resume the Railway one (its secret is already on Railway).
