# Agents

The "agency" is one **orchestrator** (the account manager the owner talks to) plus a **fixed catalog of specialist agents** that become personal to each business through its **Brand Brain**. We don't generate agents per business. Every business gets the same team, and the Brand Brain plus the business's Catalog (Products), Offers, Brand assets (photos and videos) and history make their work specific. See [ADR 0006](../decisions/0006-fixed-agent-catalog-brand-brain.md) and [ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md).

## Agent roster

| Agent | Kind | Called by | Input → Output | Effort |
|---|---|---|---|---|
| **Orchestrator** | Tool-use loop | Inbound handler | Conversation + context → reply text + tool calls | `low` |
| **Asset Analyst** | Single call, vision, structured | `analyze_asset` job | Image, or video keyframes + metadata → description, tags, suggested Products, usable-for (+ Reel suitability) | `low` |
| **Brand Strategist** | Single call, structured | `generate_brand` job | Onboarding data + Catalog + asset descriptions (+ correction) → Brand Brain | `high` |
| **Content Strategist** | Single call, structured | `generate_plan` job | Brand Brain + Catalog + active Offers + assets + recent posts + date + notes → weekly plan (images and Reels) | `medium` |
| **Copywriter** | Single call, structured | `generate_post` job | Brand Brain + brief (+ feedback, previous version) → copy | `medium` |
| **Art Director** | Single call, vision, structured | `generate_post` job | Brand Brain + copy + candidate photos + template catalog → render spec; for a Reel: candidate videos (keyframes) → video + cover frame | `medium` |
| **Feedback Classifier** | Single call, structured | `revise_post` job | Feedback text → `copy` / `image` / `both` (Reel: `copy` / `cover` / `video`) + normalized instruction | `low` |

Not agents (deterministic services): **Renderer** (render spec → JPEG; not used for Reels), **Frame Extractor** (ffmpeg/ffprobe in the backend: video → metadata + keyframes JPEGs), **Publisher** (approved post → provider API, image or Reel), **Scheduler** (delegated to the provider).

## LLM client conventions

All Claude calls go through `app/llm/client.py`. It's the only module that imports `anthropic`.

