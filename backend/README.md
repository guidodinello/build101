# Backend

FastAPI service: WhatsApp webhook, conversation routing, orchestrator + specialist agents (Gemini, [ADR 0023](../docs/decisions/0023-gemini-text-llm.md)), background jobs, AI image generation for Posts and carousels (Gemini, [ADR 0018](../docs/decisions/0018-ai-image-generation-service.md), [ADR 0019](../docs/decisions/0019-image-provider-gemini.md), [ADR 0022](../docs/decisions/0022-carousels-in-mvp.md)) and publishing (Zernio).

- Architecture: [docs/architecture/overview.md](../docs/architecture/overview.md)
- Agents: [docs/architecture/agents.md](../docs/architecture/agents.md)
- API: [docs/architecture/api.md](../docs/architecture/api.md)
- Setup: [docs/implementation/setup.md](../docs/implementation/setup.md)

Stack: **Python + FastAPI**, uv project rooted here ([ADR 0001](../docs/decisions/0001-backend-python-fastapi.md)), with SQLAlchemy 2 (async) + asyncpg, Pydantic v2, `google-genai` and Supabase ([ADR 0003](../docs/decisions/0003-database-supabase-sqlalchemy.md)).

Commands run from this folder (`uv run ruff check .`, `uv run pyright`, `uv run pytest tests/ -v`); see [`.claude/rules/python.md`](../.claude/rules/python.md).

## What exists today

