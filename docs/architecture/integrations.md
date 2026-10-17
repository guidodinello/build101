# Integrations

External services, how we call them, and the gotchas that will bite in a 24h build. Verify shapes against the official docs linked in each section. APIs change; this was written in October 2026.

## WhatsApp

The Owner's WhatsApp goes through **Kapso**, a platform for the official WhatsApp API built on top of Meta's Cloud API ([ADR 0020](../decisions/0020-whatsapp-via-kapso.md)). We call its REST API with `httpx` from `app/channels/whatsapp.py`, behind `ChannelPort`; Kapso has no Python SDK (its SDK is TypeScript only). If Kapso fails the first-hour test, [Plan B](#plan-b-meta-cloud-api-direct) is Meta's Cloud API directly behind the same port. The web simulator stays the dev channel and the stage fallback.

Kapso docs (read 2026-10-17): [API introduction](https://docs.kapso.ai/api/introduction.md), [webhooks](https://docs.kapso.ai/docs/platform/webhooks/overview.md), [webhook signatures](https://docs.kapso.ai/docs/platform/webhooks/security.md), [retries and ordering](https://docs.kapso.ai/docs/platform/webhooks/advanced.md), [reply buttons](https://docs.kapso.ai/docs/whatsapp/send-messages/buttons.md), [images](https://docs.kapso.ai/docs/whatsapp/send-messages/image.md), [sandbox](https://docs.kapso.ai/docs/how-to/whatsapp/use-sandbox-for-testing.md). Pricing: Free plan with 2,000 messages/month, 1 connected number plus a free pre-verified US number, $2 credits; Meta's fees passed through at cost ([pricing](https://kapso.com/pricing)).

### Kapso setup (hour 1)

1. Create a Kapso account on the Free plan and get a number: the free pre-verified US number, or the sandbox (it only messages the registered recipient and sends no templates).
2. Create an API key and configure the webhook to `https://<backend>/webhooks/whatsapp` with a signing secret, following the webhook docs above.
3. Record the values as `KAPSO_*` env vars ([setup.md](../implementation/setup.md#environment-variables)). Their exact names and the auth header come from Kapso's docs; confirm them before writing the adapter.
4. Run the first-hour test in [open-questions.md](../open-questions.md#whatsapp-through-kapso-first-hour-test): whether the US number is ours and delivers webhooks to our backend, the recipient limit, the payload format, and media download. Until it passes, build against the simulator.

**Policy note:** since Jan 15, 2026 Meta restricts *general-purpose* AI assistants on the WhatsApp Business API. Kapso runs on the same API, so the rule applies unchanged. Our bot is a task-specific business service (marketing for the owner's own business). That fits the allowed use, but confirm before a public launch (see [../open-questions.md](../open-questions.md)).

### Sending

What `ChannelPort` sends: text, an image with a caption, reply buttons with an optional image (or video) header, and mark-as-read. The request shapes are Kapso's ([buttons](https://docs.kapso.ai/docs/whatsapp/send-messages/buttons.md), [image](https://docs.kapso.ai/docs/whatsapp/send-messages/image.md)); Meta's shapes are under [Plan B](#plan-b-meta-cloud-api-direct). Whether Kapso offers a typing indicator is not checked.

Limits we design around. They are WhatsApp's own limits (Meta's Cloud API), so we assume they apply through Kapso too: max **3** reply buttons; button title ≤ **20** chars; button id ≤ 256 chars; interactive body ≤ **1,024** chars; image caption ≤ 1,024 chars.

**Media limits** (read 2026-10-17, [supported media types](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media)): images JPEG/PNG ≤ **5 MB**, 8-bit RGB(A); video MP4 or 3GPP ≤ **16 MB**, H.264 video + AAC audio only, single audio stream or none. Android clients don't play H.264 "High" profile with B-frames; Meta recommends "Main" profile without B-frames (or "Baseline") and the `moov` box before `mdat`. Reply-button messages accept a **video header** as well as an image header ([interactive reply buttons](https://developers.facebook.com/docs/whatsapp/cloud-api/messages/interactive-reply-buttons-messages), read 2026-10-17).

**Post variations.** An image Post has several generated variations ([ADR 0018](../decisions/0018-ai-image-generation-service.md)). The Owner sees each one as its own image message, numbered, and then picks one; the picked variation is sent as the normal post preview with `[Aprobar] [Cambiar] [Descartar]`. How the Owner picks (number buttons, which only fit up to 3 variations, or a reply in text) is not decided ([open questions](../open-questions.md#post-images-generated-by-ai-adr-0018)).

**Reel previews (Could):** the Owner's video is usually far over 16 MB, so `analyze_asset` makes a preview with ffmpeg (`app/media/video.py:whatsapp_preview`: 720 px long side, H.264 Main, no B-frames, AAC, `+faststart`, bitrate sized to fit 16 MB) and stores it at `assets/{business_id}/{asset_id}-wa.mp4`. The Reel approval message uses it as the video header. If it can't fit (very long videos), the header is the cover frame image and the body ends with a link to the Post in the dashboard.

### Receiving

Handling rules, whichever provider sits behind the port:

- **Verify the signature** on the raw bytes, before JSON parsing: Kapso signs its webhooks ([security](https://docs.kapso.ai/docs/platform/webhooks/security.md); header and algorithm to confirm in the first-hour test); Meta direct uses `X-Hub-Signature-256` ([Plan B](#plan-b-meta-cloud-api-direct)).
- **Return 200 fast.** Providers retry on slow or failed responses (Kapso documents its retries and ordering in [advanced](https://docs.kapso.ai/docs/platform/webhooks/advanced.md)), and that produces duplicates. Dedupe on the WhatsApp message id (unique `messages.external_id`).
- **Normalize** every payload into one `InboundMessage` (text, button reply, image with caption, video, unsupported). Whether Kapso forwards Meta's payload as-is is not verified; if it does, the Meta shape below applies.
- **Media download:** photos the Owner sends are *Must* (F1.5: they are how the Owner asks for a post), videos *Could*. They become Brand assets with `source = 'whatsapp'`; stream videos to Storage instead of holding them in memory. A photo's `caption` is the Owner's request or hint: keep it with the asset and pass it to the orchestrator (see the photo debounce in [agents.md](agents.md#tools)). How Kapso exposes media (a download URL, Meta's media id, or its own endpoint) is not verified; `ChannelPort.download_media` hides the difference ([open question](../open-questions.md#whatsapp-through-kapso-first-hour-test)).
- **24-hour window:** free-form messages can only be sent within 24 h of the Owner's last message; outside it only approved templates go through (post-MVP; WhatsApp's rule, so it holds through Kapso too). Job results arrive within minutes, so they are fine. **Scheduled posts are not**: the `published` / `publish_failed` notification for a post scheduled more than 24 h after the Owner's last message will be rejected. MVP behavior: send it anyway, and if it is rejected, log it and keep the status visible on the dashboard; the Owner sees it next time they write (the orchestrator mentions newly published posts). The demo only schedules within the window.

### Plan B: Meta Cloud API direct

Only if Kapso fails the first-hour test ([ADR 0020](../decisions/0020-whatsapp-via-kapso.md)). Meta's official API, called directly (no BSP). Docs: <https://developers.facebook.com/docs/whatsapp/cloud-api>

Setup (~1 hour):

1. Create a Meta developer app (type *Business*) and add the **WhatsApp** product.
2. Use the free **test phone number**. Add the demo phones (both builders + the furniture owner) as **recipient numbers**. The test number can only message up to 5 verified recipients, which is fine for the demo.
3. Create a **System User** in Meta Business Settings with a **permanent access token** (`whatsapp_business_messaging`, `whatsapp_business_management`). **Don't use the temporary token from the dashboard: it expires after 24 h, i.e. mid-hackathon.**
4. Configure the webhook: callback URL `https://<backend>/webhooks/whatsapp`, verify token = `META_VERIFY_TOKEN`; subscribe to the `messages` field.
5. Record: `META_PHONE_NUMBER_ID`, `META_ACCESS_TOKEN`, `META_APP_SECRET`, `META_VERIFY_TOKEN`, `META_GRAPH_VERSION` (use the latest version shown in the app dashboard), `WHATSAPP_BOT_NUMBER` (for wa.me links).

Sending: `POST https://graph.facebook.com/{META_GRAPH_VERSION}/{META_PHONE_NUMBER_ID}/messages` with `Authorization: Bearer {META_ACCESS_TOKEN}`.

```jsonc
// text
{"messaging_product": "whatsapp", "to": "59899123456", "type": "text",
 "text": {"body": "¡Hola! 👋 ...", "preview_url": true}}

// image (public URL; must be reachable by Meta)
{"messaging_product": "whatsapp", "to": "59899123456", "type": "image",
 "image": {"link": "https://.../renders/abc.jpg", "caption": "..."}}

// reply buttons with image header (post preview)
{"messaging_product": "whatsapp", "to": "59899123456", "type": "interactive",
 "interactive": {
   "type": "button",
   "header": {"type": "image", "image": {"link": "https://.../renders/abc.jpg"}},
   "body": {"text": "📝 Post para el martes 21 — \"Mesa Nórdica\"\n\n..."},
   "action": {"buttons": [
     {"type": "reply", "reply": {"id": "post_approve:7f3c...", "title": "Aprobar"}},
     {"type": "reply", "reply": {"id": "post_change:7f3c...",  "title": "Cambiar"}},
     {"type": "reply", "reply": {"id": "post_discard:7f3c...", "title": "Descartar"}}
   ]}}}

// mark as read (+ typing indicator while we work)
{"messaging_product": "whatsapp", "status": "read", "message_id": "wamid...",
 "typing_indicator": {"type": "text"}}
```

```jsonc
// Reel preview: reply buttons with video header
{"messaging_product": "whatsapp", "to": "59899123456", "type": "interactive",
 "interactive": {
   "type": "button",
   "header": {"type": "video", "video": {"link": "https://.../assets/...-wa.mp4?token=..."}},
   "body": {"text": "🎬 Reel para el jueves 23 — \"Así armamos la Mesa Nórdica\"\n\n..."},
   "action": {"buttons": [ /* Aprobar / Cambiar / Descartar, same ids as image Posts */ ]}}}
```

Receiving: `GET /webhooks/whatsapp` answers Meta's verification (`hub.mode == "subscribe"` and `hub.verify_token == META_VERIFY_TOKEN` → return `hub.challenge`). Webhook payload (simplified); iterate `entry[].changes[].value`:

```jsonc
{
  "contacts": [{"profile": {"name": "Laura"}, "wa_id": "59899123456"}],
  "messages": [{
    "from": "59899123456", "id": "wamid.HBg...", "timestamp": "1760712000",
    "type": "text", "text": {"body": "hola"}
    // or "type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "post_approve:7f3c", "title": "Aprobar"}}
    // or "type": "image", "image": {"id": "<media_id>", "mime_type": "image/jpeg", "caption": "..."}
    // or "type": "video", "video": {"id": "<media_id>", "mime_type": "video/mp4", "caption": "..."}  → Brand asset (Could)
    // or "type": "audio" | "sticker" | "document" | "location" → unsupported_media
  }],
  "statuses": [{"id": "wamid...", "status": "delivered", "recipient_id": "..."}]  // update messages.status
}
```

- **Signature:** `X-Hub-Signature-256` = `sha256=` + HMAC-SHA256(app secret, raw body).
- **Media download:** `GET /{version}/{media_id}` → `{"url": ...}`, then `GET url` with the same bearer token. URLs expire in minutes, so download immediately.

## Publishing provider: Zernio

Unified social publishing API (formerly *Late*, getlate.dev). Chosen because the **free tier includes full API access** (first 2 connected accounts free, unlimited posts) and a **hosted connect link we generate per business**, so we don't need our own Meta app review for Instagram publishing. See [ADR 0008](../decisions/0008-publishing-via-zernio.md) and [research](../research/social-publishing-apis.md). Docs: <https://docs.zernio.com>

### Setup (before the hackathon)

1. Sign up at zernio.com (no card) and create an API key → `ZERNIO_API_KEY`.
2. Make sure the demo Instagram account is **Business or Creator** (Instagram Login is used, so no Facebook Page is needed).
3. Do one end-to-end test the day before: create profile → connect → publish a test image → delete it from IG.
4. Optional: register a webhook (`POST /v1/webhooks/settings`) with our `ZERNIO_WEBHOOK_SECRET` for `post.published`, `post.failed`, `account.connected`.

**Free tier limit:** 2 connected accounts **across the whole team**. IG + Facebook Page for the demo business uses both slots, so connect **Instagram only** unless the FB cross-post is needed. A 3rd account returns `402 PAYMENT_REQUIRED`. Instagram caps: 25 posts/hour and 100/day per account.

### Calls

Base URL `https://zernio.com/api/v1`, header `Authorization: Bearer {ZERNIO_API_KEY}`. Use `httpx` directly (thin, explicit); the `zernio-sdk` PyPI package exists if preferred.

```python
# 1. One Zernio profile per business (store as social_accounts.provider_profile_id)
POST /v1/profiles
{"name": "Muebles Ramírez", "externalId": "<business_id>"}
→ {"profile": {"_id": "prof_..."}}

# 2. Hosted connect link (send the owner's browser to auth_url)
GET /v1/connect/instagram?profileId=prof_...&redirect_url=https://<frontend>/o/<token>?step=instagram&connected=1
→ {"authUrl": "https://..."}
# Zernio redirects back with query params including the connected accountId → store as provider_account_id

# 3. Publish now or schedule
POST /v1/posts
{
  "content": "<caption + hashtags>",
  "mediaItems": [{"type": "image", "url": "https://<supabase>/storage/v1/object/public/renders/<id>.jpg"}],
  "platforms": [{"platform": "instagram", "accountId": "<provider_account_id>"}],
  "publishNow": true
  // or: "scheduledFor": "2026-10-21T19:00:00", "timezone": "America/Montevideo"
}
→ 201 {"post": {"_id": "...", "status": "published", "platforms": [{"platformPostUrl": "https://www.instagram.com/p/..."}]}}
→ 207 = partial failure (check post.status and per-platform errors)
```

```python
# 4. Reel (Could): one video, no contentType (Zernio publishes a single video as a Reel)
POST /v1/posts
{
  "content": "<caption + hashtags>",
  "mediaItems": [{"type": "video", "url": "<signed Supabase URL of the Owner's video, valid 24 h>"}],
  "platforms": [{"platform": "instagram", "accountId": "<provider_account_id>",
                 "platformSpecificData": {"thumbOffset": 4200}}],   # posts.cover_offset_ms
  "publishNow": true
}
```

Gotchas:

- Media URL must be **public HTTPS returning the raw file**, JPEG/PNG < 8 MB, aspect ratio between 4:5 and 1.91:1. Our post images are 1080×1350 (4:5) JPEG in the public `renders` bucket, which fits.
- **Reels** (Could; [Zernio Instagram](https://docs.zernio.com/platforms/instagram), [research](../research/media-uploads.md)): MP4/MOV, H.264, 3–90 s, ≤ 300 MB, 9:16 recommended. The Owner's video lives in the **private** `assets` bucket, so pass a signed URL valid long enough for Zernio to fetch it (24 h; for a scheduled Reel, sign it when `publish_post` runs, not when the Post is approved). Zernio caps Reels at 90 s while Meta allows 15 min: the Asset Analyst only marks videos of 3–90 s as `reel_suitable` until a real test proves otherwise. Videos that aren't H.264 (e.g. iPhone HEVC) may need a transcode; test with a real phone video before the hackathon.
- Reels publish slower than images (Meta processes the video), so "publish now" can take a minute or more; the Zernio `post.published` webhook, not the `201`, is what confirms it.
- Treat `207` and any `post.status != "published"` as failure for "publish now".
- Webhook signature: `X-Zernio-Signature` = HMAC-SHA256 of the raw body with our secret.
- Things not verified by research: the exact query param names on the connect redirect (log the full query on the first test and adapt `instagram/callback`), and whether old getlate.dev URLs still work (build only against `zernio.com/api/v1`).

### Reading the Owner's existing Instagram media (Could)

The second design pass imports the Owner's feed after they connect Instagram (wizard step 6b, F2.8), so the Agency starts with more photos. Publishing access is not enough for that: we need to **read** the account's media. Checked 2026-10-17:

- **Zernio** has `GET /v1/accounts/{accountId}/posts`: "the 25 most recent posts that exist on the platform for a connected account", read live from the platform API, including posts not created through Zernio. Each post has `id`, `permalink`, `message` (caption), `mediaType` and `picture` ("Thumbnail or media URL"); there is no pagination or limit parameter and no carousel children. Its docs don't say whether Instagram is supported (a `400` means "platform does not support posts listing"), and for videos `picture` is likely only a thumbnail ([Zernio: list posts](https://docs.zernio.com/accounts/get-account-posts), read 2026-10-17). Zernio's ads endpoints can list an account's Instagram media too, but only through a Meta ads connection, not the Instagram Login connection we use ([Zernio: list Instagram posts to boost](https://docs.zernio.com/ad-accounts/list-ads-instagram-posts), read 2026-10-17).
- **Instagram Graph API**: `GET /{ig-user-id}/media` returns up to the 10K most recent media, not stories, with time-based pagination. It needs `instagram_basic` + `pages_read_engagement` (Facebook Login) ([IG User Media](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media), read 2026-10-17), or `instagram_business_basic` with Instagram Login. Each media has `media_type` (image, video, carousel album), `media_url` (omitted when the media contains copyrighted material, such as Reel audio), `thumbnail_url` (videos only) and a `children` edge for albums ([IG Media](https://developers.facebook.com/docs/instagram-platform/reference/instagram-media), read 2026-10-17). This means our own Meta app with those permissions, which [ADR 0008](../decisions/0008-publishing-via-zernio.md) avoided; whether reading other businesses' media needs App Review was not checked.

Plan for F2.8: test the Zernio endpoint on the demo Instagram before the hackathon. If it returns Instagram posts with full-size `picture` URLs, import the last 25 posts' images (first image of carousels, thumbnails of videos skipped); if not, F2.8 stays out of the MVP and the wizard's step 6 copy must not promise it. Open question: [../open-questions.md](../open-questions.md#second-design-pass-adr-0016).

### Mock publisher

`PUBLISHER=mock` → `MockPublisher` returns `published` with `permalink = https://instagram.com/p/MOCK-<post_id>` after a 2 s delay, and `connect_url` returns a frontend URL that marks the account connected. Used for local dev, the simulator, and the stage fallback.

## Claude API

See [agents.md](agents.md#llm-client-conventions) for the full conventions (model, effort, structured output, caching, fallbacks, logging). Setup: `ANTHROPIC_API_KEY` from console.anthropic.com. Check the account's rate limits before the hackathon; a demo run is roughly 10–15 calls per post-heavy minute.

## Supabase (Postgres + Storage)

- **Plan:** the **Free plan** is enough for the Must scope ([ADR 0016](../decisions/0016-demo-scope-one-post.md)): photos and logos only, ≤ 10 MB each, well under its 50 MB per-file and 1 GB storage caps. Move to **Pro** (US$25/month) and set the **global file size limit to 300 MB** (the Instagram Reel maximum) only when the Could video work starts ([ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md), [research](../research/media-uploads.md)). Record `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (backend only, never in the frontend), `DATABASE_URL` (use the **session pooler** connection string for asyncpg; the transaction pooler breaks prepared statements unless `statement_cache_size=0`).
- Apply the schema with `uv run alembic upgrade head` (see [data-model.md](data-model.md)).
- Buckets: `assets` (**private**; bucket file limit 10 MB for the Must scope, 300 MB once video is on) and `renders` (**public**; the final 1080×1350 post images, i.e. the resized variations from [Image generation](#image-generation); the name is kept from the template design).
- Python: `supabase` client for storage only (`storage.from_(bucket).upload(path, data, {"content-type": mime})`, `create_signed_url(path, 3600)`, `create_signed_upload_url(path)`, `get_public_url(path)`); SQLAlchemy 2 async + asyncpg for the DB.
- **Browser uploads** ([api.md](api.md#uploads)): the backend calls `create_signed_upload_url(path)` (valid 2 h) and returns the URL and token. The frontend uploads with `uploadToSignedUrl` from `@supabase/supabase-js` for files up to 6 MB, and with TUS (`tus-js-client`, 6 MB chunks, endpoint `{SUPABASE_URL}/storage/v1/upload/resumable/sign`, header `x-signature: <token>`) above that, so a dropped phone connection resumes instead of restarting. The frontend only needs `NEXT_PUBLIC_SUPABASE_URL` and the anon key; the signed token is what authorizes the write. Not verified yet: whether signed uploads need any Storage policy with RLS on the bucket; test it before the hackathon.
- Storage paths: `assets/{business_id}/{asset_id}.{ext}`, `assets/{business_id}/{asset_id}-wa.mp4` (WhatsApp preview of a video), `assets/{business_id}/{frame_asset_id}.jpg` (frames saved from a video), `renders/{business_id}/{post_id}-r{revision}-v{n}.jpg` (variation `n` of a revision; a new path per revision, so WhatsApp/IG never serve a cached old image).

## Video processing (ffmpeg)

Could: only needed for the Could video work (video analysis, Reels). Claude reads images, not video or audio ([research](../research/media-uploads.md)), so the backend turns each video into frames before the Asset Analyst sees it. `app/media/video.py`:

- `probe`: `ffprobe -v error -print_format json -show_format -show_streams` → duration, width, height, video and audio codecs.
- `keyframes`: 6 frames spread over the video (skip the first and last 0.5 s), scaled to ≤ 1568 px on the long side, JPEG. Scene-change detection (`select='gt(scene,0.3)'`) is a later improvement.
- `whatsapp_preview`: see [Reel previews](#sending).
- Runs inside `analyze_asset` on the downloaded file in a temp dir; delete it afterwards. A 300 MB video takes a few seconds to probe and a few more to cut frames on the backend's CPU; the preview transcode is the slow part (tens of seconds), so it runs after the analysis is saved.
- Docker: when video work starts, install `ffmpeg` from the distro packages in the final stage of the image (per [`.claude/rules/docker.md`](../../.claude/rules/docker.md)). The Must image doesn't need it.
- No audio transcription in the MVP (see [Optional](#optional-could)).

## Image generation

Post images are generated by a third-party AI image service, never composed by the backend ([ADR 0018](../decisions/0018-ai-image-generation-service.md)). Provider: Google Gemini, with OpenAI as fallback ([ADR 0019](../decisions/0019-image-provider-gemini.md)). Facts and prices: [research/image-generation-providers.md](../research/image-generation-providers.md) (read 2026-10-17, not tested hands-on). The Art Director writes the prompt and picks the reference photos ([agents.md](agents.md#art-director)); this layer only calls the provider and post-processes.

`ImageGenPort` (`app/imagegen/`, contract in [api.md](api.md#internal-module-interfaces)), selected by `IMAGE_GEN`:

| Adapter | When | Call |
|---|---|---|
| `gemini` | Primary | `gemini-nano-banana-2.1` through the official `google-genai` SDK: `client.interactions.create(model=..., input=..., response_format={"type": "image", "aspect_ratio": "4:5", "image_size": "2K"})`, synchronous, image returned as base64. Up to 10 object reference images "with high-fidelity". One image per call (the model doesn't always return the number of images asked for), so variations run as parallel calls. Try thinking `minimal` to cut cost and latency |
| `openai` | Fallback | `gpt-image-2.5-sunburst` through `POST /v1/images/edits` (official `openai` SDK): up to 16 reference images, `size = "1088x1360"` (exactly 4:5, multiples of 16), `jpeg` output (faster than `png`). Complex prompts can take up to 2 minutes |
| `mock` | Local dev, simulator, stage fallback | Returns the first reference photo, cropped and resized, after a short delay. No provider call |

- **Post-processing** (`app/media/images.py`, Pillow): center-crop to 4:5 if needed (Gemini 2K is 1856×2304, slightly off 4:5) and resize to **1080×1350**, JPEG quality 90, then upload to the public `renders` bucket. This is resizing, not composing: nothing is drawn on the image.
- **Runs in the job runner**, never in the webhook ([ADR 0005](../decisions/0005-single-instance-in-process-jobs.md)). Variations of one Post run concurrently, under a small per-job limit so a Post doesn't exhaust the provider's rate limit.
- **Cost:** every call logs the provider's `usage` (input images, prompt, thinking, output) in `agent_runs` (`agent = 'image_gen'`), so the dollars per variation can be computed. Gemini lists $0.0504 per 2K output image plus input and thinking tokens; OpenAI's per-image cost for 2.5 is not documented.
- **Data:** only call Gemini from a project with billing linked: unpaid use (AI Studio, free quota) is used for training. Paid-tier Gemini and the OpenAI API don't train on our images.
- **Limits:** Gemini Tier 1 has a $10 per 10-minute spend limit and a $250 billing cap; images per minute for 2.1 are not on the public page. OpenAI's Build tier allows 20 images per minute.
- To confirm on the first real call ([ADR 0019](../decisions/0019-image-provider-gemini.md)): 4:5 at 2K on `gemini-nano-banana-2.1`, latency per image, and that the crop keeps the product in frame.
- Docker: no browser, no fonts; Pillow is already a dependency.

## Optional (Could)

- **Voice notes**: WhatsApp audio is OGG/Opus (how Kapso hands us the file is not verified, see [Receiving](#receiving)). Transcribe with `faster-whisper` (`small` model, CPU, `language="es"`) inside the backend container, then treat the transcript as text. Adds ~500 MB to the image and a few seconds per note; only if everything else is done. The same model could transcribe what the Owner says in their videos and feed it to the Asset Analyst (post-MVP).
