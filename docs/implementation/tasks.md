# Task breakdown

Each task can be handed to a coding agent as-is: "Implement T13 from docs/implementation/tasks.md". Every task lists what to read, what to build and how to verify it. IDs match the timeline in [plan.md](plan.md).

Legend: **A** = Track A (Brain), **B** = Track B (Surface), **AB** = together. Priority: M = Must, S = Should, C = Could. Priorities follow [ADR 0016](../decisions/0016-demo-scope-one-post.md): the Must tasks build the demo (a short onboarding, then one post the Owner asks for in the chat, approved and really published); Should starts only after Checkpoint 3; Could only if everything else is solid.

## H0–1: Kickoff (together)

### T00: Backend scaffold · AB · M

- Read: [architecture/overview.md](../architecture/overview.md#repository-layout), [setup.md](setup.md)
- Build: `backend/` with `uv init`, Python 3.13 (per [`.claude/rules/python.md`](../../.claude/rules/python.md)), deps: `fastapi`, `uvicorn[standard]`, `anthropic`, `pydantic`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `httpx`, `google-genai`, `supabase`, `pillow`, `pillow-heif` (`openai` only with T43); dev deps: `pytest`, `pytest-asyncio`, `ruff`. `app/main.py` with `/health`, `app/config.py` (pydantic-settings, all env vars from setup.md), `Dockerfile` per [`.claude/rules/docker.md`](../../.claude/rules/docker.md) (no browser: images come from the image service, [ADR 0018](../decisions/0018-ai-image-generation-service.md)), `.env.example`. No `ffmpeg` yet: it's added by T36 if the Could video work starts. Add the backend job (ruff + pytest) to `.github/workflows/ci.yml` and to the `CI` gate.
- Done when: `uv run uvicorn app.main:app` serves `/health`; the Docker image builds and runs.

### T01: Frontend scaffold · AB · M

- Build: `frontend/` with `create-next-app` (TypeScript, App Router, Tailwind, ESLint), shadcn/ui init with the tokens from [design/web-app.md](../design/web-app.md#visual-language), `lib/api.ts` with `NEXT_PUBLIC_API_URL`, placeholder pages `/o/[token]`, `/dev/chat`.
- Done when: deployed on Vercel; `/dev/chat` renders.

### T02: Schema + contracts · AB · M

- Read: [architecture/data-model.md](../architecture/data-model.md), [architecture/agents.md](../architecture/agents.md), [architecture/api.md](../architecture/api.md#internal-module-interfaces)
- Build: Alembic setup + initial migration `migrations/versions/0001_initial.py` with the whole schema from data-model.md (the Could tables and columns too: they cost nothing now and a migration mid-hackathon does), applied to Supabase; `app/db/models.py` (SQLAlchemy 2 typed models) + `session.py`; `app/agents/schemas.py` (all Pydantic models: BrandBrain, AssetAnalysis, PostCopy, ImageBrief, WeeklyPlan, PostIdeas, ...; VideoAnalysis and ReelSpec can stay stubs); `app/channels/base.py`; `app/publishing/base.py`; `app/imagegen/base.py`; `app/carousel/schemas.py` (CarouselCopy, CarouselBrief, TextCheck); `app/copy/messages_es.py` (copy deck from conversation-design.md); `frontend/lib/api.ts` types.
- Done when: `python -c "from app.agents.schemas import BrandBrain; print(BrandBrain.model_json_schema())"` works; every table exists in Supabase, including `post_variations` and `post_slides`, `posts.format` accepts `carousel`, and `posts.candidate_asset_ids` is there.

### T03: Deploy + webhook verification · AB · M

- Read: [ADR 0017](../decisions/0017-backend-host-railway.md), [integrations.md § Kapso setup](../architecture/integrations.md#kapso-setup-hour-1)
- Build: backend deployed on Railway (root directory `backend/`, one replica, Railway domain) with env vars; Kapso webhook pointed at `https://<backend>/webhooks/whatsapp` (a stub that logs the raw payload and headers and returns `200`). Run the Kapso first-hour test ([open questions](../open-questions.md#whatsapp-through-kapso-first-hour-test)) and record the answers there, including a Spanish voice note: is `message.kapso.transcript.text` in the first webhook, and is it right?
- Done when: `/health` is reachable over HTTPS on the Railway domain; a message sent to the Kapso number shows up in the backend logs with its payload and signature header. If it doesn't within the hour, switch to plan B (Meta direct, [ADR 0020](../decisions/0020-whatsapp-via-kapso.md)).
- Built (2026-10-18): the real backend (not a stub) is deployed on Railway: `backend/Dockerfile` and `.dockerignore`, `alembic upgrade head` as pre-deploy, healthcheck on `/health`, one replica in `us-east4-eqdc4a`, env vars loaded from the local `.env` plus the Supabase values. Settings live in Railway and are documented in [backend README § Deploy](../../backend/README.md#deploy) (Config as Code is deprecated, [ADR 0017](../decisions/0017-backend-host-railway.md#as-built-2026-10-18-t03)). Kapso was repointed by hand: the old tunnel webhooks on the Sandbox number are paused and a new "Message received" webhook points at the Railway domain.
- Done-when met (2026-10-18, Railway logs): `/health` answers 200 over HTTPS; a WhatsApp message reached `POST /webhooks/whatsapp` (200 in 11 ms, signature valid), was queued, got an orchestrator turn from Gemini (200) and two Kapso send-message calls (200). That also shows outbound traffic from the container to Supabase (pre-deploy), Gemini and Kapso. **Still pending:** connecting the GitHub repo for deploy-on-push (after this PR merges, since `main` has no Dockerfile yet) and an outbound check against Zernio.

## H1–6

### T10: LLM client · A · M

- Read: [architecture/agents.md § LLM client conventions](../architecture/agents.md#llm-client-conventions)
- Build: `app/llm/client.py` on Gemini ([ADR 0023](../decisions/0023-gemini-text-llm.md)): `structured(agent, system, history, output_model, thinking_level, business_id, job_id=None) -> T` and a function-calling step for the orchestrator. Writes `agent_runs`. Raises `LLMError` on a non-`completed` status, empty output or SDK error. **Started:** `ChatModel` / `GeminiChat.reply()` (text turn, stateless history with thought steps kept) is in, with function calling (`tools` in, `Reply.function_calls` out; a turn that only calls tools ends in `requires_action`) and `structured(agent, system, content, schema, thinking_level)` from T56, and `grounded(...)` (structured with built-in tools) for the Niche Analyst (T58); `business_id`, `job_id` and `agent_runs` are still to do.
- Done when: a pytest (marked `live`, skipped without key) gets a valid small Pydantic object back and an `agent_runs` row exists.

### T11: Asset Analyst (photos and logo) · A · M

- Build: `app/agents/asset_analyst.py` + prompt (photo and logo mode; a photo's WhatsApp caption is passed as the owner hint); Pillow palette extraction util `app/agents/palette.py` (5 colors, skip near-white/black/transparent). Product suggestions written to `asset_products` are Could (F8.5).
- Done when: running it on 3 demo photos + logo returns sensible `AssetAnalysis`; palette of the demo logo looks right.
- **Built (photo mode):** `app/agents/asset_analyst.py` + `prompts/asset_analyst.md`, run by the `analyze_asset` job (`app/jobs/asset.py`) on the photo's `{asset_id}-llm.jpg` copy, with the Owner's hint, the Catalog and the Product the Owner linked the photo to (step 2 of the wizard). Product ids outside the Catalog and colors that aren't hex are dropped in code; the suggested `product_ids` stay in the analysis and are not written to `asset_products` (F8.5, Could). Logos aren't analyzed: their Pillow palette is taken at upload (T24, `app/onboarding/uploads.py:logo_palette`, which skips transparent pixels), and only photos are queued. On the free tier one analysis took 33–90 s.

### T12: Brand Strategist · A · M

- Build: `app/agents/brand_strategist.py` + prompt, create mode. Reads the 1–5 wizard Products from `products`; with "Todavía no tengo logo ni colores" it uses the neutral default palette and says in the summary that colors come later. Revise mode (F2.6) and palette proposals (F2.9) are Could (T54).
- Done when: with the demo business inputs (fixture `tests/fixtures/demo_business.json`), it returns a BrandBrain whose `whatsapp_summary` the owner-teammate agrees with.
- **Built:** `app/agents/brand_strategist.py` + `prompts/brand_strategist.md` (thinking `high`), run by `generate_brand` (`app/jobs/brand.py`), which waits up to 60 s for the photo analyses, saves a `brand_brains` version, sets `awaiting_brand_confirmation` and sends `brand_summary` with `brand_ok` / `brand_fix`. Enforced in code: featured Products only from the Catalog (with their Catalog names), the questionnaire's goal and posts per week (3 when the wizard doesn't ask, [ADR 0032](../decisions/0032-instagram-first-onboarding.md)), the "what to avoid" answer first in `constraints`, the Owner's colors over the model's (the neutral palette without colors), the logo's asset id; a summary over 600 characters gets one retry. Revise mode (F2.6, Could) is in too: after `[Corregir algo]` the Owner's next message runs it on the latest version (`reason = 'correction'`). The `BrandBrain` gained `visual_identity`, which agents.md defined but left out of the model. First live run (5 photos, 2 Products): 67 s and ~7,300 thought tokens for the brand, after the analyses.

### T13: Copywriter · A · M

- Build: `app/agents/copywriter.py` + prompt (create; revise mode is used by T17 revisions, Should). Takes `owner_words` and keeps the angle and details the Owner asked for, in the Brand Brain voice. Carousel mode ([ADR 0022](../decisions/0022-carousels-in-mvp.md), used by T55): returns `CarouselCopy` (caption, hashtags, 3–5 slides by default or the Owner's number up to 10, `slides[0].role == "cover"`, headline ≤ 6 words, body ≤ 20 words), with no fact on a slide that isn't in the brief, a Product, an Offer or `owner_words`.
- Done when: 3 different briefs produce Rioplatense captions within length limits, respecting emoji policy and constraints; a request with "que se luzca la madera" produces a caption about the wood; carousel mode with `slide_count = 5` returns 5 slides, cover first, within the word limits.

### T14: Art Director · A · M

- Read: [agents.md § Art Director](../architecture/agents.md#art-director), [ADR 0018](../decisions/0018-ai-image-generation-service.md)
- Build: `app/agents/art_director.py` + prompt: picks the reference photos (the Owner's photos from `posts.candidate_asset_ids` first, else the best matches from the library) and writes the image prompt from the Brand Brain, the brief and trend notes (optional input: the latest [Niche Report](../architecture/agents.md#niche-analyst), [ADR 0025](../decisions/0025-weekly-niche-report.md)). Fixed prompt rules appended in code (image Posts: no text, prices, offers or logo changes; keep the real product). Post-validation (asset ownership, candidate membership, 1–10 references, rules present) with one retry; fallback brief.
- Build (carousel mode, used by T55, [ADR 0022](../decisions/0022-carousels-in-mvp.md)): returns `CarouselBrief`: 1–10 references, one English `style_prompt` shared by every slide (palette hex, typography, layout grid, text safe area), one `SlideScene` per `CarouselCopy` slide in the same order (scene only, no text), Spanish `style_notes`. Post-validation adds: one scene per slide, indexes 1..n in order.
- Done when: given copy + 4 candidate photos it returns a valid `ImageBrief`; given 2 Owner photos its references include those 2 (interim default: only those 2, see the open question on the photo library); the fixed rules are always in the prompt; invalid outputs are corrected or fall back; given a 5-slide `CarouselCopy` it returns a `CarouselBrief` with 5 scenes.

### T15: Image generation adapter + resize · A · M

- Read: [integrations.md § Image generation](../architecture/integrations.md#image-generation), [ADR 0019](../decisions/0019-image-provider-gemini.md), [research/image-generation-providers.md](../research/image-generation-providers.md)
- Build: `app/imagegen/base.py` (`ImageGenPort.generate(prompt, reference_images, style_image=None)`, `GeneratedImage`, errors `ImageGenError`, `ImageGenBlocked`, `ImageGenNoImage`, `ImageGenUnavailable`), `gemini.py` (`gemini-nano-banana-2.1` through `client.aio.models.generate_content`, `ImageConfig(aspect_ratio="4:5", image_size="2K")`, `GEMINI_THINKING_LEVEL`, client retries set explicitly, `thought` parts skipped, no-image responses mapped to `ImageGenBlocked` / `ImageGenNoImage`, a process-wide semaphore of `IMAGE_GEN_MAX_CONCURRENCY`; details in [integrations.md § Image generation](../architecture/integrations.md#image-generation)), `mock.py` (returns the first reference photo), `IMAGE_GEN` switch; `app/media/images.py:prepare_reference` (HEIC ok, ≤ 1536 px long side, JPEG) and `to_post_image` (crop to 4:5, resize to 1080×1350 JPEG); provider `usage` logged to `agent_runs` (`agent = 'image_gen'`).
- Done when: `uv run python -m app.carousel.cli --spec tests/fixtures/carousel_spec.json --photos <demo photos> --out out/carousel` (add `--slides 1` for a single image) turns the demo business's real photos into 1080×1350 JPEGs that still show the real product, the later slides anchored on the cover; its `report.json` confirms 4:5 at 2K, and the latency and cost per image are written into the research doc's open points.

### T20: WhatsApp channel + webhook · B · M

- Read: [integrations.md § WhatsApp](../architecture/integrations.md#whatsapp), [ADR 0020](../decisions/0020-whatsapp-via-kapso.md), [api.md](../architecture/api.md), T03's first-hour test results
- Build: `app/channels/kapso.py` against Kapso's REST API with `httpx` (send_text, send_image, send_buttons with optional image or video header, `mark_read(message_id, typing=False)`, download_media); `POST /webhooks/whatsapp` with Kapso's signature check, payload parsing to a normalized `InboundMessage` model (text, button reply, image with caption, audio with transcript), dedupe behind a `DedupeStore` and handling behind an `InboundHandler` (in-memory dedupe and an echo handler until T02 and T23; T02 then dedupes by `external_id` and stores in `messages`); status updates.
- Done when: sending "hola" from a test phone stores the message and an echo reply arrives; duplicate deliveries are ignored (unit test with a fixture payload).

### T21: Simulator channel + dev endpoints · B · M

- Build: `app/channels/simulator.py` (stores outbound in `messages`), `/dev/sim/*`, `/dev/businesses/{id}/reset`, `/dev/agent-runs` per api.md; `channel_for(business)`.
- Done when: posting a message to `/dev/sim/{phone}/messages` runs the same inbound handler and the echo shows up in `GET .../messages`.

### T22: `/dev/chat` UI · B · M

- Read: [design/web-app.md § /dev/chat](../design/web-app.md#devchat-whatsapp-simulator-must)
- Build: WhatsApp-like chat with text, images, interactive buttons, image upload with an optional caption (several images in a row), polling, reset, debug side panel.
- Done when: a full conversation is usable from the browser, buttons send `button_reply`, and two photos + a caption arrive as two image messages.

### T23: Inbound handler + onboarding router (Flow 1) · B · M

- Read: [product/user-flows.md](../product/user-flows.md) (state machines, Flow 1), conversation-design.md copy deck
- Build: `app/conversation/onboarding.py`, built as `OnboardingGate`: an `InboundHandler` that wraps `ChatHandler` when `DATABASE_URL` is set. It works under a per-sender `asyncio.Lock`, creates the Business on first contact, and owns the states before the form: `new` → welcome → `awaiting_name` → the name (text or a voice-note transcript) and a magic link → `awaiting_web_form` → `link_reminder` with a new link on any message. The welcome (re-sent when the answer isn't a name) and the reminder go out at most once per 30 s, so an album gets one. Messages written up to the second the welcome went out aren't taken as the name. From `generating_brand` on, every message goes to the chat. No LLM: the texts are the copy deck's fixed rows.
- Done when: new number → welcome → name → magic link with a working URL, both on WhatsApp and simulator; unit tests for the state transitions.

## H7–12

### T16: Job runner · A · M

- Build: `app/jobs/runner.py` per [overview.md § Background jobs](../architecture/overview.md#background-jobs): `enqueue`, semaphore, `jobs` rows, failure → `job_failed` message with `retry:{job_id}` button, startup cleanup of stale `running` jobs.
- Done when: a dummy job runs, a failing dummy job sends `job_failed` in the simulator.
- **Built:** `app/jobs/runner.py` polls `jobs` every second instead of starting a task at enqueue time ([overview.md § Background jobs](../architecture/overview.md#background-jobs)); `app/jobs/setup.py` registers `analyze_asset` and `generate_brand` and is started by the app's lifespan when the database, Storage, Gemini and WhatsApp are configured. Only `generate_brand` sends `job_failed`; stale `running` jobs are failed at startup and every minute. `agent_runs` is still not written (T10).

### T17: Job pipelines · A · M

- Read: [agents.md § Job pipelines](../architecture/agents.md#job-pipelines)
- Build (Must): `jobs/asset.py` (photo and logo), `brand.py`, `post.py` (`generate_post`: waits ≤ 30 s for the candidate photos' analyses, then Copywriter → Art Director → image generation, the variations in parallel → resize → upload → `post_variations`; the carousel branch is T55), each sending its WhatsApp message via `channel_for`. Storage upload of post images (new path per revision and variation).
- Build (Should, after Checkpoint 3): `plan.py` (only when the Owner asks; plan approval creates posts and generates them sequentially) and `revise_post` with the Feedback Classifier (F4.4). Plan changes from free text (F3.3) are Could. Video and Reels are Could (T36, T39).
- Done when (Must): from the simulator, after onboarding (or the `/dev` seed), "hacé un post de la mesa Nórdica" produces the variations and, after a pick, a post preview with buttons.

### T18: Button router · A · M

- Build: `app/conversation/button_router.py` with the Must IDs from [api.md § Button IDs](../architecture/api.md#button-ids) (`brand_ok`, `brand_fix`, `post_approve`, `post_change`, `post_discard`, `post_replace`, `post_publish`, `post_retry`, `photo_post`, `retry`, `noop`; `variation_pick` if the Owner picks with buttons, see T26), state guards (`post_approve` needs a picked variation), stale-button reply. `brand_ok` sends the post-onboarding message (T48). Plan and scheduling buttons come with their Should tasks; `reel_post` with T39.
- Done when: unit tests cover each button's allowed/forbidden states.
- **Built:** `app/conversation/button_router.py`, called by `ChatHandler` for every button reply (under the sender's lock). Each tap does its work in code and returns a typed event that the orchestrator answers ([ADR 0026](../decisions/0026-owner-messages-from-the-orchestrator.md)); `events.buttons` attaches the next buttons (the post's [Aprobar] [Cambiar] [Descartar] go under the model's follow-up from #31, [Publicar ahora] after approving, [Sí, otro] after discarding, [Reintentar] on a failed publish). Brand and job buttons work on the database (`app/conversation/brand.py`, `app/jobs/queue.py:retry_failed`); post buttons on T56/T57's in-memory posts, which gained `approved` and `discarded`. "subilo" still publishes a pending or approved post. `post_change` leaves the post id in the event note so the orchestrator remakes it with `create_post(replaces=…)`; `post_replace` remakes it from the same request; `post_retry` publishes again under a new idempotency key (`{id}-r{n}`). Photos sent without a word get no buttons (the model's one question), though `photo_post` is handled. `variation_pick` (T26), `post_schedule` (T30) and the plan buttons (Should) are `StaleButton`.

### T56: Post on request in the chat, before the database · A · M

The first slice that joins the WhatsApp chat ([ADR 0020](../decisions/0020-whatsapp-via-kapso.md)), the Gemini replies (ADR 0023, PR #18) and image generation ([ADR 0019](../decisions/0019-image-provider-gemini.md), [ADR 0022](../decisions/0022-carousels-in-mvp.md)). Everything lives in memory until T02; T19 moves it onto the database and the job runner (T16).

- Read: [agents.md § When image generation runs](../architecture/agents.md#when-image-generation-runs), [§ Tools](../architecture/agents.md#tools), `docs/research/gemini-api.md` (function calling) and `app/conversation/chat.py`, both from PR #18
- Build:
  - LLM client: function calling in `GeminiChat` (tool declarations in, `function_call` steps out, `function_result` steps back with the same `call_id`), and a structured-output call (part of T10).
  - `ChatHandler`: the loop from [§ Per-turn algorithm](../architecture/agents.md#per-turn-algorithm), max 5 steps, with only `create_post` registered. The `create_post` description says when to call it.
  - Photos: inbound images are downloaded with `channel.download_media`, passed through `prepare_reference` and kept in memory per sender (last 10, 30 minutes), and listed to the model as `<recent_photos>` with short ids. A photo with a caption runs a turn; one without gets a short "guardé la foto" reply. No debounce yet (T49).
  - `create_post(brief, asset_ids, format: "image" | "carousel", slide_count)`: guards from [§ Tools](../architecture/agents.md#tools) (`generation_in_progress`, `daily_limit` with `MAX_POSTS_PER_DAY`, `unknown_asset`) kept in memory per sender, then an `asyncio` task (held in a set so it isn't garbage-collected) and `{post_id}` back to the model at once.
  - The task: one structured Gemini call turns the brief and photos into the generator's input (a stand-in for T13 and T14: `CarouselCopy` + `CarouselBrief`, or an image prompt for `format = "image"`), then `CarouselGenerator.generate` or one `ImageGenPort.generate` + `to_post_image`. The JPEGs are served by the backend at an unguessable path under `PUBLIC_BACKEND_URL` (Supabase `renders` replaces it in T17) and sent with `send_image`, carousel slides in order with "1/n" captions, then the caption text. A failure sends a fixed message from `copy/messages_es.py` and frees the guard.
- Done when: unit tests with a scripted fake `ChatModel` and a counting fake `ImageGenPort` show that "hola" and "¿cuánto sale un post?" get text and zero image calls, a request for a post makes exactly one, a second request while one is generating gets `generation_in_progress`, and the `MAX_POSTS_PER_DAY + 1`-th gets `daily_limit`. On real WhatsApp with `IMAGE_GEN=mock` and then once with `gemini` at 1K: a photo + "armame un carrusel de 3 con esta mesa" → an acknowledgement within seconds, then 3 numbered slides.
- **Built:** `app/conversation/chat.py` (loop, photo batches), `photos.py`, `tools.py`; `app/posts/` (`PostMaker` with the guards, `PostDrafter`); `app/media/public.py` (`GET /media/{token}.jpg`). Changes from the list above, after the first test on WhatsApp: WhatsApp sends an album as an `unsupported`/`album` header (ignored) plus one message per photo, so photos wait 5 s after the last one and are answered once, with any text sent meanwhile (the debounce from T49, without the `photo_saved` button); `create_post` takes `style: "photos" | "design"` instead of `format` (one photo → single image, several → carousel, one slide per photo; [agents.md § Conversation rules](../architecture/agents.md#conversation-rules)) and answers `{"error": "no_photos"}` without a photo; the context block rides on the current user step ([§ Per-turn algorithm](../architecture/agents.md#per-turn-algorithm)). When a post is sent (or fails), `PostMaker` adds a note to the sender's history (`[post <id> sent to the Owner]` with the photos, slide headlines and text), so a later "cambiale el título" has context; until `revise_post` exists the model remakes the post with `create_post`. Only designs count toward `MAX_POSTS_PER_DAY`, and WhatsApp photos over `MAX_PHOTO_MB` get `photo_too_big`. A turn still running after 20 s sends `still_working` / `looking_at_photos` once and then re-sends the typing indicator every 20 s, since WhatsApp hides it after about 25 s. The draft call took 72–111 s on the free tier, and a turn with 5 photos took 77 s after two Gemini 503s. Once T12 was built, `PostDrafter` started reading the sender's latest Brand Brain version (`BrandBrains` in `app/conversation/library.py`) as a `<brand_brain>` block at the end of its system prompt ([agents.md § Brand Brain](../architecture/agents.md#brand-brain)), without `whatsapp_summary` and `posting`. It reads it on every post, so a correction applies to the next one.

### T57: Approve and publish from the chat, before the database · A · M

The slice after T56 ([ADR 0007](../decisions/0007-approve-every-post.md), [ADR 0024](../decisions/0024-mvp-single-demo-instagram-account.md)): once `create_post` has sent a post, the Owner writes "subilo" and it goes to the demo Instagram account through `PublisherPort`. Everything lives in memory until T02; T50 and T30 later move it onto `posts` and the job runner (T16).

- Read: [agents.md § Conversation rules](../architecture/agents.md#conversation-rules) and [§ Tools](../architecture/agents.md#tools), [integrations.md § Zernio](../architecture/integrations.md#publishing-provider-zernio) (idempotency), `app/conversation/chat.py` and `app/posts/maker.py` from T56, `app/publishing/` from T27
- Build:
  - `app/posts/store.py`: `InMemoryPosts` per sender, filled by `PostMaker` once a post has been sent (`pending_approval`, its image paths in slide order, caption + hashtags). `PublicImages.keep` re-serves the images of a post that is being published, so the FIFO eviction can't drop them.
  - `app/conversation/approval.py`: the explicit approval is computed in code from the Owner's own words (message or voice transcript), never by the model: an imperative or infinitive of subir/publicar/postear with its pronoun ("subilo", "publicalo", "dale, subila"), "aprobado". When unsure it is not approval: praise alone, negations ("no lo subas", "todavía no"), questions and "can you" phrasings ("¿puedo subirlo?", "podés subirlo"), a bare "subí estas fotos" and any turn with photos attached or waiting unused. A time or a deferral ("subilo mañana", "después", "cuando termine") gets `scheduling_not_available`. With several pending posts the tool returns a numbered list and remembers the ids it listed; on the next turn only, a number ("2", "la segunda", "el último") picks the post from that list in code, and a listed post that is no longer pending is not approved (the number never slides to another post).
  - `approve_post(post_id, next = "publish_now")` in `tools.py`, guarded in `PostPublisher.approve`: `unknown_post`, `post_not_pending` (publishing, publish_pending, published, failed, replaced: this is the double-publish guard), `approval_not_explicit` / `several_pending` / `no_pending_post` / `scheduling_not_available` (only the post this turn's approval names can be published, whatever the model passes), `need_ig` (no `ZERNIO_ACCOUNT_ID` with `PUBLISHER=zernio`; no URL until the connect flow exists).
  - `create_post(replaces?: post_id)`: remaking a sent post retires the old one (`replaced`) when the new one is sent; an unknown or non-pending id is ignored.
  - `app/posts/publish.py`: an `asyncio` task (held in a set) calls `PublisherPort.publish(ZERNIO_ACCOUNT_ID, caption, media, idempotency_key = post id)`. A timeout, a 5xx or an accepted post with no id (`PublishRetryable`) is retried once with the same key; a `409` for a request still in flight (`PublishInProgress`) waits `min(Retry-After or 5 s, 30 s)` and resends; 3 attempts in all. `published` sends the link; `pending`, and any outcome still unknown after the attempts, sends "Instagram lo está procesando" (never a failure: the post may be live; the Owner learns the final state from Instagram until the webhook, T29); only a definite failure (`failed`, a 4xx, duplicate content) sends the failure message, and `failed` is terminal. The outcome message waits for the history lock, so it never arrives before the turn's own "lo subo".
  - The publisher is built once (`get_publisher`) and injected through `build_inbound_handler`.
- Done when: unit tests (fake `ChatModel`, fake channel, fake publisher) cover "subilo" with one pending post (publishes once, `idempotency_key` = post id, link sent), "me encanta" (no publish), "subilo" with two pending posts (asks which; a number then picks it), with none pending, a second "subilo" while publishing, `pending`, `failed` and `PublisherError`, a timeout retried once with the same key, `409` waits, and the guard holding when the model calls the tool on a non-approval turn. With `PUBLISHER=mock` the whole flow runs without network.
- Follow-up: retrying a `failed` post needs a new key (`{post_id}-2`), because Zernio replays the original post for the same key within 24 hours; `failed` is terminal until then.

### T19: Orchestrator v1 · A · M

- Read: [agents.md § Orchestrator](../architecture/agents.md#orchestrator), conversation-design.md (system prompt skeleton, examples)
- Build: `app/orchestrator/orchestrator.py` (manual loop, max 5 steps, starting from T56's `ChatHandler`), `tools.py` with the Must tools (`create_post` with `asset_ids`, `pick_variation`, `approve_post`, `publish_post` now, `discard_post`, `list_posts`, `get_brand_summary`, `cancel_pending`), strict schemas and guards, `prompts/system.md` with the [conversation rules](../architecture/agents.md#conversation-rules); context builder (incl. `<recent_photos>`); `awaiting` handling (free text routed with pending context). Only built tools are registered.
- Done when: the example conversations in conversation-design.md work in the simulator; "publicalo" on a non-approved post does not publish.
- **Started (with T18):** the chat reads the wizard's photos as `<brand_photos>` (`b1`, …) through `BrandLibrary`, so "hacé un post de la mesa nórdica" uses the photo the Owner linked to that Product instead of asking for it again. Posts, history and WhatsApp photos are still in memory.

### T48: Open chat after onboarding (F1.10) · A · M

- Read: [agents.md § Conversation rules](../architecture/agents.md#conversation-rules), `ready_open_chat` in conversation-design.md
- Build: `brand_ok` → state `active` + `ready_open_chat` ("¿En qué te puedo ayudar hoy?"); no plan is proposed or generated; the system prompt describes what the Owner can ask (a post, with or without photos; Should features only once built).
- Done when: after confirming the Brand Brain in the simulator, the bot asks "¿En qué te puedo ayudar hoy?" and no `generate_plan` job runs.

### T49: Post from photos and a request, with at most one question (F4.5) · A · M

- Read: [agents.md § Tools](../architecture/agents.md#tools) (photo debounce), [design/mockups/](../design/mockups/README.md) Chat-1, Chat-5
- Build: inbound photo batching (5 s debounce after the last photo; caption or text within it → one orchestrator turn with `<recent_photos>`, else one `photo_saved` for the batch); `create_post(brief, asset_ids)` storing `candidate_asset_ids`; the "at most one question, only when it changes the result" rule in the prompt, with `awaiting = post_brief` while waiting for the answer so the answer goes to the same post.
- Done when: in the simulator, 2 photos + "me llegó esta mesa ratona nueva, armame algo para subir" → one short question → the answer → variations whose image brief references those 2 photos; "hacé un post de la mesa Nórdica" with no photos → no question, straight to generation; a single photo with no text → `photo_saved` once.

### T24: Onboarding REST + uploads · B · M

- Read: [api.md § Onboarding](../architecture/api.md#onboarding-web-wizard), [research/media-uploads.md](../research/media-uploads.md)
- Build: `app/api/onboarding.py` + `app/storage.py`. Uploads go **browser → Supabase** (no multipart through the backend): `POST /api/o/{token}/uploads` accepts `logo` and `photo` only, validates content type and size (`MAX_PHOTO_MB`) and the 15-photo cap, creates the `brand_assets` row in `uploading` status and returns a signed Supabase upload URL (resumable/TUS for files > 6 MB); `POST /api/o/{token}/assets/{id}/complete` checks the object exists, converts HEIC → JPEG, writes the resized LLM copy (≤ 1568 px), runs logo palette sync and enqueues `analyze_asset`. `PUT /api/o/{token}/products` takes 1–5 Products. `PUT .../brand` accepts `no_brand_yet`. `/complete` (validations: 1–5 products, 3–15 photos; state change, enqueue `generate_brand`, WhatsApp message).
- Done when: all endpoints work via `curl` with a real token; a 16th photo and a video are rejected before upload; files land in the right buckets/paths.
- **Built:** the database part of T02 came first: Alembic with `migrations/versions/0001_initial.sql` (the whole schema from data-model.md, run statement by statement), `app/db/session.py`, and models in `app/db/models.py` only for the tables written so far (businesses, magic links, products, Brand assets, `asset_products`, jobs). Then `app/api/onboarding.py`, `app/storage.py` (Supabase Storage over httpx, the same endpoints as `storage3`), `app/onboarding/` (links, schemas, image processing) and `app/api/errors.py` (the `{"error": {code, message}}` shape, CORS from `FRONTEND_ORIGINS`). Changes from the list above: tickets are always `resumable = false`, since photos and logos are ≤ 10 MB and the wizard sends one `PUT`; the agents' copy is `{asset_id}-llm.jpg` at ≤ 1536 px (`prepare_reference`); a pending upload holds a photo slot for 2 h (the signed URL's life), so a ticket never completed stops counting; writes after `/complete` are `409 onboarding_completed`. Added after the first run of the wizard: each Product in step 2 takes up to 5 photos of its own (optional), uploaded like any photo and linked on `PUT /products` through `asset_ids`; they count toward the 3–15, and step 4 shows only the rest (frontend: `product-photos.tsx`, `photo-tile.tsx`). No job runner yet (T16), so `analyze_asset` and `generate_brand` are `queued` rows in `jobs` that nothing runs, and the wizard shows "Mirando…" on every photo until T11 and T16 exist. `POST /dev/onboarding-link` creates the Business and the link until T23 (WhatsApp onboarding) does; T23 reuses `app/onboarding/links.py`. The API tests run against a real Postgres (`TEST_DATABASE_URL`; a service in CI) and skip without one.

### T25: Onboarding wizard UI · B · M

- Read: [design/web-app.md § /o/[token]](../design/web-app.md#otoken-onboarding-wizard-must), [design/mockups/](../design/mockups/README.md) row 2, [user-flows.md § Flow 2](../product/user-flows.md#flow-2--web-onboarding-form-must)
- Build: the six steps of the second design pass ("Paso N de 6") plus the done and expired-token screens, autosave, color swatches, questionnaire controls. No IG connect step in the MVP ([ADR 0024](../decisions/0024-mvp-single-demo-instagram-account.md)). Step 2: up to 5 Products. Step 3: logo + colors, or "Todavía no tengo logo ni colores". Step 4: 3–15 photos with thumbnails, direct uploads to the signed URL with a progress overlay, retry on failure. The feed import screen (6b) is T53 (Could); until then step 6 must not promise it.
- Done when: completed on a real phone from the WhatsApp link in < 5 minutes with the demo materials.

### T26: Variations in WhatsApp and the simulator · B · M

Replaces the HTML templates task: post templates are superseded by [ADR 0018](../decisions/0018-ai-image-generation-service.md).

- Read: [user-flows.md § Flow 5](../product/user-flows.md#flow-5--post-generation-and-approval-must), [integrations.md § Sending](../architecture/integrations.md#sending), the draft `post_variations` copy in [conversation-design.md](../product/conversation-design.md)
- Build: send the variations of a Post as numbered images, then the pick prompt (`awaiting = variation_choice`); the pick by text reaches `pick_variation` (T19), by button `variation_pick` (T18) if the team chooses buttons; `/dev/chat` shows the images in order. Use the draft copy until the open question on how the Owner picks is settled.
- Done when: in the simulator and on a real phone, the variations arrive numbered and in order, "la 2" picks the second one, and the preview that follows shows that image.

### T27: Zernio publisher + connect · B · M

- Read: [integrations.md § Zernio](../architecture/integrations.md#publishing-provider-zernio)
- Build: `app/publishing/zernio.py` (ensure_profile, connect_url, publish now, 207 handling; scheduling comes with T30's Should part), `mock.py`, `/api/o/{token}/instagram/connect` + `/callback`, `PUBLISHER` env switch.
- Done when: a test publish to the demo IG succeeds (then delete the IG post by hand: Zernio can't delete a published Instagram post).
- MVP scope: one demo Instagram account from env (`ZERNIO_PROFILE_ID`, `ZERNIO_ACCOUNT_ID`); the connect endpoints, callback and wizard step 6 are out of the MVP ([ADR 0024](../decisions/0024-mvp-single-demo-instagram-account.md)).
- Fix after the first live run (2026-10-18): `publishNow` can answer 201 `publishing`, so `publish` now polls `GET /v1/posts/{id}` (2 s, up to 90 s) instead of reporting a failure, and returns `pending` if it is still not final.
- Started (PR #22): `app/publishing/` with `PublisherPort`, `ZernioPublisher` (`ensure_profile`, `connect_url`, publish now with 207 handling), `MockPublisher`, the `PUBLISHER` switch and the demo account env. Left: the live publish run on the demo IG, and wiring the publisher into `jobs/publish.py` (T30). The connect endpoints and callback are deferred by ADR 0024.

## H13–16

### T50: Approve and publish by writing (F5.6) · A · M

- Started (T57): the in-memory version of this task (the approval matcher, `approve_post(publish_now)`, the guards, the numbered question for several pending posts) is built and publishes through `PublisherPort`. Left here: move it onto `posts` and the job runner, and approval with a time (T30's Should part).
- Read: [agents.md § Conversation rules](../architecture/agents.md#conversation-rules), [ADR 0007](../decisions/0007-approve-every-post.md)
- Build: `approve_post(next = "publish_now")` for "subilo" / "publicalo" / "dale, subila"; the inbound handler's `explicit_approval` flag (approval phrase + exactly one `pending_approval` post, or the Owner named it); praise without an instruction ("me encanta") → "¿Lo subo?"; several pending posts → ask which one. Approval with a time ("subilo mañana a la tarde") answers that scheduling isn't available yet until T30's Should part exists.
- Done when: unit tests cover "subilo" with variations not picked yet (asks which one, no approval), "subilo" with one pending post (publishes), "me encanta" (asks), "subilo" with two pending posts (asks which), and "subilo" on a post that isn't pending (no publish); in the simulator "subilo" publishes through the mock publisher.

### T30: Publish job + guards · A · M

- Started (T57): the before-the-database slice (publish now from the chat, `idempotency_key` = post id, `pending` never reported as a failure, one retry on timeout/5xx, `409` waits `Retry-After`) lives in `app/posts/publish.py`. Left here: `jobs/publish.py` on the job runner and the `posts` table, and scheduling.
- Build (Must): `jobs/publish.py` (status guard, need-IG path, publish now, store permalink, messages). In the MVP the account id comes from `ZERNIO_ACCOUNT_ID`, so the need-IG path only fires when it is missing ([ADR 0024](../decisions/0024-mvp-single-demo-instagram-account.md)). Handle `PublishResult.status`: `pending` (Zernio is still publishing, or retrying on its own) means do not report a failure and do not re-publish, wait for the webhook (T29) or a status check. Pass `idempotency_key` derived from the Post id on every publish, so a retry after a timeout or a 5xx cannot publish twice. On `409 idempotency_conflict` (the first request with that key is still being processed, raised today as `PublisherError`), wait the `Retry-After` delay and resend with the same key: the `200` replay carries the original post ([Zernio OpenAPI](https://zernio.com/openapi.yaml), read 2026-10-18).
- Build (Should, F5.3): scheduling: `post_schedule`, `schedule_time` and approvals with a time in free text ("mañana a la tarde" → ISO in the Business's timezone via a tiny structured call; "a la tarde" defaults to 18:00), Zernio `scheduledFor`.
- Done when: approve → publish now on the real IG returns the permalink in WhatsApp. Should: "subilo mañana a la tarde" schedules for tomorrow 18:00 local and the bot confirms the time.

### T28: WhatsApp polish · B · M

- Build: post preview as interactive with image header (fallback to text + short body when > 1,024 chars); variations on a real phone (T26); inbound images → `brand_assets` (`source = 'whatsapp'`, caption kept as the owner hint) + `analyze_asset` + the T49 debounce; unsupported media reply (video, sticker, document, location while video is Could; audio is T40).
- Done when: Flow 5 and Flow 9 look right on a real phone; 2 photos + caption sent from a real phone reach the orchestrator as one request.

### T40: Voice notes · B · M

- Read: [ADR 0021](../decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md), [integrations.md § Speech-to-text](../architecture/integrations.md#speech-to-text), [research/voice-notes.md](../research/voice-notes.md), T03's first-hour test results
- Build: `InboundMessage` audio kind (media id, MIME, size, Kapso's transcript); `app/transcription/` (`TranscriberPort`, `gemini.py`, `mock.py`, `TRANSCRIBE_FALLBACK`); in `inbound.py`, resolve the transcript (Kapso → size check → download + Gemini → `audio_unclear`), store `type = 'audio'` with the transcript as `text`, then route it like text (onboarding router, orchestrator, T49 photo debounce); `[audio]` prefix and the ambiguous-number rule in the orchestrator prompt; `audio_unclear` and `audio_too_long` copy; simulator `{type: "audio", transcript}`.
- Done when: a Spanish voice note from a real phone asking for a post ("me llegó esta mesa, armame algo") after a photo gets the same result as the written request; a silent note gets `audio_unclear`.
- Tests: fixture Kapso payloads with and without a transcript; fallback order with the mock transcriber; empty transcript → `audio_unclear`; over `MAX_AUDIO_MB` → `audio_too_long`; a `live` test that transcribes a sample `.ogg` with Gemini.

### T31: Quality checks · A · M

- Build: `app/agents/checks.py` per [agents.md § Quality checks](../architecture/agents.md#quality-checks-cheap-deterministic) + retry-once wrapper used by Copywriter/Art Director.
- Done when: unit tests with crafted bad outputs trigger retries.

### T33: Demo seed · A · M

- Build: `app/db/seed.py` + `/dev/seed/demo`: creates the demo business with real photos and logo, its 5 Products, a reviewed Brand Brain, state `active`, connected IG account id from env. It's the stage fallback if live brand generation is slow, and the starting point for rehearsing the post request.
- Done when: a fresh environment reaches "active" in one call, and a post request works right after.

### T55: Carousels (F4.9) · AB · M

- Read: [ADR 0022](../decisions/0022-carousels-in-mvp.md), [agents.md § Copywriter, Art Director, Job pipelines](../architecture/agents.md#art-director), [ADR 0029](../decisions/0029-designed-slides-ai-scene-code-layout.md), [data-model.md](../architecture/data-model.md) (`post_slides`), [api.md § Internal module interfaces](../architecture/api.md#internal-module-interfaces), [integrations.md § Image generation](../architecture/integrations.md#image-generation), [user-flows.md § Flow 5](../product/user-flows.md#carousel-must-f49), the carousel copy in [conversation-design.md](../product/conversation-design.md)
- Prerequisite: T13 and T14 carousel modes, T15 with `style_image`, the image Post working end to end (Checkpoint 2).
- Build (A): `app/carousel/schemas.py`, `prompts.py` (`build_slide_prompt(brief, copy, index, *, anchored)`), `generator.py` (`CarouselGenerator(image_gen, text_checker=None)` with `generate` and `redo`: cover first, the other slides in parallel anchored on the cover, a redo of the cover anchored on slide 2; each output through `to_post_image`, text-checked, regenerated once on mismatch and flagged if it still fails); `app/agents/text_checker.py`; the carousel branch of `generate_post` (save `post_slides`, storage path `renders/{business_id}/{post_id}-r{revision}-s{idx}.jpg`); the `redo_slides(post_id, slides, feedback)` job (bumps `posts.revision` and copies the unchanged rows); the `create_post(format = "carousel", slide_count)` and `redo_slides` tools; `post_change` on a carousel asks which slide.
- Build (B): send the slides in order as images captioned "1/5", "2/5"…, then `carousel_preview`; `carousel_redo_ask` on `[Cambiar]`; `/dev/chat` shows the slides in order; `PublishMedia.urls` in `zernio.py` (several `mediaItems`, slide order) and `mock.py`.
- Done when: in the simulator, 3 photos + "armame un carrusel de 5 con estas fotos" → 5 numbered slides in order, each 1080×1350 with its `SlideCopy` text (or flagged), then `carousel_preview`; "cambiá la 3, más luminosa" redoes only slide 3 and keeps the other 4; "subilo" publishes 5 URLs in slide order through the mock publisher; one real Zernio carousel publish succeeds on the demo IG (then delete it). Measured latency and cost per carousel go into [open-questions.md](../open-questions.md#carousels-adr-0022).

## H16–21: tuning, then Should (only after Checkpoint 3)

### T32: Prompt tuning with real data · A · M

- Run the full demo flow with the furniture business 3 times; fix tone, hallucinations, length, and when the bot asks its one question. Keep a log of prompt changes in the PR description.

### T51: Match the Owner's style (F1.9) · A · S

- Build: `<owner_style>` in the context block (median words and casualness of the Owner's last 5 messages) and the prompt rule: short replies to short messages, fuller replies to long ones; captions keep the Brand Brain voice.
- Done when: the Chat-5 and Chat-6 conversations in [design/mockups/](../design/mockups/README.md) get replies of matching length in the simulator.

### T52: Ideas on request (F3.5) · A · S

- Build: Content Strategist ideas mode (`PostIdeas`, 3 items) + `suggest_ideas` tool storing the ideas in `conversation_state.ideas`; picking one ("la 2", "la del taller, sin caras") calls `create_post` with the idea and the Owner's extra instructions.
- Done when: "no sé qué subir, ¿se te ocurre algo?" lists 3 ideas that use existing photos, and "la del taller pero sin mostrar caras" creates that post with no faces in its variations.

### T17b: Weekly plan on request and revisions · A · S

- Build: T17's Should part: `plan_week` only when asked ("armame el plan de la semana"), plan buttons in T18, and `revise_post` with the Feedback Classifier (F4.4).
- Done when: the plan arrives only on request; "más corto y mencioná el envío gratis" produces a revised post.

### T58: Weekly Niche Report (F3.6, F3.7) · A · S

- Read: [agents.md § Niche Analyst](../architecture/agents.md#niche-analyst), [ADR 0025](../decisions/0025-weekly-niche-report.md)
- Done already: the Niche Analyst (`app/agents/niche_analyst.py`, grounded Gemini call, source checks, redirect resolution), the first niche's data, a CLI that saves a report, and its insights as trend notes of the `PostDrafter` (`NICHE_REPORT_PATH`).
- Build: the `niche_reports` migration and model, a `generate_niche_report` job kind in T16's runner, a weekly trigger (the runner has no schedule yet: every Monday per onboarded Business, retried later on `503`), the `niche_report` tool once the orchestrator runs on the database (T19), and trend notes read from the latest row instead of the file once post generation knows its Business.
- Done when: a Monday run saves one report per Business; "¿qué está funcionando en mi rubro?" answers with the report's `summary`, or starts the job when there is none this week.

### T59: Video generation port (Veo + mock, flag) · A · S

- Read: [ADR 0033](../decisions/0033-ai-generated-reels-veo.md), [integrations.md § Video generation](../architecture/integrations.md#video-generation-veo-adr-0033), [api.md § VideoGenPort](../architecture/api.md#internal-module-interfaces)
- Build: `app/videogen/` (`VideoGenPort`, `GeminiVideoGen`, `MockVideoGen` with a bundled MP4, `build_video_gen`), the `VIDEO_GEN_*` and `GEMINI_VIDEO_*` settings, `PublicVideos` and `GET | HEAD /media/{token}.mp4`. Nothing calls it yet: T67 wires the WhatsApp flow, T60 publishes the Reel.
- Done when: with `VIDEO_GEN_ENABLED=false` (default) no adapter is built; the factory refuses `gemini` without `GEMINI_VIDEO_API_KEY`; unit tests cover the adapter with a faked client; the live test exists and is not run in CI.

### T29: Zernio webhook · B · S

- Build: `POST /webhooks/zernio` with signature verification; `post.published` / `post.failed` / `account.connected`.
- Done when: a scheduled post 5 minutes ahead flips to `published` and the owner is notified.

### T38: Dashboard REST (read) · B · S

- Read: [api.md § Dashboard](../architecture/api.md#dashboard-read-should-editing-could)
- Build: `app/api/dashboard.py` under `/api/b/{token}`, the Should reads only: business + Brand Brain + Posts (+ current plan if T17b exists). `dashboard` magic links expire after `DASHBOARD_LINK_TTL_DAYS`; "¿dónde veo todo?" sends one through `send_dashboard_link`. The write endpoints (Products, assets, Offers, dashboard uploads) are Could (T38b).
- Done when: the read endpoints work via `curl` with a real token; an expired link gets the friendly expired error.

### T35: Dashboard `/b/[token]` (Inicio) · B · S

- Read: [design/web-app.md § /b/[token]](../design/web-app.md), the Dashboard artboard in [design/mockups/](../design/mockups/README.md)
- Build: the read-only Inicio page: business header, this week's Posts with status badges and Instagram links, the Brand Brain summary. The Catálogo, Contenido and Promos tabs are Could (T35b).
- Done when: on a real phone, the link from WhatsApp shows the demo business's posts with the right statuses.

### T60: Reels through Zernio · A · S

Part of story #64 (AI-generated Reels); the video itself comes from T59 and the WhatsApp flow is the story's third task.

- Read: [integrations.md § Zernio](../architecture/integrations.md#publishing-provider-zernio), [api.md § PublishMedia](../architecture/api.md), `app/publishing/zernio.py`, `app/posts/publish.py`
- Build: `ZernioPublisher` publishes `PublishMedia(format="reel")` as one `video` media item with `platformSpecificData.thumbOffset` for the cover; `PublishMedia.ai_generated` adds `isAiGenerated` (any format; nothing sets it yet). `Post.video` (`PostVideo`, like `PostImage`) and `video_cover_offset_ms` make `PostPublisher` build the Reel media from `public base URL + video.path`. Same Approval and guards as images ([ADR 0007](../decisions/0007-approve-every-post.md)); the mock publisher already accepts reels.
- Done when: unit tests with a faked HTTP client cover the Reel request, its errors and polling; a `@pytest.mark.live` Reel test exists (not run in CI); nothing publishes a video Post that was not approved.

## Could (only if everything above is solid)

### T53: Instagram feed import (F2.8) · B · C

- Read: [integrations.md § Reading the Owner's Instagram](../architecture/integrations.md#reading-the-owners-instagram-adr-0028), [ADR 0028](../decisions/0028-read-instagram-with-our-meta-app.md)
- **Built differently than first planned**: the read goes through our own Meta app with Instagram Login, not Zernio, whose read access was too thin; the import is automatic, with no step 6b review grid.
- Built: `POST /api/o/{token}/instagram/connect`, `GET /oauth/instagram/callback`, the `import_instagram` job, the Brand Strategist's `<instagram>` input, migration `0002`, wizard step 6 re-reading the state on return (the connect moved to step 2 with [ADR 0032](../decisions/0032-instagram-first-onboarding.md)).
- Done when: after connecting the demo IG (an Instagram tester of our Meta app), its profile and captions reach the Brand Strategist and its newest images become analyzed Brand assets with `source = 'instagram'`. Not yet checked against the live account.

### T54: Colors and a simple logo in the chat (F2.9) · A · C

- Read: [agents.md § Brand Strategist](../architecture/agents.md#brand-strategist), the WA-Sin-marca artboard in [design/mockups/](../design/mockups/README.md)
- Build: `propose_palettes` and `save_brand_colors` tools; after a Brand Brain with no colors, the bot asks for a photo that represents the Business, shows 3 named palettes, accepts a pick with a tweak, saves a new Brand Brain version, then offers a text logo or "más adelante".
- Done when: the WA-Sin-marca conversation works in the simulator and the next post uses the chosen colors.

### Moved down from ADR 0012

[ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md)'s Catalog, content and Reels stay the product direction; per ADR 0016 they are Could.

- T36: Video analysis (F8.3) · A · C. Add `ffmpeg` to the image (setup.md); `analyze_asset` for `kind = 'video'`: `ffprobe` metadata, ~6 keyframes ≤ 1568 px, one vision call returning `VideoAnalysis` (`reel_suitable`, `cover_offset_ms`). Done when a 15–60 s vertical video is `reel_suitable` and a 4-minute horizontal one is not.
- T37: Derived frame photos (F8.4) · A · C. Best frames saved as `photo` assets with `derived_from_asset_id`.
- T38b: Dashboard REST writes (F8.1, F8.2, F8.6) · B · C. Products CRUD, assets list and `PATCH`, Offers CRUD, dashboard uploads (photos and videos, 300 MB, needs Supabase Pro); archive only, never delete.
- T35b: Dashboard Catálogo, Contenido and Promos tabs · B · C. Per the wireframes in [design/web-app.md](../design/web-app.md).
- T39: Reels in the agents (F4.8) · A · C. Plan items and `create_post` with `format = 'reel'`, Copywriter Reel variant, Art Director Reel mode, Feedback Classifier Reel targets.
- T44: Reel publishing · B · C. One video media item by signed URL with `thumbOffset`; mock publisher support.
- T45: WhatsApp Reel preview · B · C. Video header when the preview transcode fits 16 MB, else cover + dashboard link.
- T46: Catalog and Offers from the chat (F8.7) · A · C. `list_catalog`, `save_product`, `save_offer` with confirmation; the onboarding promo as a draft Offer.
- T47: Price-list extraction (F8.8) · A · C. The Owner sends a photo or PDF of their price list and the Agency proposes Products to confirm.
- Inbound videos from WhatsApp · B · C. Stored as Brand assets and analyzed with T36.

### Other Could

- Brand Brain correction in chat (F2.6, revise mode of T12). · A · C
- Plan changes from free text (F3.3). · A · C
- T41: Facebook cross-post (uses the second Zernio slot). · C
- T42: Brand Brain correction via web. · C
- T43: OpenAI fallback adapter (`app/imagegen/openai.py`, `gpt-image-2.5-sunburst` through `/v1/images/edits`, size `1088x1360`) behind `ImageGenPort` ([ADR 0019](../decisions/0019-image-provider-gemini.md)). · A · C, or M as soon as Gemini fails the first test or blocks on stage. Needs `OPENAI_API_KEY` and possibly Organization Verification.

## Tests (minimum bar)

Unit tests for deterministic logic only (fast, no network): state machine transitions (onboarding, post), button router guards, webhook signature + dedupe, free-text approval (`explicit_approval`: one pending post, several, praise without instruction), photo debounce batching, voice-note transcript resolution, variation picking (`pick_variation`, approval blocked before a pick), quality checks, image brief validation (incl. candidate membership and the fixed prompt rules), carousel validation (slide count, cover first, one scene per slide) and `build_slide_prompt` (exact text, fixed rules), carousel anchoring order (cover first; a cover redo anchors on slide 2), resize to 1080×1350, upload validation (kind, type, size, 15-photo cap). Should and Could tasks add their own (plan state machine, time parsing, `reel_suitable` rules, archived material hidden from agents). Live LLM and image-service tests are marked `@pytest.mark.live` and excluded by default. No frontend tests.
