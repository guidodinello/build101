# Why the WhatsApp assistant feels unintelligent

Investigation of the orchestrator (the assistant the Owner talks to on WhatsApp): why it forgets what the Owner said and misreads what they want, and what to change. Read from the code at `fea71be` on 2026-10-18; every claim cites the file and line it comes from.

**Status**: every recommendation below is implemented; decision in [ADR 0030](../decisions/0030-orchestrator-memory-and-context.md). Line numbers refer to the code before that change. Two items landed differently: posts and their images still live in memory (they need T17/T19), and the onboarding gate's messages stay out of the history because the Business block carries what they collected.

## Summary

The model is not the main bottleneck; the context we give it is. The orchestrator runs `gemini-3.8-flash` at thinking level `low` ([config.py:35](../../backend/app/config.py), [chat.py:368](../../backend/app/conversation/chat.py)) with:

1. a system prompt full of rules but with **nothing about the business** (no Brand Brain, no products, no name);
2. a **40-step in-memory history** that is cut without a summary and **wiped on every deploy or restart**;
3. **keyword code that overrides the model's understanding**: "sí" or "dale" after "¿Lo subo?" is refused;
4. a post pipeline where the copywriter sees **only a one-line brief**, so a change request ("más corto") rebuilds the post from scratch instead of editing it.

