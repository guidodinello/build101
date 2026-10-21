# Setup

## Prerequisites

- Python 3.13 + [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm
- Docker (to test the production image)
- `ffmpeg` (includes `ffprobe`): only for the Could video work (video analysis, Reels); not needed for the Must scope
- A tunnel for local WhatsApp testing: `cloudflared` or `ngrok` (optional; the simulator doesn't need it). `PUBLIC_BACKEND_URL` must be a `cloudflared` tunnel (or Railway), not free ngrok: see [Run locally](#run-locally)
- Docker, or any local Postgres: for the onboarding API tests ([Tests and lint](#tests-and-lint))
- Accounts and keys: see the checklist in [plan.md](plan.md#before-the-hackathon-checklist)

## Environment variables

### Backend (`backend/.env`, see `.env.example`)

| Variable | Example | Notes |
|---|---|---|
| `ENV` | `local` \| `prod` | **Must be `prod` in production**: it turns off `/dev/*` (even with `ENABLE_DEV_ENDPOINTS=true`) and the API docs, and the backend refuses to start on a mock adapter, a missing production setting or a localhost URL ([backend/README.md](../../backend/README.md#environment-variables)). The default is `local` |
| `PUBLIC_BACKEND_URL` | `https://api-example.up.railway.app` | Railway-generated domain ([ADR 0017](../decisions/0017-backend-host-railway.md)). Used in logs/webhook docs, and for the URLs of generated images until Supabase Storage is in (T56) |
| `FRONTEND_URL` | `https://neitorai.vercel.app` | Magic links + Zernio redirect |
| `FRONTEND_ORIGINS` | `https://neitorai.vercel.app` | CORS, comma-separated. `http://localhost:3000` is for local runs only: with `ENV=prod` the backend refuses to start on a localhost origin |
| `DATABASE_URL` | `postgresql+asyncpg://...pooler.supabase.com:5432/postgres` | Session pooler |
| `SUPABASE_URL` | `https://xxxx.supabase.co` | |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJ...` | Backend only |
| `INBOUND_HANDLER` | `chat` \| `echo` | Default `chat`: answers with Gemini ([ADR 0023](../decisions/0023-gemini-text-llm.md)); `echo` repeats what arrived (channel tests, no LLM) |
| `GEMINI_CHAT_MODEL` | `gemini-3.8-flash` | Text model; uses `GEMINI_API_KEY` |
| `ASSISTANT_NAME` | `Neitor` | The assistant introduces itself by this name in the welcome (product: Neitor AI) |
| `MAX_POSTS_PER_DAY` | `5` | Designs (posts with AI-generated images: image Posts and carousels) a Business can start per day; posts of the Owner's photos as they are don't count. `create_post` answers `daily_limit` past it ([agents.md](../architecture/agents.md#when-image-generation-runs)) |
| `WHATSAPP_CHANNEL` | `kapso` \| `simulator` | Default `kapso`. `simulator` arrives with T21 |
| `KAPSO_API_KEY` | `...` | WhatsApp through Kapso ([ADR 0020](../decisions/0020-whatsapp-via-kapso.md)). Sent as the `X-API-Key` header ([API introduction](https://docs.kapso.ai/api/introduction.md)) |
| `KAPSO_WEBHOOK_SECRET` | random | Webhook signing secret: `X-Webhook-Signature` is the hex HMAC-SHA256 of the raw body ([security](https://docs.kapso.ai/docs/platform/webhooks/security.md)). Without it every webhook gets `401` |
| `KAPSO_PHONE_NUMBER_ID` | `...` | The connected number we send from: the sandbox now, the free US number later |
| `KAPSO_BASE_URL` | `https://api.kapso.ai/meta/whatsapp/v24.0` | Optional; this is the default |
| `KAPSO_TEST_RECIPIENT`, `KAPSO_TEST_MEDIA_ID` | `...` | Only for `uv run pytest -m live`: a verified recipient phone, and a media id taken from an inbound message |
| `IMAGE_GEN` | `gemini` \| `openai` \| `mock` | Image service ([ADR 0019](../decisions/0019-image-provider-gemini.md)); `openai` is the fallback, `mock` the dev fallback (refused with `ENV=prod`) |
| `GEMINI_API_KEY` | `...` | From a Google project with billing linked: unpaid use trains on the images |
| `GEMINI_IMAGE_MODEL` | `gemini-nano-banana-2.1` | |
| `TRANSCRIBE_FALLBACK` | `gemini` \| `none` \| `mock` | Voice notes without Kapso's transcript ([ADR 0021](../decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md)) |
| `TRANSCRIBE_MODEL` | `gemini-3.8-flash` | A Gemini Flash model that takes audio; confirm on the first real call |
| `GEMINI_THINKING_LEVEL` | `medium` | `minimal` \| `medium` \| `high`; thinking can't be turned off. Default `medium` until the first real calls measure `minimal` ([integrations.md](../architecture/integrations.md#image-generation)) |
| `IMAGE_GEN_MAX_CONCURRENCY` | `4` | Process-wide limit on image-service calls (variations and carousel slides) |
| `OPENAI_API_KEY` | `sk-...` | Fallback only; the OpenAI org may need Organization Verification |
| `OPENAI_IMAGE_MODEL` | `gpt-image-2.5-sunburst` | Fallback only |
| `PUBLISHER` | `zernio` \| `mock` | Default `mock`, so a missing env never posts for real. With `ENV=prod` the backend refuses to start on `mock`, and `/ready` fails on it |
| `ZERNIO_API_KEY` | `sk_...` | |
| `ZERNIO_BASE_URL` | `https://zernio.com/api/v1` | Optional; this is the default |
| `ZERNIO_PROFILE_ID`, `ZERNIO_ACCOUNT_ID` | `...` | The single demo Instagram account's Zernio profile and account ids. Temporary: they stand in for `social_accounts` until T02 exists ([ADR 0024](../decisions/0024-mvp-single-demo-instagram-account.md)). With `PUBLISHER=zernio`, publishing from the chat (T57) needs `ZERNIO_ACCOUNT_ID` and an HTTPS `PUBLIC_BACKEND_URL` (a `cloudflared` tunnel or Railway, not free ngrok) that Zernio can fetch the post images from; without the account id the bot says publishing isn't connected |
| `INSTAGRAM` | `mock` \| `meta` | Reading the Owner's Instagram for the Brand Brain ([ADR 0028](../decisions/0028-read-instagram-with-our-meta-app.md)). `mock` (default) connects at once and imports three fake posts; `meta` uses our Meta app with Instagram Login (setup in [integrations.md](../architecture/integrations.md#reading-the-owners-instagram-adr-0028): the *Instagram API with Instagram Login* product, the account added as Instagram Tester with the invite accepted, and `$PUBLIC_BACKEND_URL/oauth/instagram/callback` registered as a redirect URI) |
| `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET` | `...` | The Instagram app id and secret from the Meta app's Instagram Login settings. Required with `INSTAGRAM=meta`; the secret also signs the start ticket and the binding cookie of the OAuth flow |
| `INSTAGRAM_GRAPH_VERSION` | `v24.0` | Version of `graph.instagram.com` calls |
| `INSTAGRAM_IMPORT_MAX_POSTS`, `INSTAGRAM_IMPORT_MAX_IMAGES` | `100`, `24` | Posts whose captions and engagement feed the Brand Strategist, and the newest images imported as Brand assets (each one an Asset Analyst call) |
| `ZERNIO_TEST_IMAGE_URL` | `https://raw.githubusercontent.com/guidodinello/build101/main/backend/tests/fixtures/zernio-live-test.jpg` | Only for `uv run pytest -m live`: a public HTTPS URL serving the fixture JPEG with no redirect. Before the PR merges, put the branch name in place of `main` (the branch is deleted after the squash merge). The live publish posts to the real demo Instagram: delete the post by hand |
| `ZERNIO_WEBHOOK_SECRET` | random | |
| `WHATSAPP_BOT_NUMBER` | `56920403095` | Digits only: the shared Kapso sandbox number. The `wa.me` link on the wizard's last screen (`OnboardingState.whatsapp_url`) |
| `ENABLE_DEV_ENDPOINTS` | `true` | `/dev/*` |
| `DEV_TOKEN` | random | Header `X-Dev-Token` |
| `MAX_CONCURRENT_JOBS` | `4` | |
| `SHUTDOWN_TIMEOUT_S` | `130` | How long a shutdown (a deploy) lets the work in flight finish before cancelling it. With the 10 s uvicorn gives requests, the default 130 stays under the 150 s `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` ([backend/README.md](../../backend/README.md#deploys-and-work-in-flight)). `.env.example` sets `5`: `uvicorn --reload` waits for the work in flight before it restarts |
| `MAX_PHOTO_MB` | `10` | Rejected before the signed upload URL is issued; a WhatsApp photo over it gets `photo_too_big` without being downloaded (or after, when Kapso doesn't say its size). A WhatsApp photo over 25 megapixels gets `photo_too_large` before it is decoded, and WhatsApp photos and carousel references decode under the same limit as onboarding uploads (2 at a time) |
| `MAX_AUDIO_MB` | `3` | Voice notes over it get `audio_too_long` (~25 min of WhatsApp Opus) |
| `MAX_VIDEO_MB` | `300` | Could (video work). Must not exceed the Supabase Storage global file size limit |
| `DASHBOARD_LINK_TTL_DAYS` | `7` | Should (read-only dashboard). Dashboard magic links expire after this |

Plan B only (Meta Cloud API direct, if Kapso fails its first-hour test; [integrations.md](../architecture/integrations.md#plan-b-meta-cloud-api-direct)):

| Variable | Example | Notes |
|---|---|---|
| `META_GRAPH_VERSION` | `v2x.0` | Latest from the Meta app dashboard |
| `META_PHONE_NUMBER_ID` | `1234567890` | |
| `META_ACCESS_TOKEN` | `EAA...` | **System User permanent token** |
| `META_APP_SECRET` | `abc...` | Webhook signature |
| `META_VERIFY_TOKEN` | any random string | Webhook verification |

### Frontend (`frontend/.env.local`)

| Variable | Example |
|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` / prod backend URL |
| `SUPABASE_URL` | the project URL, same as the backend's; read at build time for the CSP (`img-src` / `connect-src`), required on Vercel, optional locally |
| `NEXT_PUBLIC_DEV_TOKEN` | same as `DEV_TOKEN` (simulator only; acceptable for a demo, remove for production) |
| `NEXT_PUBLIC_WHATSAPP_URL` | `https://wa.me/56920403095` (same number as `WHATSAPP_BOT_NUMBER`; used by the landing CTAs and the expired-link screen, which has no onboarding state) |
| `ENABLE_MOCK_API` | `true` locally to serve an in-memory mock of the onboarding API at `/mock-api` (then `NEXT_PUBLIC_API_URL=http://localhost:3000/mock-api`); never set in production (it also refuses when `VERCEL_ENV` is `production`, and serves stored files with `nosniff` and `Content-Disposition: attachment`) |

## Supabase Storage

- **Free** plan is enough for the Must scope ([ADR 0016](../decisions/0016-demo-scope-one-post.md)): the wizard and the chat only store photos and logos (≤ 10 MB each).
- Only if the Could video work starts: switch to **Pro** (Free caps files at 50 MB, [research/media-uploads.md](../research/media-uploads.md#storage-supabase)) and set Storage settings → global file size limit **300 MB** (same as `MAX_VIDEO_MB`).
- Buckets: `assets` (private; photos and logos, plus videos and derived frames later) and `renders` (public; the generated post images). The browser uploads straight to `assets` with signed upload URLs issued by the backend; photos and logos (≤ 10 MB) go in a single request, and only videos (Could) would need resumable (TUS) uploads. Create both buckets by hand in the dashboard (Storage → New bucket) before the first upload.
- **Required bucket config (`assets`).** Set a `file_size_limit` of **10 MB** (same as `MAX_PHOTO_MB`) and `allowed_mime_types` = `image/jpeg, image/png, image/webp, image/heic`. The backend re-checks both when the browser calls `/complete` (it stops reading an object past `MAX_PHOTO_MB` and opens it only as its declared type), but the signed upload URL doesn't enforce the size the browser declared, so the bucket is the first line of defense and keeps oversized or foreign files out of storage altogether. If the Could video work starts, the limit has to allow `MAX_VIDEO_MB` and `video/mp4, video/quicktime` as well.

## Run locally

```bash
# backend
cd backend
cp .env.example .env            # fill in
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
cp .env.example .env.local
npm install
npm run dev                     # http://localhost:3000/o/demo with ENABLE_MOCK_API=true (/dev/chat is T22)
```

Real WhatsApp against a local backend: `cloudflared tunnel --url http://localhost:8000` and point the Kapso webhook to `<tunnel>/webhooks/whatsapp` (remember to point it back to prod afterwards). Use the same `cloudflared` URL as `PUBLIC_BACKEND_URL`: free ngrok answers browser-like clients with an HTML warning page instead of the file, so Zernio gets HTML instead of the post image and Instagram rejects the post (`Failed to validate Instagram image: unrecognized file format`, seen 2026-10-18). ngrok is fine for the Kapso webhook alone.

The onboarding wizard against the local backend: set `ENABLE_DEV_ENDPOINTS=true` and a `DEV_TOKEN`, point `NEXT_PUBLIC_API_URL` at `http://localhost:8000` (with `ENABLE_MOCK_API=false`), then ask for a link (it stands in for the WhatsApp onboarding, T23):

```bash
curl -s -X POST localhost:8000/dev/onboarding-link \
  -H "X-Dev-Token: $DEV_TOKEN" -H 'Content-Type: application/json' \
  -d '{"phone": "59899123456", "business_name": "Muebles Ramírez"}'
# {"business_id": "...", "token": "...", "url": "http://localhost:3000/o/<token>"}
```

## Tests and lint

```bash
cd backend
uv run pytest                   # unit tests (no network); the onboarding API tests skip without TEST_DATABASE_URL
# the onboarding API tests need a Postgres they can wipe (CI runs one as a service)
docker run -d --name build101-pg -p 54329:5432 -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=build101_test postgres:17-alpine
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:54329/build101_test uv run pytest
uv run pytest -m live           # hits Gemini (text, images, transcription, conversation evals) and Kapso; needs GEMINI_API_KEY
uv run ruff check . && uv run ruff format --check .
uv run pyright                  # type check (standard mode), 0 errors

cd frontend
npm run typecheck && npm run lint && npm run build
```

## Deploy

- **Frontend**: Vercel ([ADR 0004](../decisions/0004-frontend-nextjs-vercel.md)), root directory `frontend/`, env vars above, at `https://neitorai.vercel.app`. Every push to `main` deploys; settings in [frontend/README.md](../../frontend/README.md#deploy).
- **Backend**: Railway ([ADR 0017](../decisions/0017-backend-host-railway.md)): one service with root directory `backend/`, built from `backend/Dockerfile` (no browser; `ffmpeg` is added only with the Could video work), one replica (in-process jobs and locks), Railway-generated HTTPS domain. Health check `/ready` ([api.md § Health](../architecture/api.md#health)). Trial first (1 GB RAM, account verified through GitHub so outbound calls work), Hobby if needed.
- **After the first backend deploy**: set the webhook URL in Kapso, run `/dev/seed/demo` if needed, send "hola" from a test phone.
