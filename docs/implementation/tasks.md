# Task breakdown

Each task can be handed to a coding agent as-is: "Implement T13 from docs/implementation/tasks.md". Every task lists what to read, what to build and how to verify it. IDs match the timeline in [plan.md](plan.md).

Legend: **A** = Track A (Brain), **B** = Track B (Surface), **AB** = together. Priority: M = Must, S = Should, C = Could.

## H0–1: Kickoff (together)

### T00: Backend scaffold · AB · M

- Read: [architecture/overview.md](../architecture/overview.md#repository-layout), [setup.md](setup.md)
- Build: `backend/` with `uv init`, Python 3.13 (per [`.claude/rules/python.md`](../../.claude/rules/python.md)), deps: `fastapi`, `uvicorn[standard]`, `anthropic`, `pydantic`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `httpx`, `jinja2`, `playwright`, `supabase`, `pillow`, `pillow-heif`; dev deps: `pytest`, `pytest-asyncio`, `ruff`. `app/main.py` with `/health`, `app/config.py` (pydantic-settings, all env vars from setup.md), `Dockerfile` per [`.claude/rules/docker.md`](../../.claude/rules/docker.md) with Chromium via `playwright install --with-deps chromium` and `ffmpeg` (apt), `.env.example`. Add the backend job (ruff + pytest) to `.github/workflows/ci.yml` and to the `CI` gate.
- Done when: `uv run uvicorn app.main:app` serves `/health`; Docker image builds and renders a test HTML to JPEG at startup (log line "renderer ok"); `ffmpeg -version` and `ffprobe -version` succeed at startup (log line "ffmpeg ok").

### T01: Frontend scaffold · AB · M

- Build: `frontend/` with `create-next-app` (TypeScript, App Router, Tailwind, ESLint), shadcn/ui init with the tokens from [design/web-app.md](../design/web-app.md#visual-language), `lib/api.ts` with `NEXT_PUBLIC_API_URL`, placeholder pages `/o/[token]`, `/b/[token]`, `/dev/chat`.
- Done when: deployed on Vercel; `/dev/chat` renders.

### T02: Schema + contracts · AB · M

- Read: [architecture/data-model.md](../architecture/data-model.md), [architecture/agents.md](../architecture/agents.md), [architecture/api.md](../architecture/api.md#internal-module-interfaces)
- Build: Alembic setup + initial migration `migrations/versions/0001_initial.py` with the schema from data-model.md, applied to Supabase; `app/db/models.py` (SQLAlchemy 2 typed models) + `session.py`; `app/agents/schemas.py` (all Pydantic models: BrandBrain, AssetAnalysis, VideoAnalysis, WeeklyPlan, PostCopy, RenderSpec, ...); `app/channels/base.py`; `app/publishing/base.py`; `app/copy/messages_es.py` (copy deck from conversation-design.md); `frontend/lib/api.ts` types.
- Done when: `python -c "from app.agents.schemas import BrandBrain; print(BrandBrain.model_json_schema())"` works; tables exist in Supabase, including `products`, `asset_products`, `offers` and `offer_products`, `brand_assets.kind` accepts `video`, and `posts` has `format`, `video_asset_id`, `cover_offset_ms` and `offer_id`.

### T03: Deploy + webhook verification · AB · M

- Build: backend deployed on Tenki with env vars; Meta webhook configured and verified (`GET /webhooks/whatsapp` implemented here).
- Done when: Meta dashboard shows the webhook verified; `/health` is reachable over HTTPS.

## H1–6

### T10: LLM client · A · M

- Read: [architecture/agents.md § LLM client conventions](../architecture/agents.md#llm-client-conventions)
- Build: `app/llm/client.py`: `async def structured(agent: str, system: list, messages: list, output_model: type[T], effort: str, business_id, job_id=None) -> T` and `async def tool_step(...) -> Message` for the orchestrator. Writes `agent_runs`. Handles `refusal` / `max_tokens` stop reasons with typed exceptions (`LLMRefusal`, `LLMTruncated`). Enables prompt caching and server-side fallbacks.
- Done when: a pytest (marked `live`, skipped without key) gets a valid small Pydantic object back and an `agent_runs` row exists.

### T11: Asset Analyst (photos and logo) · A · M

- Build: `app/agents/asset_analyst.py` + prompt; Pillow palette extraction util `app/agents/palette.py` (5 colors, skip near-white/black/transparent). Product suggestions: the analysis names the Products it sees, matched against the Business's active `products`, and saved as `asset_products` rows with `source = 'analyst'` (F8.5, Should).
- Done when: running it on 3 demo photos + logo returns sensible `AssetAnalysis`; palette of the demo logo looks right; a photo of a demo product is linked to that Product.

### T12: Brand Strategist · A · M

- Build: `app/agents/brand_strategist.py` + prompt (create mode; revise mode is F2.6, Could). Reads the Catalog from `products` and keeps only a summary of the main Products in the Brand Brain; Offers are read from `offers`, not stored in the Brand Brain.
- Done when: with the demo business inputs (fixture `tests/fixtures/demo_business.json`, full Catalog), it returns a BrandBrain whose `whatsapp_summary` the owner-teammate agrees with. If revise mode is built: "somos más divertidos" changes only voice fields.

### T13: Copywriter · A · M

- Build: `app/agents/copywriter.py` + prompt (create + revise).
- Done when: 3 different briefs produce Rioplatense captions within length limits, respecting emoji policy and constraints.

### T14: Art Director · A · M

- Build: `app/agents/art_director.py` + prompt; post-validation (slots, colors, asset ownership) with one retry; fallback spec.
- Done when: given copy + 4 candidate photos it returns a valid RenderSpec; invalid outputs are corrected or fall back.

### T15: Renderer engine · A · M

- Read: [design/post-templates.md](../design/post-templates.md), [integrations.md § Renderer](../architecture/integrations.md#renderer-html--image)
- Build: `app/rendering/renderer.py` (browser lifecycle on startup/shutdown, `render_post(spec, visual_identity, assets) -> bytes`), `catalog.py`, contrast guard, data-URI embedding, font loading; one placeholder template.
- Done when: `uv run python -m app.rendering.cli --spec sample.json --out out.jpg` produces a 1080×1350 JPEG in < 3 s.

### T20: WhatsApp channel + webhook · B · M

- Read: [integrations.md § WhatsApp](../architecture/integrations.md#whatsapp-cloud-api), [api.md](../architecture/api.md)
- Build: `app/channels/whatsapp.py` (send_text, send_image, send_buttons with optional image header, mark_read + typing, download_media); `POST /webhooks/whatsapp` with signature check, payload parsing to a normalized `InboundMessage` model, dedupe by `external_id`, store in `messages`, background handling; status updates.
- Done when: sending "hola" from a test phone stores the message and an echo reply arrives; duplicate deliveries are ignored (unit test with a fixture payload).

### T21: Simulator channel + dev endpoints · B · M

- Build: `app/channels/simulator.py` (stores outbound in `messages`), `/dev/sim/*`, `/dev/businesses/{id}/reset`, `/dev/agent-runs` per api.md; `channel_for(business)`.
- Done when: posting a message to `/dev/sim/{phone}/messages` runs the same inbound handler and the echo shows up in `GET .../messages`.

### T22: `/dev/chat` UI · B · M

- Read: [design/web-app.md § /dev/chat](../design/web-app.md#devchat-whatsapp-simulator-must)
- Build: WhatsApp-like chat with text, images, interactive buttons, image upload, polling, reset, debug side panel.
- Done when: a full conversation is usable from the browser, buttons send `button_reply`.

### T23: Inbound handler + onboarding router (Flow 1) · B · M

- Read: [product/user-flows.md](../product/user-flows.md) (state machines, Flow 1), conversation-design.md copy deck
- Build: `app/conversation/inbound.py` (per-business `asyncio.Lock`, create business on first contact, route by type/state), `onboarding_router.py` (states `new` → `awaiting_web_form`, magic link creation, `link_reminder`, "link" keyword re-sends), stub for `button_router` and orchestrator (echo).
- Done when: new number → welcome → name → magic link with a working URL, both on WhatsApp and simulator; unit tests for the state transitions.

## H7–12

### T16: Job runner · A · M

- Build: `app/jobs/runner.py` per [overview.md § Background jobs](../architecture/overview.md#background-jobs): `enqueue`, semaphore, `jobs` rows, failure → `job_failed` message with `retry:{job_id}` button, startup cleanup of stale `running` jobs.
- Done when: a dummy job runs, a failing dummy job sends `job_failed` in the simulator.

### T17: Job pipelines · A · M

- Read: [agents.md § Job pipelines](../architecture/agents.md#job-pipelines)
- Build: `jobs/asset.py` (photo and logo; video in T36), `brand.py`, `plan.py`, `post.py` (`generate_post`, `revise_post` with Feedback Classifier; Reels in T39), each sending its WhatsApp message via `channel_for`. Storage upload of renders (new path per revision). Plan approval creates posts and generates them sequentially. Plan changes from free text (F3.3) are Could.
- Done when: from the simulator, after onboarding is completed via `/dev` seed, the plan → posts → revision flows work.

### T18: Button router · A · M

- Build: `app/conversation/button_router.py` with every ID from [api.md § Button IDs](../architecture/api.md#button-ids), state guards, stale-button reply.
- Done when: unit tests cover each button's allowed/forbidden states.

### T19: Orchestrator v1 · A · M

- Read: [agents.md § Orchestrator](../architecture/agents.md#orchestrator), conversation-design.md (system prompt skeleton, examples)
- Build: `app/orchestrator/orchestrator.py` (manual loop, max 5 steps), `tools.py` (all tools, strict schemas, guards), `prompts/system.md`; context builder; `awaiting` handling (free text routed with pending context).
- Done when: the example conversations in conversation-design.md work in the simulator; "publicalo" on a non-approved post does not publish.

### T24: Onboarding REST + uploads · B · M

- Read: [api.md § Onboarding](../architecture/api.md#onboarding-web-wizard), [research/media-uploads.md](../research/media-uploads.md)
- Build: `app/api/onboarding.py` + `app/storage.py`. Uploads go **browser → Supabase** (no multipart through the backend): `POST /api/o/{token}/uploads` validates kind, content type and size (`MAX_PHOTO_MB`, `MAX_VIDEO_MB`), creates the `brand_assets` row in `uploading` status and returns a signed Supabase upload URL (resumable/TUS for files > 6 MB); `POST /api/o/{token}/assets/{id}/complete` checks the object exists, converts HEIC → JPEG, writes the resized LLM copy (≤ 1568 px), runs logo palette sync and enqueues `analyze_asset`. `PUT /api/o/{token}/products` takes any number of Products and writes `products` rows. `/complete` (validations, state change, enqueue `generate_brand`, WhatsApp message); the questionnaire's current promo becomes a draft Offer (T46).
- Done when: all endpoints work via `curl` with a real token; a 6 MB+ video uploads with TUS from the signed URL; oversized files are rejected before upload; files land in the right buckets/paths.

### T25: Onboarding wizard UI · B · M

- Read: [design/web-app.md § /o/[token]](../design/web-app.md#otoken-onboarding-wizard), [user-flows.md § Flow 2](../product/user-flows.md#flow-2--web-onboarding-form)
- Build: steps 1–7, autosave, color swatches, questionnaire controls, IG connect step, done screen, expired-token screen. Step 2 takes any number of Products (no cap of 5). Step 4 ("Tus fotos y videos") takes photos and videos: thumbnails (video poster frame), direct uploads to the signed URL with a progress bar (resumable for files > 6 MB), retry on failure, friendly message for files over the limit.
- Done when: completed on a real phone from the WhatsApp link in < 5 minutes with the demo materials, including one video.

### T26: Templates `product_hero` + `promo_band` · B · M

- Read: [design/post-templates.md](../design/post-templates.md)
- Build: the two HTML templates + `/dev/templates/{id}?sample=1` preview route.
- Done when: both render correctly with the demo logo/photos across the test cases listed in post-templates.md.

### T27: Zernio publisher + connect · B · M

- Read: [integrations.md § Zernio](../architecture/integrations.md#publishing-provider-zernio)
- Build: `app/publishing/zernio.py` (ensure_profile, connect_url, publish now/scheduled, 207 handling), `mock.py`, `/api/o/{token}/instagram/connect` + `/callback`, `PUBLISHER` env switch.
- Done when: connecting the demo IG from the wizard stores `provider_account_id`; a test publish succeeds (then delete the IG post).

## H13–17

### T28: WhatsApp polish · B · M

- Build: post preview as interactive with image header (fallback to text + short body when > 1,024 chars); inbound images → `brand_assets` + `analyze_asset` + Flow 9 message; inbound videos the same way (F1.5, Should); unsupported media reply.
- Done when: Flow 5 and Flow 9 look right on a real phone.

### T29: Zernio webhook · B · S

- Build: `POST /webhooks/zernio` with signature verification; `post.published` / `post.failed` / `account.connected`.
- Done when: a scheduled post 5 minutes ahead flips to `published` and the owner is notified.

### T30: Publish job + guards · A · M

- Build: `jobs/publish.py` (status guard, need-IG path, now vs scheduled, store permalink, messages), `post_publish` / `post_schedule` / `schedule_time` parsing (orchestrator turns natural language into ISO via a tiny structured call).
- Done when: approve → publish now on the real IG returns the permalink in WhatsApp; scheduling works.

### T31: Quality checks · A · M

- Build: `app/agents/checks.py` per [agents.md § Quality checks](../architecture/agents.md#quality-checks-cheap-deterministic) + retry-once wrapper used by Copywriter/Art Director.
- Done when: unit tests with crafted bad outputs trigger retries.

### T32: Prompt tuning with real data · A · M

- Run the full flow with the furniture business 3 times; fix tone, hallucinations, length. Keep a log of prompt changes in the PR description.

### T33: Demo seed · A · M

- Build: `app/db/seed.py` + `/dev/seed/demo`: creates the demo business with real assets (photos and 2–3 analyzed videos), the full Catalog, one active Offer, a reviewed Brand Brain and a plan that includes one Reel, connected IG account id from env.
- Done when: a fresh environment reaches "active with plan" in one call.

### T36: Video analysis · A · M

- Read: [agents.md § Asset Analyst](../architecture/agents.md#asset-analyst), [research/media-uploads.md](../research/media-uploads.md#what-claude-can-read)
- Build: `analyze_asset` for `kind = 'video'`: `ffprobe` for duration, size and codec (saved on `brand_assets`), ~6 keyframes with `ffmpeg` resized to ≤ 1568 px, one vision call returning `VideoAnalysis` (description, tags, Product suggestions, `reel_suitable` with reason, `cover_offset_ms`). Product suggestions saved as `asset_products` like T11.
- Done when: the demo videos get sensible descriptions; a 15–60 s vertical video is `reel_suitable`, a 4-minute horizontal one is not, and both have a cover offset that looks good as a still.

### T37: Derived frame photos · A · S

- Build: the best frames from `VideoAnalysis` are saved as `kind = 'photo'` Brand assets with `derived_from_asset_id` set, analyzed like any photo, usable by the Art Director.
- Done when: a video upload adds 1–3 derived photos that appear in the Contenido tab and can be used in an image Post.

### T38: Dashboard REST · B · M

- Read: [api.md § Dashboard](../architecture/api.md)
- Build: `app/api/dashboard.py` under `/api/b/{token}`: business + Brand Brain + Posts (existing reads); `uploads` + `assets/{id}/complete` (same flow as T24); assets list (filter by kind, Product, archived) and `PATCH` (`product_ids`, `archived`); Products CRUD with `PATCH archived`; Offers CRUD (F8.6, Should). Nothing is deleted, only archived; archived material is hidden from agents. `dashboard` magic links are editable and expire after `DASHBOARD_LINK_TTL_DAYS`; "link" in WhatsApp sends a new one.
- Done when: every endpoint works via `curl` with a real token; an archived photo no longer appears in the Content Strategist's asset list; an expired link gets the friendly expired error.

### T35: Dashboard `/b/[token]` · B · M

- Read: [design/web-app.md § /b/[token]](../design/web-app.md)
- Build: mobile tabs **Inicio** (Brand Brain summary + Posts with status badges, Reels with their cover), **Catálogo** (Products list, add/edit/archive), **Contenido** (photo/video grid, multi-select upload with progress, link Products, archive) and **Promos** (Offers list and form, Should). Plus the `dashboard` magic link via orchestrator ("¿dónde veo todo?").
- Done when: on a real phone, the Owner adds a Product, uploads 10 photos and a video, links the video to the Product and archives a photo, all from the WhatsApp link.

### T39: Reels in the agents · A · M

- Read: [agents.md](../architecture/agents.md) (Content Strategist, Copywriter, Art Director, Feedback Classifier)
- Build: plan items carry a `format` (`image` | `reel`); the Content Strategist plans a Reel only from `reel_suitable` videos; the Copywriter writes Reel captions; the Art Director picks `video_asset_id` + `cover_offset_ms` instead of a render spec; the Feedback Classifier routes Reel feedback to copy, cover or a different video. `post.py` handles Reels: no render, the cover frame is extracted as a JPEG for previews.
- Done when: with the demo seed, the weekly plan includes one Reel; "cambiá el video" swaps the video, "más corto" rewrites only the caption.

### T44: Reel publishing · B · M

- Read: [integrations.md § Zernio](../architecture/integrations.md#publishing-provider-zernio), [research/media-uploads.md](../research/media-uploads.md#publishing-video-and-carousels-zernio-instagram)
- Build: `ZernioPublisher` publishes `format = 'reel'` Posts as one video media item by public signed URL (valid long enough for Zernio to fetch it) with `thumbOffset = cover_offset_ms`; handles the slower processing (status from the webhook, T29); the mock publisher logs Reels like images.
- Done when: an approved Reel is published on the demo IG and the permalink arrives in WhatsApp; with `PUBLISHER=mock` the same flow completes.

### T45: WhatsApp Reel preview · B · M

- Read: [integrations.md § WhatsApp](../architecture/integrations.md#whatsapp-cloud-api)
- Build: Reel previews send the video with the caption and the Aprobar / Cambiar / Descartar buttons when it fits WhatsApp's media size limit; otherwise the cover frame + caption + a dashboard link to watch it. Same in the simulator.
- Done when: both paths look right on a real phone.

### T46: Catalog and Offers from the chat · A · S

- Build: orchestrator tools to add or edit a Product and to create an Offer from free text ("agregá la silla Oslo a $4500", "este finde 15% en sillas"), always confirming with the Owner before saving; the onboarding current promo becomes a draft Offer confirmed with the Brand Brain summary. Agents read active Offers from `offers` (replacing `current_offers`).
- Done when: both example messages create the right rows after confirmation; an Offer past its end date is not used by the Content Strategist.

## Demoted to Could (ADR 0012)

- T34: Templates `quote_card` + `split_story` (F4.3, 3+ templates). · B · C
- Brand Brain correction in chat (F2.6, revise mode of T12). · A · C
- Plan changes from free text (F3.3). · A · C

## Could (only after Checkpoint 3)

- T40: Voice notes with faster-whisper. · C
- T41: Facebook cross-post (uses the second Zernio slot). · C
- T42: Brand Brain correction via web. · C
- T43: AI background generation behind `ImageGenPort`. · C
- T47: Price-list extraction: the Owner sends a photo or PDF of their price list and the Agency proposes Products to confirm (F8.8). · A · C

## Tests (minimum bar)

Unit tests for deterministic logic only (fast, no network): state machine transitions (onboarding, post, plan), button router guards, webhook signature + dedupe, quality checks, render spec validation, contrast guard, upload validation (kind, type, size limits), `reel_suitable` rules, archived material hidden from agents. Live LLM tests are marked `@pytest.mark.live` and excluded by default. No frontend tests.
