# Implementation plan (24h hackathon, 2 builders)

## Strategy

1. **Deploy on hour 1, not hour 20.** A "hello world" backend on Railway ([ADR 0017](../decisions/0017-backend-host-railway.md)) and frontend on Vercel, with the Kapso webhook reaching the backend ([ADR 0020](../decisions/0020-whatsapp-via-kapso.md)), before writing features. Deploy issues are the #1 hackathon killer.
2. **Contracts first.** In hour 1 we commit the shared contracts (Pydantic schemas, `ChannelPort`, `PublisherPort`, button IDs, REST types). After that, the two tracks build in parallel against them.
3. **Simulator before WhatsApp.** The web chat simulator lets Track A test agents and flows without depending on Kapso or Meta. WhatsApp is just another `ChannelPort`.
4. **Vertical slices at checkpoints.** Three integration checkpoints where *something* works end to end, even if ugly.
5. **Freeze at H21.** The last 3 hours are rehearsal, fallbacks and the pitch. No new features.
6. **Coding agents do the typing.** Each task in [tasks.md](tasks.md) is written to be handed to Claude Code as-is: it names the files, the contract and the acceptance criteria.

## Tracks

| Track | Owner | Scope |
|---|---|---|
| **A: Brain** | Builder 1 (stronger in Python/LLMs) | DB layer, LLM client, all agents, job runner + job pipelines, orchestrator (open chat, post from photos, one question, approve by writing), image generation adapter + resize, quality checks, seed data |
| **B: Surface** | Builder 2 (stronger in web/integrations) | FastAPI skeleton, WhatsApp channel + webhook (incl. inbound photos), simulator channel + `/dev/chat`, inbound handler + onboarding/button routers, onboarding REST + direct photo uploads, Zernio publisher, Next.js wizard, showing and picking variations in WhatsApp and the simulator; dashboard if Should starts |

Shared files (coordinate before editing): `migrations/`, `app/agents/schemas.py`, `app/channels/base.py`, `app/publishing/base.py`, `app/imagegen/base.py`, `app/carousel/schemas.py`, `app/copy/messages_es.py`, `frontend/lib/api.ts`.

## Scope (ADR 0016)

[ADR 0016](../decisions/0016-demo-scope-one-post.md) cuts the MVP to what the demo shows: a **short onboarding** (WhatsApp + the web form) and then **one post** the Owner asks for in the chat, approved and really published. Full priorities: [../product/mvp.md](../product/mvp.md).

