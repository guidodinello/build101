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
- Build: Alembic setup + initial migration `migrations/versions/0001_initial.py` with the whole schema from data-model.md (the Could tables and columns too: they cost nothing now and a migration mid-hackathon does), applied to Supabase; `app/db/models.py` (SQLAlchemy 2 typed models) + `session.py`; `app/agents/schemas.py` (all Pydantic models: BrandBrain, AssetAnalysis, PostCopy, ImageBrief, WeeklyPlan, PostIdeas, ...; VideoAnalysis and ReelSpec can stay stubs); `app/channels/base.py`; `app/publishing/base.py`; `app/imagegen/base.py`; `app/copy/messages_es.py` (copy deck from conversation-design.md); `frontend/lib/api.ts` types.
- Done when: `python -c "from app.agents.schemas import BrandBrain; print(BrandBrain.model_json_schema())"` works; every table exists in Supabase, including `post_variations`, and `posts.candidate_asset_ids` is there.

### T03: Deploy + webhook verification · AB · M

- Read: [ADR 0017](../decisions/0017-backend-host-railway.md), [integrations.md § Kapso setup](../architecture/integrations.md#kapso-setup-hour-1)
- Build: backend deployed on Railway (root directory `backend/`, one replica, Railway domain) with env vars; Kapso webhook pointed at `https://<backend>/webhooks/whatsapp` (a stub that logs the raw payload and headers and returns `200`). Run the Kapso first-hour test ([open questions](../open-questions.md#whatsapp-through-kapso-first-hour-test)) and record the answers there, including a Spanish voice note: is `message.kapso.transcript.text` in the first webhook, and is it right?
- Done when: `/health` is reachable over HTTPS on the Railway domain; a message sent to the Kapso number shows up in the backend logs with its payload and signature header. If it doesn't within the hour, switch to plan B (Meta direct, [ADR 0020](../decisions/0020-whatsapp-via-kapso.md)).

## H1–6

### T10: LLM client · A · M

- Read: [architecture/agents.md § LLM client conventions](../architecture/agents.md#llm-client-conventions)
- Build: `app/llm/client.py`: `async def structured(agent: str, system: list, messages: list, output_model: type[T], effort: str, business_id, job_id=None) -> T` and `async def tool_step(...) -> Message` for the orchestrator. Writes `agent_runs`. Handles `refusal` / `max_tokens` stop reasons with typed exceptions (`LLMRefusal`, `LLMTruncated`). Enables prompt caching and server-side fallbacks.
- Done when: a pytest (marked `live`, skipped without key) gets a valid small Pydantic object back and an `agent_runs` row exists.

### T11: Asset Analyst (photos and logo) · A · M

- Build: `app/agents/asset_analyst.py` + prompt (photo and logo mode; a photo's WhatsApp caption is passed as the owner hint); Pillow palette extraction util `app/agents/palette.py` (5 colors, skip near-white/black/transparent). Product suggestions written to `asset_products` are Could (F8.5).
- Done when: running it on 3 demo photos + logo returns sensible `AssetAnalysis`; palette of the demo logo looks right.

### T12: Brand Strategist · A · M

- Build: `app/agents/brand_strategist.py` + prompt, create mode. Reads the 1–5 wizard Products from `products`; with "Todavía no tengo logo ni colores" it uses the neutral default palette and says in the summary that colors come later. Revise mode (F2.6) and palette proposals (F2.9) are Could (T54).
- Done when: with the demo business inputs (fixture `tests/fixtures/demo_business.json`), it returns a BrandBrain whose `whatsapp_summary` the owner-teammate agrees with.

### T13: Copywriter · A · M

- Build: `app/agents/copywriter.py` + prompt (create; revise mode is used by T17 revisions, Should). Takes `owner_words` and keeps the angle and details the Owner asked for, in the Brand Brain voice.
- Done when: 3 different briefs produce Rioplatense captions within length limits, respecting emoji policy and constraints; a request with "que se luzca la madera" produces a caption about the wood.

### T14: Art Director · A · M

- Read: [agents.md § Art Director](../architecture/agents.md#art-director), [ADR 0018](../decisions/0018-ai-image-generation-service.md)
- Build: `app/agents/art_director.py` + prompt: picks the reference photos (the Owner's photos from `posts.candidate_asset_ids` first, else the best matches from the library) and writes the image prompt from the Brand Brain, the brief and trend notes (optional input; source not decided). Fixed prompt rules appended in code (no text, prices, offers or logo changes; keep the real product). Post-validation (asset ownership, candidate membership, 1–10 references, rules present) with one retry; fallback brief.
- Done when: given copy + 4 candidate photos it returns a valid `ImageBrief`; given 2 Owner photos its references include those 2 (interim default: only those 2, see the open question on the photo library); the fixed rules are always in the prompt; invalid outputs are corrected or fall back.

### T15: Image generation adapter + resize · A · M

- Read: [integrations.md § Image generation](../architecture/integrations.md#image-generation), [ADR 0019](../decisions/0019-image-provider-gemini.md), [research/image-generation-providers.md](../research/image-generation-providers.md)
- Build: `app/imagegen/base.py` (`ImageGenPort`), `gemini.py` (`gemini-nano-banana-2.1`, 4:5 at 2K, one image per call), `mock.py` (returns the first reference photo), `IMAGE_GEN` switch; `app/media/images.py:to_post_image` (crop to 4:5, resize to 1080×1350 JPEG); provider `usage` logged to `agent_runs` (`agent = 'image_gen'`).
- Done when: `uv run python -m app.imagegen.cli --brief sample.json --out out.jpg` turns the demo business's real photos into a 1080×1350 JPEG that still shows the real product; the first call confirms 4:5 at 2K, and its latency and cost per image are written into the research doc's open points.

### T20: WhatsApp channel + webhook · B · M

- Read: [integrations.md § WhatsApp](../architecture/integrations.md#whatsapp), [ADR 0020](../decisions/0020-whatsapp-via-kapso.md), [api.md](../architecture/api.md), T03's first-hour test results
- Build: `app/channels/whatsapp.py` against Kapso's REST API with `httpx` (send_text, send_image, send_buttons with optional image header, mark_read, download_media; typing indicator only if Kapso has one); `POST /webhooks/whatsapp` with Kapso's signature check, payload parsing to a normalized `InboundMessage` model (text, button reply, image with caption), dedupe by `external_id`, store in `messages`, background handling; status updates.
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
- Build: `app/conversation/inbound.py` (per-business `asyncio.Lock`, create business on first contact, route by type/state), `onboarding_router.py` (states `new` → `awaiting_web_form`, magic link creation, `link_reminder`, "link" keyword re-sends), stub for `button_router` and orchestrator (echo).
- Done when: new number → welcome → name → magic link with a working URL, both on WhatsApp and simulator; unit tests for the state transitions.

## H7–12

### T16: Job runner · A · M

- Build: `app/jobs/runner.py` per [overview.md § Background jobs](../architecture/overview.md#background-jobs): `enqueue`, semaphore, `jobs` rows, failure → `job_failed` message with `retry:{job_id}` button, startup cleanup of stale `running` jobs.
- Done when: a dummy job runs, a failing dummy job sends `job_failed` in the simulator.

### T17: Job pipelines · A · M

- Read: [agents.md § Job pipelines](../architecture/agents.md#job-pipelines)
- Build (Must): `jobs/asset.py` (photo and logo), `brand.py`, `post.py` (`generate_post`: waits ≤ 30 s for the candidate photos' analyses, then Copywriter → Art Director → image generation, the variations in parallel → resize → upload → `post_variations`), each sending its WhatsApp message via `channel_for`. Storage upload of post images (new path per revision and variation).
- Build (Should, after Checkpoint 3): `plan.py` (only when the Owner asks; plan approval creates posts and generates them sequentially) and `revise_post` with the Feedback Classifier (F4.4). Plan changes from free text (F3.3) are Could. Video and Reels are Could (T36, T39).
- Done when (Must): from the simulator, after onboarding (or the `/dev` seed), "hacé un post de la mesa Nórdica" produces the variations and, after a pick, a post preview with buttons.

### T18: Button router · A · M

- Build: `app/conversation/button_router.py` with the Must IDs from [api.md § Button IDs](../architecture/api.md#button-ids) (`brand_ok`, `brand_fix`, `post_approve`, `post_change`, `post_discard`, `post_replace`, `post_publish`, `post_retry`, `photo_post`, `retry`, `noop`; `variation_pick` if the Owner picks with buttons, see T26), state guards (`post_approve` needs a picked variation), stale-button reply. `brand_ok` sends the post-onboarding message (T48). Plan and scheduling buttons come with their Should tasks; `reel_post` with T39.
- Done when: unit tests cover each button's allowed/forbidden states.

### T19: Orchestrator v1 · A · M

- Read: [agents.md § Orchestrator](../architecture/agents.md#orchestrator), conversation-design.md (system prompt skeleton, examples)
- Build: `app/orchestrator/orchestrator.py` (manual loop, max 5 steps), `tools.py` with the Must tools (`create_post` with `asset_ids`, `pick_variation`, `approve_post`, `publish_post` now, `discard_post`, `list_posts`, `get_brand_summary`, `cancel_pending`), strict schemas and guards, `prompts/system.md` with the [conversation rules](../architecture/agents.md#conversation-rules); context builder (incl. `<recent_photos>`); `awaiting` handling (free text routed with pending context). Only built tools are registered.
- Done when: the example conversations in conversation-design.md work in the simulator; "publicalo" on a non-approved post does not publish.

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

### T25: Onboarding wizard UI · B · M

- Read: [design/web-app.md § /o/[token]](../design/web-app.md#otoken-onboarding-wizard-must), [design/mockups/](../design/mockups/README.md) row 2, [user-flows.md § Flow 2](../product/user-flows.md#flow-2--web-onboarding-form-must)
- Build: the six steps of the second design pass ("Paso N de 6") plus the done and expired-token screens, autosave, color swatches, questionnaire controls, IG connect step. Step 2: up to 5 Products. Step 3: logo + colors, or "Todavía no tengo logo ni colores". Step 4: 3–15 photos with thumbnails, direct uploads to the signed URL with a progress overlay, retry on failure. The feed import screen (6b) is T53 (Could); until then step 6 must not promise it.
- Done when: completed on a real phone from the WhatsApp link in < 5 minutes with the demo materials.

### T26: Variations in WhatsApp and the simulator · B · M

Replaces the HTML templates task: post templates are superseded by [ADR 0018](../decisions/0018-ai-image-generation-service.md).

- Read: [user-flows.md § Flow 5](../product/user-flows.md#flow-5--post-generation-and-approval-must), [integrations.md § Sending](../architecture/integrations.md#sending), the draft `post_variations` copy in [conversation-design.md](../product/conversation-design.md)
- Build: send the variations of a Post as numbered images, then the pick prompt (`awaiting = variation_choice`); the pick by text reaches `pick_variation` (T19), by button `variation_pick` (T18) if the team chooses buttons; `/dev/chat` shows the images in order. Use the draft copy until the open question on how the Owner picks is settled.
- Done when: in the simulator and on a real phone, the variations arrive numbered and in order, "la 2" picks the second one, and the preview that follows shows that image.

### T27: Zernio publisher + connect · B · M

- Read: [integrations.md § Zernio](../architecture/integrations.md#publishing-provider-zernio)
- Build: `app/publishing/zernio.py` (ensure_profile, connect_url, publish now, 207 handling; scheduling comes with T30's Should part), `mock.py`, `/api/o/{token}/instagram/connect` + `/callback`, `PUBLISHER` env switch.
- Done when: connecting the demo IG from the wizard stores `provider_account_id`; a test publish succeeds (then delete the IG post).

## H13–16

### T50: Approve and publish by writing (F5.6) · A · M

- Read: [agents.md § Conversation rules](../architecture/agents.md#conversation-rules), [ADR 0007](../decisions/0007-approve-every-post.md)
- Build: `approve_post(next = "publish_now")` for "subilo" / "publicalo" / "dale, subila"; the inbound handler's `explicit_approval` flag (approval phrase + exactly one `pending_approval` post, or the Owner named it); praise without an instruction ("me encanta") → "¿Lo subo?"; several pending posts → ask which one. Approval with a time ("subilo mañana a la tarde") answers that scheduling isn't available yet until T30's Should part exists.
- Done when: unit tests cover "subilo" with variations not picked yet (asks which one, no approval), "subilo" with one pending post (publishes), "me encanta" (asks), "subilo" with two pending posts (asks which), and "subilo" on a post that isn't pending (no publish); in the simulator "subilo" publishes through the mock publisher.

### T30: Publish job + guards · A · M

- Build (Must): `jobs/publish.py` (status guard, need-IG path, publish now, store permalink, messages).
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

## Could (only if everything above is solid)

### T53: Instagram feed import (F2.8) · B · C

- Read: [integrations.md § Reading the Owner's existing Instagram media](../architecture/integrations.md#reading-the-owners-existing-instagram-media-could)
- Prerequisite: the pre-hackathon test shows Zernio's `GET /v1/accounts/{accountId}/posts` returns Instagram posts with full-size images. If not, skip this task.
- Build: `/api/o/{token}/instagram/import`, `/instagram/media`, `/instagram/media/selection`; `import_instagram_media` job; wizard step 6b (grid with progress, untick to exclude, "Listo, seguir").
- Done when: after connecting the demo IG, step 6b shows its recent posts and the kept images become analyzed Brand assets with `source = 'instagram'`.

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

Unit tests for deterministic logic only (fast, no network): state machine transitions (onboarding, post), button router guards, webhook signature + dedupe, free-text approval (`explicit_approval`: one pending post, several, praise without instruction), photo debounce batching, voice-note transcript resolution, variation picking (`pick_variation`, approval blocked before a pick), quality checks, image brief validation (incl. candidate membership and the fixed prompt rules), resize to 1080×1350, upload validation (kind, type, size, 15-photo cap). Should and Could tasks add their own (plan state machine, time parsing, `reel_suitable` rules, archived material hidden from agents). Live LLM and image-service tests are marked `@pytest.mark.live` and excluded by default. No frontend tests.
