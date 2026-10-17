# Setup

## Prerequisites

- Python 3.13 + [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm
- Docker (to test the production image)
- `ffmpeg` (includes `ffprobe`) for video analysis: `brew install ffmpeg` or your package manager
- A tunnel for local WhatsApp testing: `cloudflared` or `ngrok` (optional; the simulator doesn't need it)
- Accounts and keys: see the checklist in [plan.md](plan.md#before-the-hackathon-checklist)

## Environment variables

### Backend (`backend/.env`, see `.env.example`)

| Variable | Example | Notes |
|---|---|---|
| `ENV` | `local` \| `prod` | |
| `PUBLIC_BACKEND_URL` | `https://api.example.tenki.app` | Used in logs/webhook docs |
| `FRONTEND_URL` | `https://build101.vercel.app` | Magic links + Zernio redirect |
| `FRONTEND_ORIGINS` | `https://build101.vercel.app,http://localhost:3000` | CORS |
| `DATABASE_URL` | `postgresql+asyncpg://...pooler.supabase.com:5432/postgres` | Session pooler |
| `SUPABASE_URL` | `https://xxxx.supabase.co` | |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJ...` | Backend only |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | |
| `LLM_MODEL` | `claude-opus-5-5` | Per-agent override: `LLM_MODEL_<AGENT>` |
| `META_GRAPH_VERSION` | `v2x.0` | Latest from the Meta app dashboard |
| `META_PHONE_NUMBER_ID` | `1234567890` | |
| `META_ACCESS_TOKEN` | `EAA...` | **System User permanent token** |
| `META_APP_SECRET` | `abc...` | Webhook signature |
| `META_VERIFY_TOKEN` | any random string | Webhook verification |
| `WHATSAPP_BOT_NUMBER` | `15551234567` | For `wa.me` links |
| `PUBLISHER` | `zernio` \| `mock` | Demo fallback switch |
| `ZERNIO_API_KEY` | `sk_...` | |
| `ZERNIO_WEBHOOK_SECRET` | random | |
| `ASSISTANT_NAME` | TBD | Shown in the welcome |
| `ENABLE_DEV_ENDPOINTS` | `true` | `/dev/*` |
| `DEV_TOKEN` | random | Header `X-Dev-Token` |
| `MAX_CONCURRENT_JOBS` | `4` | |
| `MAX_PHOTO_MB` | `10` | Rejected before the signed upload URL is issued |
| `MAX_VIDEO_MB` | `300` | Must not exceed the Supabase Storage global file size limit |
| `DASHBOARD_LINK_TTL_DAYS` | `7` | Editable dashboard magic links expire after this |

### Frontend (`frontend/.env.local`)

| Variable | Example |
|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` / prod backend URL |
| `NEXT_PUBLIC_DEV_TOKEN` | same as `DEV_TOKEN` (simulator only; acceptable for a demo, remove for production) |

## Supabase Storage

- **Pro** plan: the Free plan caps files at 50 MB ([research/media-uploads.md](../research/media-uploads.md#storage-supabase)).
- Storage settings → global file size limit **300 MB** (same as `MAX_VIDEO_MB`).
- Buckets: `assets` (private; photos, videos, logos, derived frames) and `renders` (public). The browser uploads straight to `assets` with signed upload URLs issued by the backend; files over 6 MB use resumable (TUS) uploads.

## Run locally

```bash
# backend
cd backend
cp .env.example .env            # fill in
uv sync
uv run playwright install chromium
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
cp .env.example .env.local
npm install
npm run dev                     # http://localhost:3000/dev/chat
```

Real WhatsApp against a local backend: `cloudflared tunnel --url http://localhost:8000` and point the Meta webhook to `<tunnel>/webhooks/whatsapp` (remember to point it back to prod afterwards).

## Tests and lint

```bash
cd backend
uv run pytest                   # unit tests (no network)
uv run pytest -m live           # hits Claude; needs ANTHROPIC_API_KEY
uv run ruff check . && uv run ruff format --check .

cd frontend
npm run lint && npm run build
```

## Deploy

- **Frontend**: Vercel, root directory `frontend/`, env vars above. Every push to `main` deploys.
- **Backend**: Tenki (or Railway/Render) building `backend/Dockerfile` (Chromium + `ffmpeg`). One instance only (in-process jobs and locks). Health check `/health`. ≥ 1 GB RAM.
- **After the first backend deploy**: set the Meta webhook URL, run `/dev/seed/demo` if needed, send "hola" from a test phone.
