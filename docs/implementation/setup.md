# Setup

## Prerequisites

- Python 3.13 + [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm
- Docker (to test the production image)
- `ffmpeg` (includes `ffprobe`): only for the Could video work (video analysis, Reels); not needed for the Must scope
- A tunnel for local WhatsApp testing: `cloudflared` or `ngrok` (optional; the simulator doesn't need it)
- Accounts and keys: see the checklist in [plan.md](plan.md#before-the-hackathon-checklist)

## Environment variables

### Backend (`backend/.env`, see `.env.example`)

| Variable | Example | Notes |
|---|---|---|
| `ENV` | `local` \| `prod` | |
| `PUBLIC_BACKEND_URL` | `https://api-example.up.railway.app` | Railway-generated domain ([ADR 0017](../decisions/0017-backend-host-railway.md)). Used in logs/webhook docs, and for the URLs of generated images until Supabase Storage is in (T56) |
| `FRONTEND_URL` | `https://build101.vercel.app` | Magic links + Zernio redirect |
| `FRONTEND_ORIGINS` | `https://build101.vercel.app,http://localhost:3000` | CORS |
| `DATABASE_URL` | `postgresql+asyncpg://...pooler.supabase.com:5432/postgres` | Session pooler |
| `SUPABASE_URL` | `https://xxxx.supabase.co` | |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJ...` | Backend only |
| `INBOUND_HANDLER` | `chat` \| `echo` | Default `chat`: answers with Gemini ([ADR 0023](../decisions/0023-gemini-text-llm.md)); `echo` repeats what arrived (channel tests, no LLM) |
| `GEMINI_CHAT_MODEL` | `gemini-3.8-flash` | Text model; uses `GEMINI_API_KEY` |
| `ASSISTANT_NAME` | `Mora` | Placeholder until the product name is chosen; shown in the welcome |
| `MAX_POSTS_PER_DAY` | `5` | Designs (posts with AI-generated images: image Posts and carousels) a Business can start per day; posts of the Owner's photos as they are don't count. `create_post` answers `daily_limit` past it ([agents.md](../architecture/agents.md#when-image-generation-runs)) |
| `WHATSAPP_CHANNEL` | `kapso` \| `simulator` | Default `kapso`. `simulator` arrives with T21 |
| `KAPSO_API_KEY` | `...` | WhatsApp through Kapso ([ADR 0020](../decisions/0020-whatsapp-via-kapso.md)). Sent as the `X-API-Key` header ([API introduction](https://docs.kapso.ai/api/introduction.md)) |
| `KAPSO_WEBHOOK_SECRET` | random | Webhook signing secret: `X-Webhook-Signature` is the hex HMAC-SHA256 of the raw body ([security](https://docs.kapso.ai/docs/platform/webhooks/security.md)). Without it every webhook gets `401` |
| `KAPSO_PHONE_NUMBER_ID` | `...` | The connected number we send from: the sandbox now, the free US number later |
| `KAPSO_BASE_URL` | `https://api.kapso.ai/meta/whatsapp/v24.0` | Optional; this is the default |
| `KAPSO_TEST_RECIPIENT`, `KAPSO_TEST_MEDIA_ID` | `...` | Only for `uv run pytest -m live`: a verified recipient phone, and a media id taken from an inbound message |
| `WHATSAPP_BOT_NUMBER` | `15551234567` | For `wa.me` links |
| `IMAGE_GEN` | `gemini` \| `openai` \| `mock` | Image service ([ADR 0019](../decisions/0019-image-provider-gemini.md)); `openai` is the fallback, `mock` the dev and stage fallback |
| `GEMINI_API_KEY` | `...` | From a Google project with billing linked: unpaid use trains on the images |
| `GEMINI_IMAGE_MODEL` | `gemini-nano-banana-2.1` | |
| `TRANSCRIBE_FALLBACK` | `gemini` \| `none` \| `mock` | Voice notes without Kapso's transcript ([ADR 0021](../decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md)) |
| `TRANSCRIBE_MODEL` | `gemini-3.8-flash` | A Gemini Flash model that takes audio; confirm on the first real call |
| `GEMINI_THINKING_LEVEL` | `medium` | `minimal` \| `medium` \| `high`; thinking can't be turned off. Default `medium` until the first real calls measure `minimal` ([integrations.md](../architecture/integrations.md#image-generation)) |
| `IMAGE_GEN_MAX_CONCURRENCY` | `4` | Process-wide limit on image-service calls (variations and carousel slides) |
| `OPENAI_API_KEY` | `sk-...` | Fallback only; the OpenAI org may need Organization Verification |
| `OPENAI_IMAGE_MODEL` | `gpt-image-2.5-sunburst` | Fallback only |
| `PUBLISHER` | `zernio` \| `mock` | Default `mock`, so a missing env never posts for real. Demo fallback switch |
| `ZERNIO_API_KEY` | `sk_...` | |
| `ZERNIO_BASE_URL` | `https://zernio.com/api/v1` | Optional; this is the default |
| `ZERNIO_PROFILE_ID`, `ZERNIO_ACCOUNT_ID` | `...` | The single demo Instagram account's Zernio profile and account ids. Temporary: they stand in for `social_accounts` until T02 exists ([ADR 0024](../decisions/0024-mvp-single-demo-instagram-account.md)). With `PUBLISHER=zernio`, publishing from the chat (T57) needs `ZERNIO_ACCOUNT_ID` and an HTTPS `PUBLIC_BACKEND_URL` (ngrok or Railway) that Zernio can fetch the post images from; without the account id the bot says publishing isn't connected |
| `ZERNIO_TEST_IMAGE_URL` | `https://raw.githubusercontent.com/guidodinello/build101/main/backend/tests/fixtures/zernio-live-test.jpg` | Only for `uv run pytest -m live`: a public HTTPS URL serving the fixture JPEG with no redirect. Before the PR merges, put the branch name in place of `main` (the branch is deleted after the squash merge). The live publish posts to the real demo Instagram: delete the post by hand |
| `ZERNIO_WEBHOOK_SECRET` | random | |
| `ENABLE_DEV_ENDPOINTS` | `true` | `/dev/*` |
| `DEV_TOKEN` | random | Header `X-Dev-Token` |
| `MAX_CONCURRENT_JOBS` | `4` | |
| `MAX_PHOTO_MB` | `10` | Rejected before the signed upload URL is issued; a WhatsApp photo over it gets `photo_too_big` without being downloaded (or after, when Kapso doesn't say its size) |
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
| `NEXT_PUBLIC_DEV_TOKEN` | same as `DEV_TOKEN` (simulator only; acceptable for a demo, remove for production) |
| `NEXT_PUBLIC_WHATSAPP_URL` | `https://wa.me/15551234567` (same number as `WHATSAPP_BOT_NUMBER`; used by the expired-link screen, which has no onboarding state) |
| `ENABLE_MOCK_API` | `true` locally to serve an in-memory mock of the onboarding API at `/mock-api` (then `NEXT_PUBLIC_API_URL=http://localhost:3000/mock-api`); never set in production |

## Supabase Storage

- **Free** plan is enough for the Must scope ([ADR 0016](../decisions/0016-demo-scope-one-post.md)): the wizard and the chat only store photos and logos (≤ 10 MB each).
- Only if the Could video work starts: switch to **Pro** (Free caps files at 50 MB, [research/media-uploads.md](../research/media-uploads.md#storage-supabase)) and set Storage settings → global file size limit **300 MB** (same as `MAX_VIDEO_MB`).
- Buckets: `assets` (private; photos and logos, plus videos and derived frames later) and `renders` (public; the generated post images). The browser uploads straight to `assets` with signed upload URLs issued by the backend; files over 6 MB use resumable (TUS) uploads.

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
npm run dev                     # http://localhost:3000/dev/chat
```

Real WhatsApp against a local backend: `cloudflared tunnel --url http://localhost:8000` and point the Kapso webhook to `<tunnel>/webhooks/whatsapp` (remember to point it back to prod afterwards).

## Tests and lint

```bash
cd backend
uv run pytest                   # unit tests (no network)
uv run pytest -m live           # hits Gemini (text, images, transcription) and Kapso; needs GEMINI_API_KEY
uv run ruff check . && uv run ruff format --check .

cd frontend
npm run lint && npm run build
```

## Deploy

- **Frontend**: Vercel, root directory `frontend/`, env vars above. Every push to `main` deploys.
- **Backend**: Railway ([ADR 0017](../decisions/0017-backend-host-railway.md)): one service with root directory `backend/`, built from `backend/Dockerfile` (no browser; `ffmpeg` is added only with the Could video work), one replica (in-process jobs and locks), Railway-generated HTTPS domain. Health check `/health`. Trial first (1 GB RAM, account verified through GitHub so outbound calls work), Hobby if needed.
- **After the first backend deploy**: set the webhook URL in Kapso, run `/dev/seed/demo` if needed, send "hola" from a test phone.
