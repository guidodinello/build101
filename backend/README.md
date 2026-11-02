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

Compare Art Director and Design Critic models on fixed briefs, end to end, with a blind A/B page ([research/post-design/designer-agent.md](../docs/research/post-design/designer-agent.md)):

```bash
uv run python -m app.posts.design_eval run --label flash --out ../.design-eval
uv run python -m app.posts.design_eval run --label opus --art-director claude-opus-5-5 \
  --critic claude-opus-5-5 --out ../.design-eval
uv run python -m app.posts.design_eval compare ../.design-eval/flash ../.design-eval/opus
```

It needs `IMAGE_GEN=gemini`, `RENDERER=takumi` with the frontend running, and `ANTHROPIC_API_KEY` for a Claude model.

With the database, the job runner writes each niche's weekly Niche Report to `niche_reports` on its own ([ADR 0025](../docs/decisions/0025-weekly-niche-report.md), `app/jobs/niche.py`): it checks at start and every 15 minutes. Without the database, write this week's report of a niche to a file by hand; set `NICHE_REPORT_PATH=out/niche-report.json` and post generation gets its insights as trend notes:

```bash
uv run python -m app.agents.niche_cli --niche curated-wood-furniture-uy --out out/niche-report.json
```

It needs `GEMINI_API_KEY` from a project with billing (Google Search grounding isn't on the free tier) and takes 30–100 s.

## Deploy

The backend runs on Railway ([ADR 0017](../docs/decisions/0017-backend-host-railway.md)): project `build101`, service `backend`, environment `production`, one replica in `us-east4-eqdc4a` (Virginia; Railway has no South America region). The image is built from [`Dockerfile`](Dockerfile): two stages, uv with `--frozen`, non-root, one uvicorn worker on `0.0.0.0:$PORT` ([ADR 0005](../docs/decisions/0005-single-instance-in-process-jobs.md)).

### How it deploys

- **Push to `main`** builds and deploys the service from the connected GitHub repo, only when it changes a file under `backend/` (the watch paths below). Docs-only and frontend-only pushes don't redeploy it.
- **Manual deploy** from the repo root, with the service linked (`railway link`): `railway up --service backend --detach`. Run it from the repo root and not from `backend/`: the service's root directory is `/backend`, so Railway expects the repo layout in the upload.
- Each deploy runs the pre-deploy command, then starts the container; Railway switches traffic only after `/ready` answers 200. A deploy that refuses to start (see [Environment variables](#environment-variables)) or never gets ready doesn't take traffic, and the previous deployment keeps serving. Then the old deployment gets a SIGTERM and has the draining time to finish its work in flight before the SIGKILL ([Deploys and work in flight](#deploys-and-work-in-flight)).

### Service settings

Railway "Config as Code" files (`railway.json`, `railway.toml`) are deprecated and unavailable to new services, so the settings live in the service, not in the repo. They are applied with the Railway CLI or dashboard and must match this table:

| Setting | Value |
|---|---|
| Source | GitHub `guidodinello/build101`, branch `main` |
| Root directory | `/backend` |
| Builder / Dockerfile | Dockerfile, `Dockerfile` |
| Pre-deploy command | `alembic upgrade head` (timeout 300 s) |
| Healthcheck | `/ready` (dashboard: service, Settings, Deploy, Healthcheck Path), timeout 60 s. Railway calls it only during a deploy, not once the deployment is live ([Railway docs](https://docs.railway.com/reference/healthchecks), read 2026-10-20) |
| Watch paths | `/backend/**`: only a push that changes the backend redeploys it. Patterns match from the repo root even with the root directory set ([Railway: watch paths](https://docs.railway.com/builds/build-configuration#configure-watch-paths), read 2026-10-20) |
| Draining time | 150 s, the service variable `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=150`: the time between the old deployment's SIGTERM and its SIGKILL. Railway's default is 0 s ([Railway: deployments](https://docs.railway.com/reference/deployments), read 2026-10-20) |
| Restart policy | on failure, up to 10 retries |
| Region / replicas | `us-east4-eqdc4a` × 1 |
| Domain | Railway-generated (`*.up.railway.app`) |

### Deploys and work in flight

On a deploy the old backend gets a SIGTERM once the new one answers `/ready`, and a SIGKILL `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` (150 s) later. It uses that time to finish what it was doing ([#180](https://github.com/guidodinello/build101/issues/180)):

1. uvicorn stops taking connections and gives the requests in flight 10 s to finish (`--timeout-graceful-shutdown 10` in the [`Dockerfile`](Dockerfile)). The webhook answers in well under a second: the Owner's turn runs after the 200, as background work.
2. The app's shutdown ([`app/main.py`](app/main.py)): the job poller claims no new job, then the background work (Owner turns, the `brand_generating` message of a submitted onboarding form, Post and video generation, publishes, the wait that groups a photo album, running jobs) gets up to `SHUTDOWN_TIMEOUT_S` (130 s) to finish. What is still running at the deadline is cancelled and logged with its ids: `shutdown deadline passed, cancelling N background tasks: post <id> for ***1234; job <id> (generate_brand) for business <id>; ...`. A cancelled brand job or photo analysis goes back to the queue, and the new deployment runs it: `job <id> (generate_brand) interrupted on attempt 1: queued again` ([#178](https://github.com/guidodinello/build101/issues/178), [overview.md § Background jobs](../docs/architecture/overview.md#background-jobs)).
3. The Kapso and Zernio clients close last, so the text that work ends with in step 2 still reaches the Owner: a reply, the brand summary, a publish's link.

10 s plus 130 s stays under the 150 s drain, so the process exits on its own before the SIGKILL. Raising one of the three means checking the other two.

Post images and videos are the exception. Kapso, WhatsApp and Zernio fetch them by link from `/media/<token>.jpg` (or `.mp4`), which each process serves from its own memory. Once Railway switches traffic, those requests reach the new deployment, which doesn't have them and answers 404, and from the SIGTERM on the old one stops listening anyway. So a Post, Carousel or video sent during the drain doesn't reach the Owner: the send fails and the Owner gets the failure message, or WhatsApp drops the image later. A publish whose media Zernio fetches after the switch fails the same way. The images are still paid for. Fixing it needs the media out of the process (T17: the Storage `renders` bucket).

During the drain two processes talk to the same Owners: the new one answers their new messages while the old one finishes its turns. The per-Owner lock is in memory ([ADR 0005](../docs/decisions/0005-single-instance-in-process-jobs.md)), so the two don't wait for each other, and an Owner can get two replies that don't know about each other.

Still lost on a deploy: work cancelled at the deadline other than those jobs (an Instagram import fails and needs a reconnect, a job interrupted a second time fails and a brand job's Owner gets Reintentar), Post images and videos sent during the drain, and the Posts and chat photos, which still live in memory ([One instance](#one-instance)). A crash or an out-of-memory kill gets no drain at all: the jobs it leaves `running` are recovered the same way once they started more than 5 minutes ago.

### When to merge backend changes during the pilot

While pilot Owners are active, merge PRs that change `backend/` outside Uruguayan business hours, by default 09:00-20:00 Montevideo time (UTC-3). A deploy still loses the Posts kept in memory, the Post images sent during the drain and any work that outlasts it, and during the drain two processes answer the same Owners. Owners write during business hours. Other PRs don't redeploy the backend (watch paths), so they can merge any time.

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
| `PILOT_SENDERS` | unset: the pilot numbers are rows of the `pilot_senders` table, edited in the Supabase SQL editor with no redeploy ([setup.md § Pilot numbers](../docs/implementation/setup.md#pilot-numbers)). With both empty nobody gets in, and the boot log says so |
| `ZERNIO_OWNER_PHONE` | the WhatsApp number of the Owner whose Instagram `ZERNIO_ACCOUNT_ID` is; unset, nobody publishes ([ADR 0024](../docs/decisions/0024-mvp-single-demo-instagram-account.md#interim-publish-guard-2026-10-20)) |
| `ENABLE_DEV_ENDPOINTS`, `DEV_TOKEN` | unset (dev endpoints off) |
| `RENDERER`, `RENDERER_URL`, `RENDERER_SECRET` | `takumi`, the Vercel domain, and the same secret as the frontend's `RENDER_SECRET` |
| `IMAGE_GEN` | `gemini` |
| `PUBLISHER` | `zernio` (`mock` tells the Owner a Post is live when nothing reached Instagram) |
| `ZERNIO_API_KEY`, `ZERNIO_ACCOUNT_ID` | the Zernio API key and the demo account every Post goes to ([ADR 0024](../docs/decisions/0024-mvp-single-demo-instagram-account.md)) |
| `INSTAGRAM`, `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET` | `off` until our Meta app exists: the wizard skips Instagram and the id and secret aren't needed. Then `meta` and the Meta app's id and secret ([ADR 0028](../docs/decisions/0028-read-instagram-with-our-meta-app.md)). Unset is `mock`, which production refuses |
| `INBOUND_HANDLER` | `chat` |
| `VIDEO_GEN_ENABLED`, `VIDEO_GEN` | `false` while AI Reels are off ([ADR 0033](../docs/decisions/0033-ai-generated-reels-veo.md)); once on, `true` and `gemini`, with `GEMINI_VIDEO_API_KEY` |
| `WHATSAPP_CHANNEL` | `kapso` |
| `KAPSO_API_KEY`, `KAPSO_WEBHOOK_SECRET`, `KAPSO_PHONE_NUMBER_ID` | the Kapso project key, the signing secret of the Railway webhook (see [below](#switching-whatsapp-between-railway-and-local-development)) and the number we send from |
| `GEMINI_API_KEY` | a key of the Google project with billing linked |
| `SHUTDOWN_TIMEOUT_S` | unset: the default 130 s ([Deploys and work in flight](#deploys-and-work-in-flight)). `.env.example` sets 5 for local runs |

Settings not listed (model names, limits, base URLs) can keep their defaults.

With `ENV=prod` the app refuses to start when an adapter is a demo fallback (`mock`, `INBOUND_HANDLER=echo`, `WHATSAPP_CHANNEL=simulator`) or when a key, id, number or URL of this table is unset (`GEMINI_VIDEO_API_KEY` only while `VIDEO_GEN_ENABLED=true`, `INSTAGRAM_APP_ID` and `INSTAGRAM_APP_SECRET` only with `INSTAGRAM=meta`; `INSTAGRAM=off` is not a demo fallback); `FRONTEND_URL`, `FRONTEND_ORIGINS`, `PUBLIC_BACKEND_URL` and `RENDERER_URL` must also be public URLs: not `localhost` (or a `*.localhost` name), nor a loopback or private IP address. One error names every such setting and never prints a value (`check_production` in `app/config.py`). Every start logs the adapters in use, by name only: `adapters in use: IMAGE_GEN=gemini RENDERER=takumi PUBLISHER=zernio ...`. With `ENV=local` this check is skipped and the mocks stay the defaults. `INBOUND_HANDLER=chat` still needs `GEMINI_API_KEY` and `PUBLIC_BACKEND_URL` to boot, in any environment; without `DATABASE_URL`, `SUPABASE_URL` or `SUPABASE_SERVICE_ROLE_KEY` the app boots with the job runner off (the startup log says so).

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

State kept in memory is lost on every deploy or restart: the progress of jobs still running at the shutdown deadline, or when the process dies (the brand job and photo analyses start over once, [#178](https://github.com/guidodinello/build101/issues/178)), the webhook dedupe store when there is no `DATABASE_URL` (with one it is the `inbound_deliveries` table), served post images (`/media/*.jpg`) and the in-memory photo and post stores. The orchestrator's history, its conversation summary and the Owner's notes are in Postgres ([ADR 0028](../docs/decisions/0030-orchestrator-memory-and-context.md)), and so are the chat photos once kept as Brand assets. Keep one replica ([ADR 0005](../docs/decisions/0005-single-instance-in-process-jobs.md)).

### Switching WhatsApp between Railway and local development

Kapso calls `https://<service>.up.railway.app/webhooks/whatsapp` through a "Message received" webhook on the number. **Each Kapso webhook has its own signing secret**: after creating or replacing a webhook, set that webhook's secret as `KAPSO_WEBHOOK_SECRET` wherever that backend runs (Railway variable on stdin, or `backend/.env` locally). A mismatched secret gives 401s on every delivery.

Point the number at one backend at a time: two backends would both answer the Owner, and the dedupe store is per process. The `simulator` channel is not built yet (T21), so developing against real WhatsApp locally means toggling:

1. In the Kapso dashboard, pause the Railway webhook.
2. Start a tunnel to the local backend (cloudflared or ngrok), set `PUBLIC_BACKEND_URL` in `backend/.env` to the tunnel URL, and enable (or create) a webhook on the tunnel URL `/webhooks/whatsapp`.
3. Put that webhook's secret in `backend/.env` as `KAPSO_WEBHOOK_SECRET`.
4. To go back: pause the tunnel webhook and resume the Railway one (its secret is already on Railway).