Most of this is the gap between the v0 slice and the design in [architecture/agents.md § Orchestrator](../architecture/agents.md#orchestrator), which planned a brand block, a `<now>`/`<pending_posts>` context block, `get_brand_summary`, `list_posts`, `revise_post` and history in the `messages` table. None of these is built yet.

## Findings

### 1. The orchestrator doesn't know the business

- The system prompt is the static rules with only `{assistant_name}` filled in ([chat.py:65-67](../../backend/app/conversation/chat.py), [orchestrator.md](../../backend/app/conversation/prompts/orchestrator.md)).
- The Brand Brain (voice, audiences, pillars, featured products, constraints, CTAs, promo) reaches only the post drafter ([drafts.py:112-121](../../backend/app/posts/drafts.py)). The orchestrator never sees it, nor the Business row (name, Owner name, location, one-liner) nor the Catalog.
- Effects: ideas are generic instead of coming from the pillars; it can't answer "¿qué productos tengo cargados?" or "¿qué te dije de mi marca?"; it doesn't know the current promo; it can't tell that a request contradicts a constraint the Owner gave in onboarding.
- Out-of-band messages are also invisible to it: the onboarding welcome and link ([onboarding.py](../../backend/app/conversation/onboarding.py)) and the brand summary ([jobs/brand.py:82-86](../../backend/app/jobs/brand.py)) go straight to the channel, never into the history. If the Owner replies to the summary in text instead of a button, the model doesn't know what they are replying to.

### 2. Memory is short, lossy and volatile

| Problem | Evidence | Effect on the Owner |
|---|---|---|
| History lives in process memory | `InMemoryHistory` ([history.py:9-10](../../backend/app/conversation/history.py)); ADR 0005 runs one container | Every Railway deploy or crash erases every conversation, the pending posts ([store.py](../../backend/app/posts/store.py)) and the photos |
| 40 steps, counted in steps, not tokens | [history.py:6](../../backend/app/conversation/history.py) | A plain exchange is about 3 steps (user, thought, reply); a post request with a tool call about 6; each event note (post sent, published...) about 3. One full post cycle (ask → ideas → pick → sent → approve → published) takes about 20 steps, so the model remembers roughly the last one or two posts |
| Hard cut, no summary | `del history[: -self._max_steps]` ([history.py:27](../../backend/app/conversation/history.py)) | What the Owner said 15 minutes ago ("no pongas precios", "abrimos los sábados") is gone, silently |
| No durable Owner facts | Only the "Corregir algo" button path changes the Brand Brain ([brand.py:37-50](../../backend/app/conversation/brand.py)) | Preferences stated in chat never persist anywhere, and never reach the drafter unless the orchestrator copies them into the brief |
| Photos are seen once, then only as ids | Images ride only on the current step for unseen photos ([chat.py:253-256](../../backend/app/conversation/chat.py)); the stored step is the plain text ([chat.py:250, 271](../../backend/app/conversation/chat.py)) | Next turn the model knows "f2 sent 14:02", not what f2 shows. "La de la veta" works only if its own earlier reply happened to describe it |
| WhatsApp photos expire after 30 minutes | `RECENT_FOR` ([photos.py:10](../../backend/app/conversation/photos.py)) | "Usá la foto de la mesa que te mandé hoy" gets "mandámela de nuevo" |
| The `messages` table exists but is unused | [0001_initial.sql](../../backend/migrations/versions/0001_initial.sql) `create table messages` | The planned persistence (T02/T19) never landed |

Gemini Flash has a very large context window ([gemini-api.md](gemini-api.md)), so 40 steps is far more conservative than cost or limits require.

### 3. Keyword code overrides the model's understanding

Approval is decided in code, not by the model ([approval.py](../../backend/app/conversation/approval.py), ADR 0007). Probing `classify()` on 2026-10-18:

| Owner says | Result |
|---|---|
| "perfecto, subilo", "sí, publicalo", "publícalo ya" | approve |
| "sí", "dale", "dale!", "ok", "si dale", "sí, ahora", "mandale", "metele", "listo, andá nomás", "buenísimo, dale para adelante" | **none** |

The prompt tells the bot to ask "¿Lo subo?" ([publishing.md](../../backend/app/conversation/prompts/publishing.md)). The natural answer, "Sí" or "Dale", is then refused with `approval_not_explicit`, and the same prompt tells the bot to ask "¿Lo subo?" again: a loop. This is likely the most visible "it doesn't understand me" moment. A "sí" to "¿Lo subo?" is an explicit approval in the sense of ADR 0007.

Two more code rules misread intent:

- **Unused photos block approval.** `has_photos = attached or bool(self._photos.recent(sender))` ([chat.py:431](../../backend/app/conversation/chat.py), [approval.py:102](../../backend/app/conversation/approval.py)). If the Owner sent 3 photos and the post used 2, "subilo" is refused for the next 30 minutes.
- **The brand correction swallows the next message.** After "Corregir algo", whatever comes next is taken as the correction ([brand.py:37-50](../../backend/app/conversation/brand.py), [chat.py:141](../../backend/app/conversation/chat.py)), even "¿qué querés que cambie?" or a photo request.

### 4. Change requests rebuild instead of edit

- A change is `create_post(replaces=...)` with a new brief ([making_posts.md](../../backend/app/conversation/prompts/making_posts.md)). The drafter receives only the brief, the photos, the trend notes and the Brand Brain ([drafts.py:55-104](../../backend/app/posts/drafts.py)): never the previous caption, headlines or `style_prompt`, although the `Post` keeps the brief ([store.py:43-47](../../backend/app/posts/store.py)).
- So "más corto", "cambiale solo el título" or "el mismo pero sin emojis" produce a new post with new copy and a new design. To the Owner it looks like the bot ignored the request.

### 5. The orchestrator-to-drafter handoff is a single free-text brief

All the Owner's intent has to survive the orchestrator's paraphrase in `brief` ([tools.py:18-24](../../backend/app/conversation/tools.py)). Preferences from earlier turns, the chosen idea's exact wording and details from a voice note get lost when the model summarizes. The drafter can't ask back.

### 6. Little reasoning budget and a rules-only prompt

- **Thinking `low`** for the agent that has to resolve references ("la otra", "la de antes"), pick photos and decide between chat and an expensive generation ([chat.py:368](../../backend/app/conversation/chat.py)). Event turns are trivial; Owner turns are not.
- **No date or time.** The planned `<now>` is missing ([chat.py:510-526](../../backend/app/conversation/chat.py) builds only photos, brand photos and logo), so "para el finde", "algo para el Día de la Madre" or "hoy" can't be grounded.
- **Prompt shape.** About 60 lines of rules for events, errors and edge cases; nothing on understanding the Owner: tracking what they want across turns, resolving references, not re-asking what was already answered. "Never a second question for the same post" pushes the model to guess when the first answer was unclear.
- **Two tools only** ([tools.py:99](../../backend/app/conversation/tools.py)). It can't look up posts, the brand or ideas, or save anything it learns, so outside "make a post" and "publish it" it improvises or refuses ("you only help with marketing", [orchestrator.md:3](../../backend/app/conversation/prompts/orchestrator.md)).

### 7. No way to measure it

The tests run on fakes; there is no multi-turn evaluation against the real model. The logs record tool calls and their results ([chat.py:444, 455](../../backend/app/conversation/chat.py)) but not what the bot answered, so a bad conversation can't be reviewed after the fact.

## Recommendations

Ordered by impact over effort. P0 is a day of work and fixes most of what an Owner notices.

### P0: quick wins

1. **Contextual approval.** In `decide()`, an affirmative reply ("sí", "dale", "ok", "de una", "mandale", "👍") approves when exactly one post is approvable and the bot's last message asked to publish it (or the post was just sent). Keep it decided in code, as ADR 0007 requires. Block on photos only when they came with this message, not because some recent photo is unused.
2. **A brand block in the system prompt**: Business name, Owner name, one-liner, location, the Brand Brain (voice, audiences, pillars, featured products, constraints, CTAs, promo) and the brand photos list. It is stable per Business, so it keeps the prefix cacheable. Reuse `BrandBrains.latest` ([library.py:110-125](../../backend/app/conversation/library.py)).
3. **`<now>`** in the context block (date, weekday, time in America/Montevideo).
4. **Edit, don't rebuild.** When `replaces` is set, pass the old post's brief, caption, headlines and `style_prompt` to the drafter with "change only what the Owner asked; keep everything else". Keep the old post's photos and style unless told otherwise.
5. **Thinking `medium` for Owner turns**, `low` for event turns. Check latency against the 20 s keep-alive ([chat.py:61](../../backend/app/conversation/chat.py)).
6. **Log the reply text** (redacted, like the tool logs), so real conversations can be reviewed.
7. **Out-of-band messages as notes**: put the brand summary and the onboarding messages into the history as `[...]` notes, as ADR 0026 does for events.

### P1: real memory

1. **Persist the history** (T19): store the turn's steps, thought steps included, per Business in Postgres, so a deploy no longer erases conversations, posts or photos.
2. **Budget by tokens and summarize instead of cutting.** Raise the window to a token budget (tens of thousands of tokens is cheap on Flash with implicit caching). When the oldest turns must go, fold them into a stored `<conversation_summary>` with one structured call instead of dropping them.
3. **Owner memory.** A `remember` tool (or a post-turn extractor) that saves durable facts and preferences ("no poner precios", "prefiere carruseles", "abre sábados 9 a 13") per Business, injected in the brand block and passed to the drafter. Changes to the brand itself go through the Brand Strategist's revise mode (the planned `update_brand_brain`).
4. **Describe WhatsApp photos once and keep them.** Run the Asset Analyst on chat photos (as planned in agents.md) and list descriptions in `<recent_photos>`: "f2: detalle de la veta, roble". Store them as Brand assets so they outlive the 30-minute window.

### P2: understanding and capabilities

1. **Prompt rewrite**: a short section on understanding the Owner (keep track of what they asked across turns, resolve "la otra" or "como el anterior", never re-ask what was answered, restate your understanding before an expensive generation when unsure). Relax "never a second question" to "ask the minimum; never ask again what the Owner already answered".
2. **The planned tools**: `get_brand_summary`, `list_posts`, `suggest_ideas` (Content Strategist), `revise_post` (Feedback Classifier), `update_brand_brain`.
3. **Conversation evals**: scripted multi-turn scenarios run against the real model and judged by an LLM, kept as a backend test suite. For example: a preference given in turn 2 is respected by the caption in turn 12; "¿Lo subo?" → "Sí" publishes; "más corto" keeps the design and shortens the caption; the conversation survives a restart. Then compare the model and thinking level on numbers instead of impressions (for example Flash at `medium` against a Pro model).

## Decisions this needs

- Persisted history and Owner memory are hard to reverse and change the data model: they deserve an ADR (see [ADR-FORMAT.md](../../.claude/skills/domain-modeling/ADR-FORMAT.md)).
- Contextual approval changes how ADR 0007 is applied: worth a line in that ADR or a new one.
