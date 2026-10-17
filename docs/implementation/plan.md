# Implementation plan (24h hackathon, 2 builders)

## Strategy

1. **Deploy on hour 1, not hour 20.** A "hello world" backend on Tenki and frontend on Vercel, with the WhatsApp webhook verified, before writing features. Deploy issues are the #1 hackathon killer.
2. **Contracts first.** In hour 1 we commit the shared contracts (Pydantic schemas, `ChannelPort`, `PublisherPort`, button IDs, REST types). After that, the two tracks build in parallel against them.
3. **Simulator before WhatsApp.** The web chat simulator lets Track A test agents and flows without depending on Meta. WhatsApp is just another `ChannelPort`.
4. **Vertical slices at checkpoints.** Three integration checkpoints where *something* works end to end, even if ugly.
5. **Freeze at H21.** The last 3 hours are rehearsal, fallbacks and the pitch. No new features.
6. **Coding agents do the typing.** Each task in [tasks.md](tasks.md) is written to be handed to Claude Code as-is: it names the files, the contract and the acceptance criteria.

## Tracks

| Track | Owner | Scope |
|---|---|---|
| **A: Brain** | Builder 1 (stronger in Python/LLMs) | DB layer, LLM client, all agents (including video analysis and Reels), job runner + job pipelines, orchestrator, renderer engine, quality checks, seed data |
| **B: Surface** | Builder 2 (stronger in web/integrations) | FastAPI skeleton, WhatsApp channel + webhook, simulator channel + `/dev/chat`, inbound handler + onboarding/button routers, onboarding and dashboard REST + direct uploads, Zernio publisher (images and Reels), Next.js wizard + dashboard, HTML post templates |

Shared files (coordinate before editing): `migrations/`, `app/agents/schemas.py`, `app/channels/base.py`, `app/publishing/base.py`, `app/copy/messages_es.py`, `frontend/lib/api.ts`.

## Scope changes from ADR 0012

[ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md) made the editable dashboard (Catálogo, Contenido, Promos), video uploads with analysis, and Reels from the Owner's own videos part of the MVP. To make room:

- **Demoted to Could:** Brand Brain correction in chat (F2.6), plan changes from free text (F3.3), and the third and fourth templates `quote_card` + `split_story` (F4.3, T34). The demo uses `product_hero` + `promo_band` and one Reel.
- **Still Should, after Checkpoint 3 only:** derived frame photos (T37), Offers in the dashboard and from the chat (T38 Promos, T46), inbound videos from WhatsApp (F1.5), scheduling (F5.3) and the Zernio webhook (T29).
- **Not in the MVP:** video editing, transcription, carousels, Agency-suggested Offers (F8.9), price-list extraction (T47, Could).

## Timeline

| Hour | Track A: Brain | Track B: Surface | Together |
|---|---|---|---|
| **0–1** | — | — | Kickoff: scaffold `backend/` (uv + FastAPI) and `frontend/` (Next.js + shadcn). Apply schema. Commit contracts. Deploy both. Verify the Meta webhook against the deployed URL. **(T00–T03)** |
| **1–6** | LLM client + `agent_runs` (T10). Asset Analyst + Brand Strategist (T11–T12). Copywriter + Art Director (T13–T14). Renderer engine with a placeholder template (T15) | WhatsApp channel + webhook + dedupe (T20). Simulator channel + `/dev/chat` UI (T21–T22). Inbound handler + onboarding router Flow 1 (T23) | |
| **6–7** | | | **Checkpoint 1:** "hola" on real WhatsApp → welcome → name → magic link. A script renders a post for the demo business from its real photos |
| **7–12** | Job runner (T16). Jobs: brand, plan, post, revise (T17). Video analysis (T36). Button router handlers (T18). Orchestrator v1 + tools (T19) | Onboarding REST + direct uploads to storage + palette (T24). Next.js wizard steps 1–7 with videos (T25). Templates `product_hero` + `promo_band` (T26). Zernio publisher + connect flow (T27) | |
| **12–13** | | | **Checkpoint 2:** in the simulator: onboarding with a video upload → video analyzed as `reel_suitable` → Brand Brain summary → plan → post preview → change request → revised post |
| **13–17** | Reels in the agents (T39). Publish job + guards (T30). Quality checks + retries (T31). Demo seed with Catalog, videos and one Offer (T33) | Dashboard REST (T38). Dashboard Inicio + Catálogo + Contenido (T35). Reel publishing (T44). WhatsApp Reel preview + image header + media inbound (T45, T28) | |
| **17–18** | | | **Checkpoint 3:** full flow on real WhatsApp, with a real Instagram image post and a real Reel on the demo account; a Product and a video added from the dashboard on a phone |
| **18–21** | Prompt tuning with real data (T32). Latency pass. Should items if green: derived frames (T37), Catalog and Offers from the chat (T46) | Mobile QA of the wizard and dashboard (iOS in-app browser). Error states. Fallback switches tested. Should items if green: Promos tab, Zernio webhook (T29) | Bug bash. Each person runs the demo script once |
| **21** | | | **Code freeze.** Tag `demo-v1`. |
| **21–23** | | | Rehearse the demo ×2 (one with a forced fallback). Record a backup video of the full flow |
| **23–24** | | | Pitch slides, buffer |

