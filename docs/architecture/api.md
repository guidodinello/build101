# Backend API

FastAPI. JSON in and out, `snake_case` fields. Errors use `{"error": {"code": "...", "message": "..."}}` with a proper HTTP status. OpenAPI is served at `/docs`; the frontend's `lib/api.ts` types are written by hand from this document (no codegen in the hackathon).

## Authentication

| Caller | Mechanism |
|---|---|
| WhatsApp webhook (Kapso) | `X-Webhook-Signature`: hex HMAC-SHA256 of the **raw body** with `KAPSO_WEBHOOK_SECRET` (confirmed 2026-10-17, [Kapso's docs](https://docs.kapso.ai/docs/platform/webhooks/security.md)). `401` on a mismatch, a missing header or no configured secret. Plan B (Meta direct): `X-Hub-Signature-256` HMAC with `META_APP_SECRET` |
| Zernio webhook | `X-Zernio-Signature` HMAC with `ZERNIO_WEBHOOK_SECRET` |
| Web app (owner) | Magic-link token in the path: `/api/o/{token}/...`. Server hashes it, looks up `magic_links`, checks expiry → `business_id` |
| Dev tools | Header `X-Dev-Token: $DEV_TOKEN`, only if `ENABLE_DEV_ENDPOINTS=true` |

CORS: allow every origin in `FRONTEND_ORIGINS` (comma-separated: Vercel URL + `http://localhost:3000`).

## Endpoints

### Health

| Method | Path | Response |
|---|---|---|
| GET | `/health` | `{"ok": true, "version": "<git sha>"}` |

### WhatsApp webhook

| Method | Path | Notes |
|---|---|---|
| GET | `/webhooks/whatsapp` | Plan B (Meta direct) only. Verification: if `hub.mode == "subscribe"` and `hub.verify_token == META_VERIFY_TOKEN`, return `hub.challenge` as plain text, else 403. Whether Kapso needs a verification handshake is part of the first-hour test |
| POST | `/webhooks/whatsapp` | Bodies over 256 KiB get `413` (checked from `Content-Length`, and while reading when it is missing), before the signature check. Then verify signature → dedupe → enqueue handling as a background task → return `200` immediately; a failure inside the background handler is logged with the message id and kind, and is not retried by Kapso (durable retry belongs to the job runner, T16). Only `X-Webhook-Event: whatsapp.message.received` is handled; other events (and payloads that don't parse) get `200` and are ignored, so Kapso doesn't retry. Dedupe key: `message.id` (the `wamid`), or `X-Idempotency-Key` when the id is missing. Payload shapes in [integrations.md](integrations.md#whatsapp) |

### Zernio webhook

| Method | Path | Notes |
|---|---|---|
| POST | `/webhooks/zernio` | Verify signature. On `post.published` → post `published` + permalink + notify owner (if it was scheduled). On `post.failed` → `failed` + `publish_failed`. On `account.connected` → `social_accounts.status = connected` |

### Onboarding (web wizard)

All under `/api/o/{token}`. The token is the onboarding magic link. Must, except the Instagram feed import endpoints (Could).

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/api/o/{token}` | — | `OnboardingState` (below) |
| PUT | `/api/o/{token}/business` | `{name, category, one_liner, description?, location, website?, instagram_handle?}` | `OnboardingState` |
| PUT | `/api/o/{token}/products` | `{products: [{id?, name, description, price?, category?}]}` (1–5) | `OnboardingState`: upserts `products` rows in the given order; rows left out are archived. More than 5 → `422 too_many_products` |
| PUT | `/api/o/{token}/brand` | `{three_words: [str, str, str], colors: [hex...], no_brand_yet?: bool}` | `OnboardingState`. `no_brand_yet = true` ("Todavía no tengo logo ni colores") allows an empty `colors` list; the Brand Strategist uses the neutral default palette, and the colors are chosen later in the chat (F2.9, Could) |
| POST | `/api/o/{token}/uploads` | `UploadRequest` (below) | `UploadTicket`: see [Uploads](#uploads). The wizard accepts `logo` and `photo` only, at most 15 photos (`422 too_many_photos`) |
| POST | `/api/o/{token}/assets/{asset_id}/complete` | — | `Asset` (logo includes `palette`) |
| DELETE | `/api/o/{token}/assets/{asset_id}` | — | `204`: archives the asset (the ✕ on a wizard thumbnail) |
| PUT | `/api/o/{token}/preferences` | `Questionnaire` (below) | `OnboardingState` |
| POST | `/api/o/{token}/instagram/connect` | `{}` | `{"auth_url": "..."}`: creates the Zernio profile if needed and returns the hosted connect URL. `redirect_url` = `{FRONTEND_URL}/o/{token}?step=instagram&connected=1` |
| POST | `/api/o/{token}/instagram/callback` | `{account_id?, query: {...}}`: the frontend forwards the query params Zernio appended to the redirect | `OnboardingState` |
| POST | `/api/o/{token}/instagram/import` | `{}` | `202 {"job_id"}`: **Could (F2.8)**, only once a way to read the account's media exists ([integrations.md](integrations.md#reading-the-owners-existing-instagram-media-could)). Lists the recent media and creates `InstagramMedia` candidates |
| GET | `/api/o/{token}/instagram/media` | — | **Could.** `{status: "importing" \| "done" \| "unavailable", done, total, items: InstagramMedia[]}` for the progress bar and the grid on step 6b |
| PUT | `/api/o/{token}/instagram/media/selection` | `{excluded_ids: [str]}` | **Could.** The Owner unticks what we shouldn't use; the rest is downloaded as Brand assets (`source = 'instagram'`) by `import_instagram_media` |
| POST | `/api/o/{token}/complete` | — | `202 {"status": "generating_brand"}`. Validates required fields (name, category, 1–5 products, 3–15 photos, logo optional but recommended), sets state, enqueues `generate_brand`, sends `brand_generating` on WhatsApp |

```ts
type OnboardingState = {
  business: { name: string | null; category: string | null; one_liner: string | null;
              description: string | null; location: string | null; website: string | null;
              instagram_handle: string | null };
  products: Product[];
  brand: { three_words: string[]; colors: string[] };
  assets: Asset[];
  preferences: Questionnaire | null;
  instagram: { status: "not_connected" | "pending" | "connected" | "error"; handle: string | null };
  completed: boolean;               // magic_links.completed_at != null
  whatsapp_url: string;             // https://wa.me/<bot number>
};
type Asset = {
  id: string;
  kind: "logo" | "photo" | "video";
  status: "uploading" | "ready" | "failed";
  url: string;                      // signed, 1h
  thumbnail_url: string | null;     // videos: the cover frame, or the first frame until analyzed
  width: number | null; height: number | null;
  duration_ms: number | null;       // videos only
  derived_from_asset_id: string | null;   // a photo saved from a video's frame
  owner_hint: string | null;
  palette: string[] | null;         // logos
  product_ids: string[];
  reel_suitable: boolean | null;    // videos: null until analyzed
  analyzed: boolean;
  archived: boolean;
};
type InstagramMedia = { id: string; media_type: "image" | "video" | "carousel"; thumbnail_url: string;
                        permalink: string | null; taken_at: string | null; excluded: boolean };   // Could (F2.8)
type Product = { id: string; name: string; description: string; price: string | null;
                 category: string | null; position: number; asset_count: number; archived: boolean };
type Offer = { id: string; kind: "pack" | "promo"; title: string; conditions: string;
               price: string | null; starts_on: string | null; ends_on: string | null;   // ISO dates
               status: "draft" | "active" | "archived"; product_ids: string[] };
type Questionnaire = {
  goal: "sales" | "awareness" | "launch" | "loyalty";
  audiences: string[];              // from fixed options + free "otro"
  formality: 1 | 2 | 3 | 4 | 5;     // slider
  humor: 1 | 2 | 3 | 4 | 5;         // slider
  posts_per_week: 2 | 3 | 5;
  emoji_policy: "many" | "few" | "none";
  avoid: string | null;
  current_offer: string | null;
};
```

### Uploads

The wizard (`/api/o/{token}`, Must, photos and logo only) and the dashboard (`/api/b/{token}`, Could) share one upload flow. Files go **from the browser straight to Supabase Storage**; the backend never receives the bytes ([ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md), facts in [../research/media-uploads.md](../research/media-uploads.md)).

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/{o\|b}/{token}/uploads` | `UploadRequest` | `UploadTicket`. Validates type and size, creates a `brand_assets` row with `status = 'uploading'`, returns a signed upload URL for `assets/{business_id}/{asset_id}.{ext}` |
| POST | `/api/{o\|b}/{token}/assets/{asset_id}/complete` | — | `Asset`. Checks the object exists in Storage (else `409 upload_missing`), sets `status = 'ready'` and `size_bytes`, converts HEIC to JPEG (`pillow-heif`), runs logo palette extraction synchronously, enqueues `analyze_asset` for photos and videos |

1. `POST .../uploads` → `UploadTicket`.
2. The browser uploads to `upload_url`: a single `PUT` when `resumable = false`, or TUS with `x-signature: upload_token` when `resumable = true` (files over 6 MB).
3. `POST .../assets/{asset_id}/complete`. A ticket never completed stays `uploading` and is ignored; a nightly cleanup can mark it `failed`.

Accepted files:

| Kind | Types | Max size |
|---|---|---|
| `photo`, `logo` | `image/jpeg`, `image/png`, `image/webp`, `image/heic` | 10 MB |
| `video` (Could: dashboard only, not the wizard) | `video/mp4`, `video/quicktime` (MOV) | 300 MB |

Anything else → `422 unsupported_file` with a Spanish `message` the UI shows as is. Video duration and size in pixels are read with `ffprobe` during `analyze_asset`, not at upload.

```ts
type UploadRequest = { kind: "logo" | "photo" | "video"; filename: string; content_type: string;
                       size_bytes: number; owner_hint?: string };
type UploadTicket = { asset_id: string; upload_url: string; upload_token: string; resumable: boolean };
```

### Dashboard (read Should, editing Could)

Per [ADR 0016](../decisions/0016-demo-scope-one-post.md), the read endpoints (Inicio: Brand Brain + Posts) are **Should** and everything that writes (Products, Brand assets, Offers, dashboard uploads) is **Could**. Token = a `dashboard` magic link (the bot sends it when the owner asks "¿dónde veo todo?" or "quiero subir fotos"). Valid for **7 days**; writing "link" in WhatsApp sends a new one. Anyone with the link can edit until there are user accounts (F7.4), so **nothing is hard-deleted**: `archived: true` hides a Product, Brand asset or Offer from agents and the dashboard. Archiving material used by a draft Post (`pending_approval`, `revising`) flags that Post for review; published and scheduled Posts don't change.

| Method | Path | Priority | Body / Query | Response |
|---|---|---|---|---|
| GET | `/api/b/{token}` | Should | — | `{business: {...}, brand_brain: BrandBrain, instagram: {...}, counts: {products, photos, videos, active_offers}}` |
| GET | `/api/b/{token}/posts?status=` | Should | — | `[{id, title, format, status, image_url, video_url, cover_url, caption, scheduled_for, published_at, permalink, needs_review}]` |
| GET | `/api/b/{token}/plans/current` | Should | — | `{week_start, status, items: [...]}` |
| GET | `/api/b/{token}/products?include_archived=` | Could | — | `Product[]` (by `position`) |
| POST | `/api/b/{token}/products` | Could | `{name, description?, price?, category?}` | `Product` |
| PATCH | `/api/b/{token}/products/{id}` | Could | any of `{name, description, price, category, position, archived}` | `Product` |
| GET | `/api/b/{token}/assets?kind=&product_id=&include_archived=` | Could | — | `Asset[]` (newest first; derived frames included, with `derived_from_asset_id`) |
| PATCH | `/api/b/{token}/assets/{id}` | Could | any of `{owner_hint, product_ids, archived}` | `Asset`. `product_ids` replaces the links and marks them `source = 'owner'` |
| GET | `/api/b/{token}/offers?status=` | Could | — | `Offer[]` |
| POST | `/api/b/{token}/offers` | Could | `{kind, title, conditions, price?, starts_on?, ends_on?, product_ids?, status?}` | `Offer` (default `status = 'active'`: the Owner wrote it, so it's confirmed) |
| PATCH | `/api/b/{token}/offers/{id}` | Could | any Offer field, or `status: "archived"` | `Offer` |

Uploads from the dashboard use [Uploads](#uploads) with the `b` prefix. Products and Offers created in the chat go through the orchestrator tools in [agents.md](agents.md), and appear here too.

### Dev / simulator

Used by `/dev/chat` (the WhatsApp simulator) and for local testing. The simulator is a full channel: messages go through the same inbound handler; outbound messages for `channel = 'simulator'` businesses are stored in `messages` and polled by the UI.

| Method | Path | Body / Query | Response |
|---|---|---|---|
| POST | `/dev/sim/businesses` | `{phone?: str}` | `{business_id, phone}`: creates or resets a simulator business (`sim-<random>`) |
| POST | `/dev/sim/{phone}/messages` | `{type: "text", text}` or `{type: "button_reply", button_id, title}` or `{type: "image" \| "video", url}` or `{type: "audio", transcript}` (a voice note with a provider transcript; empty to exercise the fallback) | `202` |
| GET | `/dev/sim/{phone}/messages?after=<iso>` | — | `[SimMessage]` (both directions, ascending) |
| POST | `/dev/businesses/{id}/reset` | `{to_state?: "new" \| "active"}` | resets conversation state (for rehearsals) |
| POST | `/dev/seed/demo` | — | loads the demo business seed (pre-generated Brand Brain + photos; the stage fallback if live brand generation is slow) |
| GET | `/dev/agent-runs?business_id=&limit=` | — | latest `agent_runs` (debug panel) |

```ts
type SimMessage = {
  id: string; direction: "in" | "out"; created_at: string;
  type: "text" | "image" | "video" | "interactive" | "button_reply";
  text: string | null;
  image_url: string | null;
  video_url: string | null;
  buttons: { id: string; title: string }[] | null;   // for interactive messages
};
```

## Button IDs

Free-text approvals ("subilo", "publicalo") reach the same handlers through the orchestrator's `approve_post` tool ([agents.md](agents.md#conversation-rules)). Format: `<action>:<entity_id>`, or `<action>:<entity_id>:<n>` for `variation_pick` (≤ 256 chars). Parsed by `conversation/button_router.py`. Unknown or stale IDs (entity in a state that doesn't allow the action) → send `stale_button` and do nothing else.

| ID | Allowed when | Handler |
|---|---|---|
| `brand_ok` | `awaiting_brand_confirmation` | state → `active`, send `ready_open_chat` ("¿En qué te puedo ayudar hoy?", F1.10). No plan is proposed |
| `brand_fix` | `awaiting_brand_confirmation` | `awaiting = brand_correction`, send `brand_fix_prompt` |
| `plan_start` | active | Should. Enqueue `generate_plan`, send `plan_generating`. Only sent if the bot offers a plan; after F1.10 the plan normally starts from text ("armame el plan de la semana") through `plan_week` |
| `plan_later` | active | Should. Send `plan_later` |
| `plan_approve:{plan_id}` | plan `pending_approval` (Should) | plan → `approved`, create posts, enqueue `generate_post` sequentially, send `plan_approved` |
| `plan_change:{plan_id}` | plan `pending_approval` (Could, F3.3) | `awaiting = plan_feedback` |
| `variation_pick:{post_id}:{n}` | post `pending_approval`, no variation picked yet | Draft: only if the Owner picks with buttons (max 3, so up to 3 variations; [open questions](../open-questions.md#post-images-generated-by-ai-adr-0018)). Same handler as the `pick_variation` tool: copy variation `n` to the Post, send `post_preview` |
| `post_approve:{post_id}` | post `pending_approval` with a picked variation (image Posts), or with its slides sent (carousels) | post → `approved`, `approved_at = now()`, send `publish_when` / `publish_when_adhoc` |
| `post_change:{post_id}` | post `pending_approval` (revision is Should; until then reply that changes come later and offer `[Descartar]`) | `awaiting = post_feedback`, send `post_change_prompt`. Carousel (Must, [ADR 0022](../decisions/0022-carousels-in-mvp.md)): send `carousel_redo_ask`; the answer goes to the orchestrator, which calls `redo_slides` |
| `post_discard:{post_id}` | post `pending_approval` | post → `discarded`, send `post_discarded` |
| `post_replace:{post_id}` | post `discarded` | new post with the same brief (origin same) → `generate_post` |
| `post_publish:{post_id}` | post `approved` | enqueue `publish_post(now)` |
| `post_schedule:{post_id}` | post `approved` (Should) | if `scheduled_for` in future → enqueue `publish_post(scheduled_for)`; else `awaiting = schedule_time`, send `schedule_ask` |
| `post_retry:{post_id}` | post `failed` | retry the last failed job for that post |
| `photo_post:{asset_id}` | active | `create_post(origin="photo", asset_id, brief="Post con esta foto")` |
| `reel_post:{asset_id}` | active, video asset with `reel_suitable` (Could) | `create_post(origin="photo", format="reel", asset_id, brief="Reel con este video")` (`origin = "photo"` covers any asset the Owner sent) |
| `retry:{job_id}` | job `failed` | re-enqueue same kind + payload |
| `noop` | always | send nothing (or a 👍 reaction) |

## Internal module interfaces

These signatures are the contracts between the two build tracks.

```python
# app/channels/base.py
class Button(BaseModel):
    id: str
    title: str                         # ≤ 20 chars

class ChannelPort(Protocol):
    async def send_text(self, to: str, text: str) -> str: ...                       # returns message id
    async def send_image(self, to: str, image_url: str, caption: str | None = None) -> str: ...
    async def send_buttons(self, to: str, body: str, buttons: list[Button],
                           header_image_url: str | None = None,
                           header_video_url: str | None = None) -> str: ...        # 1–3 buttons; one header at most
    async def mark_read(self, message_id: str, typing: bool = False) -> None: ...   # typing: also show the typing indicator (~25 s or until we send)
    async def download_media(self, media_id: str) -> tuple[bytes, str]: ...         # (bytes, mime)

def channel_for(business: Business) -> ChannelPort: ...   # whatsapp | simulator

class InboundMedia(BaseModel):         # image or audio payload
    media_id: str
    url: str | None                    # Kapso's message.kapso.media_url
    mime_type: str | None
    byte_size: int | None

class InboundAudio(BaseModel):         # InboundMessage kind "audio" (voice note, ADR 0021)
    media_id: str
    mime_type: str                     # audio/ogg; codecs=opus
    byte_size: int | None
    provider_transcript: str | None    # Kapso's message.kapso.transcript.text; None if empty or on plan B

class InboundMessage(BaseModel):       # app/channels/base.py; one per webhook delivery
    kind: Literal["text", "button", "image", "audio", "other"]
    message_id: str                    # wamid; the dedupe key
    sender: str                        # phone number, digits only
    phone_number_id: str
    timestamp: int | None
    text: str | None                   # the body, or the caption of an image
    button: Button | None              # kind "button": the id and title of the tapped button
    media: InboundMedia | None         # kinds "image" and "audio"
    audio: InboundAudio | None         # kind "audio"
    raw: dict                          # the webhook body as received

# app/channels/inbound.py: the seams T02 and T23 replace
class DedupeStore(Protocol):
    async def first_seen(self, key: str) -> bool: ...      # atomic; True the first time

class InboundHandler(Protocol):
    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None: ...

# app/transcription/base.py  (ADR 0021; TRANSCRIBE_FALLBACK = gemini | none | mock)
class Transcript(BaseModel):
    text: str                          # empty when there is no speech
    source: Literal["kapso", "gemini", "mock"]
    usage: dict                        # provider usage, logged to agent_runs (agent = "transcribe")

class TranscriberPort(Protocol):
    async def transcribe(self, audio: bytes, mime: str) -> Transcript: ...

# app/publishing/base.py
class PublishResult(BaseModel):
    status: Literal["published", "scheduled", "failed"]
    external_post_id: str | None
    permalink: str | None
    error: str | None

class PublisherPort(Protocol):
    async def ensure_profile(self, business: Business) -> str: ...                  # provider profile id
    async def connect_url(self, business: Business, platform: str, redirect_url: str) -> str: ...
    async def publish(self, account: SocialAccount, caption: str, media: PublishMedia,
                      when: datetime | None) -> PublishResult: ...

class PublishMedia(BaseModel):
    format: Literal["image", "reel", "carousel"]
    url: str | None                    # image/reel: public or long-lived signed URL of the picked variation or the Owner's video
    urls: list[str] = []               # carousel, in slide order, ≤ 10 JPEGs (ADR 0022)
    cover_offset_ms: int | None = None # reel only

# app/imagegen/base.py  (ADR 0018, 0019; IMAGE_GEN = gemini | openai | mock)
class GeneratedImage(BaseModel):
    data: bytes                        # provider output, before resizing
    mime: str
    provider: str                      # gemini | openai | mock
    model: str | None
    usage: dict                        # provider usage, logged to agent_runs (agent = "image_gen")
    finish_reason: str | None = None

class ImageGenPort(Protocol):
    async def generate(self, prompt: str, reference_images: list[bytes],
                       style_image: bytes | None = None) -> GeneratedImage: ...   # one image per call; style_image = carousel anchor
# errors: ImageGenError (base), ImageGenBlocked(reason), ImageGenNoImage, ImageGenUnavailable

# app/media/images.py
def to_post_image(data: bytes) -> bytes: ...       # center-crop to 4:5 and resize to 1080x1350 JPEG
def prepare_reference(data: bytes) -> bytes: ...   # reference photo for the image service: HEIC ok, ≤ 1536 px long side, JPEG

# app/carousel/schemas.py  (ADR 0022; field docs in agents.md)
SlideRole = Literal["cover", "content", "cta"]
class SlideCopy(BaseModel):
    role: SlideRole
    headline: str            # ≤ 6 words
    body: str | None = None  # ≤ 20 words
class CarouselCopy(BaseModel):          # Copywriter, carousel mode
    caption: str
    hashtags: list[str]
    slides: list[SlideCopy]  # 3–5 by default, the Owner's number up to 10; slides[0].role == "cover"
class SlideScene(BaseModel):
    index: int               # 1-based
    scene_prompt: str        # English: what this slide shows (scene, composition); no text
class CarouselBrief(BaseModel):         # Art Director, carousel mode
    reference_asset_ids: list[str]   # 1–10
    style_prompt: str                # English: shared visual system (palette hex, typography, layout grid, text safe area)
    slides: list[SlideScene]         # one per CarouselCopy slide, same order
    style_notes: str                 # short Spanish summary for the Owner
class TextCheck(BaseModel):             # Text Checker
    matches: bool
    found: str
    issues: list[str]

# app/carousel/prompts.py
def build_slide_prompt(brief: CarouselBrief, copy: CarouselCopy, index: int, *, anchored: bool) -> str: ...
    # style + scene + "render exactly this text and no other text" + fixed rules (keep the product unchanged,
    # no logos, no prices/numbers unless in the given text, text inside the central 90%)

# app/carousel/generator.py
class GeneratedSlide:
    index: int
    image: bytes                       # 1080x1350 JPEG
    prompt: str
    provider: str
    model: str | None
    usage: dict
    text_check: TextCheck | None

class CarouselGenerator:
    def __init__(self, image_gen: ImageGenPort, text_checker=None): ...   # text_checker: app/agents/text_checker.py
    async def generate(self, copy: CarouselCopy, brief: CarouselBrief,
                       references: list[bytes]) -> list[GeneratedSlide]: ...
        # cover first, the others in parallel anchored on it; each resized with to_post_image,
        # text-checked, regenerated once on mismatch (kept and flagged if it still fails)
    async def redo(self, copy: CarouselCopy, brief: CarouselBrief, references: list[bytes],
                   slides: list[GeneratedSlide], indexes: list[int]) -> list[GeneratedSlide]: ...
        # anchored on the current cover; a redo of the cover anchors on slide 2

# app/media/video.py (ffmpeg / ffprobe; Could)
async def probe(path: Path) -> VideoInfo: ...                                     # duration_ms, width, height, codecs
async def keyframes(path: Path, count: int = 6, max_side: int = 1568) -> list[Frame]: ...   # JPEG bytes + offset_ms
async def whatsapp_preview(path: Path) -> bytes | None: ...                        # MP4 ≤ 16 MB, or None if it can't fit

# app/jobs/runner.py
async def enqueue(kind: str, payload: dict, business_id: UUID | None) -> UUID: ...
```