- `app/main.py`: `/health` (`uv run uvicorn app.main:app --reload`); `app/api/ready.py`: `/ready`, the deploy healthcheck ([api.md § Health](../docs/architecture/api.md#health)).
- `app/imagegen/`: `ImageGenPort` with the Gemini and mock adapters, selected by `IMAGE_GEN`.
- `app/media/images.py`: reference photo normalization, the 1080×1350 resize, panorama slicing and logo prep.
- `app/carousel/`: carousel schemas, scene prompts and `CarouselGenerator` (text-free scenes: cover first, other slides anchored on it, or one wide panorama sliced).
- `app/rendering/`: `RendererPort` with the Takumi (the frontend's `/api/render`) and mock adapters, selected by `RENDERER`; `render_slides` designs every slide of a post ([ADR 0029](../docs/decisions/0029-designed-slides-ai-scene-code-layout.md)).
- `app/channels/`: `ChannelPort` with the Kapso adapter, `POST /webhooks/whatsapp` (signature check, dedupe, background handling) and an echo handler until the conversation router (T23) exists.

Generate a carousel from a copy + brief spec without the database or the agents:

```bash
cp .env.example .env   # set IMAGE_GEN=gemini and GEMINI_API_KEY for real calls
uv run python -m app.carousel.cli --spec tests/fixtures/carousel_spec.json \
  --photos ~/demo/photo1.jpg ~/demo/photo2.jpg --out out/carousel [--slides 1]
```

With `RENDERER=takumi` and the frontend running (`RENDERER_URL=http://localhost:3000`, `RENDERER_SECRET` = its `RENDER_SECRET`), it writes the designed `slide-N.jpg` next to each `scene-N.jpg`; with `RENDERER=mock` both are the bare scene. It also writes each slide's prompt and a `report.json` with latency, raw size and token usage per call. Live tests run with `uv run pytest -m live` (skipped without `GEMINI_API_KEY`).

With the database, the job runner writes each niche's weekly Niche Report to `niche_reports` on its own ([ADR 0025](../docs/decisions/0025-weekly-niche-report.md), `app/jobs/niche.py`): it checks at start and every 15 minutes. Without the database, write this week's report of a niche to a file by hand; set `NICHE_REPORT_PATH=out/niche-report.json` and post generation gets its insights as trend notes:

```bash
uv run python -m app.agents.niche_cli --niche curated-wood-furniture-uy --out out/niche-report.json
```

It needs `GEMINI_API_KEY` from a project with billing (Google Search grounding isn't on the free tier) and takes 30–100 s.

## Deploy

The backend runs on Railway ([ADR 0017](../docs/decisions/0017-backend-host-railway.md)): project `build101`, service `backend`, environment `production`, one replica in `us-east4-eqdc4a` (Virginia; Railway has no South America region). The image is built from [`Dockerfile`](Dockerfile): two stages, uv with `--frozen`, non-root, one uvicorn worker on `0.0.0.0:$PORT` ([ADR 0005](../docs/decisions/0005-single-instance-in-process-jobs.md)).

### How it deploys

- **Push to `main`** builds and deploys the service from the connected GitHub repo.
- **Manual deploy** from the repo root, with the service linked (`railway link`): `railway up --service backend --detach`. Run it from the repo root and not from `backend/`: the service's root directory is `/backend`, so Railway expects the repo layout in the upload.
- Each deploy runs the pre-deploy command, then starts the container; Railway switches traffic only after `/ready` answers 200. A deploy that refuses to start (see [Environment variables](#environment-variables)) or never gets ready doesn't take traffic, and the previous deployment keeps serving.

### Service settings

Railway "Config as Code" files (`railway.json`, `railway.toml`) are deprecated and unavailable to new services, so the settings live in the service, not in the repo. They are applied with the Railway CLI or dashboard and must match this table:

| Setting | Value |
|---|---|
| Source | GitHub `guidodinello/build101`, branch `main` |
| Root directory | `/backend` |
| Builder / Dockerfile | Dockerfile, `Dockerfile` |
| Pre-deploy command | `alembic upgrade head` (timeout 300 s) |
| Healthcheck | `/ready` (dashboard: service, Settings, Deploy, Healthcheck Path), timeout 60 s. Railway calls it only during a deploy, not once the deployment is live ([Railway docs](https://docs.railway.com/reference/healthchecks), read 2026-10-20) |
| Restart policy | on failure, up to 10 retries |
| Region / replicas | `us-east4-eqdc4a` × 1 |
| Domain | Railway-generated (`*.up.railway.app`) |

### Environment variables

Set on the service (`railway variable set KEY --stdin --service backend`, value on stdin so it never lands in shell history). Names are in [`.env.example`](.env.example); the production values:

| Variable | Production value |
|---|---|
| `ENV` | `prod`. Without it nothing below is checked at startup (`/ready` still fails on the mock publisher) |
| `PUBLIC_BACKEND_URL` | the Railway domain (`https://<service>.up.railway.app`) |
| `DATABASE_URL` | Supabase **session pooler**, port 5432, `postgresql+asyncpg://` (the transaction pooler breaks asyncpg prepared statements, see [ADR 0003](../docs/decisions/0003-database-supabase-sqlalchemy.md)) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | the project URL and its legacy `service_role` JWT (the code sends it as `apikey` and as a Bearer token) |
| `FRONTEND_URL`, `FRONTEND_ORIGINS` | the Vercel domain, `https://neitorai.vercel.app` (no `localhost` in production CORS) |
| `WHATSAPP_BOT_NUMBER` | `56920403095`, the shared Kapso sandbox number (only answers phones with an active sandbox session) |
| `ENABLE_DEV_ENDPOINTS`, `DEV_TOKEN` | unset (dev endpoints off) |
| `RENDERER`, `RENDERER_URL`, `RENDERER_SECRET` | `takumi`, the Vercel domain, and the same secret as the frontend's `RENDER_SECRET` |
| `IMAGE_GEN` | `gemini` |
| `PUBLISHER` | `zernio` (`mock` tells the Owner a Post is live when nothing reached Instagram) |
| `ZERNIO_API_KEY`, `ZERNIO_ACCOUNT_ID` | the Zernio API key and the demo account every Post goes to ([ADR 0024](../docs/decisions/0024-mvp-single-demo-instagram-account.md)) |
| `INSTAGRAM`, `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET` | `meta` and our Meta app's id and secret ([ADR 0028](../docs/decisions/0028-read-instagram-with-our-meta-app.md)) |
| `INBOUND_HANDLER` | `chat` |
| `VIDEO_GEN_ENABLED`, `VIDEO_GEN` | `false` while AI Reels are off ([ADR 0033](../docs/decisions/0033-ai-generated-reels-veo.md)); once on, `true` and `gemini`, with `GEMINI_VIDEO_API_KEY` |
| `WHATSAPP_CHANNEL` | `kapso` |
| `KAPSO_API_KEY`, `KAPSO_WEBHOOK_SECRET`, `KAPSO_PHONE_NUMBER_ID` | the Kapso project key, the signing secret of the Railway webhook (see [below](#switching-whatsapp-between-railway-and-local-development)) and the number we send from |
| `GEMINI_API_KEY` | a key of the Google project with billing linked |

Settings not listed (model names, limits, base URLs) can keep their defaults.

With `ENV=prod` the app refuses to start when an adapter is a demo fallback (`mock`, `INBOUND_HANDLER=echo`, `WHATSAPP_CHANNEL=simulator`) or when a key, id, number or URL of this table is unset (`GEMINI_VIDEO_API_KEY` only while `VIDEO_GEN_ENABLED=true`); `FRONTEND_URL`, `FRONTEND_ORIGINS`, `PUBLIC_BACKEND_URL` and `RENDERER_URL` must also be public URLs: not `localhost` (or a `*.localhost` name), nor a loopback or private IP address. One error names every such setting and never prints a value (`check_production` in `app/config.py`). Every start logs the adapters in use, by name only: `adapters in use: IMAGE_GEN=gemini RENDERER=takumi PUBLISHER=zernio ...`. With `ENV=local` this check is skipped and the mocks stay the defaults. `INBOUND_HANDLER=chat` still needs `GEMINI_API_KEY` and `PUBLIC_BACKEND_URL` to boot, in any environment; without `DATABASE_URL`, `SUPABASE_URL` or `SUPABASE_SERVICE_ROLE_KEY` the app boots with the job runner off (the startup log says so).

### Migrations

`alembic upgrade head` runs as the pre-deploy command in a separate container with the service variables. A failing migration fails the deploy and the previous deployment keeps serving. It reads `DATABASE_URL` through the app settings, so `app` must stay importable from the image working directory (`/app`).

### Logs and checks

- `railway logs --service backend` (deploy logs) and `railway logs --service backend --build` (build logs).
- `curl -sS https://<service>.up.railway.app/health` returns `{"status":"ok"}` while the process is up.
- `curl -sS https://<service>.up.railway.app/ready` returns `{"status":"ok","checks":{"database":"ok","job_runner":"ok","publisher":"ok"},"commit":"<sha>"}`, or a 503 with the failed checks. `commit` is the deployed commit (Railway's `RAILWAY_GIT_COMMIT_SHA`, so `null` after a `railway up`): compare it with `main`.
- Pre-deploy output shows up in the deploy logs of the new deployment; `Running upgrade ...` lines appear only when a migration was pending.
- uvicorn and the app log to stderr, so Railway tags every line `level=error`, including the normal `INFO` ones. It is known noise: read the message text, not the Railway level.

### Rollback

Redeploy the previous deployment from the Railway dashboard (service, Deployments, the earlier one, Redeploy) or revert on `main`. A rollback does not undo migrations: an Alembic `downgrade` has to be run by hand against the database.

### One instance

State kept in memory is lost on every deploy or restart: running jobs (the job runner marks jobs stuck for more than 5 minutes as failed), the webhook dedupe store, served post images (`/media/*.jpg`) and the in-memory photo and post stores. The orchestrator's history, its conversation summary and the Owner's notes are in Postgres ([ADR 0028](../docs/decisions/0030-orchestrator-memory-and-context.md)), and so are the chat photos once kept as Brand assets. Keep one replica ([ADR 0005](../docs/decisions/0005-single-instance-in-process-jobs.md)).

### Switching WhatsApp between Railway and local development

Kapso calls `https://<service>.up.railway.app/webhooks/whatsapp` through a "Message received" webhook on the number. **Each Kapso webhook has its own signing secret**: after creating or replacing a webhook, set that webhook's secret as `KAPSO_WEBHOOK_SECRET` wherever that backend runs (Railway variable on stdin, or `backend/.env` locally). A mismatched secret gives 401s on every delivery.

Point the number at one backend at a time: two backends would both answer the Owner, and the dedupe store is per process. The `simulator` channel is not built yet (T21), so developing against real WhatsApp locally means toggling:

1. In the Kapso dashboard, pause the Railway webhook.
2. Start a tunnel to the local backend (cloudflared or ngrok), set `PUBLIC_BACKEND_URL` in `backend/.env` to the tunnel URL, and enable (or create) a webhook on the tunnel URL `/webhooks/whatsapp`.
3. Put that webhook's secret in `backend/.env` as `KAPSO_WEBHOOK_SECRET`.
4. To go back: pause the tunnel webhook and resume the Railway one (its secret is already on Railway).