- **Must:** WhatsApp + simulator channels, onboarding (Flow 1, the wizard with up to 5 Products and 3–15 photos and no Instagram step, [ADR 0024](../decisions/0024-mvp-single-demo-instagram-account.md); Brand Brain + summary), the open chat after onboarding, a post from photos and/or a request with at most one question, AI-generated variations and the Owner's pick ([ADR 0018](../decisions/0018-ai-image-generation-service.md)), carousels with text slides and slide redo ([ADR 0022](../decisions/0022-carousels-in-mvp.md), T55, built H13–16 once the image Post works), approval by button or by writing ("subilo"), voice notes handled as their transcript ([ADR 0021](../decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md)), publish now through Zernio, mock publisher, demo seed.
- **Should, after Checkpoint 3 (~H16):** matching the Owner's style, weekly plan on request, ideas on request, revisions, scheduling (incl. by writing), the Zernio webhook, the read-only dashboard.
- **Moved down from [ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md) to Could:** the editable dashboard (Catálogo, Contenido, Promos), video uploads and analysis, derived frames, Reels, Catalog and Offers from the chat. The wizard is back to the design's limits: up to 5 Products, 3–15 photos, no videos.
- **New Could from the second design pass:** Instagram feed import (needs read access we haven't verified), building colors and a simple logo in the chat.
- **Not in the MVP:** stories, video editing, transcribing the audio of videos, Agency-suggested Offers (F8.9).

## Timeline

| Hour | Track A: Brain | Track B: Surface | Together |
|---|---|---|---|
| **0–1** | — | — | Kickoff: scaffold `backend/` (uv + FastAPI) and `frontend/` (Next.js + shadcn). Apply schema. Commit contracts. Deploy both. Point the Kapso webhook at the deployed URL and run the Kapso first-hour test ([open questions](../open-questions.md#whatsapp-through-kapso-first-hour-test)). First real Gemini call with the demo photos (fidelity, 4:5, latency, cost). **(T00–T03)** |
| **1–6** | LLM client + `agent_runs` (T10). Asset Analyst + Brand Strategist (T11–T12). Copywriter + Art Director (T13–T14). Image generation adapter + resize (T15) | WhatsApp channel + webhook + dedupe (T20). Simulator channel + `/dev/chat` UI with photos (T21–T22). Inbound handler + onboarding router Flow 1 (T23) | |
| **6–7** | | | **Checkpoint 1:** "hola" on real WhatsApp → welcome → name → magic link. A script generates image variations for the demo business from its real photos |
| **7–12** | Post on request in the chat, before the database (T56). Job runner (T16). Jobs: asset, brand, post (T17, Must part). Button router (T18). Orchestrator v1 + Must tools (T19). Open chat after onboarding (T48). Post from photos + one question (T49) | Onboarding REST + direct photo uploads + palette (T24). Next.js wizard, six steps (T25). Variations in WhatsApp and the simulator (T26). Zernio publisher + connect flow (T27) | |
| **12–13** | | | **Checkpoint 2:** in the simulator: wizard → Brand Brain summary → "¿En qué te puedo ayudar hoy?" → two photos + a request → one question → variations → pick → post preview |
| **13–16** | Approve and publish by writing (T50). Publish job, publish now (T30, Must part). Quality checks + retries (T31). Demo seed (T33). Carousel pipeline: modes, generator, Text Checker, `redo_slides` (T55, A part) | WhatsApp polish: image-header previews, inbound photo batching on a real phone (T28). Carousel slides in WhatsApp and the simulator, carousel publish (T55, B part). Mock publisher switch tested. Mobile QA of the wizard (iOS in-app browser) | |
| **16** | | | **Checkpoint 3:** the full demo on real WhatsApp: onboarding, a post asked for with a photo, "subilo", a real Instagram post and its permalink in the chat |
| **16–21** | Prompt tuning with real data (T32). Latency pass. Should if Checkpoint 3 is green: style matching (T51), ideas (T52), plan on request + revisions (T17b), scheduling (T30, Should part) | Error states. Fallback switches tested. Should if green: Zernio webhook (T29), read-only dashboard (T38, T35) | Bug bash. Each person runs the demo script once |
| **21** | | | **Code freeze.** Tag `demo-v1`. |
| **21–23** | | | Rehearse the demo ×2 (one with a forced fallback). Record a backup video of the full flow |
| **23–24** | | | Pitch slides, buffer |

Rest: if the hackathon allows it, take staggered 90-minute breaks between H13 and H17 (one person always awake on the integration).

## Before the hackathon (checklist)

Check the hackathon rules first: if pre-written code is not allowed, do only accounts and materials, not scaffolding.

**Accounts and keys** (owner: both, **by the day before**):

- [ ] Anthropic API key with credits; check rate limits for `claude-opus-5-5`.
- [ ] Kapso account (Free plan) and a number: the free US number or the sandbox; webhook pointed at the backend. At the hackathon this moved to hour 1 ([ADR 0020](../decisions/0020-whatsapp-via-kapso.md), [integrations.md](../architecture/integrations.md#kapso-setup-hour-1)). Meta's developer app and System User token only if plan B is needed.
- [ ] Google project with a **billing account linked** and a Gemini API key (unpaid use trains on images). OpenAI key and Organization Verification only if the fallback is needed ([ADR 0019](../decisions/0019-image-provider-gemini.md)).
- [ ] Zernio account + API key; demo IG account switched to **Business or Creator**; one manual test post via their dashboard.
- [ ] Supabase project (the **Free** plan is enough for the Must scope: photos only); `assets` (private) and `renders` (public) buckets. Pro + a 300 MB file limit only if the Could video work starts ([../research/media-uploads.md](../research/media-uploads.md)).
- [ ] Vercel project linked to the repo (`frontend/` root).
- [ ] Railway account verified through GitHub (Trial); check the Trial's end date against the demo ([ADR 0017](../decisions/0017-backend-host-railway.md)).
- [ ] Call Zernio's `GET /v1/accounts/{accountId}/posts` for the demo IG and note whether it returns Instagram posts with full-size images: that decides whether the Could feed import (T53) is possible ([../architecture/integrations.md](../architecture/integrations.md#reading-the-owners-existing-instagram-media-could)).

**Demo business materials** (from the teammate with the furniture business):

- [ ] Logo (PNG with transparency if possible, or SVG).
- [ ] 12–15 good photos: products, workshop, details, finished rooms. Varied, well lit.
- [ ] 1–2 photos of something **new** on the owner's phone (a recent piece) for the live request on stage ("me llegó esta mesa ratona nueva, armame algo para subir").
- [ ] The 5 star products with a one-line description and price.
- [ ] Their answers to the questionnaire (so the demo answers are realistic and fast to type).
- [ ] One real current promo or news item (makes the plan feel real).
- [ ] Permission to publish 1–3 posts on their real Instagram during the demo (and to delete them after if they want).

**Assets:**

- [ ] Product name + assistant name decided (see [../open-questions.md](../open-questions.md)).

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Kapso number, webhook or media download doesn't work as needed | Medium | High | First-hour test; simulator as full fallback channel; Meta Cloud API direct as plan B (~1 h setup) |
| Zernio connect redirect params differ from docs | Medium | Medium | Log the full redirect query on the first test (pre-hackathon); manual `provider_account_id` via `/dev` endpoint as fallback |
| Generated images alter the real product or add text, prices or logos | Medium | High | Fidelity test with the demo photos in H0–1; fixed prompt rules; the Owner picks and approves every image ([ADR 0007](../decisions/0007-approve-every-post.md)); fallback provider |
| Carousel slides misspell the copy's text or drift in style | Medium | Medium | Text Checker + one regeneration per slide; slides anchored on the cover; the Owner redoes a slide or discards; Approval before publishing ([ADR 0022](../decisions/0022-carousels-in-mvp.md)) |
| Image service slow, rate-limited or blocked on stage | Medium | High | Variations in parallel in the job runner; `IMAGE_GEN=openai` fallback (up to 2 min per complex image; only if T43 is built and the OpenAI org is verified) or `mock`; rehearsal variations kept as proof |
| LLM latency too high on stage (> 60 s per post) | Medium | Medium | Effort tuning; send the acknowledgement and typing indicator at once; pre-seeded Brand Brain so only the post is generated live |
| Agents produce off-brand or hallucinated content | Medium | High | Real data from the owner, Brand Brain constraints, deterministic quality checks, rehearsal with the owner |
| Free tier limits (Zernio 2 accounts, Kapso 2,000 messages/month and an unverified recipient limit, Gemini Tier 1 $10 per 10 minutes) | Low | Medium | Use IG only; don't connect test accounts to Zernio; check Kapso's limit in the first-hour test |
| Brand generation too slow for a live onboarding on stage | Medium | Medium | Pre-generated Brand Brain in the seed (T33); if live generation passes ~60 s, the narrator switches to the seeded business and continues with the post request |
| Zernio publish fails or is slow on stage | Medium | High | `PUBLISHER=mock` switch tested at Checkpoint 3; a post published before the pitch as proof |
| Should features creep in before the Must flow works | High | High | Nothing from Should before Checkpoint 3 is green on real WhatsApp ([Scope](#scope-adr-0016)) |
| Running out of time | High | High | MoSCoW in [../product/mvp.md](../product/mvp.md); freeze at H21; Should only after Checkpoint 3, Could only if everything else is solid |

## After the hackathon (product path)

The demo architecture is meant to survive. Next steps in order:

1. The Should features not finished on the day (plan on request, ideas, revisions, scheduling, style matching, read-only dashboard), then [ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md)'s Catalog, content uploads and Reels ([ADR 0016](../decisions/0016-demo-scope-one-post.md)).
2. Real job queue (arq/Redis or Postgres-based) + multiple backend instances (move locks to Postgres advisory locks).
3. RLS on Supabase; generated frontend API types from OpenAPI.
4. WhatsApp Business verification + own number + approved templates for proactive messages.
5. Plans/quotas enforcement + billing (Mercado Pago / Stripe).
6. Evals for each agent (golden briefs → graded outputs) before changing prompts or models.
7. More networks (Facebook, TikTok) through the same publisher; stories; video transcription.
8. User accounts for the dashboard (replacing editable magic links); Agency-suggested Offers (F8.9).