Rest: if the hackathon allows it, take staggered 90-minute breaks between H13 and H17 (one person always awake on the integration).

## Before the hackathon (checklist)

Check the hackathon rules first: if pre-written code is not allowed, do only accounts and materials, not scaffolding.

**Accounts and keys** (owner: both, **by the day before**):

- [ ] Anthropic API key with credits; check rate limits for `claude-opus-5-5`.
- [ ] Meta developer app + WhatsApp product + test number; 3 recipient numbers verified; **System User permanent token** (not the 24h one). See [../architecture/integrations.md](../architecture/integrations.md#whatsapp-cloud-api).
- [ ] Zernio account + API key; demo IG account switched to **Business or Creator**; one manual test post via their dashboard.
- [ ] Supabase project on the **Pro** plan (Free caps files at 50 MB); Storage global file size limit set to **300 MB**; `assets` (private) and `renders` (public) buckets. See [../research/media-uploads.md](../research/media-uploads.md).
- [ ] Vercel project linked to the repo (`frontend/` root).
- [ ] Tenki (or Railway/Render) account; confirm it runs a Docker image with ≥ 1 GB RAM, Chromium and `ffmpeg`, and gives a public HTTPS URL.
- [ ] Publish one test Reel to the demo IG through Zernio (note processing time and whether a 60 s video is accepted).

**Demo business materials** (from the teammate with the furniture business):

- [ ] Logo (PNG with transparency if possible, or SVG).
- [ ] 12–15 good photos: products, workshop, details, finished rooms. Varied, well lit.
- [ ] 2–3 vertical videos, 15–60 s each, shot on the phone (a product close-up, the workshop, a finished room).
- [ ] The full product list with a one-line description and price; mark the 5 star products.
- [ ] Their answers to the questionnaire (so the demo answers are realistic and fast to type).
- [ ] One real current promo or news item (makes the plan feel real).
- [ ] Permission to publish 1–3 posts on their real Instagram during the demo (and to delete them after if they want).

**Assets:**

- [ ] Download the 4 font pairs (OFL) into `backend/app/rendering/fonts/`.
- [ ] Product name + assistant name decided (see [../open-questions.md](../open-questions.md)).

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Meta webhook/token problems | Medium | High | Permanent token prepared before; simulator as full fallback channel |
| Zernio connect redirect params differ from docs | Medium | Medium | Log the full redirect query on the first test (pre-hackathon); manual `provider_account_id` via `/dev` endpoint as fallback |
| Playwright/Chromium won't run on the host | Medium | High | Deploy the Playwright base image in H0–1 and render a test HTML immediately; fallback host Railway |
| LLM latency too high on stage (> 60 s per post) | Medium | Medium | Effort tuning; pre-seeded Brand Brain + plan; show live generation only for the ad-hoc post |
| Agents produce off-brand or hallucinated content | Medium | High | Real data from the owner, Brand Brain constraints, deterministic quality checks, rehearsal with the owner |
| Free tier limits (Zernio 2 accounts, Meta 5 recipients) | Low | Medium | Use IG only; don't connect test accounts to Zernio |
| Video uploads fail or crawl on conference Wi-Fi | High | High | Demo videos pre-loaded in the seed (T33); live upload on stage only for a short clip over the mobile hotspot |
| Zernio Reel processing takes minutes | Medium | Medium | Publish the demo Reel before the pitch and show the permalink; on stage, publish an image post live |
| Reel too large for a WhatsApp video preview | Medium | Low | Cover frame + dashboard link fallback (T45); keep demo videos short |
| Scope grew with the dashboard and Reels (ADR 0012) | High | High | Demotions listed in [Scope changes](#scope-changes-from-adr-0012); Should items only after Checkpoint 3 |
| Running out of time | High | High | MoSCoW in [../product/mvp.md](../product/mvp.md); freeze at H21; Should/Could only after Checkpoint 3 |

## After the hackathon (product path)

The demo architecture is meant to survive. Next steps in order:

1. Real job queue (arq/Redis or Postgres-based) + multiple backend instances (move locks to Postgres advisory locks).
2. RLS on Supabase; generated frontend API types from OpenAPI.
3. WhatsApp Business verification + own number + approved templates for proactive messages (weekly plan push).
4. Plans/quotas enforcement + billing (Mercado Pago / Stripe).
5. Evals for each agent (golden briefs → graded outputs) before changing prompts or models.
6. More networks (Facebook, TikTok) through the same publisher; carousels; voice notes and video transcription.
7. User accounts for the dashboard (replacing editable magic links); Agency-suggested Offers (F8.9).