- SDK: official `anthropic` Python SDK, `AsyncAnthropic` client. Read the key from `ANTHROPIC_API_KEY`.
- Model: `claude-opus-5-5` for every agent (configurable per agent in `config.py`). Tune **effort** per agent (table above) rather than switching models. Thinking is always on in this model, so don't send `thinking: disabled` or `budget_tokens` (both return 400). Control depth with `output_config={"effort": ...}`.
- **Structured output** for every specialist: Pydantic model → `output_config={"format": {"type": "json_schema", "schema": Model.model_json_schema()}}` (or `client.messages.parse(output_format=Model)`), then `Model.model_validate_json(...)`. Keep schemas simple: objects, strings, ints, enums, lists. Set `additionalProperties: false` and put every field in `required`.
- **Refusal fallback**: enable server-side fallbacks on every call (`betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"` on `client.beta.messages.create`). Always check `stop_reason` (`refusal`, `max_tokens`) before reading content.
- **Prompt caching**: top-level `cache_control={"type": "ephemeral"}`. Order the prompt stable → volatile: system prompt (static) → Brand Brain (per business) → dynamic context. Never put timestamps in the system prompt.
- **Images**: pass by URL (`{"type": "image", "source": {"type": "url", "url": signed_url}}`) using a short-lived signed Supabase URL, or base64 for small files. Resize to max 1568 px on the long side before upload to save tokens.
- **Video**: Claude takes no video or audio input ([research/media-uploads.md](../research/media-uploads.md#what-claude-can-read)). Agents see a video as its ffprobe metadata plus keyframes (JPEG, ≤ 1568 px long edge) extracted by the Frame Extractor, each labeled with its offset in ms. No transcription in the MVP.
- **Timeouts/retries**: SDK defaults (2 retries). Per-call timeout 90 s for specialists, 30 s per orchestrator step.
- **Logging**: each call writes `agent_runs` (business_id, agent, model, effort, input JSON, output JSON, input/output/cache tokens, latency_ms, stop_reason, error).
- **Max tokens**: 16000 for specialists, 4000 for orchestrator steps.

Before changing any of this, check the current Claude API docs. Model IDs and parameters change.

## Brand Brain

The single source of truth about a business, consumed by every agent. Stored as versioned JSON in `brand_brains` (each change = new version; agents read the latest).

```python
class Voice(BaseModel):
    descriptors: list[str]            # 3–5 adjectives, e.g. ["cercano", "cálido", "artesanal"]
    formality: int                    # 1 (muy informal) – 5 (muy formal)
    humor: int                        # 1 (serio) – 5 (divertido)
    emoji_policy: Literal["many", "few", "none"]
    do: list[str]                     # "Hablar de vos", "Mencionar que es hecho a mano"
    dont: list[str]                   # "No hablar de precios", "No usar 'barato'"
    sample_phrases: list[str]         # 3–5 phrases in the brand's voice (Rioplatense)

class Audience(BaseModel):
    name: str                         # "Parejas jóvenes armando su primera casa"
    description: str
    pains: list[str]
    motivations: list[str]

class ContentPillar(BaseModel):
    id: str                           # slug: "a-medida"
    name: str                         # "Piezas a medida"
    description: str
    example_ideas: list[str]

class FeaturedProduct(BaseModel):
    product_id: str                   # a row in `products` (the Catalog)
    name: str
    why: str                          # why it leads: "el más vendido", "lo nuevo"

class VisualIdentity(BaseModel):
    primary_color: str                # hex
    secondary_color: str
    accent_color: str
    background_color: str
    text_color: str
    font_pair: Literal["modern", "classic", "warm", "bold"]   # maps to bundled fonts
    logo_asset_id: str | None
    photo_style: str                  # "luz natural, madera, ambientes cálidos"

class BrandBrain(BaseModel):
    business_name: str
    one_liner: str
    description: str
    category: str
    location: str
    goal: Literal["sales", "awareness", "launch", "loyalty"]
    audiences: list[Audience]         # 1–3
    value_props: list[str]            # 3–5
    voice: Voice
    pillars: list[ContentPillar]      # 3–5
    featured_products: list[FeaturedProduct]   # ≤ 5, chosen from the Catalog; the full Catalog lives in `products`
    ctas: list[str]                   # "Escribinos por WhatsApp", "Visitá el showroom"
    hashtags: list[str]               # 10–20, mix of niche + local
    posting: PostingPrefs             # posts_per_week, preferred_days, preferred_time ("19:00")
    constraints: list[str]            # hard "never" rules from the owner
    whatsapp_summary: str             # ≤ 600 chars, WhatsApp-formatted, for brand_summary message
```

`PostingPrefs`: `posts_per_week: int`, `preferred_days: list[Literal["mon",...,"sun"]]`, `preferred_time: str` (HH:MM, local).

The Brand Brain holds **who the brand is**, not what it sells today. Products (the Catalog) and Offers live in their own tables because the Owner edits them constantly from the dashboard and the chat; versioning the whole Brand Brain on every price change would be noise. Agents that need them receive them as separate input blocks:

- `<catalog>`: active Products (`archived_at is null`): id, name, description, price (free text as the Owner wrote it, or null), category, linked asset ids.
- `<offers>`: Offers with `status = 'active'` whose `starts_on`/`ends_on` include the relevant date: id, kind (`pack` | `promo`), title, conditions, price, dates, product ids. Drafts are never shown to content agents.

Agents receive the Brand Brain rendered as compact JSON inside a `<brand_brain>` tag in the system prompt. It sits right after the static instructions so it's cached per business.

## Specialist agents

Each agent lives in `app/agents/<name>.py` with:

- `Input` and `Output` Pydantic models (in `app/agents/schemas.py`),
- a system prompt in `app/agents/prompts/<name>.md`,
- one public function `async def run(input: Input, *, business_id: UUID) -> Output`.

Prompts are written in English (instructions) and require output content in Rioplatense Spanish. Every prompt includes the voice rules from [../product/conversation-design.md](../product/conversation-design.md) where relevant.

### Asset Analyst

**Purpose:** understand each uploaded photo or video so other agents can choose material without looking at every file again.

- Input: `asset_id`, `kind` (`logo` | `photo` | `video`), owner-provided hint (optional, e.g. product name), the Catalog (product ids + names + descriptions) so it can suggest links.
  - Photo / logo: the image (URL).
  - Video: ffprobe metadata (`duration_ms`, `width`, `height`, fps) + ~6 keyframes from the Frame Extractor (one per scene change, topped up at fixed intervals), each with its `frame_offset_ms`.
- Output (photo / logo):

  ```python
  class AssetAnalysis(BaseModel):
      description: str                 # 1–2 sentences in Spanish: what's in the photo
      subjects: list[str]              # ["mesa de comedor", "roble", "living"]
      product_ids: list[str]           # Catalog Products visible in the photo (0..n), only if clearly shown
      quality: Literal["high", "ok", "low"]   # blur, lighting, framing
      orientation: Literal["portrait", "landscape", "square"]
      has_people: bool
      has_text: bool
      dominant_colors: list[str]       # hex, from the model (logo: refined by Pillow palette)
      best_for: list[Literal["hero", "background", "detail", "behind_the_scenes"]]
      safe_crop_focus: Literal["center", "top", "bottom", "left", "right"]
  ```

- Output (video):

  ```python
  class VideoAnalysis(BaseModel):
      description: str                 # 1–2 sentences in Spanish: what happens in the video
      subjects: list[str]
      product_ids: list[str]           # Catalog Products shown (0..n)
      quality: Literal["high", "ok", "low"]   # shake, lighting, framing across keyframes
      orientation: Literal["portrait", "landscape", "square"]
      has_people: bool
      has_text: bool
      best_frame_offsets_ms: list[int] # ≤ 3 frames worth keeping as photos, from the offsets given
      cover_offset_ms: int             # best frame to use as the Reel cover
      reel_suitable: bool
      reel_reason: str                 # short Spanish reason, e.g. "Vertical, 24 s, buena luz"
  ```

- `reel_suitable` is a model judgment checked in code: it is forced to `false` unless `3000 ≤ duration_ms ≤ 90000` (Zernio's Reel limit, see [research/media-uploads.md](../research/media-uploads.md#publishing-video-and-carousels-zernio-instagram)) and the video is portrait or square. All offsets must be among the keyframe offsets passed in.
- Product links: every id in `product_ids` is written to `asset_products` with `source = 'analyst'`. Links with `source = 'owner'` (set or removed from the dashboard) always win; the analyst never re-adds a link the Owner removed.
- Derived frames (Should): each `best_frame_offsets_ms` frame is saved as a new `photo` Brand asset with `derived_from_asset_id` = the video and `frame_offset_ms`, then analyzed as a photo, so the Art Director can use it in image templates.
- Logo special case: also run a deterministic palette extraction (Pillow quantize to 5 colors, ignore near-white/near-black/transparent) and store both. The web wizard shows the Pillow palette as editable swatches.

### Brand Strategist

**Purpose:** turn onboarding inputs into the Brand Brain. Also handles corrections.

- Input: business fields, the Catalog (`<catalog>`), questionnaire answers, owner's "3 words", asset analyses (descriptions only, not images), Pillow palette + owner-confirmed colors, optional `previous_brand_brain` + `correction` (revise mode).
- Output: `BrandBrain`.
- Rules in the prompt:
  - Use only facts given by the owner; mark nothing as fact that wasn't provided (no invented awards, years, locations).
  - Owner-confirmed colors win over model guesses.
  - `constraints` must include every "no quiero que..." answer verbatim.
  - In revise mode: change only what the correction implies; keep everything else.
  - `whatsapp_summary` follows the 4-bullet format in conversation-design.md.
  - `featured_products`: up to 5 Products from the Catalog, referenced by id; never a Product that isn't in the Catalog.

### Content Strategist

**Purpose:** weekly plan.

- Input: Brand Brain, `<catalog>`, `<offers>` (active during the plan week), `week_start` (date), `posts_count`, today's date, last 10 posts (title, pillar, format, date), owner notes ("cambiá la 2 por algo de la promo de sillas"), previous plan (revise mode), list of available assets (id + kind + description + best_for + product ids; videos add duration and `reel_suitable`). Archived assets and Products are excluded before the call.
- Output:

  ```python
  class PlanItem(BaseModel):
      scheduled_for: datetime          # local time, within the week, uses preferred days/time
      pillar_id: str
      format: Literal["image", "reel"]
      title: str                       # ≤ 40 chars, internal + shown in plan list
      idea: str                        # 1–2 sentences: what the post says
      angle: str                       # why it works for the audience
      product_ids: list[str]           # Catalog Products featured (0..n)
      offer_id: str | None             # an active Offer this post promotes
      suggested_asset_ids: list[str]   # 1–3 candidates; for a Reel, reel-suitable videos only
      suggested_template: TemplateId | None   # null for Reels
  class WeeklyPlan(BaseModel):
      items: list[PlanItem]
      whatsapp_text: str               # numbered list for plan_preview, ≤ 900 chars
  ```

- Rules: rotate pillars, don't repeat a product two posts in a row, promote an active Offer at most once per week unless asked, only reference assets, Products and Offers that exist, respect `constraints`. At most **one Reel** per weekly plan unless the Owner asks for more, and only when a `reel_suitable` video exists; otherwise every item is `image`. Never put a price or discount in `idea` that isn't in a Product or Offer. Commercial dates may be used only when they fall in the plan week and come from the `commercial_dates` list passed in the input (a small static list per country in `app/agents/data/commercial_dates_uy.json`, so the model never guesses dates).

### Copywriter

**Purpose:** write the caption and on-image text.

- Input: Brand Brain, brief (plan item or ad-hoc request text), `format` (`image` | `reel`), the Products and Offer the brief references (from `<catalog>` / `<offers>`), platform (`instagram`), optional `previous` copy + `feedback` (revise mode). For a Reel, also the video's `VideoAnalysis.description` so the caption matches what is on screen.
- Output:

  ```python
  class PostCopy(BaseModel):
      title: str                       # internal title, ≤ 40 chars
      headline: str                    # on-image, ≤ 40 chars, no hashtags/emojis
      subheadline: str | None          # on-image, ≤ 60 chars
      caption: str                     # 150–900 chars, Instagram-ready, line breaks allowed
      cta: str                         # included at the end of the caption too
      hashtags: list[str]              # 5–10, without '#' duplicates, lowercase, no spaces
  ```

- Rules: voice from the Brand Brain; first line must hook (≤ 80 chars); no invented facts (prices, discounts, dates only if in a referenced Product or Offer, or in an ad-hoc brief from the Owner); respect emoji policy; Rioplatense *vos*; never mention AI. In revise mode, apply the feedback literally and change as little else as possible.
- Reel variant: same `PostCopy` model, but `headline` and `subheadline` are unused (nothing is drawn on the video; set `headline` to the title and `subheadline` to null), the caption is shorter (80–400 chars) and its first line is the hook, because Instagram truncates Reel captions early.

### Art Director

**Purpose:** decide what the image looks like. It picks, it doesn't draw.

- Input: Brand Brain (visual identity), `PostCopy`, candidate assets (IDs + analyses + **the images themselves**, max 4, as URLs), template catalog (IDs, slots, best-for — see [../design/post-templates.md](../design/post-templates.md)), optional feedback + previous spec (revise mode), optional `force_asset_id`.
- Output (`RenderSpec`):

  ```python
  class RenderSpec(BaseModel):
      template_id: TemplateId          # "product_hero" | "promo_band" | "quote_card" | "split_story"
      photo_asset_id: str | None       # required unless template is text-only
      crop_focus: Literal["center", "top", "bottom", "left", "right"]
      slots: dict[str, str]            # template slot → text, e.g. {"headline": "...", "badge": "15% OFF"}
      color_roles: ColorRoles          # background, text, accent: hex from the brand palette only
      show_logo: bool
  ```

- Rules: only colors from `visual_identity`; text in slots must fit template max lengths (validated after the call, see below); prefer `quality=high` photos (derived video frames are valid photos); for promos use `promo_band`; for tips/quotes without a strong photo use `quote_card`.
- **Post-validation (code):** check slot lengths, color hex membership, asset ownership. On violation, retry once with the error list appended; if it fails again, fall back to `product_hero` with the copy headline.
- **Reel mode:** input is the copy plus up to 3 candidate videos (each as metadata + its keyframes with offsets + `VideoAnalysis`). No template, no render. Output:

  ```python
  class ReelSpec(BaseModel):
      video_asset_id: str
      cover_offset_ms: int             # one of the keyframe offsets; defaults to VideoAnalysis.cover_offset_ms
  ```

  Post-validation (code): the video belongs to the business, is not archived, is `reel_suitable`, and `0 ≤ cover_offset_ms ≤ duration_ms`. On violation, retry once; then fall back to the first suggested video and its analyzed cover.

### Feedback Classifier

- Input: feedback text, post `format`, current copy, current render spec summary (image) or current video + cover summary (Reel).
- Output: `{"target": ..., "instruction": str}` (instruction = normalized, explicit version of the feedback, e.g. "Acortar el caption a 2 líneas y mencionar envío gratis en Montevideo").
  - Image Post: `target` is `copy` | `image` | `both`.
  - Reel: `target` is `copy` | `cover` (pick another frame of the same video) | `video` (swap to another reel-suitable video). We don't edit video, so "cortalo más corto" or "ponele música" maps to `copy` with an instruction that the Orchestrator turns into a short "eso todavía no lo puedo hacer" reply plus an offer to swap the video.

## Orchestrator

A manual tool-use loop in `app/orchestrator/orchestrator.py` (we need async, DB persistence and our own guards, so we don't use the SDK's beta tool runner).

### Per-turn algorithm

```text
run_turn(business, inbound_text):
    context = build_context(business)        # brand summary, pending posts, awaiting state, now
    history = last 20 messages (role user/assistant, text only)
    messages = history + [user: inbound_text (+ pending-state note)]
    for step in range(MAX_STEPS = 5):
        resp = llm.create(system=[static_prompt, brand_block, dynamic_block], tools=TOOLS, messages)
        handle stop_reason: refusal → send generic fallback text; max_tokens → truncate safely
        append resp.content (all blocks, including thinking) to messages
        if no tool_use blocks: break
        execute all tool_use blocks (concurrently), append ONE user message with all tool_results
    reply = concatenated text blocks of the last response
    if reply: channel.send_text(reply); store assistant message
```

- History rebuilt from the DB each turn contains **text only** (no tool or thinking blocks from earlier turns). Within a turn, pass `resp.content` back unchanged (thinking blocks included).
- Tools are defined with `strict: true` and `additionalProperties: false`.
- `tool_choice` stays `auto`. Forced tool choice is not supported on this model.
- If the model returns text **and** a long-running tool, send the text (the acknowledgement) and let the job send the result.

### Tools

| Tool | Input | Does | Returns |
|---|---|---|---|
| `plan_week` | `notes?: str`, `week_start?: date` | Enqueue `generate_plan` | `{job_id, status: "started"}` |
| `revise_plan` | `plan_id`, `feedback` | Enqueue `generate_plan` (revise mode) | `{job_id}` |
| `create_post` | `brief: str`, `format?: "image" \| "reel"`, `scheduled_for?: datetime`, `asset_id?: str`, `offer_id?: str` | Create post row + enqueue `generate_post`. `format = "reel"` requires a reel-suitable video, else returns `{"error": "no_reel_video"}` | `{post_id, job_id}` |
| `revise_post` | `post_id`, `feedback` | Enqueue `revise_post` | `{job_id}` |
| `approve_post` | `post_id` | Same handler as `[Aprobar]` button (sends `publish_when`) | `{status}` |
| `publish_post` | `post_id`, `when: "now" \| ISO datetime` | Guard: status must be `approved`; enqueue `publish_post` | `{job_id}` or error |
| `discard_post` | `post_id` | Status → `discarded` | `{status}` |
| `list_posts` | `statuses?: list[str]`, `limit?: int` | Query posts | `[{id, title, status, scheduled_for, permalink}]` |
| `get_brand_summary` | — | Read latest Brand Brain + active Offers | `{whatsapp_summary, pillars, featured_products, offers, constraints}` |
| `update_brand_brain` | `change: str` | Enqueue `generate_brand` revise mode (silent: no summary message unless asked) | `{job_id}` |
| `list_catalog` | `query?: str` | Search active Products by name/category | `[{id, name, price, category}]` |
| `save_product` | `product_id?: str`, `name`, `description?`, `price?`, `category?`, `confirmed: bool` | Create or update a Product. With `confirmed = false` it only returns the preview; the model must read it back to the Owner ("¿Lo guardo así?") and call again with `confirmed = true` after an explicit yes | `{product, saved}` |
| `save_offer` | `offer_id?: str`, `kind: "pack" \| "promo"`, `title`, `conditions`, `price?`, `starts_on?`, `ends_on?`, `product_ids?`, `confirmed: bool` | Create or update an Offer. `confirmed = false` saves it as `draft` and returns the preview; `confirmed = true` (after the Owner's explicit yes) sets `status = 'active'`. Prices and conditions come only from the Owner's words | `{offer, status}` |
| `send_dashboard_link` | — | Create a `dashboard` magic link (7 days) and send it as a CTA URL button ("Abrí tu panel") | `{sent: true}` |
| `cancel_pending` | — | Clear `conversation_state.awaiting` | `{ok}` |

Guards are in the tool implementations, not in the prompt: `publish_post` returns `{"error": "post_not_approved"}` if the status is wrong, and the model must relay that. `save_product` and `save_offer` never persist active data without `confirmed = true`, and the inbound handler rejects `confirmed = true` unless the Owner's last message is an explicit yes (button reply or affirmative text).

### Context block (dynamic, after the cache breakpoint)

```text
<now>2026-10-20T14:32:00-03:00 (lunes)</now>
<awaiting>post_feedback for post 7f3c… ("Mesa Nórdica")</awaiting>
<pending_posts>
- 7f3c… "Mesa Nórdica" — pending_approval — mar 21 19:00
- 1a9e… "Promo sillas" — approved — sin fecha
</pending_posts>
<instagram_connected>true</instagram_connected>
<catalog_size>products: 23 · photos: 64 · videos: 7 (reel-suitable: 4)</catalog_size>
<active_offers>
- 5c21… promo "15% en sillas" — hasta dom 26
</active_offers>
<unannounced_results>
- 3b7d… "Taller por dentro" — published — https://www.instagram.com/p/…
</unannounced_results>
```

`<unannounced_results>` lists scheduled posts whose `published` / `publish_failed` notification WhatsApp rejected (outside the 24-hour window, see [integrations.md](integrations.md#receiving)). The orchestrator mentions them in its next reply; the inbound handler then clears them.

## Job pipelines

| Job | Steps | Sends to owner |
|---|---|---|
| `analyze_asset(asset_id)` | Photo/logo: Asset Analyst → save analysis (+ Pillow palette for logos) → write analyst `asset_products`. Video: Frame Extractor (ffprobe + keyframes) → Asset Analyst (video mode) → save `VideoAnalysis`, `duration_ms`, `width`, `height` → write analyst `asset_products` → (Should) save best frames as derived photo assets and enqueue `analyze_asset` for each | nothing (or `photo_saved` for WhatsApp photos) |
| `generate_brand(business_id, correction?)` | wait for pending `analyze_asset` → Brand Strategist → save new version | `brand_summary` (onboarding/correction) |
| `generate_plan(business_id, notes?, plan_id?)` | Content Strategist → save plan + items | `plan_preview` |
| `generate_post(post_id)` | Image: Copywriter → Art Director → validate → Renderer → upload → save. Reel: Copywriter (Reel variant) → Art Director (Reel mode) → validate → save `video_asset_id` + `cover_offset_ms` + cover JPEG (the keyframe at that offset) | `post_preview`; Reel: `reel_preview` (video header when the preview transcode fits WhatsApp's 16 MB) or `reel_preview_link` (cover + dashboard link), see [integrations.md](integrations.md) |
| `revise_post(post_id, feedback)` | Feedback Classifier → (Copywriter) → (Art Director) → (Renderer, image only) → save revision | `post_preview` |
| `publish_post(post_id, when)` | guard → Publisher (now / schedule; image or Reel by `posts.format`) → save external id + permalink | `published` / `scheduled` / `publish_failed` |

Posts from an approved plan are generated **sequentially** in plan order, so previews arrive in order and we stay under rate limits.

## Quality checks (cheap, deterministic)

Run after every agent call, before saving:

- Caption length 150–900 chars for images, 80–400 for Reels; headline ≤ 40; hashtags 5–10, no duplicates.
- No phrase from `constraints` appears in caption/headline (case-insensitive substring).
- No price/discount numbers in copy unless they appear in a referenced Product or active Offer, or in the Owner's own ad-hoc brief (regex for `%`, `$`, `USD`, `UYU`).
- Referenced asset, Product and Offer IDs belong to the business and are not archived; a Reel's video is `reel_suitable`.

On failure: one retry with the violations listed; then accept and log a warning (demo shouldn't block).
