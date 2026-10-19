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

- A **Niche Report** per niche, shared by every Business in it (amended 2026-10-19, was per Business, see [Amendment](#amendment-2026-10-19-one-report-per-niche)): a short structured summary of what is working in the niche this week (themes, formats, hooks, visual cues), each point with its source links.
- Written by a new Specialist, the **Niche Analyst**, on **Gemini** (`GEMINI_CHAT_MODEL`, Interactions API) with the `url_context` and `google_search` tools, through `backend/app/llm/client.py` like every other agent ([ADR 0023](0023-gemini-text-llm.md)). Input: the niche's description, location, reference websites and search themes (a static list per niche, starting with [research/furniture-decor-uruguay.md](../research/furniture-decor-uruguay.md)). Amended 2026-10-19: the Business's `category`, location and Brand Brain and the Owner's reference websites are no longer input.
- Runs **weekly** in the in-process job runner ([ADR 0005](0005-single-instance-in-process-jobs.md)) and on demand when the Owner asks ("¿qué está funcionando en mi rubro?"). The weekly run is silent: the Owner sees the report only when they ask, since messages outside the 24-hour window are Won't in the MVP (F1.8).
- The latest report is the **trend notes** input of the agents that make content: Content Strategist, Copywriter and Art Director (the Art Director turns its visual cues into the image and carousel prompts).
- Priority **Should** in [mvp.md](../product/mvp.md) (F3.6, F3.7): the demo of [ADR 0016](0016-demo-scope-one-post.md) does not depend on it.

## Consequences

- One provider and one key stay ([ADR 0023](0023-gemini-text-llm.md)). Google Search grounding needs billing on the key (already required there).
- Trend notes may change the angle, format and styling of a Post, never its facts: prices, discounts, dates and claims still come only from the Brand Brain, the Catalog, Offers and the Owner's words. Commercial dates come from the static list the Content Strategist already uses.
- Other stores' websites are read to learn what works, never copied: no reuse of their photos, product names or copy.
- Cost: one call per niche per week (amended 2026-10-19, was per Business), plus on-demand calls; each call can run several billed searches, and the reference websites count as input tokens. A failing call is retried at most once a week, so a 429 can't loop on billed searches.
- Reference websites the Owner names are not part of the report (amended 2026-10-19): a report shared by a niche can't follow one Owner's list. The wizard doesn't ask for them anyway (`onboarding/schemas.py` has no such field); using them would take a separate per-Business step.
- The report reflects what websites and the web show, not measured engagement.
- How good the report is for a Uruguayan niche in Spanish is not verified yet; a hands-on run comes before building.

## Amendment (2026-10-19): one report per niche

What works in a niche is the same for every Business in it, so the report is written once per niche and week instead of once per Business. Each Business's angle still comes from its own Brand Brain, which the agents that read the trend notes (the `PostDrafter`, the orchestrator) already have. The analyst's input is only the niche, its `post_idea` is an idea for any business in the niche, and the cost no longer grows with the number of Businesses. Recorded in the Decision and Consequences above; the first schema design, one row per Business, was never migrated.

## As built (2026-10-19)

- **Postgres table `niche_reports`** (migration `0004`): `niche_id` (a key of `app/agents/data/niches.py`, plain text since niches live in code), `week_start` (Monday in the niche's timezone, a field of the niche), `report` (`NicheReport` JSON), unique on `(niche_id, week_start)`. The `generate_niche_report` job (`app/jobs/niche.py`) upserts the week's row, so a retry never hits the unique key. Its `jobs` row has no Business (`business_id` is null) and carries `{"niche_id": ...}` in its payload: a report belongs to no single Business.
- **Catch-up scheduler, not a cron:** the job runner runs a check when it starts and then every 15 minutes (`PeriodicCheck` in `app/jobs/runner.py`). It queues the job for each niche with at least one `active` Business (onboarding finished: the Owner confirmed the brand) and no report for the current week. A deploy therefore writes the week's report at once, and a missed Monday is caught up. Single instance, as [ADR 0005](0005-single-instance-in-process-jobs.md) requires.
- **Attempt cap:** at most 2 `generate_niche_report` jobs per niche per week (counted from Monday 00:00 in the niche's timezone), failed ones included, and none while one is queued, running or done. A job interrupted by a restart counts as a failed attempt.
- **Default niche:** nothing records a Business's niche yet (no wizard field, no classifier), so `niche_of` maps every Business to `curated-wood-furniture-uy`, the MVP's vertical ([mvp.md](../product/mvp.md)).
- **Readers:** the `PostDrafter` and the orchestrator's context read the latest report of the Business's niche on every post and every turn, as an escaped `<trend_notes>` block (`app.prompts.tagged`), since the notes come from web pages. A database failure leaves them out rather than failing the post. `NICHE_REPORT_PATH` (a report saved by `app/agents/niche_cli.py`) is only read when there is no database.
- **Not built:** the on-demand `niche_report` tool and any Owner message.
