# 0025: Weekly Niche Report from the niche's websites and Google Search

- Date: 2026-10-18
- Status: proposed

## Context

Posts are written from the Brand Brain and the Owner's brief only. Nothing tells the Agency what is working in the Owner's niche right now, and the Art Director's **trend notes** input has had no source ([open questions](../open-questions.md#post-images-generated-by-ai-adr-0018)). The team wants a weekly analysis of the niche (what works, which formats and angles, what to talk about) that feeds post and carousel generation, starting with curated solid-wood furniture and home stores in Uruguay (like La Ibérica), the MVP's vertical ([mvp.md](../product/mvp.md)).

The analysis hands its result to the Gemini agents that write and generate posts and carousels ([ADR 0023](0023-gemini-text-llm.md), [ADR 0019](0019-image-provider-gemini.md)). Reference **websites** of stores in the niche are the main input; Instagram accounts are not needed. Sources compared in [research/niche-trend-sources.md](../research/niche-trend-sources.md):

- **Gemini with the URL context and Google Search tools**: the same model and key as the other agents. URL context reads up to 20 public URLs per request, billed as input tokens ([URL context docs](https://ai.google.dev/gemini-api/docs/url-context), updated 2026-10-13); Google Search grounding for Gemini 3+ gives 5,000 free search requests per month, then US$14 per 1,000, and is not on the free tier ([Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), updated 2026-10-16).
- **Claude with web search and web fetch**: same job (US$10 per 1,000 searches), but it adds a second LLM provider and key for one agent.
- **Instagram Business Discovery, Hashtag Search, scrapers**: not needed (no Instagram input); scrapers break Instagram's terms anyway.

## Decision

- A **Niche Report** per Business: a short structured summary of what is working in its niche this week (themes, formats, hooks, visual cues), each point with its source links.
- Written by a new Specialist, the **Niche Analyst**, on **Gemini** (`GEMINI_CHAT_MODEL`, Interactions API) with the `url_context` and `google_search` tools, through `backend/app/llm/client.py` like every other agent ([ADR 0023](0023-gemini-text-llm.md)). Input: the Business's `category`, location and Brand Brain, the niche's reference websites and search themes (a static list per niche, starting with [research/furniture-decor-uruguay.md](../research/furniture-decor-uruguay.md)), plus reference websites the Owner names.
- Runs **weekly** in the in-process job runner ([ADR 0005](0005-single-instance-in-process-jobs.md)) and on demand when the Owner asks ("¿qué está funcionando en mi rubro?"). The weekly run is silent: the Owner sees the report only when they ask, since messages outside the 24-hour window are Won't in the MVP (F1.8).
- The latest report is the **trend notes** input of the agents that make content: Content Strategist, Copywriter and Art Director (the Art Director turns its visual cues into the image and carousel prompts).
- Priority **Should** in [mvp.md](../product/mvp.md) (F3.6, F3.7): the demo of [ADR 0016](0016-demo-scope-one-post.md) does not depend on it.

## Consequences

- One provider and one key stay ([ADR 0023](0023-gemini-text-llm.md)). Google Search grounding needs billing on the key (already required there).
- Trend notes may change the angle, format and styling of a Post, never its facts: prices, discounts, dates and claims still come only from the Brand Brain, the Catalog, Offers and the Owner's words. Commercial dates come from the static list the Content Strategist already uses.
- Other stores' websites are read to learn what works, never copied: no reuse of their photos, product names or copy.
- Cost: one call per Business per week, plus on-demand calls; each call can run several billed searches, and the reference websites count as input tokens.
- The report reflects what websites and the web show, not measured engagement.
- How good the report is for a Uruguayan niche in Spanish is not verified yet; a hands-on run comes before building.
