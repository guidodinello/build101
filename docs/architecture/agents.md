# Agents

The "agency" is one **orchestrator** (the account manager the owner talks to) plus a **fixed catalog of specialist agents** that become personal to each business through its **Brand Brain**. We don't generate agents per business. Every business gets the same team, and the Brand Brain plus the business's Catalog (Products), Offers, Brand assets (photos and videos) and history make their work specific. See [ADR 0006](../decisions/0006-fixed-agent-catalog-brand-brain.md) and [ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md).

**Build priority** ([ADR 0016](../decisions/0016-demo-scope-one-post.md), full list in [../product/mvp.md](../product/mvp.md)): the Must scope is one post the Owner asks for in the chat, from request to published. It needs the Orchestrator, the Asset Analyst (photos and logo), the Brand Strategist (create mode), the Copywriter and the Art Director (image mode). Carousels are Must too ([ADR 0022](../decisions/0022-carousels-in-mvp.md)): the Copywriter and Art Director carousel modes and the Text Checker. The Content Strategist (weekly plan, ideas) and the Feedback Classifier (revisions) are Should. Video mode, Reels, the Catalog and Offers are Could; they stay documented here so the code leaves room for them.

## Agent roster

| Agent | Kind | Called by | Input → Output | Effort |
|---|---|---|---|---|
| **Orchestrator** | Tool-use loop | Inbound handler | Conversation + context → reply text + tool calls | `low` |
| **Asset Analyst** | Single call, vision, structured | `analyze_asset` job | Image, or video keyframes + metadata → description, tags, suggested Products, usable-for (+ Reel suitability) | `low` |
| **Brand Strategist** | Single call, structured | `generate_brand` job | Onboarding data + Catalog + asset descriptions (+ correction) → Brand Brain | `high` |
| **Content Strategist** | Single call, structured | `generate_plan` job; `suggest_ideas` tool | Brand Brain + Catalog + active Offers + assets + recent posts + date + notes → weekly plan (images and Reels), or 3 ideas | `medium` |
| **Copywriter** | Single call, structured | `generate_post` job | Brand Brain + brief + the Owner's own words (+ feedback, previous version) → copy; for a carousel: + slide count → caption + the text of each slide | `medium` |
| **Art Director** | Single call, vision, structured | `generate_post` job | Brand Brain + brief + copy + candidate photos (the ones the Owner sent with the request, if any) + trend notes → image brief (reference photos + image prompt); for a Reel: candidate videos (keyframes) → video + cover frame; for a carousel: → reference photos + shared style + one scene per slide | `medium` |
| **Feedback Classifier** | Single call, structured | `revise_post` job | Feedback text → `copy` / `image` / `both` (Reel: `copy` / `cover` / `video`) + normalized instruction | `low` |
| **Text Checker** | Single call, vision, structured | `CarouselGenerator` (carousel slides) | Slide image + expected `SlideCopy` → `TextCheck` | `low` |

Not agents (deterministic services): **Image generator** (`ImageGenPort`: image brief → variations from the third-party image service, resized to 1080×1350 JPEG, [ADR 0018](../decisions/0018-ai-image-generation-service.md); not used for Reels), **Carousel generator** (`app/carousel/generator.py`: `CarouselCopy` + `CarouselBrief` → slides through the same port, [ADR 0022](../decisions/0022-carousels-in-mvp.md)), **Frame Extractor** (Could; ffmpeg/ffprobe in the backend: video → metadata + keyframes JPEGs), **Publisher** (approved post → provider API, image, carousel or Reel), **Scheduler** (delegated to the provider).

## LLM client conventions

All Claude calls go through `app/llm/client.py`. It's the only module that imports `anthropic`.

