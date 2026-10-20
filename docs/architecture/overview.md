# Architecture overview

## System context

```mermaid
flowchart LR
    Owner((Owner<br/>phone)) -- WhatsApp --> Kapso[Kapso<br/>on WhatsApp Cloud API]
    Owner -- magic link --> Web[Next.js web app<br/>Vercel]
    Kapso -- webhook --> API[FastAPI backend<br/>Railway]
    API -- send messages --> Kapso
    Web -- REST --> API
    Web -- "uploads (signed URL)" --> Storage
    API -- Interactions API --> Gemini[Gemini API]
    API -- reference photos + prompt --> ImgGen[Image service<br/>Gemini, OpenAI fallback]
    API -- SQL --> DB[(Supabase Postgres)]
    API -- files --> Storage[(Supabase Storage)]
    API -- publish / schedule --> Pub[Publishing provider API]
    Pub -- posts --> IG[Instagram]
    Owner -- connect account --> Pub
```

## Components

| Component | Tech | Responsibility |
|---|---|---|
| **Web app** | Next.js (App Router, TypeScript), Tailwind, shadcn/ui, on Vercel | Onboarding wizard, IG connect hand-off, **dashboard** where the Owner manages their Catalog, Brand assets (photos and videos) and Offers, **chat simulator** (`/dev/chat`) |
| **Backend API** | Python 3.13, FastAPI, uvicorn, one container on Railway ([ADR 0017](../decisions/0017-backend-host-railway.md)) | Webhooks, REST for the web app, orchestrator, agents, jobs, image generation calls, publishing |
| **Database** | Supabase Postgres | All state. Schema in [data-model.md](data-model.md) |
| **File storage** | Supabase Storage (Free plan for the Must scope; Pro with a 300 MB file limit only once the Could video work starts, [ADR 0016](../decisions/0016-demo-scope-one-post.md)), two buckets: `assets` (private uploads), `renders` (public JPEGs) | Logos and photos (uploaded straight from the browser or received in the chat), generated post images (variations and carousel slides); videos, frames and Reel previews only with the Could video work |
| **LLM** | Gemini API (`gemini-3.8-flash`) via the official `google-genai` Python SDK ([ADR 0023](../decisions/0023-gemini-text-llm.md)) | Orchestrator + specialist agents. See [agents.md](agents.md) |
| **WhatsApp** | Kapso, on top of Meta's WhatsApp Cloud API ([ADR 0020](../decisions/0020-whatsapp-via-kapso.md)); Meta direct is plan B | Inbound/outbound messages, buttons, media |
| **Publishing** | Zernio, unified social publishing API (see [integrations.md](integrations.md#publishing-provider-zernio)) | Instagram connect + publish + schedule |
| **Image generation** | Third-party image service behind `ImageGenPort`: Google Gemini `gemini-nano-banana-2.1`, OpenAI `gpt-image-2.5-sunburst` as fallback ([ADR 0018](../decisions/0018-ai-image-generation-service.md), [ADR 0019](../decisions/0019-image-provider-gemini.md)); Pillow resize to 1080×1350 | Post image variations and carousel slides ([ADR 0022](../decisions/0022-carousels-in-mvp.md)) from the Owner's photos ([integrations.md](integrations.md#image-generation)) |
| **Video tools** (Could) | ffmpeg / ffprobe in the backend container, only once the video work starts | Video metadata, keyframes for the Asset Analyst, WhatsApp previews of Reels. Claude reads no video ([integrations.md](integrations.md#video-processing-ffmpeg)) |

## Backend internal architecture

The backend is a modular monolith. Each layer only calls the layer below it.

```mermaid
flowchart TB
    subgraph Entry["Entry points (app/api)"]
        WH[WhatsApp webhook]
        REST[Onboarding + dashboard REST]
        DEV[Dev chat endpoints]
    end
    subgraph Conv["Conversation (app/conversation)"]
        IN[Inbound handler<br/>dedupe, store, route]
        ONB[Onboarding router<br/>deterministic]
        BTN[Button router<br/>deterministic]
        ORC[Orchestrator<br/>Gemini + tools]
    end
    subgraph Work["Jobs (app/jobs)"]
        J1[generate_brand]
        J2[generate_plan]
        J3[generate_post / revise_post]
        J4[publish_post]
        J5[analyze_asset<br/>photos + videos]
    end
    subgraph Agents["Agents (app/agents)"]
        A1[Asset Analyst]
        A2[Brand Strategist]
        A3[Content Strategist]
        A4[Copywriter]
        A5[Art Director]
    end
    subgraph Services["Services"]
        CH[Channel port<br/>WhatsApp / Simulator]
        PUB[Publisher port<br/>Provider / Mock]
        IMG[ImageGen port<br/>Gemini / OpenAI / Mock]
        STO[Storage]
        VID[Video tools<br/>ffmpeg]
        LLM[LLM client<br/>logging to agent_runs]
        REPO[Repositories / DB]
    end
    WH --> IN
    DEV --> IN
    REST --> REPO
    REST --> Work
    IN --> ONB
    IN --> BTN
    IN --> ORC
    ORC -- tools --> Work
    BTN --> Work
    Work --> Agents
    Work --> CH
    Work --> PUB
    Work --> IMG
    Agents --> LLM
    ONB --> CH
    BTN --> CH
    ORC --> CH
    IMG --> STO
    Work --> VID
    VID --> STO
```

### Key design rules

1. **Deterministic where it matters, LLM where it helps.** Button taps, onboarding steps, approval, and publishing are plain code. The LLM handles free text, planning, writing and design choices.
2. **Agents are functions, not processes.** Each specialist is an async function: typed input (Pydantic) → one Gemini call with structured output → typed output. Only the orchestrator runs a tool-use loop.
3. **Long work runs in background jobs.** The webhook returns `200` in < 1 s. The orchestrator's tools *enqueue* jobs and return immediately; jobs send their own WhatsApp messages when they finish.
4. **Ports for everything external.** `ChannelPort` (WhatsApp through Kapso / Simulator), `PublisherPort` (Provider / Mock), `ImageGenPort` (Gemini / OpenAI / Mock), `TranscriberPort` (Gemini / Mock). Switching is an env var, which is also our demo fallback.
5. **Per-business serialization.** Inbound messages for the same business are processed one at a time (an in-process `asyncio.Lock` per business ID). Different businesses run concurrently.
6. **Everything is logged.** Every LLM call writes an `agent_runs` row (agent, input, output, tokens, latency, error). It's our debugger during the hackathon.

## Request lifecycle: inbound WhatsApp message

```mermaid
sequenceDiagram
    participant M as Kapso
    participant W as Webhook
    participant H as Inbound handler
    participant R as Router
    participant O as Orchestrator
    participant J as Job runner
    participant A as Agents
    participant C as Channel

    M->>W: POST /webhooks/whatsapp (signed)
    W->>W: verify the webhook signature
    W->>H: schedule handle(payload) as background task
    W-->>M: 200 OK (immediately)
    H->>H: dedupe by wa_message_id, mark as read
    opt voice note
        H->>H: Kapso transcript, else download + Gemini transcribe
    end
    H->>H: store message (a voice note as its transcript)
    H->>R: route(business, message)
    alt interactive button reply
        R->>J: deterministic handler (e.g. approve_post, publish_post)
    else onboarding not finished
        R->>C: onboarding step reply
    else free text, active business
        R->>O: run turn (history + context)
        O->>J: tool call: create_post(brief)
        J-->>O: {job_id, status: "started"}
        O->>C: "¡Dale! Lo armo ⏳"
    end
    J->>A: Copywriter → Art Director (image brief)
    J->>J: image service → variations, resize, upload
    J->>C: variations, then the picked one as a preview with buttons
```

For a Reel, the Art Director picks the video and the cover frame instead of writing an image prompt, nothing is generated, and the preview's header is the video's WhatsApp preview ([integrations.md](integrations.md#sending)).

## Request lifecycle: upload from the web

The bytes never pass through the backend or Vercel: the browser writes to Storage with a one-path signed URL ([api.md](api.md#uploads), [ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md)). In the Must scope this is the wizard's logo and photos; dashboard uploads and videos are Could ([ADR 0016](../decisions/0016-demo-scope-one-post.md)).

```mermaid
sequenceDiagram
    participant B as Browser (wizard / dashboard)
    participant API as Backend
    participant S as Supabase Storage
    participant J as Job runner
    participant A as Asset Analyst

    B->>API: POST /api/b/{token}/uploads {kind, content_type, size_bytes}
    API->>API: validate, insert brand_assets (status = uploading)
    API->>S: create_signed_upload_url(path)
    API-->>B: {asset_id, upload_url, upload_token, resumable}
    B->>S: PUT file, or TUS in 6 MB chunks if > 6 MB
    B->>API: POST /api/b/{token}/assets/{asset_id}/complete
    API->>S: object exists?
    API->>J: enqueue analyze_asset (status = ready)
    API-->>B: Asset (thumbnail, spinner until analyzed)
    alt video
        J->>J: ffprobe + 6 keyframes
        J->>A: frames + metadata
        A-->>J: VideoAnalysis (description, products, reel_suitable, cover, best frames)
        J->>S: save best frames as photo assets, then the WhatsApp preview
    else photo
        J->>A: image
        A-->>J: AssetAnalysis
    end
    J->>J: save analysis, suggested asset_products
```

## Background jobs

**One mechanism for all background work** (`app/background.py`, [ADR 0005](../decisions/0005-single-instance-in-process-jobs.md)): `BackgroundWork` is the one place that starts an `asyncio` task, keeps it alive, waits for it (`join`, tests) and drains it at shutdown (`drain`, called once from the app's lifespan). A failure that escapes a task is logged there, once, with the task's name. Post generation, publishing, video generation, the photo keeper, the history compaction and the photo debounce run on it. They don't use the `jobs` table: they work with in-memory Posts and photos, so they run without a database, and nothing about them survives a restart (T17, T19). The Owner's turns from the webhook and the `brand_generating` message of `/complete` run on it too, and so do the `jobs` below. Work that turns a failure into something else keeps its own `except`: a `PostFailed` event, a failed `jobs` row.

**Shutdown** ([#180](https://github.com/guidodinello/build101/issues/180)): on a deploy the job poller first stops claiming jobs (`JobRunner.stop`), then `drain` lets all the work end on its own for up to `SHUTDOWN_TIMEOUT_S` (130 s), and cancels what is left with one log line naming each task and its ids. A job it cancels is recovered like the jobs of a dead process (below). The Kapso and Zernio clients close after it, so the text that work ends with still reaches the Owner. Post images and videos sent during the drain don't: Kapso, WhatsApp and Zernio fetch them from `/media`, which this process serves from memory, and by then requests go to the new deployment (until T17 moves them to Storage). The timing against Railway's drain, and what is still lost, are in [backend/README.md](../../backend/README.md#deploys-and-work-in-flight).

Hackathon implementation (`app/jobs/runner.py`, T16): a small in-process `JobRunner` that polls `jobs` every second, claims `queued` rows with `FOR UPDATE SKIP LOCKED` (so a job starts only after the transaction that queued it commits, and jobs queued before a restart still run), and runs each as a `BackgroundWork` task. It

- writes a `jobs` row (`queued → running → succeeded | failed`) with `kind`, `payload`, `result`, `error`;
- catches exceptions, marks the job failed, and raises the `JobFailed` event for the Owner (`notify`, sent as fixed text);
- limits concurrency with a semaphore (`MAX_CONCURRENT_JOBS=4`).

Only `generate_brand` raises `JobFailed` (the `job_failed` text with `retry:{job_id}`); a failed photo analysis is only logged, since the brand is generated without it. Once the message went out the runner sets `retry_offered_at` on the row. `retry:{job_id}` queues a copy and records `retried_by` on the failed row, so a second tap does nothing.

**Interrupted jobs** ([#178](https://github.com/guidodinello/build101/issues/178)): a job is interrupted when the shutdown cancels it at the drain's deadline, or when its process dies (a crash, an out-of-memory kill) and leaves it `running`. The runner takes a `running` job that is not one of its own for dead once it started more than 5 minutes ago, at startup and then every minute. Each claim adds one to `jobs.attempts`, so the count survives the restart:

- `generate_brand` and `analyze_asset` are safe to repeat (`REQUEUE_IF_INTERRUPTED` in `app/jobs/setup.py`): an interrupted one goes back to `queued` and the next process (or, on a deploy, the new instance) runs it from the start.
- Interrupted on its second attempt, or of another kind, the job is **abandoned**: marked `failed` (`error = 'interrupted by a restart'`), then the runner does what the job's own failure would have done. For `generate_brand` that is putting back the state a revision left (`resume_revision`, [ADR 0030](../decisions/0030-orchestrator-memory-and-context.md)) and `JobFailed` with Reintentar. Two attempts so that a job that kills its process can't take the next one down too.
- `import_instagram` is never repeated: it claims the Owner's token when it starts, so an interrupted import is failed at once and still needs a reconnect. A failed `generate_niche_report` is queued again by its own weekly check.
- A run only finishes its own attempt (`attempts` in the final update). During a deploy's overlap the new instance can take for dead a job the old one is still running more than 5 minutes after it started, and run it again; the old run then no longer writes the row. Both runs still do their work: for the brand job, two summaries, and two versions with the same number until [#94](https://github.com/guidodinello/build101/issues/94).

**Stuck brands at startup** (`queue_stranded_brands`, a `PeriodicCheck` with no period, so once per process): each Business in `generating_brand` whose last brand job is neither queued nor running, and was not answered by a Reintentar sent (`retry_offered_at`) or tapped (`retried_by`), gets a copy of that job, or a first one. That covers Businesses stranded before #178 and the ones whose failure message never reached the Owner. A Reintentar tap and this check lock the same job row, so between them only one new job is queued, and a job back in `queued` has no Reintentar at all. One overlap still costs a message: if the check runs while another instance is sending `JobFailed`, the Owner gets that message, and its Reintentar answers as a stale button while the check's copy runs.

Besides queueing jobs, the poller runs small periodic checks on its first round and then every so often (`PeriodicCheck`). One is the **orphaned-upload sweep** (`app/jobs/uploads.py`, hourly): per Business it removes Storage objects whose asset is archived or `failed`, and objects with no asset row once older than the signed upload URL lifetime (2 h; rows can trail their object, and after that the URL can no longer be used). An object is protected by the asset id in its name, so the converted-HEIC original and the `-llm` copy of an active asset stay. Assets still `uploading` and names the sweep doesn't recognise are never touched. A round runs as a background task, so it never delays claiming jobs, and a round is skipped while the previous one is still running; a Storage failure ends the round after one log line. `/complete` also removes the files of an asset it marks `failed`; the sweep only catches what that missed.

**Production path (post-hackathon):** replace `JobRunner` with a real queue (arq on Redis, or Postgres-based like `procrastinate`) without changing job functions. That's why jobs are plain `async def job(ctx, payload)` functions.

The single-process assumption (in-memory locks, in-process jobs) is deliberate for the demo: **run exactly one backend instance**.

## Deployment

| Piece | Where | Notes |
|---|---|---|
| Web | Vercel | `NEXT_PUBLIC_API_URL` → backend URL |
| Backend | Railway ([ADR 0017](../decisions/0017-backend-host-railway.md)): one service, 1 replica, Trial first (1 GB RAM), Hobby if needed; a few GB of temp disk only for the Could video work | Dockerfile per [`.claude/rules/docker.md`](../../.claude/rules/docker.md), no browser (`ffmpeg` only for the Could video work) |
| DB + storage | Supabase (Free plan for the Must scope; Pro with a 300 MB global file limit for the Could video work) | Schema applied with `uv run alembic upgrade head` (runs on deploy) |
| WhatsApp webhook | `https://<backend>/webhooks/whatsapp` | Configured in Kapso (in the Meta app dashboard only for plan B) |
| Secrets | Platform env vars | Full list in [../implementation/setup.md](../implementation/setup.md) |

## Security (demo-appropriate, production-ready seams)

- WhatsApp webhook: verify the provider's signature (Kapso's per its [security docs](https://docs.kapso.ai/docs/platform/webhooks/security.md), header to confirm; `X-Hub-Signature-256` with the app secret on plan B); reject unsigned requests.
- Web access: magic-link token (random 32 bytes, stored hashed, expires in 7 days) is the only credential. Every web endpoint resolves `token → business_id`; there are no business IDs in URLs. The dashboard link can edit, so anyone it's forwarded to can too: edits only archive, never hard-delete, until there are user accounts.
- Storage: `assets` bucket private (signed URLs for the web, service key for the backend); `renders` bucket public (images must be fetchable by WhatsApp and the publishing provider). Browser uploads use signed upload URLs scoped to one path and issued only after the backend validated type and size; Reel videos reach Zernio and Meta through signed read URLs, never by making `assets` public.
- Dev endpoints (`/dev/*`) enabled only when `ENABLE_DEV_ENDPOINTS=true`, protected by `DEV_TOKEN`.
- Secrets only in env vars; `.env.example` in the repo, `.env` gitignored.

## Repository layout

```text
build101/
├── AGENTS.md                 # team workflow + MVP build rules
├── docs/                     # this documentation
├── backend/
│   ├── pyproject.toml        # uv-managed
│   ├── Dockerfile
│   ├── .env.example
│   ├── app/
│   │   ├── main.py           # FastAPI app, routers, startup
│   │   ├── config.py         # pydantic-settings
│   │   ├── api/              # webhooks_whatsapp.py, onboarding.py, dashboard.py, uploads.py, dev.py
│   │   ├── conversation/     # onboarding.py (OnboardingGate: Flow 1 before the web form, wraps chat.py), chat.py (routes each kind of message), turns.py (one orchestrator turn: Owner and event turns),
│   │   │                     # toolbox.py (tool dispatch), photo_batches.py (photo debounce), tools.py (schemas), approval.py, button_router.py, brand.py, history.py, photos.py, outbound.py (the one way to send an event to the Owner), factory.py,
│   │   │                     # prompts/ (orchestrator.md + making_posts.md, publishing.md, rules.md); planned: state.py
│   │   ├── posts/            # lifecycle.py (PostLifecycle: every Post state change and the Approval inputs), store.py (InMemoryPosts), maker.py, video_maker.py, publish.py, drafts.py
│   │   ├── knowledge/        # base.py (Knowledge: what the Agency knows about a Business), db.py (DbKnowledge + readers), local.py (LocalKnowledge, no database)
│   │   ├── agents/           # asset_analyst.py, brand_strategist.py, content_strategist.py,
│   │   │                     # copywriter.py, art_director.py, text_checker.py, schemas.py, prompts/*.md
│   │   ├── carousel/         # schemas.py (CarouselCopy, CarouselBrief, TextCheck), prompts.py (build_slide_prompt), generator.py (CarouselGenerator)
│   │   ├── jobs/             # runner.py, brand.py, plan.py, post.py, publish.py, asset.py
│   │   ├── channels/         # base.py (ChannelPort), kapso.py (Kapso; Meta direct on plan B), kapso_webhook.py, inbound.py, router.py, simulator.py
│   │   ├── publishing/       # base.py (PublisherPort), zernio.py, mock.py
│   │   ├── imagegen/         # base.py (ImageGenPort), gemini.py, openai.py, mock.py
│   │   ├── transcription/    # base.py (TranscriberPort), gemini.py, mock.py (voice notes)
│   │   ├── media/            # video.py (ffprobe, keyframes, WhatsApp preview), images.py (HEIC, palette, prepare_reference, resize to 1080×1350)
│   │   ├── llm/              # client.py (wrapper + agent_runs logging)
│   │   ├── prompts/          # __init__.py (load_prompt, {{include}}), shared/writing_style.md
│   │   ├── storage.py
│   │   ├── copy/messages_es.py
│   │   └── db/               # models.py, session.py, repositories.py, seed.py
│   ├── migrations/           # Alembic (env.py, versions/0001_initial.py)
│   └── tests/
└── frontend/
    ├── package.json
    ├── app/
    │   ├── o/[token]/        # onboarding wizard
    │   ├── b/[token]/        # dashboard: posts, Catalog, Brand assets, Offers
    │   └── dev/chat/         # chat simulator
    ├── components/
    └── lib/                  # api.ts (typed client for the backend), upload.ts (signed / TUS uploads)
```
