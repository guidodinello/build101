# Backend API

FastAPI. JSON in and out, `snake_case` fields. Errors use `{"error": {"code": "...", "message": "..."}}` with a proper HTTP status. OpenAPI is served at `/docs`; the frontend's `lib/api.ts` types are written by hand from this document (no codegen in the hackathon).

## Authentication

| Caller | Mechanism |
|---|---|
| Meta webhook | `X-Hub-Signature-256` HMAC with `META_APP_SECRET` |
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
| GET | `/webhooks/whatsapp` | Verification: if `hub.mode == "subscribe"` and `hub.verify_token == META_VERIFY_TOKEN`, return `hub.challenge` as plain text, else 403 |
| POST | `/webhooks/whatsapp` | Verify signature → enqueue handling as a background task → return `200` immediately. Handles `messages` and `statuses` changes. Payload shapes in [integrations.md](integrations.md#whatsapp-cloud-api) |

### Zernio webhook

| Method | Path | Notes |
|---|---|---|
| POST | `/webhooks/zernio` | Verify signature. On `post.published` → post `published` + permalink + notify owner (if it was scheduled). On `post.failed` → `failed` + `publish_failed`. On `account.connected` → `social_accounts.status = connected` |

### Onboarding (web wizard)

All under `/api/o/{token}`. The token is the onboarding magic link.

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/api/o/{token}` | — | `OnboardingState` (below) |
| PUT | `/api/o/{token}/business` | `{name, category, one_liner, description?, location, website?, instagram_handle?}` | `OnboardingState` |
| PUT | `/api/o/{token}/products` | `{products: [{id?, name, description, price?, category?}]}` (≥ 1, no maximum) | `OnboardingState`: upserts `products` rows in the given order; rows left out are archived |
| PUT | `/api/o/{token}/brand` | `{three_words: [str, str, str], colors: [hex...]}` | `OnboardingState` |
| POST | `/api/o/{token}/uploads` | `UploadRequest` (below) | `UploadTicket`: see [Uploads](#uploads) |
| POST | `/api/o/{token}/assets/{asset_id}/complete` | — | `Asset` (logo includes `palette`) |
| DELETE | `/api/o/{token}/assets/{asset_id}` | — | `204`: archives the asset (the ✕ on a wizard thumbnail) |
| PUT | `/api/o/{token}/preferences` | `Questionnaire` (below) | `OnboardingState` |
| POST | `/api/o/{token}/instagram/connect` | `{}` | `{"auth_url": "..."}`: creates the Zernio profile if needed and returns the hosted connect URL. `redirect_url` = `{FRONTEND_URL}/o/{token}?step=instagram&connected=1` |
| POST | `/api/o/{token}/instagram/callback` | `{account_id?, query: {...}}`: the frontend forwards the query params Zernio appended to the redirect | `OnboardingState` |
| POST | `/api/o/{token}/complete` | — | `202 {"status": "generating_brand"}`. Validates required fields (name, category, ≥ 1 product, ≥ 3 photos (videos optional), logo optional but recommended), sets state, enqueues `generate_brand`, sends `brand_generating` on WhatsApp |

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

The wizard (`/api/o/{token}`) and the dashboard (`/api/b/{token}`) share one upload flow. Files go **from the browser straight to Supabase Storage**; the backend never receives the bytes ([ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md), facts in [../research/media-uploads.md](../research/media-uploads.md)).

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
| `video` | `video/mp4`, `video/quicktime` (MOV) | 300 MB |

Anything else → `422 unsupported_file` with a Spanish `message` the UI shows as is. Video duration and size in pixels are read with `ffprobe` during `analyze_asset`, not at upload.

```ts
type UploadRequest = { kind: "logo" | "photo" | "video"; filename: string; content_type: string;
                       size_bytes: number; owner_hint?: string };
type UploadTicket = { asset_id: string; upload_url: string; upload_token: string; resumable: boolean };
```

### Dashboard (Must, editable)

Token = a `dashboard` magic link (the bot sends it when the owner asks "¿dónde veo todo?" or "quiero subir fotos"). Valid for **7 days**; writing "link" in WhatsApp sends a new one. Anyone with the link can edit until there are user accounts (F7.4), so **nothing is hard-deleted**: `archived: true` hides a Product, Brand asset or Offer from agents and the dashboard. Archiving material used by a draft Post (`pending_approval`, `revising`) flags that Post for review; published and scheduled Posts don't change.

| Method | Path | Body / Query | Response |
|---|---|---|---|
| GET | `/api/b/{token}` | — | `{business: {...}, brand_brain: BrandBrain, instagram: {...}, counts: {products, photos, videos, active_offers}}` |
| GET | `/api/b/{token}/posts?status=` | — | `[{id, title, format, status, image_url, video_url, cover_url, caption, scheduled_for, published_at, permalink, needs_review}]` |
| GET | `/api/b/{token}/plans/current` | — | `{week_start, status, items: [...]}` |
| GET | `/api/b/{token}/products?include_archived=` | — | `Product[]` (by `position`) |
| POST | `/api/b/{token}/products` | `{name, description?, price?, category?}` | `Product` |
| PATCH | `/api/b/{token}/products/{id}` | any of `{name, description, price, category, position, archived}` | `Product` |
| GET | `/api/b/{token}/assets?kind=&product_id=&include_archived=` | — | `Asset[]` (newest first; derived frames included, with `derived_from_asset_id`) |
| PATCH | `/api/b/{token}/assets/{id}` | any of `{owner_hint, product_ids, archived}` | `Asset`. `product_ids` replaces the links and marks them `source = 'owner'` |
| GET | `/api/b/{token}/offers?status=` | — | `Offer[]` |
| POST | `/api/b/{token}/offers` | `{kind, title, conditions, price?, starts_on?, ends_on?, product_ids?, status?}` | `Offer` (default `status = 'active'`: the Owner wrote it, so it's confirmed) |
| PATCH | `/api/b/{token}/offers/{id}` | any Offer field, or `status: "archived"` | `Offer` |

Uploads from the dashboard use [Uploads](#uploads) with the `b` prefix. Products and Offers created in the chat go through the orchestrator tools in [agents.md](agents.md), and appear here too.

### Dev / simulator

Used by `/dev/chat` (the WhatsApp simulator) and for local testing. The simulator is a full channel: messages go through the same inbound handler; outbound messages for `channel = 'simulator'` businesses are stored in `messages` and polled by the UI.

| Method | Path | Body / Query | Response |
|---|---|---|---|
| POST | `/dev/sim/businesses` | `{phone?: str}` | `{business_id, phone}`: creates or resets a simulator business (`sim-<random>`) |
| POST | `/dev/sim/{phone}/messages` | `{type: "text", text}` or `{type: "button_reply", button_id, title}` or `{type: "image" \| "video", url}` | `202` |
| GET | `/dev/sim/{phone}/messages?after=<iso>` | — | `[SimMessage]` (both directions, ascending) |
| POST | `/dev/businesses/{id}/reset` | `{to_state?: "new" \| "active"}` | resets conversation state (for rehearsals) |
| POST | `/dev/seed/demo` | — | loads the demo business seed (pre-generated Brand Brain + plan) |
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

Format: `<action>:<entity_id>` (≤ 256 chars). Parsed by `conversation/button_router.py`. Unknown or stale IDs (entity in a state that doesn't allow the action) → send `stale_button` and do nothing else.

| ID | Allowed when | Handler |
|---|---|---|
| `brand_ok` | `awaiting_brand_confirmation` | state → `active`, send `ready_first_plan` |
| `brand_fix` | `awaiting_brand_confirmation` | `awaiting = brand_correction`, send `brand_fix_prompt` |
| `plan_start` | active | enqueue `generate_plan`, send `plan_generating` |
| `plan_later` | active | send `plan_later` |
| `plan_approve:{plan_id}` | plan `pending_approval` | plan → `approved`, create posts, enqueue `generate_post` sequentially, send `plan_approved` |
| `plan_change:{plan_id}` | plan `pending_approval` | `awaiting = plan_feedback` |
| `post_approve:{post_id}` | post `pending_approval` | post → `approved`, `approved_at = now()`, send `publish_when` / `publish_when_adhoc` |
| `post_change:{post_id}` | post `pending_approval` | `awaiting = post_feedback`, send `post_change_prompt` |
| `post_discard:{post_id}` | post `pending_approval` | post → `discarded`, send `post_discarded` |
| `post_replace:{post_id}` | post `discarded` | new post with the same brief (origin same) → `generate_post` |
| `post_publish:{post_id}` | post `approved` | enqueue `publish_post(now)` |
| `post_schedule:{post_id}` | post `approved` | if `scheduled_for` in future → enqueue `publish_post(scheduled_for)`; else `awaiting = schedule_time`, send `schedule_ask` |
| `post_retry:{post_id}` | post `failed` | retry the last failed job for that post |
| `photo_post:{asset_id}` | active | `create_post(origin="photo", asset_id, brief="Post con esta foto")` |
| `reel_post:{asset_id}` | active, video asset with `reel_suitable` | `create_post(origin="photo", format="reel", asset_id, brief="Reel con este video")` (`origin = "photo"` covers any asset the Owner sent) |
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
    async def mark_read(self, message_id: str) -> None: ...
    async def download_media(self, media_id: str) -> tuple[bytes, str]: ...         # (bytes, mime)

def channel_for(business: Business) -> ChannelPort: ...   # whatsapp | simulator

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
    format: Literal["image", "reel"]
    url: str                           # public or long-lived signed URL: the render (image) or the Owner's video (reel)
    cover_offset_ms: int | None = None # reel only

# app/rendering/renderer.py
async def render_post(spec: RenderSpec, brand: VisualIdentity, assets: AssetResolver) -> bytes: ...  # JPEG

# app/media/video.py (ffmpeg / ffprobe)
async def probe(path: Path) -> VideoInfo: ...                                     # duration_ms, width, height, codecs
async def keyframes(path: Path, count: int = 6, max_side: int = 1568) -> list[Frame]: ...   # JPEG bytes + offset_ms
async def whatsapp_preview(path: Path) -> bytes | None: ...                        # MP4 ≤ 16 MB, or None if it can't fit

# app/jobs/runner.py
async def enqueue(kind: str, payload: dict, business_id: UUID | None) -> UUID: ...
```
