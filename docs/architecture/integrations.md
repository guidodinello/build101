# Integrations

External services, how we call them, and the gotchas that will bite in a 24h build. Verify shapes against the official docs linked in each section. APIs change; this was written in October 2026.

Each adapter (`channels/kapso_webhook.py`, `channels/kapso.py`, `instagram/meta.py`, `publishing/zernio.py`) parses the provider's JSON with private Pydantic models defined next to it. Unknown fields are ignored, a missing field the code needs raises the adapter's own error (`ChannelError`, `InstagramError`, `PublisherError`), and optional fields that are `null` or oddly shaped count as absent.

## WhatsApp

The Owner's WhatsApp goes through **Kapso**, a platform for the official WhatsApp API built on top of Meta's Cloud API ([ADR 0020](../decisions/0020-whatsapp-via-kapso.md)). We call its REST API with `httpx` from `app/channels/kapso.py`, behind `ChannelPort`; Kapso has no Python SDK (its SDK is TypeScript only). If Kapso fails the first-hour test, [Plan B](#plan-b-meta-cloud-api-direct) is Meta's Cloud API directly behind the same port. The web simulator stays the dev channel and the stage fallback.

Kapso docs (read 2026-10-17): [API introduction](https://docs.kapso.ai/api/introduction.md), [webhooks](https://docs.kapso.ai/docs/platform/webhooks/overview.md), [webhook signatures](https://docs.kapso.ai/docs/platform/webhooks/security.md), [retries and ordering](https://docs.kapso.ai/docs/platform/webhooks/advanced.md), [reply buttons](https://docs.kapso.ai/docs/whatsapp/send-messages/buttons.md), [images](https://docs.kapso.ai/docs/whatsapp/send-messages/image.md), [sandbox](https://docs.kapso.ai/docs/how-to/whatsapp/use-sandbox-for-testing.md). Pricing: Free plan with 2,000 messages/month, 1 connected number plus a free pre-verified US number, $2 credits; Meta's fees passed through at cost ([pricing](https://kapso.com/pricing)).

### Kapso setup (hour 1)

1. Create a Kapso account on the Free plan and get a number: the free pre-verified US number, or the sandbox (it only messages the registered recipient and sends no templates).
2. Create an API key and configure the webhook to `https://<backend>/webhooks/whatsapp` with a signing secret, following the webhook docs above.
3. Record the values as `KAPSO_*` env vars ([setup.md](../implementation/setup.md#environment-variables)). Their exact names and the auth header come from Kapso's docs; confirm them before writing the adapter.
4. Run the first-hour test in [open-questions.md](../open-questions.md#whatsapp-through-kapso-first-hour-test): whether the US number is ours and delivers webhooks to our backend, the recipient limit, the payload format, and media download. Until it passes, build against the simulator.

**On Railway** ([backend README § Deploy](../../backend/README.md#deploy)): the webhook URL is `https://<service>.up.railway.app/webhooks/whatsapp` (a "Message received" webhook on the number), and `PUBLIC_BACKEND_URL` is the same Railway domain (the image URLs WhatsApp and Zernio fetch are built from it). **Each Kapso webhook has its own signing secret**, so a new webhook URL means setting that webhook's secret as `KAPSO_WEBHOOK_SECRET` where that backend runs; the old secret gives 401s. Point the Kapso webhook at one backend at a time.

**Policy note:** since Jan 15, 2026 Meta restricts *general-purpose* AI assistants on the WhatsApp Business API. Kapso runs on the same API, so the rule applies unchanged. Our bot is a task-specific business service (marketing for the owner's own business). That fits the allowed use, but confirm before a public launch (see [../open-questions.md](../open-questions.md)).

### Sending

What `ChannelPort` sends: text, an image with a caption, reply buttons with an optional image (or video) header, and mark-as-read. The request shapes are Kapso's ([buttons](https://docs.kapso.ai/docs/whatsapp/send-messages/buttons.md), [image](https://docs.kapso.ai/docs/whatsapp/send-messages/image.md)); Meta's shapes are under [Plan B](#plan-b-meta-cloud-api-direct). Whether Kapso offers a typing indicator is not checked.

**Text formatting.** Gemini writes Markdown; WhatsApp bold is `*x*` and italic `_x_`. Every text, image caption and button body the channel sends goes through `to_whatsapp` (`app/channels/whatsapp_format.py`): `**x**` → `*x*`, `__x__` → `_x_`, `***x***` → `*_x_*`. URLs, already-valid WhatsApp formatting and underscores inside words are left alone. A new channel adapter must call it too.

Limits we design around. They are WhatsApp's own limits (Meta's Cloud API), so we assume they apply through Kapso too: max **3** reply buttons; button title ≤ **20** chars; button id ≤ 256 chars; interactive body ≤ **1,024** chars; image caption ≤ 1,024 chars.

**Media limits** (read 2026-10-17, [supported media types](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media)): images JPEG/PNG ≤ **5 MB**, 8-bit RGB(A); video MP4 or 3GPP ≤ **16 MB**, H.264 video + AAC audio only, single audio stream or none. Android clients don't play H.264 "High" profile with B-frames; Meta recommends "Main" profile without B-frames (or "Baseline") and the `moov` box before `mdat`. Reply-button messages accept a **video header** as well as an image header ([interactive reply buttons](https://developers.facebook.com/docs/whatsapp/cloud-api/messages/interactive-reply-buttons-messages), read 2026-10-17).

**Post variations.** An image Post has several generated variations ([ADR 0018](../decisions/0018-ai-image-generation-service.md)). The Owner sees each one as its own image message, numbered, and then picks one; the picked variation is sent as the normal post preview with `[Aprobar] [Cambiar] [Descartar]`. How the Owner picks (number buttons, which only fit up to 3 variations, or a reply in text) is not decided ([open questions](../open-questions.md#post-images-generated-by-ai-adr-0018)).

**Carousel slides** ([ADR 0022](../decisions/0022-carousels-in-mvp.md)): each slide is its own image message, sent in order and captioned "1/5", "2/5"…, then `carousel_preview` (text + `[Aprobar] [Cambiar] [Descartar]`). WhatsApp has no album message we can send, so the order is ours to keep: send one slide after the other, not concurrently. After a slide redo, only the redone slides are sent again, then the preview.

**Reel previews (Could):** the Owner's video is usually far over 16 MB, so `analyze_asset` makes a preview with ffmpeg (`app/media/video.py:whatsapp_preview`: 720 px long side, H.264 Main, no B-frames, AAC, `+faststart`, bitrate sized to fit 16 MB) and stores it at `assets/{business_id}/{asset_id}-wa.mp4`. The Reel approval message uses it as the video header. If it can't fit (very long videos), the header is the cover frame image and the body ends with a link to the Post in the dashboard.

### Kapso as built (confirmed 2026-10-17, Kapso sandbox)

- **Sending:** `POST https://api.kapso.ai/meta/whatsapp/v24.0/{phone_number_id}/messages` with header `X-API-Key` and Meta's Cloud API body (`messaging_product: "whatsapp"`, `recipient_type: "individual"`, `to`, `type`, ...). The response carries the message id at `messages[0].id`. Verified for text, image (`image.link` + `caption`) and interactive buttons with an image header. The video header is built from Meta's shape and not yet verified.
- **Mark as read and typing indicator** ([send a message](https://docs.kapso.ai/api/meta/whatsapp/messages/send-a-message.md), read 2026-10-17): the same endpoint takes `{"messaging_product": "whatsapp", "status": "read", "message_id": "<wamid>"}`, optionally with `"typing_indicator": {"type": "text"}` (shown for about 25 s or until we send). Confirmed live: the typing indicator shows on a text echo.
- **Webhook headers:** `X-Webhook-Event` (`whatsapp.message.received`), `X-Webhook-Signature` (hex HMAC-SHA256 of the raw body with the webhook secret), `X-Idempotency-Key`, `X-Webhook-Payload-Version: v2`. Kapso expects `200` within 10 s and retries about twice. Batching is off.
- **Payload v2 is not Meta's `entry/changes` envelope.** Top level: `message`, `conversation`, `phone_number_id`. `message` has Meta-style fields (`id` = `wamid...`, `from`, `type`, `timestamp`, `text.body` / `interactive` / `image` / `audio`) plus `message.kapso{...}`. `kapso.content` repeats the last text of the conversation, so it is never used as the message text.
- **Button tap:** `type: "interactive"`, `interactive: {type: "button_reply", button_reply: {id, title}}`; our own ids (`post_approve:<uuid>`) come back intact.
- **Image:** `image{id, link, mime_type, sha256, url}`, `kapso.media_url` and `kapso.media_data{content_type, byte_size, filename}`. The caption is **not** in `image.caption` but in `kapso.message_type_data.caption`; the parser reads Meta's field first and falls back to Kapso's.
- **Audio (voice note):** `audio{id, link, mime_type, sha256, url, voice}` with `mime_type: "audio/ogg; codecs=opus"` (`kapso.media_data.content_type` says `audio/ogg`; we keep the first), plus `kapso.transcript.text`, already transcribed in the first webhook.
- **Media download:** `GET kapso.media_url` with `X-API-Key` returned `200` with the bytes. `ChannelPort.download_media(media_id)` uses the documented two steps instead ([Receiving](#receiving)), confirmed live for a photo and a voice note; `media_url` stays on `InboundMessage` as a fallback. The download URL carries a signed `token` query param: `app/log_redaction.py` redacts it (and `key`) from the `httpx` INFO log lines, wired in `app/main.py`; `httpx` stays at INFO so Gemini/Kapso status codes remain visible.
- **Env vars:** `WHATSAPP_CHANNEL`, `KAPSO_API_KEY`, `KAPSO_WEBHOOK_SECRET`, `KAPSO_PHONE_NUMBER_ID`, `KAPSO_BASE_URL` ([setup.md](../implementation/setup.md#environment-variables)).

### Receiving

Handling rules, whichever provider sits behind the port:

- **Verify the signature** on the raw bytes, before JSON parsing: Kapso signs its webhooks ([security](https://docs.kapso.ai/docs/platform/webhooks/security.md); header and algorithm to confirm in the first-hour test); Meta direct uses `X-Hub-Signature-256` ([Plan B](#plan-b-meta-cloud-api-direct)).
- **Return 200 fast.** Providers retry on slow or failed responses (Kapso documents its retries and ordering in [advanced](https://docs.kapso.ai/docs/platform/webhooks/advanced.md)), and that produces duplicates. Dedupe on the WhatsApp message id: `INSERT ... ON CONFLICT DO NOTHING` on `inbound_deliveries` (not `messages.external_id`, see [data-model.md](data-model.md)), so a restart doesn't forget it. The HMAC covers the body only, so messages with a `timestamp` older than 1 hour are acknowledged and dropped.
- **Normalize** every payload into one `InboundMessage` (text, button reply, image with caption, video, audio, unsupported). An audio message carries its media id, MIME type, size and Kapso's transcript when present (`message.kapso.transcript.text`, [message events](https://docs.kapso.ai/docs/platform/webhooks/message-events.md)); see [Speech-to-text](#speech-to-text). Kapso does not forward Meta's envelope: its v2 shape is under [Kapso as built](#kapso-as-built-confirmed-2026-10-17-kapso-sandbox); the Meta shape below is plan B only.
- **Media download:** photos the Owner sends are *Must* (F1.5: they are how the Owner asks for a post), videos *Could*. They become Brand assets with `source = 'whatsapp'`; stream videos to Storage instead of holding them in memory. A photo's `caption` is the Owner's request or hint: keep it with the asset and pass it to the orchestrator (see the photo debounce in [agents.md](agents.md#tools)). Kapso documents a two-step download: `GET https://api.kapso.ai/meta/whatsapp/v24.0/{media_id}?phone_number_id=...` with `X-API-Key` returns `mime_type`, `file_size` and a `download_url` with the token built in, valid about 4 minutes ([get media URL](https://docs.kapso.ai/api/meta/whatsapp/media/get-media-url.md), read 2026-10-17). Fetch it right away and check the status (Meta's `url` without Meta's token returns a 401 body). To confirm in the first-hour test; `ChannelPort.download_media` hides the difference ([open question](../open-questions.md#whatsapp-through-kapso-first-hour-test)).
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
    // or "type": "audio", "audio": {"id": "<media_id>", "mime_type": "audio/ogg; codecs=opus", "voice": true}  → voice note (no transcript: always Gemini)
    // or "type": "sticker" | "document" | "location" → unsupported_media
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
3. Do one end-to-end test the day before: create profile → connect → publish a test image → delete it from IG **by hand in the Instagram app**. Zernio can't do it: `DELETE /v1/posts/{id}` refuses published posts ("Published posts cannot be deleted") and does not remove anything already live on a platform, and `POST /v1/posts/{id}/unpublish` is "Not supported on Instagram, TikTok, or Snapchat" ([Zernio: delete post](https://docs.zernio.com/posts/delete-post), [unpublish post](https://docs.zernio.com/posts/unpublish-post), read 2026-10-17).
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
→ 201 {"post": {"_id": "...", "status": "publishing", "platforms": [{"status": "processing"}]}}   # no platformPostUrl yet (see gotchas)
→ 207 = the inline publish did not fully succeed (check post.status and per-platform errors)

# 3a. Poll until Zernio reaches a final status (what ZernioPublisher does after a non-final answer)
GET /v1/posts/<post_id>
→ 200 {"post": {"status": "published", "platforms": [{"status": "published", "platformPostUrl": "https://www.instagram.com/p/..."}]}}
```

```python
# 3b. Carousel (Must, ADR 0022): several image mediaItems in slide order (≤ 10), same call as 3
POST /v1/posts
{
  "content": "<caption + hashtags>",
  "mediaItems": [{"type": "image", "url": "https://<supabase>/storage/v1/object/public/renders/<business_id>/<post_id>-r<rev>-s1.jpg"},
                 {"type": "image", "url": "...-s2.jpg"}, ...],
  "platforms": [{"platform": "instagram", "accountId": "<provider_account_id>"}],
  "publishNow": true
}
```

Zernio's Instagram page says carousels take up to 10 items and are cropped to the first item's ratio ([Zernio Instagram](https://docs.zernio.com/platforms/instagram), [research](../research/media-uploads.md#publishing-video-and-carousels-zernio-instagram)); every slide is 1080×1350, so nothing is cropped. **Not verified:** that several `mediaItems` without any other field publish as a carousel, and that it works with our public `renders` URLs. Test one carousel publish on the demo IG before relying on it (T55).

```python
# 4. Reel (T60): one video, no contentType (Zernio publishes a single video as a Reel)
POST /v1/posts
{
  "content": "<caption + hashtags>",
  "mediaItems": [{"type": "video", "url": "<public HTTPS URL of the video, or a signed Supabase URL valid 24 h>"}],
  "platforms": [{"platform": "instagram", "accountId": "<provider_account_id>",
                 "platformSpecificData": {"thumbOffset": 4200,      # PublishMedia.cover_offset_ms, omitted when null
                                          "isAiGenerated": true}}],  # PublishMedia.ai_generated, omitted when false
  "publishNow": true
}
```

Sources, read 2026-10-19: "A single video publishes as a Reel with no `contentType`" ([Zernio: Instagram posts](https://docs.zernio.com/platforms/instagram/posts)); `thumbOffset` (integer ms ≥ 0, default 0, ignored when `instagramThumbnail` is set) and `isAiGenerated` ("the post is labeled by Instagram as containing AI-generated media", Reels included) in [Platform Fields](https://docs.zernio.com/platforms/instagram/fields) and the [OpenAPI spec](https://zernio.com/openapi.yaml) v1.297.1; video limits in [Media Requirements](https://docs.zernio.com/platforms/instagram/media): MP4/MOV, H.264, 30 fps, 1080×1920 (9:16), 3–90 s, ≤ 300 MB. Code does not check these (it only has a URL). A custom cover image (`instagramThumbnail`) exists but is not used: a generated video has no separate cover. **Not verified live:** a real Reel publish on the demo account (`test_publish_one_reel_to_the_demo_account`, `@pytest.mark.live`, needs `ZERNIO_TEST_VIDEO_URL`).

Gotchas:

- Media URL must be **public HTTPS returning the raw file**, JPEG/PNG < 8 MB, aspect ratio between 4:5 and 1.91:1. Our post images are 1080×1350 (4:5) JPEG in the public `renders` bucket, which fits.
- **Reels** (Could; [Zernio Instagram](https://docs.zernio.com/platforms/instagram), [research](../research/media-uploads.md)): MP4/MOV, H.264, 3–90 s, ≤ 300 MB, 9:16 recommended. The Owner's video lives in the **private** `assets` bucket, so pass a signed URL valid long enough for Zernio to fetch it (24 h; for a scheduled Reel, sign it when `publish_post` runs, not when the Post is approved). Zernio caps Reels at 90 s while Meta allows 15 min: the Asset Analyst only marks videos of 3–90 s as `reel_suitable` until a real test proves otherwise. Videos that aren't H.264 (e.g. iPhone HEVC) may need a transcode; test with a real phone video before the hackathon.
- Reels publish slower than images (Meta processes the video), so "publish now" can take a minute or more; the Zernio `post.published` webhook, not the `201`, is what confirms it.
- **`publishNow` is not always synchronous.** The OpenAPI spec says `publishNow: true` publishes "synchronously, inside this request", but on the live test (2026-10-18) the demo Instagram answered **201 with `post.status = "publishing"`**, the Instagram entry `processing` and no `platformPostUrl`; about 10 s later `GET /v1/posts/{id}` returned `published` with the URL, and the post really went live. A 201 is therefore not a confirmation, and mapping `publishing` to a failure would report a failure for a post that goes out (and a retry would publish it twice).
- `post.status` decides ([OpenAPI spec](https://zernio.com/openapi.yaml) v1.290.1, read 2026-10-18): `published` is a success once the platform entry has its `platformPostUrl`; `failed`, `partial` and `cancelled` are final failures; `publishing` and `scheduled` are not final, and neither is a `207` whose `post.status` is `scheduled` ("Zernio retries automatically. This is **not** a failure", [Zernio: create post](https://docs.zernio.com/posts/create-post), read 2026-10-17). `ZernioPublisher` returns every non-final outcome as `PublishResult.status = "pending"`: never report a failure and never re-publish.
- After a non-final answer `publish` polls `GET /v1/posts/{id}` every 2 s until a 90 s wall-clock cap (`POLL_INTERVAL_S`, `POLL_TIMEOUT_S`; the cap is generous so carousels fit) and never re-POSTs. Each poll has its own 10 s timeout (`POLL_REQUEST_TIMEOUT_S`), so a hung `GET` overruns the cap by at most one poll. It returns `published` with the permalink, `failed` with the platform error, or `pending` if the cap runs out or the polls keep failing. At that point the webhook (T29) or a later `GET` confirms it. A non-final POST answer **without a post id** raises `PublisherError` instead: there is nothing to poll and nothing for the webhook to match.
- **Idempotency.** `POST /v1/posts` takes an optional `Idempotency-Key` header, which `publish(..., idempotency_key=...)` sends. The spec: "Optional client-generated unique key (e.g. a UUID) that makes retries safe. Same key + same body replays the original response; same key + different body → 422; key still processing → 409", and for create-post: "A retry with the same key within 24 hours returns the original post (HTTP 200) whatever its body; while the original is still being processed it returns 409 `idempotency_conflict` with `Retry-After`" ([OpenAPI spec](https://zernio.com/openapi.yaml), read 2026-10-18). The caller (T57, then T30) picks the key from the Post id, so a retry after a timeout or a 5xx cannot publish twice. `ZernioPublisher` raises `PublishRetryable` for a timeout, a dropped connection, a 5xx or an accepted post with no id (outcome unknown: retry once with the same key), and `PublishInProgress(retry_after_s)` for a `409` that carries `Retry-After` or `idempotency_conflict` (the request with that key is still being processed: wait, then resend with the same key). A `409` for duplicate content has no `Retry-After` and stays a plain `PublisherError`. Both are `PublisherError` subclasses.
- Identical content to the same account within 24 h returns `409` (`details.existingPostId`), so repeated test posts need a different caption or image.
- Webhook signature: `X-Zernio-Signature` = HMAC-SHA256 of the raw body with our secret.
- Things not verified by research: the exact query param names on the connect redirect (log the full query on the first test and adapt `instagram/callback`), and whether old getlate.dev URLs still work (build only against `zernio.com/api/v1`).

### Reading the Owner's Instagram (ADR 0028)

The Owner connects their Instagram in wizard step 2 ([ADR 0032](../decisions/0032-instagram-first-onboarding.md)), and we read it to build the Brand Brain: profile, captions, engagement and the newest images ([ADR 0028](../decisions/0028-read-instagram-with-our-meta-app.md)). This uses **our own Meta app with Instagram Login**, not Zernio, and only reads: publishing stays on Zernio's single demo account ([ADR 0024](../decisions/0024-mvp-single-demo-instagram-account.md)). Code: `app/instagram/` behind `InstagramPort` (`MetaInstagram`, `MockInstagram`), the connect and callback in `app/api/instagram.py`, the job in `app/jobs/instagram.py`.

**Why not Zernio** (checked 2026-10-18, [Zernio OpenAPI spec](https://zernio.com/openapi.yaml) v1.292.0):

- `GET /v1/accounts/{accountId}/posts` gives only "the 25 most recent posts", with no limit or pagination, a caption, and a `picture` described as "Thumbnail or media URL", and no carousel slides.
- `GET /v1/accounts` has no bio or website for Instagram.
- `GET /v1/accounts/{id}/instagram/business-discovery` (bio, website, full media, children) needs a **Facebook Login** connection: "accounts connected with classic Instagram Login receive a 400".
- Paginated posts with carousel items (`GET /v1/analytics?source=external`) need the Analytics add-on (402 without it); comments and DMs need the Inbox add-on. Zernio's [pricing page](https://zernio.com/pricing) says "No add-ons", which contradicts the spec; not confirmed for our account.

**Meta setup:** add the *Instagram API with Instagram Login* product to the app, add the Owner's account (Business or Creator) as an **Instagram Tester** and accept the invite from the account, and register `{PUBLIC_BACKEND_URL}/oauth/instagram/callback` as a valid OAuth redirect URI. Meta matches it exactly, so a deploy sets `PUBLIC_BACKEND_URL`. Without App Review this is Standard Access: it works only for accounts with a role on the app. Serving any other Business needs Advanced Access, App Review and Business Verification ([overview](https://developers.facebook.com/documentation/instagram-platform/overview.md), [App Review](https://developers.facebook.com/documentation/instagram-platform/app-review.md), read 2026-10-18).

**Calls** ([Business Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login), read 2026-10-18):

```python
# 1. The wizard's POST /api/o/{token}/instagram/connect returns our own start hop,
#    GET /api/o/{token}/instagram/start?ticket=..., which sets the `ig_oauth` binding cookie
#    (HttpOnly, SameSite=Lax) and redirects to
https://www.instagram.com/oauth/authorize?client_id={INSTAGRAM_APP_ID}&redirect_uri={callback}
    &response_type=code&scope=instagram_business_basic&state={nonce}
# The code Instagram sends back "is valid for 1 hour and can only be used once"

# 2. GET /oauth/instagram/callback?code&state (+ the cookie, whose nonce must equal `state`):
#    code → short-lived token (form POST)
POST https://api.instagram.com/oauth/access_token
client_id, client_secret, grant_type=authorization_code, redirect_uri, code
→ {"access_token": "...", "user_id": 178...}      # also seen as {"data": [{...}]}: both are read

# 3. Short-lived → long-lived (60 days), server side only
GET https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret=...&access_token=...
→ {"access_token": "...", "token_type": "bearer", "expires_in": 5184000}

# 4. Profile
GET https://graph.instagram.com/{INSTAGRAM_GRAPH_VERSION}/me
    ?fields=user_id,username,name,followers_count,media_count,biography,website

# 5. Media, newest first, 50 per page; follow paging.next up to INSTAGRAM_IMPORT_MAX_POSTS
GET https://graph.instagram.com/{INSTAGRAM_GRAPH_VERSION}/me/media?limit=50&fields=id,media_type,
    media_url,thumbnail_url,permalink,timestamp,like_count,comments_count,
    children{id,media_type,media_url,thumbnail_url},caption
```

- **Optional fields.** Meta's [IG User](https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user.md) reference lists `biography` and `website` for Instagram Login, but its getting-started `/me` table leaves them out. Its [IG Media](https://developers.facebook.com/documentation/instagram-platform/reference/instagram-media.md) reference labels `caption` "Available for Instagram API with Facebook Login only", yet Zernio returns captions over Instagram Login. The adapter asks for them and, on a `400`, asks again without them, so a refusal loses signal instead of failing the import. Not yet confirmed on the demo account ([open questions](../open-questions.md#instagram-import-adr-0028)).
- **Images.** A photo's `media_url`; for a carousel, each child's (a video child gives its `thumbnail_url`); for a video, its `thumbnail_url` (the cover). `media_url` "is omitted … if the media contains copyrighted material" (Reels with licensed audio), and such an item is skipped. CDN URLs stop working "when the content has been deleted or has expired" ([overview](https://developers.facebook.com/documentation/instagram-platform/overview.md)), so images are downloaded and stored, never linked.
- **Limits.** `/me/media` "Returns a maximum of 10K of the most recently created media" and never stories ([IG User Media](https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media.md)). Stories exist only for 24 hours ([IG User Stories](https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/stories.md)), and there is no highlights edge. Comments need `instagram_business_manage_comments` and DMs `instagram_business_manage_messages`; neither is requested. All read 2026-10-18.
- **What the job does.** `import_instagram` reads the profile and up to `INSTAGRAM_IMPORT_MAX_POSTS` (100) posts into `businesses.onboarding_data["instagram"]`. It downloads up to `INSTAGRAM_IMPORT_MAX_IMAGES` (24) of the newest images not imported yet, 4 at a time, and stores each in the `assets` bucket with its agents' copy, as a `photo` Brand asset with `source = 'instagram'` and `external_id` = the media id. It queues one `analyze_asset` per image. An image that fails to download or decode is logged and skipped.
- **Tokens.** The callback stores the long-lived token on `social_accounts.access_token` (RLS on, [data-model.md](data-model.md)) only so the queued `import_instagram` can read it. The job is the one reader, and it claims the token first: one transaction reads it under a row lock (`SELECT ... FOR UPDATE`) and sets the column to null, committed before the first call to Instagram. From then on the token lives only in the job's memory, so a failed, cancelled (a deploy stops the runner) or killed (SIGKILL, OOM) import leaves nothing to clean up, a database dump holds no Instagram token, a reconnect's fresh token is untouched and claimed by the import that reconnect queued, and two overlapping imports can't both get one (the second is skipped). The price: an import that fails is not retried, the Owner reconnects. `token_expires_at` stays as a record of the connect. Nothing refreshes the token (`GET /refresh_access_token?grant_type=ig_refresh_token` works once it is 24 hours old, and it expires after 60 days): to read the account again, the Owner reconnects, which stores a fresh token and queues a new import. httpx logs redact `access_token` and `client_secret` in query strings.
- **Mock.** `INSTAGRAM=mock` (the default): the authorize URL points straight at our callback with a fake code, and the import brings three fake posts with plain-color images. Local dev and the demo work without a Meta app.

### Mock publisher

`PUBLISHER=mock` (the default) → `MockPublisher` returns `published` with `permalink = https://instagram.com/p/MOCK-<id>` after a 2 s delay, and `connect_url` returns a frontend URL that marks the account connected. Used for local dev, the simulator and rehearsals; with `ENV=prod` the backend refuses to start on it.

## Gemini API (text)

See [agents.md](agents.md#llm-client-conventions) for the full conventions (model, thinking level, history, structured output, errors, logging) and [research/gemini-api.md](../research/gemini-api.md) for prices and limits ([ADR 0023](../decisions/0023-gemini-text-llm.md)). Setup: the same `GEMINI_API_KEY` as image generation, from <https://aistudio.google.com/api-keys> with billing linked. Check the account's rate limits before the hackathon; a demo run is roughly 10–15 calls per post-heavy minute.

## Supabase (Postgres + Storage)

- **Plan:** the **Free plan** is enough for the Must scope ([ADR 0016](../decisions/0016-demo-scope-one-post.md)): photos and logos only, ≤ 10 MB each, well under its 50 MB per-file and 1 GB storage caps. Move to **Pro** (US$25/month) and set the **global file size limit to 300 MB** (the Instagram Reel maximum) only when the Could video work starts ([ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md), [research](../research/media-uploads.md)). Record `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (backend only, never in the frontend), `DATABASE_URL` (use the **session pooler** connection string for asyncpg; the transaction pooler breaks prepared statements unless `statement_cache_size=0`).
- `SUPABASE_SERVICE_ROLE_KEY` is the **legacy `service_role` JWT**: `app/storage.py` sends it as the `apikey` header and as the `Authorization: Bearer` token, so a new-style `sb_secret_...` key is not what the code expects. The session pooler host comes from `supabase link` (`supabase/.temp/pooler-url`: for `build101` it is `aws-1-sa-east-1.pooler.supabase.com:5432`, not `aws-0`).
- Apply the schema with `uv run alembic upgrade head` (see [data-model.md](data-model.md)); on Railway it runs as the pre-deploy command ([backend README § Deploy](../../backend/README.md#deploy)).
- Buckets: `assets` (**private**; bucket file limit 10 MB for the Must scope, 300 MB once video is on) and `renders` (**public**; the final 1080×1350 post images, i.e. the resized variations from [Image generation](#image-generation); the name is kept from the template design).
- Python: `supabase` client for storage only (`storage.from_(bucket).upload(path, data, {"content-type": mime})`, `create_signed_url(path, 3600)`, `create_signed_upload_url(path)`, `get_public_url(path)`); SQLAlchemy 2 async + asyncpg for the DB.
- **Browser uploads** ([api.md](api.md#uploads)): the backend calls `create_signed_upload_url(path)` (valid 2 h) and returns the URL and token. The frontend uploads photos and logos (≤ 10 MB) with a single `PUT` of the same shape as `uploadToSignedUrl` from `@supabase/supabase-js` (`frontend/lib/upload.ts`; Supabase only recommends resumable uploads above 6 MB, it doesn't require them). Videos (Could) would use TUS (`tus-js-client`, 6 MB chunks, endpoint `{SUPABASE_URL}/storage/v1/upload/resumable/sign`, header `x-signature: <token>`), so a dropped phone connection resumes instead of restarting. The upload URL the backend returns is absolute and carries its token, so the frontend needs no Supabase key or URL of its own. Not verified yet: whether signed uploads need any Storage policy with RLS on the bucket; test it before the hackathon.
- Storage paths: `assets/{business_id}/{asset_id}.{ext}` (a HEIC original is replaced by `{asset_id}.jpg`), `assets/{business_id}/{asset_id}-llm.jpg` (the copy of a photo or logo the agents read, ≤ 1536 px), `assets/{business_id}/{asset_id}-wa.mp4` (WhatsApp preview of a video), `assets/{business_id}/{frame_asset_id}.jpg` (frames saved from a video), `renders/{business_id}/{post_id}-r{revision}-v{n}.jpg` (variation `n` of a revision; a new path per revision, so WhatsApp/IG never serve a cached old image).

## Video processing (ffmpeg)

Could: only needed for the Could video work (video analysis, Reels). Claude reads images, not video or audio ([research](../research/media-uploads.md)), so the backend turns each video into frames before the Asset Analyst sees it. `app/media/video.py`:

- `probe`: `ffprobe -v error -print_format json -show_format -show_streams` → duration, width, height, video and audio codecs.
- `keyframes`: 6 frames spread over the video (skip the first and last 0.5 s), scaled to ≤ 1568 px on the long side, JPEG. Scene-change detection (`select='gt(scene,0.3)'`) is a later improvement.
- `whatsapp_preview`: see [Reel previews](#sending).
- Runs inside `analyze_asset` on the downloaded file in a temp dir; delete it afterwards. A 300 MB video takes a few seconds to probe and a few more to cut frames on the backend's CPU; the preview transcode is the slow part (tens of seconds), so it runs after the analysis is saved.
- Docker: when video work starts, install `ffmpeg` from the distro packages in the final stage of the image (per [`.claude/rules/docker.md`](../../.claude/rules/docker.md)). The Must image doesn't need it.
- No transcription of a video's audio in the MVP; voice notes are transcribed (see [Speech-to-text](#speech-to-text)).

## Video generation (Veo, ADR 0033)

Behind `VideoGenPort` (`app/videogen/`), only built when `VIDEO_GEN_ENABLED=true` (default `false`: no adapter, no Veo call). `VIDEO_GEN=gemini | mock`; the mock returns a bundled 1 s 9:16 MP4 so the whole flow runs without billed calls. Sources: [Veo docs](https://ai.google.dev/gemini-api/docs/veo) and [pricing](https://ai.google.dev/gemini-api/docs/pricing), read 2026-10-19.

- **Key**: `GEMINI_VIDEO_API_KEY` only. The adapter never falls back to `GEMINI_API_KEY`; the same value may be set in both by choice.
- **Models** (`GEMINI_VIDEO_MODEL`): `veo-3.1-lite-generate-preview` (default, US$0.05/s at 720p), `veo-3.1-fast-generate-preview` (US$0.10/s), `veo-3.1-generate-preview` (US$0.40/s). No free tier; blocked videos are not billed.
- **Modes**: Lite has no reference images, so the product image is the **first frame** (`source.image`, center-cropped to the clip's ratio in code). Fast and Standard take up to 3 `ASSET` reference images, which force 8 s. Both need `person_generation="allow_adult"`. Clips are 4, 6 or 8 s at 24 fps, 16:9 or 9:16, audio always on.
- **Call**: `aio.models.generate_videos(model, source=GenerateVideosSource(prompt, image), config)` starts a long-running operation; `aio.operations.get` polls it every 10 s, up to `VIDEO_GEN_TIMEOUT_S` (600; the docs say 11 s to 6 min at peak); `aio.files.download` fetches the MP4. The server keeps a video 2 days, so it is downloaded at once.
- **Retries**: polling and download retry like the image client. The **submit call never retries**: a retried submit after a timeout could start, and bill, a second clip.
- **Errors**: `operation.error` and API errors are `VideoGenUnavailable`; a deadline is `VideoGenTimeout`; RAI filtering is `VideoGenBlocked(reason)`; a finished operation without a video is `VideoGenNoVideo`.
- **Serving**: `PublicVideos` serves the MP4 at `/media/{token}.mp4` (GET and HEAD) for WhatsApp and Zernio to fetch. The 20-clip LRU only bounds clips whose Post is gone: on a miss it serves the clip of any Post still in `InMemoryPosts` (`serve_from`, same bytes object, no extra memory), so the Owner's header link and Zernio's fetch never 404 while the Post exists. No `Range` support yet; check whether they need it when the flag is first turned on.
- **Unconfirmed**: Veo with reference images at 9:16 (Fast/Standard) and how the 4:5 crop looks as a first frame; one live call settles both.

## Image generation

Post images are generated by a third-party AI image service, never composed by the backend ([ADR 0018](../decisions/0018-ai-image-generation-service.md)). Provider: Google Gemini, with OpenAI as fallback ([ADR 0019](../decisions/0019-image-provider-gemini.md)). Facts and prices: [research/image-generation-providers.md](../research/image-generation-providers.md) (read 2026-10-17, not tested hands-on). The Art Director writes the prompt and picks the reference photos ([agents.md](agents.md#art-director)); this layer only calls the provider and post-processes.

`ImageGenPort` (`app/imagegen/`, contract in [api.md](api.md#internal-module-interfaces)), selected by `IMAGE_GEN`:

| Adapter | When | Call |
|---|---|---|
| `gemini` | Primary | `gemini-nano-banana-2.1` through the official `google-genai` SDK and `generateContent` (not the Interactions API, which is Beta, [ADR 0022](../decisions/0022-carousels-in-mvp.md)); call shape below. Up to 10 object reference images "with high-fidelity". One image per call (the model doesn't always return the number of images asked for), so variations and slides run as parallel calls |
| `openai` | Fallback | `gpt-image-2.5-sunburst` through `POST /v1/images/edits` (official `openai` SDK): up to 16 reference images, `size = "1088x1360"` (exactly 4:5, multiples of 16), `jpeg` output (faster than `png`). Complex prompts can take up to 2 minutes |
| `mock` | Local dev, simulator, rehearsals (refused with `ENV=prod`) | Returns the first reference photo, cropped and resized, after a short delay. No provider call |

Gemini call (`app/imagegen/gemini.py`; facts in [research](../research/image-generation-providers.md#verified-2026-10-17-docs--sdk-source-not-hands-on)):

```python
client = genai.Client(api_key=GEMINI_API_KEY, http_options=HttpOptions(
    timeout=120_000,
    retry_options=HttpRetryOptions(attempts=4, initial_delay=2, max_delay=30)))  # the SDK does not retry by default

resp = await client.aio.models.generate_content(
    model=GEMINI_IMAGE_MODEL,
    contents=[prompt, *labelled_reference_parts, *optional_style_reference],
    config=GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=ImageConfig(aspect_ratio="4:5", image_size="2K"),
        thinking_config=ThinkingConfig(thinking_level=GEMINI_THINKING_LEVEL)))
```

- **Reading the response:** skip parts with `part.thought` (interim thought images, not charged); the first remaining inline image is the result. No image → map `finish_reason` (`IMAGE_SAFETY`, `IMAGE_PROHIBITED_CONTENT`, `IMAGE_RECITATION`, `IMAGE_OTHER`, `NO_IMAGE`) or `prompt_feedback.block_reason` to `ImageGenBlocked(reason)` (a block) or `ImageGenNoImage`; SDK `ClientError` / `ServerError` after the retries → `ImageGenUnavailable`.
- **References:** each photo goes through `app/media/images.py:prepare_reference` (HEIC ok, ≤ 1536 px long side, JPEG) and is sent as a labelled inline part, which keeps ~10 photos under Gemini's 20 MB inline request cap.
- **Concurrency:** one process-wide semaphore of `IMAGE_GEN_MAX_CONCURRENCY` (default 4) around every provider call, shared by variations and carousel slides.
- **Carousels** ([ADR 0022](../decisions/0022-carousels-in-mvp.md), [ADR 0029](../decisions/0029-designed-slides-ai-scene-code-layout.md)): `CarouselGenerator` generates text-free scenes: the cover first, then the other slides in parallel, each with the cover passed as `style_image` (sent after the product photos, labelled "Another slide of this carousel", since `gemini-nano-banana-2.1` has no style-reference slot) and a prompt from `build_slide_prompt(..., anchored=True)`. A redone slide anchors on the current cover; a redone cover anchors on slide 2. A `panorama` is one call at `16:9`, `21:9`, `4:1` or `8:1` (by slide count) and 4K, center-cropped to N × 4:5 and sliced with `slice_panorama`; its redo regenerates the whole scene. Slides are about $0.05 each at 2K plus input tokens; a panorama is one 4K image ($0.113). The [Slide renderer](#slide-renderer-takumi-on-vercel) then sets the design over each scene.
- **Post-processing** (`app/media/images.py`, Pillow): center-crop to 4:5 if needed (Gemini 2K is 1856×2304, slightly off 4:5) and resize to **1080×1350**, JPEG quality 90, then upload to the public `renders` bucket. Image Posts are only resized; designed slides are composed by the Slide renderer below.
- **Runs in the job runner**, never in the webhook ([ADR 0005](../decisions/0005-single-instance-in-process-jobs.md)). Variations of one Post run concurrently, under the shared semaphore so a Post doesn't exhaust the provider's rate limit.
- **Cost:** every call logs the provider's `usage` (input images, prompt, thinking, output) in `agent_runs` (`agent = 'image_gen'`), so the dollars per variation can be computed. Gemini lists $0.0504 per 2K output image plus input and thinking tokens; OpenAI's per-image cost for 2.5 is not documented.
- **Data:** only call Gemini from a project with billing linked: unpaid use (AI Studio, free quota) is used for training. Paid-tier Gemini and the OpenAI API don't train on our images.
- **Limits:** Gemini Tier 1 has a $10 per 10-minute spend limit and a $250 billing cap; images per minute for 2.1 are not on the public page. OpenAI's Build tier allows 20 images per minute.
- To confirm on the first real call ([ADR 0019](../decisions/0019-image-provider-gemini.md)): 4:5 at 2K on `gemini-nano-banana-2.1`, latency per image, the cost of `GEMINI_THINKING_LEVEL` (`minimal` vs `medium`), and that the crop keeps the product in frame.
- Docker: no browser, no fonts; Pillow is already a dependency.

## Slide renderer (Takumi on Vercel)

[ADR 0029](../decisions/0029-designed-slides-ai-scene-code-layout.md), [ADR 0035](../decisions/0035-art-director-design-rules-and-design-critic.md). Designed slides are composed from code templates over the text-free scenes.

- **Where:** `POST /api/render` in the Next.js app (`frontend/app/api/render/route.ts`), Node runtime, rendered by Takumi (`takumi-js` + `@takumi-rs/core`, MIT or Apache-2.0, no browser). Templates are async functions in `frontend/lib/post-render/families/` (`editorial`, `numbers`, `panorama`, `minimal`, `notes`, `scrapbook`), each with layouts per role, and shared chrome (brand mark, page counter, swipe cue, save pill) in `chrome.tsx`. `design.ts` fits every text block with Takumi's `measure()` (largest size within the slot's width and line limit) and reads the scene as raw pixels to pick the text color and shade for 4.5:1 contrast. Fonts are six OFL pairs plus Caveat, committed in `frontend/lib/post-render/fonts/` and listed in `fonts.ts`; icons are Lucide path data (`lucide`, ISC), drawn as inline SVG because `lucide-react` icons are client components.
- **Contract:** one slide per request, JSON `{family, index, count, role, layout, emphasis, focus, surface, kicker, headline, body, items, image, logo: {src, tone} | null, brand: {name, colors: {primary, secondary, accent, background, text}, fonts}}`; `image` and `logo.src` are base64 data URIs. `layout`, `emphasis`, `focus`, `surface` and `brand.fonts` fall back to their defaults when missing or unknown; `items` (at most 5, 80 characters each) feeds the notes checklist. Validated in `frontend/lib/post-render/spec.ts` (400 `invalid_spec` on a bad field, 422 on an image over the limits below). Answers a 1080×1350 JPEG with an `x-render-report` header: the layout drawn, each text slot's fitted size and lines (`clamped` when it needed more room) and each text block's contrast, shade and whether the photo under it is busy.
- **Auth:** `Authorization: Bearer <RENDER_SECRET>`; 401 on a mismatch, 503 when the frontend has no secret.
- **Deploy order:** when the contract grows, deploy the frontend before the backend. New fields are optional and unknown knob values fall back to defaults, but a family the deployed renderer doesn't know is a 400.
- **Backend side:** `app/rendering/` (`RendererPort`; `TakumiRenderer` over httpx, 30 s timeout; `MockRenderer` returns the scene unchanged). `render_slides` sends every slide of a post in parallel with its knobs and the Brand Brain's name, colors (a color that isn't `#RRGGBB` keeps the default) and font pair, and, when the Owner asked, the logo trimmed to PNG with its tone (`logo_for_render`), so the template can put it on a chip.
- **Settings:** `RENDERER` (`takumi` | `mock`, default `mock`), `RENDERER_URL` (the frontend's origin), `RENDERER_SECRET` (= the frontend's `RENDER_SECRET`).
- **Limits:** Vercel caps request and response bodies at 4.5 MB; a 1080×1350 scene is a few hundred KB, so one slide per request stays far under it. The route enforces its own caps before rendering, measured on worst-case noise inputs (scene 1.25 MB and logo 1.8 MB as data URIs, 3.05 MB body): the body stays under 4 MB (413 `body_too_large`, by `Content-Length` and by the bytes actually read), each data URI under 1.968 M characters (half of what the body cap leaves after 64 KB for the rest of the spec, so a scene and a logo both at that cap still fit and an oversized image gets 422, not 413), and each image at most 4096 px on a side, read from its JPEG, PNG or WebP header without decoding (422 `image_too_large`, or `image_unreadable` when no header is found). The backend treats any non-200 as a `RendererError`, so a rejected slide fails like any renderer error.
- **Preview:** with `ENABLE_TEMPLATE_PREVIEW=true` the frontend serves `/dev/post-templates`, every family and layout over sample copy and the landing photos, for four sample brands (`?brand=roble|lumbre|nube|mercado`). `/api/render/preview` takes `family`, `index`, `brand`, `fonts`, `layout`, `emphasis`, `focus`, `surface` and `logo=1`.

## Speech-to-text

Voice notes are Must (F1.7, [ADR 0021](../decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md)). Claude takes no audio, so the inbound handler turns each voice note into text before routing; after that it is handled exactly like a text message. Facts and alternatives: [research/voice-notes.md](../research/voice-notes.md) (read 2026-10-17).

Order, in the inbound handler after dedupe:

1. **Kapso's transcript.** If `InboundMessage.provider_transcript` (from `message.kapso.transcript.text`) is non-empty, use it. When Kapso fills it in, and how well it handles Rioplatense Spanish, are to confirm in the first-hour test.
2. **Gemini fallback** (`TranscriberPort`, `app/transcription/`, selected by `TRANSCRIBE_FALLBACK`): if the audio is over `MAX_AUDIO_MB`, send `audio_too_long` and stop. Otherwise `ChannelPort.download_media(media_id)`, then one `google-genai` call to `TRANSCRIBE_MODEL` with the audio inline (`audio/ogg` and `audio/opus` are accepted, 20 MB per request; [Gemini audio](https://ai.google.dev/gemini-api/docs/audio)) and a fixed prompt: verbatim transcription in Rioplatense Spanish, no summary, no answer to what is said, empty output if there is no speech. Log the call's usage in `agent_runs` (`agent = 'transcribe'`; 32 tokens per second of audio).
3. **Nothing usable** (both empty, or the call failed): send `audio_unclear` and don't run the orchestrator.

| Adapter | When |
|---|---|
| `gemini` | Default fallback, and the only path on plan B (Meta sends no transcript) |
| `none` | Only Kapso's transcript; a voice note without one gets `audio_unclear` |
| `mock` | Local dev and tests: returns a fixed transcript |

- Store the message as `type = 'audio'` with the transcript in `messages.text` ([data-model.md](data-model.md)); don't keep the audio bytes.
- Same paid-tier rule as images: only call Gemini from a project with billing linked ([ADR 0019](../decisions/0019-image-provider-gemini.md)).
- Inbound only: the bot replies in text. No speech synthesis.
- Not covered: the audio track of the Owner's videos (post-MVP, [open questions](../open-questions.md#catalog-content-and-reels-could)).