- SDK: official `anthropic` Python SDK, `AsyncAnthropic` client. Read the key from `ANTHROPIC_API_KEY`.
- Model: `claude-opus-5-5` for every agent (configurable per agent in `config.py`). Tune **effort** per agent (table above) rather than switching models. Thinking is always on in this model, so don't send `thinking: disabled` or `budget_tokens` (both return 400). Control depth with `output_config={"effort": ...}`.
- **Structured output** for every specialist: Pydantic model → `output_config={"format": {"type": "json_schema", "schema": Model.model_json_schema()}}` (or `client.messages.parse(output_format=Model)`), then `Model.model_validate_json(...)`. Keep schemas simple: objects, strings, ints, enums, lists. Set `additionalProperties: false` and put every field in `required`.
- **Refusal fallback**: enable server-side fallbacks on every call (`betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"` on `client.beta.messages.create`). Always check `stop_reason` (`refusal`, `max_tokens`) before reading content.
- **Prompt caching**: top-level `cache_control={"type": "ephemeral"}`. Order the prompt stable → volatile: system prompt (static) → Brand Brain (per business) → dynamic context. Never put timestamps in the system prompt.
- **Images**: pass by URL (`{"type": "image", "source": {"type": "url", "url": signed_url}}`) using a short-lived signed Supabase URL, or base64 for small files. Resize to max 1568 px on the long side before upload to save tokens.
- **Video** (Could): Claude takes no video or audio input ([research/media-uploads.md](../research/media-uploads.md#what-claude-can-read)). Agents see a video as its ffprobe metadata plus keyframes (JPEG, ≤ 1568 px long edge) extracted by the Frame Extractor, each labeled with its offset in ms. No transcription in the MVP.
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
    logo_asset_id: str | None
    photo_style: str                  # "luz natural, madera, ambientes cálidos"; feeds the image prompt

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

- Priority: photo and logo mode are Must; video mode and Product links are Could.
- Input: `asset_id`, `kind` (`logo` | `photo` | `video`), owner-provided hint (optional, e.g. product name, or the caption the Owner wrote under a photo sent in the chat), the Catalog (product ids + names + descriptions) so it can suggest links.
  - Photo / logo: the image (URL).
  - Video (Could): ffprobe metadata (`duration_ms`, `width`, `height`, fps) + ~6 keyframes from the Frame Extractor (one per scene change, topped up at fixed intervals), each with its `frame_offset_ms`.
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

- Output (video, Could):

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
- Product links (Could, F8.5): every id in `product_ids` is written to `asset_products` with `source = 'analyst'`. Links with `source = 'owner'` (set or removed from the dashboard) always win; the analyst never re-adds a link the Owner removed.
- Derived frames (Could): each `best_frame_offsets_ms` frame is saved as a new `photo` Brand asset with `derived_from_asset_id` = the video and `frame_offset_ms`, then analyzed as a photo, so the Art Director can use it as a reference photo.
- Logo special case: also run a deterministic palette extraction (Pillow quantize to 5 colors, ignore near-white/near-black/transparent) and store both. The web wizard shows the Pillow palette as editable swatches.

### Brand Strategist

**Purpose:** turn onboarding inputs into the Brand Brain. Also handles corrections.

- Priority: create mode is Must; revise mode (corrections, F2.6) and palette proposals (F2.9) are Could.
- Input: business fields, the Catalog (`<catalog>`: in the Must scope, the 1–5 Products from the wizard), questionnaire answers, owner's "3 words", asset analyses (descriptions only, not images), Pillow palette + owner-confirmed colors, optional `previous_brand_brain` + `correction` (revise mode).
- Output: `BrandBrain`.
- Rules in the prompt:
  - Use only facts given by the owner; mark nothing as fact that wasn't provided (no invented awards, years, locations).
  - Owner-confirmed colors win over model guesses.
  - `constraints` must include every "no quiero que..." answer verbatim.
  - In revise mode: change only what the correction implies; keep everything else.
  - `whatsapp_summary` follows the 4-bullet format in conversation-design.md.
  - `featured_products`: up to 5 Products from the Catalog, referenced by id; never a Product that isn't in the Catalog.
  - No logo and no colors (the Owner ticked "Todavía no tengo logo ni colores" in the wizard): use the neutral default palette, and say in `whatsapp_summary` that colors can be chosen later in the chat.
- **Palette proposals (Could, F2.9):** for an Owner without colors, a separate structured call takes one photo the Owner sent (its Pillow palette + `AssetAnalysis`) and returns 3 named palettes (`[{name, colors: [hex × 3]}]`, e.g. "Bosque", "Nogal", "Carbón"). The Owner picks one in the chat, optionally with a tweak ("el marrón un toque más claro"); the result is saved as owner-confirmed colors and a new Brand Brain version. A simple text logo (the business name) was offered after the colors when the backend rendered templates; with generated images ([ADR 0018](../decisions/0018-ai-image-generation-service.md)) how to produce it is open ([open questions](../open-questions.md#post-images-generated-by-ai-adr-0018)). Generating a graphic logo is out of scope.

### Content Strategist

**Purpose:** weekly plan, and ideas on request. Should: the plan is generated only when the Owner asks for it ("armame el plan de la semana"); nothing pushes it after onboarding.

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
  class WeeklyPlan(BaseModel):
      items: list[PlanItem]
      whatsapp_text: str               # numbered list for plan_preview, ≤ 900 chars
  ```

- Rules: rotate pillars, don't repeat a product two posts in a row, promote an active Offer at most once per week unless asked, only reference assets, Products and Offers that exist, respect `constraints`. At most **one Reel** per weekly plan unless the Owner asks for more, and only when a `reel_suitable` video exists (Could); otherwise every item is `image`. Never put a price or discount in `idea` that isn't in a Product or Offer. Commercial dates may be used only when they fall in the plan week and come from the `commercial_dates` list passed in the input (a small static list per country in `app/agents/data/commercial_dates_uy.json`, so the model never guesses dates).
- **Ideas mode (Should, F3.5):** for "no sé qué subir, ¿se te ocurre algo?". Same input without `week_start`/`posts_count`, plus the Owner's request text. Output `PostIdeas = {ideas: list[PostIdea]}` with exactly 3 items; `PostIdea` is a `PlanItem` without `scheduled_for`. Same rules as the plan; each idea must be doable with existing photos (its `suggested_asset_ids` non-empty) or say which photo the Owner should send. Called synchronously by the `suggest_ideas` tool (effort `low`), not as a job.

### Copywriter

**Purpose:** write the caption. Image Posts carry no text ([ADR 0018](../decisions/0018-ai-image-generation-service.md)), so there is no on-image copy; on a carousel the Copywriter also writes the text of each slide, the only text allowed on it ([ADR 0022](../decisions/0022-carousels-in-mvp.md)).

- Input: Brand Brain, brief (plan item or ad-hoc request text), `owner_words` (the Owner's own messages about this post, verbatim: the request, the answer to the bot's question), `format` (`image` | `reel` | `carousel`), `slide_count` (carousel: the Owner's number, or none), the Products and Offer the brief references (from `<catalog>` / `<offers>`), the analyses of the photos the Owner sent with the request (if any), platform (`instagram`), optional `previous` copy + `feedback` (revise mode). For a Reel, also the video's `VideoAnalysis.description` so the caption matches what is on screen.
- Output:

  ```python
  class PostCopy(BaseModel):
      title: str                       # internal title, ≤ 40 chars
      caption: str                     # 150–900 chars, Instagram-ready, line breaks allowed
      cta: str                         # included at the end of the caption too
      hashtags: list[str]              # 5–10, without '#' duplicates, lowercase, no spaces
  ```

- Rules: voice from the Brand Brain; first line must hook (≤ 80 chars); no invented facts (prices, discounts, dates only if in a referenced Product or Offer, or in an ad-hoc brief from the Owner); respect emoji policy; Rioplatense *vos*; never mention AI. Keep the angle and the concrete details the Owner asked for in `owner_words` ("que se luzca la madera", "que se note que es a medida", "sin nombrar al cliente"); the caption's voice still comes from the Brand Brain, not from how the Owner writes in the chat. In revise mode, apply the feedback literally and change as little else as possible.
- Reel variant (Could): same `PostCopy` model, but the caption is shorter (80–400 chars) and its first line is the hook, because Instagram truncates Reel captions early.
- **Carousel mode (Must, F4.9, [ADR 0022](../decisions/0022-carousels-in-mvp.md)):** output `CarouselCopy` (`app/carousel/schemas.py`):

  ```python
  SlideRole = Literal["cover", "content", "cta"]
  class SlideCopy(BaseModel):
      role: SlideRole
      headline: str            # ≤ 6 words
      body: str | None = None  # ≤ 20 words
  class CarouselCopy(BaseModel):          # Copywriter, carousel mode
      caption: str
      hashtags: list[str]
      slides: list[SlideCopy]  # 3–5 by default, the Owner's number up to 10; slides[0].role == "cover"
  ```

  Same voice and fact rules as the caption: a price, discount or date goes on a slide only when it comes from a referenced Product, an Offer or `owner_words`. The slide text is what the image model renders, so it is short and spelled exactly as it should appear.

### Art Director

**Purpose:** decide what the image shows and how it looks. It doesn't draw and doesn't compose: it picks the reference photos and writes the prompt; a third-party image service generates the variations ([ADR 0018](../decisions/0018-ai-image-generation-service.md), provider in [ADR 0019](../decisions/0019-image-provider-gemini.md)).

- Input: Brand Brain (visual identity: palette, `photo_style`; voice; `constraints`), the brief and `owner_words`, `PostCopy` (for the angle; none of it goes on the image), candidate photos (IDs + analyses + **the images themselves**, as URLs), trend notes (optional; their source is not decided, see [open questions](../open-questions.md#post-images-generated-by-ai-adr-0018)), optional feedback + previous brief (revise mode), optional `force_asset_id`.
- Candidates: when the Owner sent photos with the request (`posts.candidate_asset_ids`), those photos are the preferred references; whether the Business's photo library also complements them is not decided ([open questions](../open-questions.md#post-images-generated-by-ai-adr-0018)). With no photos in the request, the best matches from the library (by the brief, `best_for` and `quality`).
- Output (`ImageBrief`):

  ```python
  class ImageBrief(BaseModel):
      reference_asset_ids: list[str]   # 1–10 photos of the real product (Gemini takes up to 10 object references)
      prompt: str                      # English instructions for the image model: scene, composition, light, palette, mood
      style_notes: str                 # short Spanish summary for the Owner and the revision loop
  ```

- **Prompt rules** (in the system prompt, and appended in code to every `prompt` so they can't be dropped):
  - Show the real product from the reference photos; keep its shape, color, material and proportions. Change the scene, light and styling, never the product.
  - **No text of any kind** in the image (image Posts): no headlines, prices, discounts, offers, dates, slogans or watermarks. Prices and offers only appear in the caption, and only when they come from a Product, an Offer or the Owner's words. Carousel slides are the exception: they carry the copy's text and nothing else (see carousel mode below, [ADR 0022](../decisions/0022-carousels-in-mvp.md)).
  - **No logos:** don't draw, invent or alter a logo. Whether the Owner's real logo appears on the image is not decided ([open questions](../open-questions.md#post-images-generated-by-ai-adr-0018)).
  - Use the Brand Brain palette and `photo_style`; respect `constraints` (e.g. "sin mostrar caras").
  - Trend notes may change the scene or styling, never the facts.
- **Post-validation (code):** reference ids belong to the business and are not archived; when the Owner sent photos, they are among the references (interim default: only those photos, until the open question on the library is settled); 1–10 references; the fixed rules are present. On violation, retry once with the error list appended; if it fails again, fall back to the candidate photos with a plain prompt built from the brief and `photo_style`.
- The generated variations are not checked by an LLM before the Owner sees them: the Owner picks one and approves it ([ADR 0007](../decisions/0007-approve-every-post.md)), and nothing is published without that Approval. The one exception is carousel slides, whose rendered text the [Text Checker](#text-checker) compares with the copy ([ADR 0022](../decisions/0022-carousels-in-mvp.md)).
- **Carousel mode (Must, F4.9, [ADR 0022](../decisions/0022-carousels-in-mvp.md)):** input adds the `CarouselCopy`. The Art Director writes the look and the scene of each slide, never its text. Output `CarouselBrief` (`app/carousel/schemas.py`):

  ```python
  class SlideScene(BaseModel):
      index: int               # 1-based
      scene_prompt: str        # English: what this slide shows (scene, composition); no text
  class CarouselBrief(BaseModel):         # Art Director, carousel mode
      reference_asset_ids: list[str]   # 1–10
      style_prompt: str                # English: shared visual system (palette hex, typography, layout grid, text safe area)
      slides: list[SlideScene]         # one per CarouselCopy slide, same order
      style_notes: str                 # short Spanish summary for the Owner
  ```

  Code builds each slide's prompt with `app/carousel/prompts.py:build_slide_prompt(brief, copy, index, *, anchored: bool)`: the shared style, the slide's scene, "render exactly this text and no other text" with that slide's `SlideCopy`, and the fixed rules (keep the product unchanged, no logos, no prices or numbers unless they are in the given text, text inside the central 90%). `anchored` adds that the attached style image (the cover) sets the look. Post-validation adds: one scene per slide, indexes 1..n in order.
- **Reel mode (Could):** input is the copy plus up to 3 candidate videos (each as metadata + its keyframes with offsets + `VideoAnalysis`). No image generation: the video is published as the Owner shot it. Output:

  ```python
  class ReelSpec(BaseModel):
      video_asset_id: str
      cover_offset_ms: int             # one of the keyframe offsets; defaults to VideoAnalysis.cover_offset_ms
  ```

  Post-validation (code): the video belongs to the business, is not archived, is `reel_suitable`, and `0 ≤ cover_offset_ms ≤ duration_ms`. On violation, retry once; then fall back to the first suggested video and its analyzed cover.

### Feedback Classifier

Should (revisions, F4.4).

- Input: feedback text, post `format`, current copy, current image brief summary (`style_notes`, image Posts) or current video + cover summary (Reel).
- Output: `{"target": ..., "instruction": str}` (instruction = normalized, explicit version of the feedback, e.g. "Acortar el caption a 2 líneas y mencionar envío gratis en Montevideo").
  - Image Post: `target` is `copy` | `image` | `both` (`image` regenerates the variations from a revised image brief).
  - Reel (Could): `target` is `copy` | `cover` (pick another frame of the same video) | `video` (swap to another reel-suitable video). We don't edit video, so "cortalo más corto" or "ponele música" maps to `copy` with an instruction that the Orchestrator turns into a short "eso todavía no lo puedo hacer" reply plus an offer to swap the video.

### Text Checker

Must (carousels, F4.9, [ADR 0022](../decisions/0022-carousels-in-mvp.md)). The only LLM check of a generated image.

- Input: one generated slide (1080×1350 JPEG) + the expected `SlideCopy`.
- Output:

  ```python
  class TextCheck(BaseModel):             # Text Checker
      matches: bool
      found: str
      issues: list[str]
  ```

- One structured `claude-opus-5-5` call with effort `low` ([LLM client conventions](#llm-client-conventions)), in `app/agents/text_checker.py`. `matches` is false when a word is missing, misspelled or added, or when other text (a price, a number, a logo) appears. Called by `CarouselGenerator`: a mismatch regenerates that slide once; if it still fails, the slide is kept with its `TextCheck` saved and flagged.

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

- **Voice notes** arrive as their transcript ([integrations.md](integrations.md#speech-to-text)). In the history and the current turn they are prefixed with `[audio]`, and the prompt says a transcript can mishear names, numbers and prices: before using a price, date or quantity heard in a voice note that looks off or ambiguous, confirm it as part of the one allowed question.
- History rebuilt from the DB each turn contains **text only** (no tool or thinking blocks from earlier turns). Within a turn, pass `resp.content` back unchanged (thinking blocks included).
- Tools are defined with `strict: true` and `additionalProperties: false`.
- `tool_choice` stays `auto`. Forced tool choice is not supported on this model.
- If the model returns text **and** a long-running tool, send the text (the acknowledgement) and let the job send the result.

### Conversation rules

From the second design pass ([../design/mockups/](../design/mockups/README.md), rows 1 and 1b). They live in `prompts/system.md`, with the guards in code.

- **Open chat after onboarding (Must, F1.10).** Once the Owner confirms the Brand Brain, the bot sends `ready_open_chat` ("¿En qué te puedo ayudar hoy?") and waits. Nothing proposes or generates a weekly plan unless the Owner asks for one.
- **A post from photos and a request (Must, F4.5).** The Owner sends one or more photos and asks for a post in their own words ("me llegó esta mesa ratona nueva, armame algo para subir"), or only writes the request. Photos the Owner just sent appear in `<recent_photos>`; the model passes them to `create_post` as `asset_ids`.
- **At most one question (Must).** Before `create_post`, ask **one** short question only when the answer changes the result: the angle (novedad, promo, detrás de escena), a price or condition the Owner hasn't given, or what to highlight. Otherwise create right away and say so ("Dale, lo armo con la foto del detalle de la veta ⏳"). Never a second question for the same post; missing details become a neutral choice.
- **Approve and publish by writing (Must, F5.6).** While a post is `pending_approval`, an explicit approval in text maps to the same handlers as the buttons: "subilo", "publicalo", "dale, subila" → `approve_post(next = "publish_now")`. Praise without an instruction ("me encanta", "está lindo") is not approval: the bot asks "¿Lo subo?". An approval with a time ("subilo mañana a la tarde") → `approve_post(next = "schedule", when = ...)` (Should, F5.3); until scheduling exists the bot publishes only on an explicit "ahora". If more than one post is pending, the bot asks which one.
- **Match the Owner's style (Should, F1.9).** Replies mirror how the Owner writes: short and casual when they write two words ("subila" → "arriba ✅"), fuller when they write long messages. `<owner_style>` in the context block gives the hint. Post captions keep the Brand Brain voice regardless.
- **Carousels (Must, F4.9, [ADR 0022](../decisions/0022-carousels-in-mvp.md)).** "Armame un carrusel con estas fotos" → `create_post(format = "carousel", slide_count)`, with `slide_count` only when the Owner gave a number (up to 10). One carousel per request, no Variations. While its preview is pending, "cambiá la 3" or "la portada más clara" → `redo_slides(post_id, slides, feedback)`; approval works as for image Posts.
- **Ideas on request (Should, F3.5).** "¿Se te ocurre algo?" → `suggest_ideas`; the bot lists the 3 ideas as a short numbered message. When the Owner picks one ("la del taller, pero sin mostrar caras"), the model calls `create_post` with that idea as the brief and the Owner's extra instructions in it.

### Tools

| Tool | Priority | Input | Does | Returns |
|---|---|---|---|---|
| `create_post` | Must | `brief: str`, `asset_ids?: list[str]`, `format: "image" \| "carousel" = "image"` (`"reel"` Could), `slide_count: int \| None`, `scheduled_for?: datetime`, `offer_id?: str` | Create post row (`origin = "adhoc"`, `candidate_asset_ids = asset_ids`) + enqueue `generate_post`. `asset_ids` are photos the Owner sent (from `<recent_photos>`); they must belong to the business. `slide_count` only with `format = "carousel"`, at most 10, null lets the agents choose 3–5 ([ADR 0022](../decisions/0022-carousels-in-mvp.md)). `format = "reel"` (Could) requires a reel-suitable video, else returns `{"error": "no_reel_video"}`; `offer_id` is Could | `{post_id, job_id}` |
| `redo_slides` | Must | `post_id`, `slides: list[int]`, `feedback` | Carousel only, while `pending_approval`: enqueue `redo_slides` for those 1-based slides ([ADR 0022](../decisions/0022-carousels-in-mvp.md)) | `{job_id}` |
| `pick_variation` | Must | `post_id`, `n: int` | Choose variation `n` of the current revision: copy its image to the Post, clear `awaiting`, send `post_preview`. Only while the post is `pending_approval` with no variation picked | `{status}` |
| `approve_post` | Must | `post_id`, `next?: "ask" \| "publish_now" \| "schedule"`, `when?: datetime` | Same handler as the `[Aprobar]` button. `next = "ask"` (default) sends `publish_when`; `"publish_now"` approves and enqueues `publish_post(now)` in one step ("subilo"); `"schedule"` (Should) approves and schedules at `when` | `{status, job_id?}` |
| `publish_post` | Must (`now`), Should (datetime) | `post_id`, `when: "now" \| ISO datetime` | Guard: status must be `approved`; enqueue `publish_post` | `{job_id}` or error |
| `discard_post` | Must | `post_id` | Status → `discarded` | `{status}` |
| `list_posts` | Must | `statuses?: list[str]`, `limit?: int` | Query posts ("¿cuándo sale lo de la mesa ratona?") | `[{id, title, status, scheduled_for, permalink}]` |
| `get_brand_summary` | Must | — | Read latest Brand Brain (+ active Offers, Could) | `{whatsapp_summary, pillars, featured_products, offers, constraints}` |
| `cancel_pending` | Must | — | Clear `conversation_state.awaiting` | `{ok}` |
| `revise_post` | Should | `post_id`, `feedback` | Enqueue `revise_post` | `{job_id}` |
| `plan_week` | Should | `notes?: str`, `week_start?: date` | Enqueue `generate_plan`, only when the Owner asks for a plan | `{job_id, status: "started"}` |
| `suggest_ideas` | Should | `request: str` | Content Strategist ideas mode (synchronous); stores the 3 ideas in `conversation_state.ideas` so "la 2" or "la del taller" can be resolved | `{ideas: [{n, title, idea, suggested_asset_ids}]}` |
| `send_dashboard_link` | Should | — | Create a `dashboard` magic link (7 days) and send it as a CTA URL button ("Abrí tu panel") | `{sent: true}` |
| `revise_plan` | Could | `plan_id`, `feedback` | Enqueue `generate_plan` (revise mode) | `{job_id}` |
| `update_brand_brain` | Could | `change: str` | Enqueue `generate_brand` revise mode (silent: no summary message unless asked) | `{job_id}` |
| `propose_palettes` | Could | `asset_id` | Palette proposals from one photo (F2.9, see [Brand Strategist](#brand-strategist)); the bot shows them as numbered swatches | `{palettes: [{name, colors}]}` |
| `save_brand_colors` | Could | `colors: list[str]`, `confirmed: bool` | Save owner-confirmed colors and create a new Brand Brain version (same confirm rule as `save_product`) | `{saved}` |
| `list_catalog` | Could | `query?: str` | Search active Products by name/category | `[{id, name, price, category}]` |
| `save_product` | Could | `product_id?: str`, `name`, `description?`, `price?`, `category?`, `confirmed: bool` | Create or update a Product. With `confirmed = false` it only returns the preview; the model must read it back to the Owner ("¿Lo guardo así?") and call again with `confirmed = true` after an explicit yes | `{product, saved}` |
| `save_offer` | Could | `offer_id?: str`, `kind: "pack" \| "promo"`, `title`, `conditions`, `price?`, `starts_on?`, `ends_on?`, `product_ids?`, `confirmed: bool` | Create or update an Offer. `confirmed = false` saves it as `draft` and returns the preview; `confirmed = true` (after the Owner's explicit yes) sets `status = 'active'`. Prices and conditions come only from the Owner's words | `{offer, status}` |

Tools that are not built yet are not registered, so the model can't call them; the system prompt only describes registered tools.

Guards are in the tool implementations, not in the prompt: `publish_post` returns `{"error": "post_not_approved"}` if the status is wrong, and the model must relay that. `approve_post` called from free text (not a button) is accepted only when the Owner's last message is an explicit approval of that post ([ADR 0007](../decisions/0007-approve-every-post.md)): the inbound handler marks the turn with `explicit_approval = true` when the message matches an approval phrase ("subilo", "publicalo", "dale, subila", "aprobado") and only one post is `pending_approval`, or the Owner named which one; otherwise the tool returns `{"error": "approval_not_explicit"}` and the bot asks. An image Post with several variations and none picked yet can't be approved: `approve_post` returns `{"error": "variation_not_picked"}` and the bot asks which one. `save_product`, `save_offer` and `save_brand_colors` never persist active data without `confirmed = true`, and the inbound handler rejects `confirmed = true` unless the Owner's last message is an explicit yes (button reply or affirmative text).

**Photos sent with a request.** WhatsApp delivers each photo as its own message, with the caption (if any) on one of them. The inbound handler stores each photo as a Brand asset (`source = 'whatsapp'`), enqueues `analyze_asset`, and waits a short debounce (5 s after the last photo) before deciding: if any photo has a caption, or a text or a voice note (its transcript) arrives within the debounce, one orchestrator turn runs with all those photos in `<recent_photos>`; if not, the bot sends `photo_saved` once for the batch with its `[Sí, armalo]` button (Flow 9). `generate_post` waits up to 30 s for the candidate photos' `analyze_asset` jobs, then proceeds with whatever analyses exist (the Art Director sees the images anyway).

**Picking a variation.** When `generate_post` produced more than one variation, the post waits in `pending_approval` with `awaiting = variation_choice`; the Owner's pick (a button or a reply such as "la 2") goes to `pick_variation(post_id, n)`, which copies that variation to the Post and sends `post_preview`. Approval applies to the picked variation only. How the Owner picks, and how many variations there are, is not decided ([open questions](../open-questions.md#post-images-generated-by-ai-adr-0018); draft copy in [conversation-design.md](../product/conversation-design.md)).

### Context block (dynamic, after the cache breakpoint)

```text
<now>2026-10-20T14:32:00-03:00 (lunes)</now>
<awaiting>post_feedback for post 7f3c… ("Mesa Nórdica")</awaiting>
<pending_posts>
- 7f3c… "Mesa Nórdica" — pending_approval — mar 21 19:00
- 1a9e… "Promo sillas" — approved — sin fecha
</pending_posts>
<instagram_connected>true</instagram_connected>
<recent_photos>
- a91c… sent 16:20, caption "me llegó esta mesa ratona nueva 😍 armame algo para subir" — "Mesa ratona de roble, vista de frente"
- a92d… sent 16:20 — "Detalle de la veta de la madera"
</recent_photos>
<owner_style>short (last 5 messages: median 6 words, casual)</owner_style>
<catalog_size>products: 23 · photos: 64 · videos: 7 (reel-suitable: 4)</catalog_size>
<active_offers>
- 5c21… promo "15% en sillas" — hasta dom 26
</active_offers>
<unannounced_results>
- 3b7d… "Taller por dentro" — published — https://www.instagram.com/p/…
</unannounced_results>
```

`<recent_photos>` lists photos the Owner sent in the last 30 minutes that no post uses yet, with their caption and the Asset Analyst's description once it exists ("analizando…" before). `<owner_style>` (Should, F1.9) is computed in code from the Owner's last 5 messages. `<catalog_size>` and `<active_offers>` appear only once the Could Catalog and Offer features exist.

`<unannounced_results>` lists scheduled posts whose `published` / `publish_failed` notification WhatsApp rejected (outside the 24-hour window, see [integrations.md](integrations.md#receiving)). The orchestrator mentions them in its next reply; the inbound handler then clears them.

## Job pipelines

| Job | Priority | Steps | Sends to owner |
|---|---|---|---|
| `analyze_asset(asset_id)` | Must (photo, logo), Could (video) | Photo/logo: Asset Analyst → save analysis (+ Pillow palette for logos) → (Could) write analyst `asset_products`. Video: Frame Extractor (ffprobe + keyframes) → Asset Analyst (video mode) → save `VideoAnalysis`, `duration_ms`, `width`, `height` → write analyst `asset_products` → save best frames as derived photo assets and enqueue `analyze_asset` for each | nothing (WhatsApp photos without a request: `photo_saved`, sent by the inbound handler after the debounce) |
| `generate_brand(business_id, correction?)` | Must (create), Could (correction) | wait for pending `analyze_asset` → Brand Strategist → save new version | `brand_summary` (onboarding/correction) |
| `generate_post(post_id)` | Must (image, carousel), Could (Reel) | Image: wait for the candidate photos' analyses (≤ 30 s) → Copywriter → Art Director → validate → Image generator (the variations in parallel) → resize to 1080×1350 → upload → save `post_variations`. Carousel (`posts.format = 'carousel'`): wait for the photo analyses → Copywriter (carousel mode) → Art Director (carousel mode) → validate → `CarouselGenerator.generate` (cover first, the rest in parallel anchored on it, each text-checked) → upload → save `post_slides`. Reel: Copywriter (Reel variant) → Art Director (Reel mode) → validate → save `video_asset_id` + `cover_offset_ms` + cover JPEG (the keyframe at that offset) | several variations: `post_variations` (each image, numbered), then `post_preview` once the Owner picks; one variation: `post_preview` directly; Reel: `reel_preview` (video header when the preview transcode fits WhatsApp's 16 MB) or `reel_preview_link` (cover + dashboard link), see [integrations.md](integrations.md); carousel: the slides in order, captioned "1/5", "2/5"…, then `carousel_preview` |
| `publish_post(post_id, when)` | Must (now), Should (scheduled) | guard → Publisher (now / schedule; image, carousel or Reel by `posts.format`) → save external id + permalink | `published` / `scheduled` / `publish_failed` |
| `redo_slides(post_id, slides, feedback)` | Must (carousel) | (Copywriter, when the feedback changes the words of those slides) → Art Director (carousel mode, new scenes for those slides) → `CarouselGenerator.redo` (a redone slide anchors on the current cover; a redone cover anchors on slide 2) → upload → bump `posts.revision`, save the new rows and copy the unchanged ones to the new revision | the redone slides, numbered, then `carousel_preview` |
| `generate_plan(business_id, notes?, plan_id?)` | Should | Content Strategist → save plan + items | `plan_preview` |
| `revise_post(post_id, feedback)` | Should | Feedback Classifier → (Copywriter) → (Art Director → Image generator, image only) → save revision | `post_preview`, or `post_variations` first when the image was regenerated |
| `import_instagram_media(business_id)` | Could (F2.8) | List the connected account's recent media ([integrations.md](integrations.md#reading-the-owners-existing-instagram-media-could)) → download the images the Owner kept → store as Brand assets (`source = 'instagram'`) → enqueue `analyze_asset` for each | nothing (the wizard shows progress) |

Posts from an approved plan are generated **sequentially** in plan order, so previews arrive in order and we stay under rate limits.

## Quality checks (cheap, deterministic)

Run after every agent call, before saving:

- Caption length 150–900 chars for images, 80–400 for Reels; hashtags 5–10, no duplicates.
- Carousels: 3–10 slides (the Owner's number when given), `slides[0].role == "cover"`, headline ≤ 6 words, body ≤ 20 words; the price/discount rule below applies to slide text too.
- No phrase from `constraints` appears in the caption (case-insensitive substring).
- No price/discount numbers in copy unless they appear in a referenced Product or active Offer, or in the Owner's own ad-hoc brief (regex for `%`, `$`, `USD`, `UYU`).
- Referenced asset, Product and Offer IDs belong to the business and are not archived; a Reel's video is `reel_suitable`.

On failure: one retry with the violations listed; then accept and log a warning (demo shouldn't block).
