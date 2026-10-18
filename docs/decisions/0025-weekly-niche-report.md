# 0025: Weekly Niche Report written by Claude

- Date: 2026-10-18
- Status: proposed

## Context

Posts are written from the Brand Brain and the Owner's brief only. Nothing tells the Agency what is working in the Owner's niche right now, and the Art Director's **trend notes** input has had no source ([open questions](../open-questions.md#post-images-generated-by-ai-adr-0018)). The team wants a weekly analysis of the niche (what works, which formats and angles, what to talk about) that feeds post and carousel generation, starting with curated solid-wood furniture and home stores in Uruguay (like La Ibérica), the MVP's vertical ([mvp.md](../product/mvp.md)).

The team wants **Claude** to do the analysis and hand the result to the Gemini agents that write and generate posts and carousels ([ADR 0023](0023-gemini-text-llm.md), [ADR 0019](0019-image-provider-gemini.md)); Gemini itself doesn't search. Reference **websites** of stores in the niche are the main input; Instagram accounts are not needed. Sources compared in [research/niche-trend-sources.md](../research/niche-trend-sources.md):

- **Claude with the web search and web fetch server tools**: web search costs US$10 per 1,000 searches plus tokens; web fetch has no extra charge beyond tokens and only fetches URLs already in the conversation, so the reference websites go in the prompt ([Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing), read 2026-10-18).
- **Gemini with Grounding with Google Search**: same job, but the team wants Claude doing the analysis.
- **Instagram Business Discovery, Hashtag Search, scrapers**: not needed (no Instagram input); scrapers break Instagram's terms anyway.

## Decision

- A **Niche Report** per Business: a short structured summary of what is working in its niche this week (themes, formats, hooks, visual cues), each point with its source links.
- Written by a new Specialist, the **Niche Analyst**, running on **Claude** (`claude-opus-5-5`, Anthropic Python SDK) with the `web_search_20260209` and `web_fetch_20260209` server tools and structured output. Input: the Business's `category`, location and Brand Brain, the niche's reference websites and search themes (a static list per niche, starting with [research/furniture-decor-uruguay.md](../research/furniture-decor-uruguay.md)), plus reference websites the Owner names.
- The call goes through `backend/app/llm/` in its own adapter next to `GeminiChat`; every other agent stays on Gemini ([ADR 0023](0023-gemini-text-llm.md)).
- Runs **weekly** in the in-process job runner ([ADR 0005](0005-single-instance-in-process-jobs.md)) and on demand when the Owner asks ("¿qué está funcionando en mi rubro?"). The weekly run is silent: the Owner sees the report only when they ask, since messages outside the 24-hour window are Won't in the MVP (F1.8).
- The latest report is the **trend notes** input of the Gemini agents that make content: Content Strategist, Copywriter and Art Director (the Art Director turns its visual cues into the image and carousel prompts).
- Priority **Should** in [mvp.md](../product/mvp.md) (F3.6, F3.7): the demo of [ADR 0016](0016-demo-scope-one-post.md) does not depend on it.

## Consequences

- Two LLM providers again: `ANTHROPIC_API_KEY` joins `GEMINI_API_KEY`, and [ADR 0023](0023-gemini-text-llm.md)'s "one provider, one key, one bill" holds for every agent but this one.
- Trend notes may change the angle, format and styling of a Post, never its facts: prices, discounts, dates and claims still come only from the Brand Brain, the Catalog, Offers and the Owner's words. Commercial dates come from the static list the Content Strategist already uses.
- Other stores' websites are read to learn what works, never copied: no reuse of their photos, product names or copy.
- Cost: one call per Business per week, plus on-demand calls; each call can run several billed searches (cap them with `max_uses`), and fetched pages count as input tokens (cap with `max_content_tokens`).
- The report reflects what websites and the web show, not measured engagement.
- How good the report is for a Uruguayan niche in Spanish is not verified yet; a hands-on run comes before building.
