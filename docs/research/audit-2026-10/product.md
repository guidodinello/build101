# Product, UX and feature gaps

This doc covers the product side of Neitor AI: what the Owner experiences from the first WhatsApp message to a published Post, how the MVP scope compares with what the code does, and which new features fit the persona. It is part of the 2026-10-19 audit (index in [README.md](README.md), cross-dimension synthesis in [summary.md](summary.md)); the code was read at commit `dc0bc01`. An independent adversarial reviewer checked each finding against the code and the cited sources. "Adjusted" means the reviewer corrected its severity or details; the severity and recommendation shown here already include those corrections.

## Summary

- **The core loop works and is well documented.** WhatsApp onboarding, then a Post or Carousel from the Owner's photos, then Approval enforced in code, then a real publish, with good Rioplatense UX.
- **Three things block a real pilot outright.** Every approved Post goes to the one shared demo Instagram account (PRD-1, [ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md)). Posts, images and limits live in memory, so any deploy kills pending Approvals (PRD-2). The only WhatsApp entry point is a Chilean Kapso sandbox number that answers only registered phones and cannot send templates (PRD-3).
- **Neitor is purely reactive.** It never writes first and has no scheduling, Content plan, calendar or results, and its only trend input is one furniture Niche Report applied to every Business. That leaves it open to the same abandoned-Instagram pattern the persona already has, and gives nothing to justify US$29 once Free is used up.
- **Monetization and legal basics do not exist yet**: no quotas, payment or upgrade flow, and no privacy policy, terms or data-deletion path.
- **The biggest leverage is Zernio**, which already powers publishing. Per its docs and pricing it covers Stories, Reels, Facebook, Google Business Profile, analytics, comments and DMs on every account at no extra cost, so many roadmap items, including parts of Pro, can ship without Meta App Review.
- **Recommended order**: (1) the pilot blockers PRD-1 to PRD-3; (2) the cheap fixes PRD-4 to PRD-8; (3) the retention loop of scheduling, Monday nudges and results in Basic (PRD-9 to PRD-11); (4) billing; then new formats (Stories, testimonials, Reels, Facebook and Google Business Profile).

## Findings at a glance

Effort: S is under half a day, M is 1-2 days, L is about a week, XL is more than a week.

| Id | Severity | Effort | Finding |
|---|---|---|---|
| PRD-1 | critical | M | Every Owner's approved Post publishes to the one shared demo Instagram account |
| PRD-3 | critical | M | Pilot Owners can't reach Neitor: the CTA is a Chilean sandbox number that can't send templates |
| PRD-2 | high | M | Posts, images and limits live in memory, so every deploy silently kills pending Approvals |
| PRD-8 | high | S | No privacy policy, terms, consent or data-deletion path before onboarding real Owners |
| PRD-4 | medium | S | One furniture Niche Report is injected into every Business, whatever its category |
| PRD-5 | medium | S | After onboarding the Owner gets an empty "¿En qué te puedo ayudar hoy?" instead of a first Post |
| PRD-6 | medium | S | The landing is in English for a 50+ Spanish-speaking Owner, and the WhatsApp prefill says "Hi Neitor" |
| PRD-7 | medium | S | No Uruguayan commercial calendar, just as Black Friday and the holiday season begin |
| PRD-9 | medium | M | Neitor never writes first: no weekly nudge, no "7 días sin publicar", nothing that builds a habit |
| PRD-10 | medium | M | Scheduling is sold in Basic and designed into the flows, but "subilo mañana a la tarde" is refused |
| PRD-11 | medium | M | The Owner never sees results; put a basic results summary in Basic, not only Pro |
| PRD-12 | medium | M | There is no way to charge: no quota, no payment, no upgrade moment, and Basic has no cost ceiling |
| PRD-13 | medium | S | The Instagram connect fails without guidance for personal accounts and non-testers |
| PRD-14 | medium | S | Failure UX and capability promises don't match what's built |
| PRD-15 | medium | S | Hashtag rules go over Instagram's 5-hashtag cap |
| PRD-16 | medium | S (reviewer: M) | "Cambiá la 3" regenerates the whole Carousel (Slide redo is Must but not wired) |
| PRD-19 | medium | M | New: Reels from the Owner's own videos (her most natural content is rejected today) |
| PRD-21 | medium | L | Shape Pro as "your inbox, in your WhatsApp" with the Owner in the loop, not autonomous DM replies |
| PRD-17 | low | S | New: customer-photo testimonial Posts and review requests, using what she already gets in WhatsApp |
| PRD-18 | low | M | New: Stories, plus a vertical copy "para tu estado" of WhatsApp |
| PRD-20 | low | M | New: cross-post to Facebook and publish Google Business Profile updates and offers through Zernio |
| PRD-22 | low | S | No undo after publishing ("borralo") |
| PRD-23 | low | M | New: let staff send photos and Voice notes for the Owner to approve |
| PRD-24 | low | M | New: a price-list photo or PDF becomes Products and a "lista de precios" Post |

## Scope, funnel and cost numbers

### MVP gap table

Must and Should items in [mvp.md](../../product/mvp.md) compared with the code at `dc0bc01` (audit observation, 2026-10-19).

| Id | Feature | Priority | Status |
|---|---|---|---|
| F1.1–F1.7, F1.10 | WhatsApp text, buttons, images, Orchestrator, photos, progress, voice | Must | Built |
| F2.1/F2.2/F2.4/F2.5 | WhatsApp first contact, 6-step wizard, Asset Analyst, Brand Brain | Must | Built |
| F4.1/F4.2/F4.5 | Copy, images (photos or design), ad-hoc Post | Must | Built (no Variation pick; "photos" and "design" styles instead) |
| F4.9 | Carousels | Must | Built, **Slide-level redo not wired** |
| F5.1/F5.2/F5.5/F5.6 | Approval in code, publish now, mock, approve by writing | Must | Built, **but in memory and to the single demo account** |
| F6.2 | Web chat simulator | Must (dev) | **Not built** |
| F7.1 | One Business per number | Must | Partial (Posts keyed by phone in memory, one Instagram account) |
| F7.2 | Agent run log | Must | **Not built** (`agent_runs` table exists, unused) |
| F2.3/F2.8 | Instagram connect and import | Should | Built (read only, testers only) |
| F4.4 / F2.6 | Revisions / brand fix in chat | Should/Could | Built (`revise_post`, `update_brand`) |
| F3.5 / F1.9 | Ideas / style matching | Should | Prompt-only (no tool) |
| F3.1/F3.2 | Weekly plan | Should | **Not built** |
| F3.6/F3.7 | Weekly Niche Report / on request | Should | CLI plus one global file; **no job, no tool** |
| F5.3 / F5.6 schedule | Scheduling | Should | **Not built** (refused in `approval.py`) |
| F6.3 | Read-only dashboard | Should | **Not built** |
| F7.3 | Plans and usage in the data model | Should | Columns in SQL, unmapped and unenforced (quota default 30, while Free is 3) |

### Activation funnel today

The Owner's actions until the first published Post, traced through the code (audit observation, 2026-10-19):

1. Tap the landing CTA, which opens the sandbox number (it blocks non-registered phones).
2. Send "Hi Neitor" and type the Business name.
3. Open the link and go through wizard steps 1 to 6: Instagram OAuth (professional accounts and testers only, up to 90 s import wait), at least 1 Product, at least 3 photos.
4. Back in WhatsApp, receive the brand summary (target under 60 s) and tap [Sí, es mi marca].
5. Get a blank "¿En qué te puedo ayudar?".
6. Send photos and a request, answer the style or ideas question, and wait "a few minutes".
7. Tap [Aprobar], then [Publicar ahora], and receive the permalink (on the demo account).

That is about 15 Owner actions and an estimated 12–20 minutes (estimate; the reviewer called it unsupported, and MVP success criterion 1 targets under 5 minutes for onboarding). No proactive message ever brings her back.

### Image cost per Post

Estimates from the list prices in [ADR 0019](../../decisions/0019-image-provider-gemini.md) (US$0.0504 per 2K image) and [ADR 0029](../../decisions/0029-designed-slides-ai-scene-code-layout.md) (US$0.113 per 4K panorama). Full cost model in [unit-economics.md](unit-economics.md).

| Post | Image calls | Approx. image cost (estimate) |
|---|---|---|
| Photos as they are | 0 | US$0 |
| Design, 1 image | 1 × 2K | ~US$0.05 plus inputs |
| Design Carousel, 5 Slides | 5 × 2K | ~US$0.25 output; [ADR 0022](../../decisions/0022-carousels-in-mvp.md) estimates US$0.30–0.40 total |
| Panorama, 4–5 Slides | 1 × 4K | US$0.113 |
| One image revision of a 5-Slide Carousel (no Slide redo) | 5 × 2K again | +US$0.30–0.40 |
| Basic worst case: 5 designs a day × 30 days as 10-Slide Carousels | 1,500 × 2K | ~US$75.6 a month against US$29 revenue |

Per-Business platform costs at pilot scale:

- Zernio: US$6 per account per month for accounts 3–10 and US$3 for 11–100, and each extra network is one more account ([Zernio pricing](https://zernio.com/pricing), read 2026-10-19).
- Kapso: Free has 2,000 messages a month and Pro is US$25 a month ([ADR 0020:14](../../decisions/0020-whatsapp-via-kapso.md)).
- WhatsApp templates are billed per delivered message at the Rest of Latin America rate for +598 numbers ([WhatsApp pricing](https://developers.facebook.com/docs/whatsapp/pricing), read 2026-10-19).

## Findings

### PRD-1: Every Owner's approved Post publishes to the one shared demo Instagram account

- **Severity**: critical · **Effort**: M · **Confidence**: high · **Verified**: confirmed
- **Evidence**: one global `ZERNIO_PROFILE_ID` / `ZERNIO_ACCOUNT_ID` serves every Business ([config.py:56-62](../../../backend/app/config.py)); `_start` publishes every sender's Post to `self._account_id` ([publish.py:103-110](../../../backend/app/posts/publish.py)); "Every Business in the demo publishes to the same Instagram account" ([ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md)); the wizard asks the Owner to connect *her* Instagram, which is read-only per [ADR 0028](../../decisions/0028-read-instagram-with-our-meta-app.md) ([instagram-step.tsx:55-56](../../../frontend/components/onboarding/steps/instagram-step.tsx)); the landing promises "Published to your Instagram" ([pricing-section.tsx:67](../../../frontend/components/landing/pricing-section.tsx)); `ensure_profile` and `connect_url` are already built and unused ([zernio.py:85,103](../../../backend/app/publishing/zernio.py)); `instagram_business_content_publish` is a scope of the same Instagram Login Neitor already uses ([Instagram API with Instagram Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login), read 2026-10-19).
- **Problem**: The wizard connects the Owner's Instagram only to read it; publishing still uses the env account. The first pilot Owner who taps Aprobar gets her Product on Neitor's demo feed, with a permalink to someone else's account, and every pilot Business shares one feed. That breaks the core promise and hits the persona's biggest fear, losing control of her account.
- **Recommendation**: Resolve the publishing account per Business: connect each Owner's Instagram in Zernio through the existing `connect_url` and look the ids up in `social_accounts`. This replaces a recorded decision, so it needs an ADR superseding [ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md); [open-questions.md:94](../../open-questions.md) already frames it ("one connection instead of two"). As an interim for a single-Owner pilot, connect her account in Zernio (free up to 2 accounts) and gate publishing on the sender being that Owner's phone until resolution through `social_accounts` ships.
- **Impact**: Unblocks 100% of pilot publishes and avoids a trust-ending incident on day one.
- **Verifier note**: `_start` uses the single `ZERNIO_ACCOUNT_ID` from env for every sender, and [meta.py:15](../../../backend/app/instagram/meta.py) asks only for `instagram_business_basic`, so the wizard connect is read-only. Meta's Instagram Login page lists `instagram_business_content_publish` as one of four scopes. Zernio pricing (checked): accounts 1-2 free, 3-10 US$6 a month, 11-100 US$3 a month, so the per-Business Zernio route is cheap. This is a documented MVP decision rather than a bug, but still the top pilot blocker. Even a one-Owner pilot that points `ZERNIO_ACCOUNT_ID` at her account is unsafe: any other onboarded phone, a teammate's tests included, would publish onto her real account, so per-Business resolution is needed.
- **Related**: [BUG-1](bugs-reliability.md), [ARCH-4](backend-architecture.md), [SEC-2](security-privacy.md), [GRW-2](growth-pricing-market.md), [GAP-1](cross-cutting-gaps.md)

### PRD-2: Posts, images and limits live in memory, so every deploy silently kills pending Approvals

- **Severity**: high · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**: `InMemoryPosts` holds Posts "until T19 moves them onto posts" ([store.py:63-64](../../../backend/app/posts/store.py)); Posts, generated JPEGs, photos and dedupe are lost on restart and image links return 404 ([how-it-works.md:167-177](../../architecture/how-it-works.md)); a Post that is gone turns [Aprobar] into a `StaleButton` ([button_router.py:154-156](../../../backend/app/conversation/button_router.py)) with "Ese botón ya no está activo" ([messages_es.py:14](../../../backend/app/copy/messages_es.py)); the daily design cap is a dict that resets on deploy ([maker.py:106,188-191](../../../backend/app/posts/maker.py)); a `posts` table with an approved-before-publish check already exists, unused ([0001_initial.sql:168-214](../../../backend/migrations/versions/0001_initial.sql)).
- **Problem**: The team deploys several times a day. An Owner who gets a preview at 18:00 and answers "subilo" at 21:00 after a redeploy gets "ese botón ya no está activo" or `unknown_post`. She has to ask again and wait minutes again, and Neitor pays for the generation again. The daily limit also resets. Scheduling (PRD-10), history and quotas (PRD-12) all depend on persisted Posts.
- **Recommendation**: Do T17/T19 (renders to the Supabase `renders` bucket, Post rows plus Slides and source asset ids, re-hydrate on lookup) before or early in the pilot. Until then, freeze deploys during pilot hours. The `posts` table's status check lacks `publish_pending` and `replaced`, which the code uses, so the migration needs updating.
- **Impact**: Removes the most likely day-to-day failure Owners would see. It is also the prerequisite for scheduling, metrics and billing.
- **Verifier note**: `InMemoryPosts`, `PublicImages` ([public.py](../../../backend/app/media/public.py), "lost on restart") and the daily-design dict all live in memory. After a restart `button_router._post` returns `None` and the Owner gets `StaleButton`; "subilo" finds no pending Post. Photos are also kept only 30 minutes (`RECENT_FOR` in [photos.py](../../../backend/app/conversation/photos.py)), so the Owner must re-send them too. The deploy cadence is real (26 commits on 2026-10-18). Downgraded from critical: it is a known, documented gap with a cheap operational mitigation for a small pilot, and the Owner loses a pending preview, not her data.
- **Related**: [ARCH-1](backend-architecture.md), [BUG-5](bugs-reliability.md), [OPS-1](platform-ops.md), [GRW-1](growth-pricing-market.md)

### PRD-3: Pilot Owners can't reach Neitor: the CTA is a Chilean sandbox number that can't send templates

- **Severity**: critical · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**: the CTA is a +56 wa.me link that "only answers phones with an active sandbox session" ([PRODUCT.md:36](../../../PRODUCT.md)), and the same number is in [frontend/.env.example:4](../../../frontend/.env.example); the sandbox only messages the registered recipient and sends no templates ([ADR 0020:18](../../decisions/0020-whatsapp-via-kapso.md)); the policy check, Business Verification, own number and templates are still open ([open-questions.md:17-18](../../open-questions.md)); `ChannelPort` has no `send_template` ([base.py:12-28](../../../backend/app/channels/base.py)); a business can start contact only with a template, and Uruguay is billed at the "Rest of Latin America" rate ([WhatsApp pricing](https://developers.facebook.com/docs/whatsapp/pricing), read 2026-10-19); the WhatsApp ban targets AI-provider assistants, not businesses using AI ([TechCrunch](https://techcrunch.com/2025/10/18/whatssapp-changes-its-terms-to-bar-general-purpose-chatbots-from-its-platform), read 2026-10-19).
- **Problem**: A Uruguayan Owner who taps "Get started" lands on a +56 number that ignores her unless she joined the sandbox. Even after joining, nothing can reach her outside the 24-hour window: no reminders, no weekly plan, no confirmation that a scheduled Post went out. A foreign test number also costs trust with a 50+ Owner.
- **Recommendation**: Fastest unblock: move off the sandbox to Kapso's free pre-verified US number, a real number that supports templates and many recipients. In parallel, get a Uruguayan line (one not used on the WhatsApp app), connect it through Kapso's connect flow, complete Business Verification and set the display name. Add `send_template` to `ChannelPort` and submit the templates. Write the policy memo for [open-questions.md:17](../../open-questions.md). Model template costs with the 2026-10-01 pricing change.
- **Impact**: Without this there is no pilot; it is also the prerequisite for every retention loop (PRD-9).
- **Verifier note**: Confirmed in PRODUCT.md, the frontend env example and the README. Correction: Kapso does not sell +598 numbers. Its pricing page offers only pre-verified US numbers (Free includes one; Pro, US$25, includes 3 connected numbers), so a Uruguayan number has to be a line the team obtains and connects through Kapso (Free allows 1 connected number). Also from Meta's page: since 2026-10-01, utility replies inside the service window are billed as regular messages, no longer free, which affects the template and messaging cost model.
- **Related**: [FE-1](frontend.md), [OPS-3](platform-ops.md), [DOC-1](docs-process.md), [GRW-2](growth-pricing-market.md)

### PRD-4: One furniture Niche Report is injected into every Business, whatever its category

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**: `trend_notes = load_trend_notes(settings.niche_report_path)` is loaded once at startup ([factory.py:59](../../../backend/app/conversation/factory.py)), and the same notes go to `PostDrafter` and the Orchestrator for every sender (factory.py:61 and :96); only `CURATED_WOOD_FURNITURE_UY` exists ([niches.py:46](../../../backend/app/agents/data/niches.py)); the wizard offers Gastronomía, Indumentaria, Belleza, Servicios and Otro ([categories.ts:9-46](../../../frontend/lib/categories.ts)).
- **Problem**: With `NICHE_REPORT_PATH` set, a pasta shop or nail salon gets "what's working in solid-wood furniture" as trend notes in its system prompt and its Post brief. That pushes off-niche angles and visuals, and it reads as "generic AI", which breaks principle 3 in [PRODUCT.md](../../../PRODUCT.md).
- **Recommendation**: Inject the trend notes only when `business.category` maps to the report's niche ("Muebles y deco" to `curated-wood-furniture-uy`); otherwise inject nothing. Do this before any non-furniture pilot Owner onboards.
- **Impact**: Prevents off-brand content for every non-furniture pilot Owner; a few lines of code.
- **Verifier note**: [drafts.py:170-172](../../../backend/app/posts/drafts.py) and [context.py:111](../../../backend/app/conversation/context.py) inject the notes with no category check. Conditions lower the severity: it only happens when `NICHE_REPORT_PATH` is set (it is commented out in [backend/.env.example](../../../backend/.env.example)), and only for non-furniture Owners. It is a documented interim stand-in for the per-Business weekly job in [ADR 0025](../../decisions/0025-weekly-niche-report.md), the pilot persona is furniture, and the prompts say trend notes change angle and format, never facts. Still a cheap, worthwhile guard before onboarding mixed categories.
- **Related**: [GRW-12](growth-pricing-market.md), [AIQ-12](ai-quality.md)

### PRD-5: After onboarding the Owner gets an empty "¿En qué te puedo ayudar hoy?" instead of a first Post

- **Severity**: medium · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: on brand confirmation the prompt says "Never propose a plan or a post by yourself" ([events.md:16](../../../backend/app/conversation/prompts/events.md)); the reply is `READY_OPEN_CHAT` ([messages_es.py:32](../../../backend/app/copy/messages_es.py)); F1.10 was chosen for the stage demo ([mvp.md:38](../../product/mvp.md)); photos sent before the form is finished get no reply or a link reminder and are not kept ([onboarding.py:73-74,91-92](../../../backend/app/conversation/onboarding.py)).
- **Problem**: By the time she confirms her brand, the Owner has spent about 10 minutes and already given at least 3 photos and 1 Product, maybe plus an Instagram import. Then Neitor hands her a blank prompt, the empty state where reactive tools lose non-technical users. Time to first value is about 15 Owner actions and 12–20 minutes (estimate). Photos she sends early, her natural first move ("me llegó esta mesa"), are dropped.
- **Recommendation**: Treat the first-Post offer as a pilot experiment that needs a team decision revising F1.10 and MVP success criterion 3, not as a defect. Separately and uncontroversially, keep photos sent before the form is finished as Brand assets (`source='whatsapp'`) instead of dropping them.
- **Impact**: Cuts time to the first preview by several minutes and removes the biggest drop-off step. Activation is the metric the pilot can actually move.
- **Verifier note**: In `onboarding.py`, an album during `awaiting_web_form` returns `''` (silent) and a single image gets only a link reminder; neither is stored. But F1.10 is a deliberate Must and success criterion 3 ([mvp.md:13](../../product/mvp.md)), and [ADR 0016](../../decisions/0016-demo-scope-one-post.md)'s context explains the move to a free-form chat. The "about 15 actions, 12–20 minutes" figure is an unsupported estimate (criterion 1 targets under 5 minutes for onboarding). Reasonable as a hypothesis to test in the pilot; high severity was inflated.
- **Related**: [GRW-11](growth-pricing-market.md)

### PRD-6: The landing is in English for a 50+ Spanish-speaking Owner, and the WhatsApp prefill says "Hi Neitor"

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**: landing copy is in English for judges ([PRODUCT.md:13](../../../PRODUCT.md)); "No app to install", "Speaks your Spanish" ([hero.tsx:8](../../../frontend/components/landing/hero.tsx)); "/ month" ([pricing-section.tsx:45](../../../frontend/components/landing/pricing-section.tsx)); `lang="es"` on English copy ([layout.tsx:28](../../../frontend/app/layout.tsx)); the prefilled text is "Hi Neitor" ([whatsapp.ts:3](../../../frontend/lib/whatsapp.ts)).
- **Problem**: Pilot Owners will reach Neitor from a link or a referral. An English page with US$ prices and an English opener contradicts "speaks your Spanish" and principle 1. `lang="es"` on English text also hurts screen readers and SEO.
- **Recommendation**: Revisit [PRODUCT.md:13](../../../PRODUCT.md) for the pilot: serve a Rioplatense Spanish landing (English at `/en` for judges), prefill "Hola Neitor", and set `lang` to match each page's content. A demo recording and peso prices are optional.
- **Impact**: Better conversion from the landing to the first message for the actual persona.
- **Verifier note**: The `lang` mismatch is a real accessibility issue. But PRODUCT.md:13 and :41 record English as a deliberate choice for hackathon judges and investors, and pilot Owners are likely to be onboarded by referral or a direct wa.me link rather than the landing. Valid to revisit now that a pilot starts, but medium, not high.
- **Related**: [FE-3](frontend.md), [FE-4](frontend.md), [DOC-3](docs-process.md), [GRW-14](growth-pricing-market.md)

### PRD-7: No Uruguayan commercial calendar, just as Black Friday and the holiday season begin

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**: a planned `app/agents/data/commercial_dates_uy.json` "so the model never guesses dates" ([agents.md:209](../../architecture/agents.md)); [backend/app/agents/data/](../../../backend/app/agents/data) holds only `niches.py`; the roadmap's weekly plan comes "with Uruguayan commercial dates" ([roadmap.md:10](../../roadmap.md)); Uruguay holidays, Reyes on 6 January and Semana de Turismo moving with Easter ([Remote support article](https://support.remote.com/hc/en-us/articles/40650162828813), read 2026-10-19; [Montevideo Portal](https://www.montevideo.com.uy/Noticias/Semana-de-Turismo-2025-cuando-es-el-proximo-feriado-en-Uruguay-uc919265), read 2026-10-19).
- **Problem**: On 2026-10-19, Black Friday (Friday 27 November 2026), the year-end season (Navidad and Fiestas) and Reyes (6 January) are close, and they are when a furniture store sells most. Neitor has no dates in context, so it can't suggest "faltan 3 semanas para Black Friday, ¿armamos la promo?", and the prompts forbid guessing dates.
- **Recommendation**: Turn the existing research table into `commercial_dates_uy.json`, with a category fit and lead time per date, after verifying the November 2026 CyberLunes date. Inject the next ~45 days into the Orchestrator context and the Post brief. Let the Brand Brain, not a default, decide whether price-led dates like Black Friday fit the Business.
- **Impact**: Turns the pilot's timing into a strong demo of value (promo Posts for peak season); about one day of work.
- **Verifier note**: [rules.md:1](../../../backend/app/conversation/prompts/rules.md) forbids inventing dates, and Black Friday on 27 November 2026 is correct. Two corrections. First, [furniture-decor-uruguay.md:58-100](../furniture-decor-uruguay.md) already holds the candidate calendar with sources. Second, that research contradicts the finding's premise: it calls Día de la Madre "the biggest commercial date", says "this segment may skip CyberLunes and Black Friday altogether", and advises avoiding price-led promos. Without proactive messaging (PRD-3, PRD-9) the dates only help when the Owner asks for ideas, so the "pilot timing demo" value is overstated.

### PRD-8: No privacy policy, terms, consent or data-deletion path before onboarding real Owners

- **Severity**: high · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**: no privacy, terms or deletion pages in [frontend/app](../../../frontend/app) or [frontend/components](../../../frontend/components) (a grep for `privacidad|términos|privacy|terms` returns nothing, audit observation, 2026-10-19); only connect and callback endpoints, no deauthorize or data-deletion callback ([instagram.py:43,57](../../../backend/app/api/instagram.py)); no "borrar mis datos" or "pausa" handling in [the prompts](../../../backend/app/conversation/prompts); apps that access user data must offer deletion and specify a deletion instructions URL or callback URL ([Meta data deletion callback](https://developers.facebook.com/docs/development/create-an-app/app-dashboard/data-deletion-callback), read 2026-10-19).
- **Problem**: Neitor stores Owners' photos, logos, Instagram captions and tokens, and their chat history, with no stated policy. Meta needs a deletion instructions or callback URL for the Instagram app, and App Review (PRD-1) needs a privacy policy. Uruguay's data-protection law applies to the pilot. Owners also have no way to say "borrá todo" or to pause.
- **Recommendation**: Publish Spanish privacy and terms pages and a data-deletion instructions page, and register them in the Meta app. Implement the Meta deauthorize and data-deletion callbacks. Add a consent line at wizard step 1 ("Al seguir aceptás..."). Add chat commands "pausar" and "borrar mis datos" that confirm with buttons. Say plainly that design images are AI-generated around her real Product.
- **Impact**: Required for App Review and going Live, and builds trust with Owners who fear losing control.
- **Verifier note**: `social_accounts` stores Instagram access tokens ([0002_instagram_import.sql](../../../backend/migrations/versions/0002_instagram_import.sql)). Meta's page (checked) requires either a data deletion instructions URL or a callback URL, and apps must explain deletion in their privacy policy. The recommendation is proportionate and small.
- **Related**: [SEC-3](security-privacy.md), [SEC-6](security-privacy.md), [FE-2](frontend.md), [DOC-5](docs-process.md), [GAP-4](cross-cutting-gaps.md)

### PRD-9: Neitor never writes first: no weekly nudge, no "7 días sin publicar", nothing that builds a habit

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**: no template send ([base.py:12-28](../../../backend/app/channels/base.py)); the Orchestrator never proposes by itself ([events.md:16](../../../backend/app/conversation/prompts/events.md)); the weekly run is silent and F1.8 (proactive) is Won't ([ADR 0025](../../decisions/0025-weekly-niche-report.md)); the Niche Report is a static file read at startup, not a weekly job ([factory.py:114-120](../../../backend/app/conversation/factory.py)); the persona updates Instagram "when she can" ([PRODUCT.md:11](../../../PRODUCT.md)); a weekly plan every Monday is planned for Phase 1 ([roadmap.md:10](../../roadmap.md)).
- **Problem**: Neitor's value is "posts consistently", yet it is 100% reactive. An Owner who forgets for a week is never brought back, which is the same abandoned-Instagram pattern the product exists to fix. The pilot's stated success metric (hours saved, consistency) can't move if nothing prompts the Owner.
- **Recommendation**: Sequence after PRD-3. During the pilot, run the Monday nudge by hand to validate it. Then build the per-Business Monday job with one template (marketing category, costed accordingly), a "pausa" opt-out and a weekly-active-posting metric.
- **Impact**: The main retention lever. Each nudge costs one template (Rest of Latin America rate) and can lead to 1 to 3 Posts.
- **Verifier note**: ADR 0025:20 makes the weekly run silent because F1.8 is Won't in the MVP. The finding correctly frames this as speeding up roadmap Phase 1. Downgraded because it is fully blocked on PRD-3 (number plus templates), and for a 2–4 week pilot with one or a few Owners the team can nudge manually to learn the loop first. Cost: a "weekly ideas" template is marketing category, the most expensive in Rest of Latin America, and per Meta's page utility replies are no longer free since 2026-10-01.
- **Related**: [GRW-10](growth-pricing-market.md)

### PRD-10: Scheduling is sold in Basic and designed into the flows, but "subilo mañana a la tarde" is refused

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**: `approve_later` maps to `scheduling_not_available` ([approval.py:81,158-159](../../../backend/app/conversation/approval.py)); the `approve_post` `next` enum is only `publish_now` ([tools.py:89-93](../../../backend/app/conversation/tools.py)); "scheduling isn't built yet" ([rules.md:2](../../../backend/app/conversation/prompts/rules.md)); the landing's Basic card says "Publish now or schedule on Instagram" ([pricing-section.tsx:79](../../../frontend/components/landing/pricing-section.tsx)); scheduling by writing and default times are designed ([user-flows.md:245,248](../../product/user-flows.md)); Zernio takes `scheduledFor` plus a timezone on the same call ([integrations.md:166](../../architecture/integrations.md)); the scheduled-publish confirmation falls outside the 24-hour window ([integrations.md:58](../../architecture/integrations.md)).
- **Problem**: The persona is in the workshop at the hours Posts do best. Without scheduling she has to be on her phone at 19:00 to tap publish, or post at random times. Basic charges for it and it doesn't exist.
- **Recommendation**: Short term, mark scheduling "soon" on the landing. Build it per the existing user-flows design after PRD-2, and rely on the documented MVP fallback ([integrations.md:58](../../architecture/integrations.md)) for confirmations outside the window until templates exist.
- **Impact**: Delivers a headline Basic feature, removes a reason to churn, and enables batch-creating a week of Posts in one sitting.
- **Verifier note**: Scheduling is a known Should (F5.3, F5.6, T30) already in roadmap Phase 1, and Basic can't be bought yet (no billing, PRD-12), so "Basic charges for it" isn't happening today. The real immediate issue is the landing promise. The dependencies in the recommendation (PRD-2, PRD-3) are correctly stated.
- **Related**: [GAP-11](cross-cutting-gaps.md)

### PRD-11: The Owner never sees results; put a basic results summary in Basic, not only Pro

- **Severity**: medium · **Effort**: M · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: the weekly results summary is Pro-only, "as they ship" ([ADR 0031:18](../../decisions/0031-pricing-free-basic-pro.md)); "this post brought N messages" is still open ([open-questions.md:117](../../open-questions.md)); the Instagram import already reads likes and comments per caption ([brand_strategist.md:11](../../../backend/app/agents/prompts/brand_strategist.md)); analytics for impressions, reach, engagement and followers are included on every Zernio account with no add-ons ([Zernio pricing](https://zernio.com/pricing), read 2026-10-19), and Instagram analytics are supported ([Zernio platforms](https://docs.zernio.com/platforms), read 2026-10-19).
- **Problem**: After "¡Publicado! 🎉 <link>" there is no feedback loop. An Owner paying US$29 can't tell if it works, which is the number one churn reason for a marketing service. The import also already has engagement data on her own Posts, and nothing uses it.
- **Recommendation**: After PRD-1, ship a short weekly or monthly results message from Zernio analytics. Whether it belongs in Basic needs an ADR amending [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md). Feeding the Owner's top-engaged imported captions into the drafter is a cheap win available now.
- **Impact**: Makes the value visible, supports the Free to Basic upgrade, and makes Pro an add-on rather than the only place value shows up.
- **Verifier note**: Roadmap Phase 1 already lists "Basic metrics: weekly WhatsApp summary from Instagram Insights" ([roadmap.md:20](../../roadmap.md)). More importantly, per-Owner results are meaningless until PRD-1 ships, because every Post currently goes to the shared demo account and the Owner's Instagram connect asks only `instagram_business_basic`. Moving metrics to Basic contradicts ADR 0031, so it needs a new pricing ADR. A useful idea, but a pricing and feature proposal, not high severity.

### PRD-12: There is no way to charge: no quota, no payment, no upgrade moment, and Basic has no cost ceiling

- **Severity**: medium · **Effort**: M · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: `businesses.plan` defaults to `'free'` and `monthly_post_quota` to 30, "not enforced", while [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md) says Free is 3 ([0001_initial.sql:20-21](../../../backend/migrations/versions/0001_initial.sql)); the `Business` model maps no plan or quota ([models.py:24-46](../../../backend/app/db/models.py)); the only cap is `max_posts_per_day = 5`, designs only, in memory ([config.py:44](../../../backend/app/config.py)); "Join the Pro list" opens the same WhatsApp chat, so no waitlist is captured ([pricing-section.tsx:85](../../../frontend/components/landing/pricing-section.tsx)); Posts per month for Basic and Pro are undecided ([open-questions.md:113](../../open-questions.md)); US$0.0504 per 2K image ([ADR 0019:12](../../decisions/0019-image-provider-gemini.md)); Mercado Pago Subscriptions are available in Uruguay with card, account money, Abitab and Red Pagos, and automatic retries ([Mercado Pago subscriptions](https://www.mercadopago.com.uy/developers/es/docs/subscriptions/overview), read 2026-10-19); CFE e-Factura and e-Ticket obligations (vendor blog, [yo-facturo](https://yo-facturo.com/blog/obligatoriedad-factura-electronica-uruguay/), read 2026-10-19).
- **Problem**: Free isn't limited, Basic can't be bought, and the Pro waitlist records nothing. Basic has no monthly cap: 5 designs a day as 10-Slide Carousels could cost about US$75 a month in images against US$29 of revenue (estimate). No moment in the chat turns a happy Free Owner into a payer.
- **Recommendation**: For the pilot: map plan and quota on `Business`, fix the quota default to match ADR 0031, enforce a monthly cap counted from persisted Posts (after PRD-2), and capture Pro interest (a "Quiero Pro" prefill plus a flag). Defer the Mercado Pago subscription and e-Factura (with an accountant) to the Phase 2 billing work; Basic and Pro quotas need an ADR next to ADR 0031.
- **Impact**: Turns on revenue, caps the image-cost downside, and turns the Pro waitlist into real demand data.
- **Verifier note**: "Join the Pro list" is a `CtaLink` to the same `WHATSAPP_START_URL` ("Hi Neitor"). Cost check: the Gemini pricing page lists `gemini-nano-banana-2.1` at US$0.0504 per 2K image (4K panorama US$0.113); `MAX_SLIDES = 10`, each Slide is one generated scene, so 5 × 10 × 30 × 0.0504 ≈ US$75.6 a month worst case, and the math is correct. But ADR 0031:25 and roadmap Phase 2 already defer billing and enforcement and the pilot is free, so high was inflated. The urgent part for the pilot is the cost cap and Pro-interest capture, not payments.
- **Related**: [GRW-3](growth-pricing-market.md), [GRW-5](growth-pricing-market.md), [GRW-6](growth-pricing-market.md), [GRW-13](growth-pricing-market.md), [COST-2](unit-economics.md), [ARCH-5](backend-architecture.md), [BUG-9](bugs-reliability.md), [SEC-4](security-privacy.md), [FE-17](frontend.md), [GAP-9](cross-cutting-gaps.md)

### PRD-13: The Instagram connect fails without guidance for personal accounts and non-testers

- **Severity**: medium · **Effort**: S · **Confidence**: medium · **Verified**: confirmed
- **Evidence**: a generic "No pude conectar tu Instagram. Probá de nuevo." ([instagram-step.tsx:14](../../../frontend/components/onboarding/steps/instagram-step.tsx)); dev mode works only for accepted Instagram testers ([ADR 0028:26](../../decisions/0028-read-instagram-with-our-meta-app.md)); the API is for Instagram professionals, business and creator accounts ([Instagram API with Instagram Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login), read 2026-10-19).
- **Problem**: Many 50+ Owners run a personal Instagram account, and in dev mode every pilot Owner must first accept a tester invite buried in Instagram settings. Both fail at the most hopeful step with "probá de nuevo", which won't help. She skips, loses the import, and Brand Brain quality drops.
- **Recommendation**: Before the button, add a short check, "¿Tu cuenta es profesional?", with a 3-step visual guide to switch for free. Turn OAuth errors into specific copy (not professional, not a tester, refused). For the pilot, send tester invites before sharing the magic link and include a screenshot guide. If she skips, re-offer the connect later in the chat ([open-questions.md:97](../../open-questions.md)).
- **Impact**: Higher connect rate, which means better voice and photos for every later Post.
- **Verifier note**: The callback collapses every failure (refusal, `InstagramError`) into `connected=0`. [open-questions.md:92](../../open-questions.md) also confirms dev mode works only for accepted testers. Whether Meta's flow offers a personal-to-professional switch could not be confirmed. The tester-invite step for pilot Owners is the concrete must-do.
- **Related**: [FE-5](frontend.md)

### PRD-14: Failure UX and capability promises don't match what's built

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**: `PostFailed` gets no buttons ([events.py:247-266](../../../backend/app/conversation/events.py)) while [user-flows.md:283](../../product/user-flows.md) promises [Reintentar]; a second request while one is generating is refused, not queued ([maker.py:179](../../../backend/app/posts/maker.py)); the fallback says it understands "fotos y videos" ([messages_es.py:15-17](../../../backend/app/copy/messages_es.py)); a video becomes kind `other`, unsupported ([kapso_webhook.py:63-64](../../../backend/app/channels/kapso_webhook.py)); the role claims Reels and a weekly Content plan with no tool behind them ([orchestrator.md:3](../../../backend/app/conversation/prompts/orchestrator.md)); the welcome promises "planear" ([messages_es.py:62-63](../../../backend/app/copy/messages_es.py)).
- **Problem**: Owners send two Products in a row and get "esperá". A failed generation needs typing instead of a tap. Sending a workshop video, her most natural content, gets a message claiming videos work (corrected by the reviewer: only on the fallback path, see below). The model is told it does Reels and weekly plans, so it may promise them and then fail.
- **Recommendation**: Add [Reintentar] on `PostFailed`, drop "Reels" from the Orchestrator role line, and fix the `UNSUPPORTED_MEDIA` fallback text. Queue one follow-up request per sender, or at least have the model re-offer it when the first finishes.
- **Impact**: Fewer dead ends and broken promises in the first week of use; cheap.
- **Verifier note**: `maker._start` refuses with `generation_in_progress`, and `GENERATION_BUSY` even reads as if it will queue. Correction: `UNSUPPORTED_MEDIA` ("fotos y videos") is only the fallback sent when the LLM turn fails ([events.py:299](../../../backend/app/conversation/events.py)); the normal path follows [events.md:12](../../../backend/app/conversation/prompts/events.md), which correctly says text, Voice notes and photos. So a video does not normally get a message claiming videos work. A plain-text weekly plan is within what the model can do without a tool, so "planear" is less of a broken promise than Reels.
- **Related**: [AIQ-16](ai-quality.md), [GAP-13](cross-cutting-gaps.md)

### PRD-15: Hashtag rules go over Instagram's 5-hashtag cap

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**: "hashtags: 5 to 10" ([draft.md:6](../../../backend/app/posts/prompts/draft.md)); "10 to 20" ([brand_strategist.md:30](../../../backend/app/agents/prompts/brand_strategist.md)); already flagged and still open ([open-questions.md:40](../../open-questions.md)); Posts with hashtags got fewer views, capped at 5 ([instagram-content-trends.md:26](../instagram-content-trends.md)); Instagram caps posts and reels at 5 hashtags since December 2025 ([Social Media Today](https://www.socialmediatoday.com/news/instagrams-implementing-new-limits-on-hashtag-use/808309/), read 2026-10-19).
- **Problem**: Captions with 6–10 hashtags may be rejected or cut by Instagram, untested through Zernio. Hashtags no longer add reach, while keyword-rich first lines help search. The current rule makes Posts look spammy and "AI".
- **Recommendation**: Close the open question: at most 3–5 hashtags (keep the Owner's own from the import), a keyword-rich first line with the Product and the place ("Mesa de roble maciza en Montevideo"), and a validator in `drafts.py` that trims to 5. The Brand Brain stores at most 8 candidates.
- **Impact**: Prevents publish failures and improves reach and search; a prompt and validator change.
- **Verifier note**: Social Media Today, 18 December 2025 (checked): Instagram "will gradually update the number of hashtags… for a reel or post to five". No source confirms whether the Graph API or Zernio rejects or trims captions with more than 5, so "may be rejected" is correctly hedged.
- **Related**: [AIQ-3](ai-quality.md), [AIQ-14](ai-quality.md), [AIQ-15](ai-quality.md)

### PRD-16: "Cambiá la 3" regenerates the whole Carousel (Slide redo is Must but not wired)

- **Severity**: medium · **Effort**: S (reviewer: M) · **Confidence**: high · **Verified**: adjusted
- **Evidence**: success criterion 6 and F4.9 say to redo only that Slide ([mvp.md:16,78](../../product/mvp.md)); `revise_post(part='images')` rebuilds every image ([maker.py:131-157](../../../backend/app/posts/maker.py)); `part` is `caption|images`, with no Slide index ([tools.py:121-129](../../../backend/app/conversation/tools.py)); `CarouselGenerator.redo` exists ([generator.py:65](../../../backend/app/carousel/generator.py)) but only the maker's generate path is called (maker.py:325).
- **Problem**: Changing one Slide of a 5–10-Slide design costs 5–10 new images (US$0.25–0.50+), the full multi-minute wait, and a design against the daily cap, and the other Slides change too. The Owner liked them and loses them. Photos-style Posts also can't drop or reorder one photo without a full remake (partly corrected by the reviewer, see below).
- **Recommendation**: Keep the scenes, copy and brief on the Post (in Storage or the DB, per PRD-2), add `slides: [int]` to `revise_post`, and call `redo` plus a re-render for those indexes only. Effort M, not S.
- **Impact**: Revisions become 3–10× cheaper and faster, and the Owner's sense of control improves.
- **Verifier note**: `CarouselGenerator.redo` is called only from tests. The cost per redo is right (US$0.0504 per 2K Slide). Effort is understated: `Post` stores only the rendered JPEGs, headlines and `style_prompt`, not the text-free scenes, `CarouselCopy` or `CarouselBrief` that `redo()` needs (it anchors on the cover scene and re-renders text over scenes), so persisting those comes first (ties to PRD-2). Minor correction: photos-style Posts can already drop a photo via `create_post` with `replaces` and fewer `asset_ids`, which generates no images, only a new caption.
- **Related**: [AIQ-7](ai-quality.md), [COST-6](unit-economics.md), [MOD-6](models.md)

### PRD-17: New: customer-photo testimonial Posts and review requests, using what she already gets in WhatsApp

- **Severity**: low · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: the persona lives in WhatsApp with clients all day ([PRODUCT.md:11](../../../PRODUCT.md)); Slides use code templates ([ADR 0029](../../decisions/0029-designed-slides-ai-scene-code-layout.md)), and a quote card was among the first templates ([mockups README](../../design/mockups/README.md), row 4); Zernio supports listing and replying to Google Business Profile reviews ([Zernio platforms](https://docs.zernio.com/platforms), read 2026-10-19).
- **Problem**: Furniture customers send "así quedó en casa 😍" photos and thank-you messages to the Owner on WhatsApp. That is the most credible content a small Business has, and Neitor has no path for it. Neitor also never helps collect Google reviews, which drive local search.
- **Recommendation**: Low priority. Add a testimonial angle to the drafter prompt with a consent question. Defer the template and the Google review features until after the pilot.
- **Impact**: High-trust content at almost no generation cost (no AI image), plus a reason to talk to Neitor after every sale.
- **Verifier note**: Partly possible today: the Owner can forward a customer photo and ask for a Post in "photos" style, which uses the real photo with no AI image. The new pieces are a quote or testimonial template (`Tpl-quote-card` exists only as a superseded mockup), the customer-consent prompt ([conversation-design.md:24](../../product/conversation-design.md) already considers "whether a client can be named") and a Google review-request message. Zernio's docs list Google Business Profile in its reviews table, but the support checkmarks weren't readable, so review replies are unverified. A nice-to-have before the core loop is proven.

### PRD-18: New: Stories, plus a vertical copy "para tu estado" of WhatsApp

- **Severity**: low · **Effort**: M · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: F4.7 Stories is Won't ([mvp.md:76](../../product/mvp.md)); Stories are in Phase 1 with "publishing support through Zernio to verify" ([roadmap.md:17](../../roadmap.md), [open-questions.md:84](../../open-questions.md)); Zernio lists Instagram Feed, Stories, Reels and Carousels publishing ([Zernio platforms](https://docs.zernio.com/platforms), read 2026-10-19).
- **Problem**: Small shops post day-to-day updates (hours, "nuevo ingreso", "hoy abrimos el taller") as Stories and WhatsApp Status, not as feed Posts. The roadmap holds Stories back to verify Zernio support, which Zernio's docs now list.
- **Recommendation**: Record in the roadmap and open questions that Zernio supports Instagram Stories, and keep Stories as a Phase 1 item after the core loop. A vertical "para tu estado" export is a cheap experiment.
- **Impact**: Raises posting frequency at low effort and adds a WhatsApp-native touchpoint the persona already uses.
- **Verifier note**: Zernio's platform docs (checked) list Instagram "Feed, Stories, Reels, Carousels", so that open point can be closed. Building a 1080×1920 template family plus `format=story` is real work (M) for an ephemeral format; the WhatsApp Status copy is a cheap add-on. Plausible but lower priority than PRD-1, PRD-2, PRD-3 and PRD-16.

### PRD-19: New: Reels from the Owner's own videos (her most natural content is rejected today)

- **Severity**: medium · **Effort**: M · **Confidence**: medium · **Verified**: confirmed
- **Evidence**: F4.8 is Could ([mvp.md:77](../../product/mvp.md)); Reels are the product direction ([ADR 0012](../../decisions/0012-catalog-content-dashboard-reels.md)); video is mapped to unsupported ([kapso_webhook.py:63-64](../../../backend/app/channels/kapso_webhook.py)); Reels for reach, raw over polished ([instagram-content-trends.md:76-78](../instagram-content-trends.md)); Zernio's video scheduling includes Reels ([Zernio pricing](https://zernio.com/pricing), read 2026-10-19).
- **Problem**: Workshop and finished-piece videos are what Owners have on their phones, and Reels are Instagram's reach format. Today a video gets "no lo entiendo".
- **Recommendation**: Reels v1 as in ADR 0012: accept WhatsApp video (3–90 s), store it in Storage, pick a cover frame with ffmpeg, write a hook caption, keep the same Approval flow, and publish through Zernio. Before-and-after slideshow Reels (roadmap v2) later. Tier: Basic, or the "Reels" upsell the roadmap leaves unpriced.
- **Impact**: Gets Owners into the format with the most reach, using content they already have, with no AI video costs.
- **Verifier note**: ADR 0012 sets Reels v1 as the Owner's own unedited video, and roadmap Phase 1 lists it. The 3–90 s window matches [mvp.md:125](../../product/mvp.md) ("Zernio's Reel cap"). Correctly framed as an already-planned item. It depends on Storage (PRD-2) and ffmpeg in the container.

### PRD-20: New: cross-post to Facebook and publish Google Business Profile updates and offers through Zernio

- **Severity**: low · **Effort**: M · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: F5.4 Facebook cross-post is Could ([mvp.md:87](../../product/mvp.md)); Facebook is in Phase 3 ([roadmap.md:34](../../roadmap.md)); Zernio supports Facebook images, Reels and Page posts, and Google Business Profile updates, photos, offers and events ([Zernio platforms](https://docs.zernio.com/platforms), read 2026-10-19); US$6 per account for accounts 3–10 and US$3 for 11–100 ([Zernio pricing](https://zernio.com/pricing), read 2026-10-19).
- **Problem**: Many of a 50+ Owner's customers are on Facebook, and "mueblería en Montevideo" searches land on Google Business Profile. The same approved Post could go to both with one extra tap, but the product is Instagram-only.
- **Recommendation**: Revisit after PRD-1 and the pilot. Facebook cross-post (F5.4) first, since the same Zernio connection flow applies. Price the extra Zernio accounts into unit economics.
- **Impact**: More reach per Approval at almost no extra creation cost; makes the subscription feel like a multi-channel agency.
- **Verifier note**: Facts check out. But it is fully blocked on PRD-1 (per-Business accounts), adds per-network account cost and connect friction for the Owner, and is a Phase 3 item. Low for a pre-PMF pilot.

### PRD-21: Shape Pro as "your inbox, in your WhatsApp" with the Owner in the loop, not autonomous DM replies

- **Severity**: medium · **Effort**: L · **Confidence**: medium · **Verified**: confirmed
- **Evidence**: Pro is replies to comments and DMs, sale alerts and a results summary, on a waitlist ([ADR 0031:18,24](../../decisions/0031-pricing-free-basic-pro.md)); Pro features are planned through Neitor's own Meta app with Instagram Login, and App Review is needed once accounts outside the team connect ([roadmap.md:11,26](../../roadmap.md)); Meta Business Agent went GA in June 2026 and answers customers ([competitive-landscape.md:7](../competitive-landscape.md)); Agenteala starts at US$49 a month ([competitive-landscape.md:28](../competitive-landscape.md)); the comments and DMs inbox is included, and the first 10,000 DMs a month are free ([Zernio pricing](https://zernio.com/pricing), read 2026-10-19); `instagram_business_manage_comments` and `_messages` scopes ([Instagram API with Instagram Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login), read 2026-10-19).
- **Problem**: Autonomous replies to customers are the riskiest feature (wrong prices or stock in public, brand damage). They also need App Review on Neitor's own app, and Meta Business Agent plus LatAm sales bots already compete there at about US$49. Pro risks staying a waitlist with no differentiator.
- **Recommendation**: Pro v1: Neitor forwards new Instagram comments and DMs to the Owner on WhatsApp with a suggested reply and [Responder] [Editar] [Ignorar] buttons, keeping the Owner in the loop, consistent with [ADR 0007](../../decisions/0007-approve-every-post.md). Auto-reply only for FAQs she approved once. "Alerta de venta": classify purchase intent (precio, envío, ¿tienen?) and send an alert. Build it on Zernio's inbox to skip App Review for the pilot. Add a deeper monthly results report (PRD-11). Treat alerts outside the window as template cost.
- **Impact**: Gives Pro a defensible, low-risk wedge (Owner-facing, which matches the positioning) that can ship in weeks instead of after App Review.
- **Verifier note**: Zernio pricing (checked): every account includes "inbox (comments + DMs)", received DMs are free, and the first 10,000 sent DMs a month are free. An Owner-in-the-loop draft-and-approve design fits ADR 0007. Caveat: building on Zernio's inbox requires each Owner's Instagram connected to Zernio, so it depends on PRD-1. It is a strategy proposal rather than a defect; medium is fair.
- **Related**: [GRW-7](growth-pricing-market.md), [GAP-3](cross-cutting-gaps.md)

### PRD-22: No undo after publishing ("borralo")

- **Severity**: low · **Effort**: S · **Confidence**: low · **Verified**: adjusted
- **Evidence**: `PublisherPort` has `ensure_profile`, `connect_url` and `publish`, and no delete ([base.py:30-43](../../../backend/app/publishing/base.py)); Meta added an endpoint to delete posts, stories and reels, via the Instagram API with Facebook Login ([Meta developer blog, 2025-12-03](https://developers.facebook.com/blog/post/2025/12/03/instragram-api-updates/), read 2026-10-19).
- **Problem**: Approval prevents most mistakes, but a typo or wrong price seen after publishing has no fix inside WhatsApp. She has to open Instagram and find the delete option, which defeats "you stay in control".
- **Recommendation**: First verify whether Zernio can delete a published Instagram Post on an Instagram Login connection. Only then add delete to `PublisherPort` and a confirmed "borralo" intent. Otherwise, reply with step-by-step instructions to delete it in the app.
- **Impact**: Trust and a safety net for a fear-driven persona.
- **Verifier note**: The Meta blog (checked) says the media deleting API "is available through the Instagram API with Facebook Login". Neitor uses Instagram Login for its own app and Zernio for publishing, so the Graph route is not available as built, and Zernio's docs don't say whether deleting a published Post is supported. Feasibility is unverified; the low confidence is warranted.

### PRD-23: New: let staff send photos and Voice notes for the Owner to approve

- **Severity**: low · **Effort**: M · **Confidence**: medium · **Verified**: confirmed
- **Evidence**: the Business has 2–4 employees ([PRODUCT.md:11](../../../PRODUCT.md)); multiple users per Business are out of scope ([mvp.md:131](../../product/mvp.md)); `owner_phone` is unique, one phone per Business ([0001_initial.sql:24](../../../backend/migrations/versions/0001_initial.sql)).
- **Problem**: The workshop staff take the best "en proceso" photos, but only the Owner's phone can talk to Neitor, so material arrives late or never.
- **Recommendation**: Add a `business_members` table (phone, role contributor). Contributors can send material and requests; only the Owner's phone approves, and she is notified to approve. Tier: Pro.
- **Impact**: More and fresher material, and it moves Neitor toward a team tool. Low priority until the pilot proves the core loop.
- **Verifier note**: `uq_businesses_owner_phone` enforces one phone per Business, and mvp.md's out-of-scope list includes "multiple users per business, team roles". Correctly framed as a later, low-priority idea that keeps Approval with the Owner ([ADR 0007](../../decisions/0007-approve-every-post.md)).
- **Related**: [GAP-8](cross-cutting-gaps.md)

### PRD-24: New: a price-list photo or PDF becomes Products and a "lista de precios" Post

- **Severity**: low · **Effort**: M · **Confidence**: medium · **Verified**: confirmed
- **Evidence**: F8.8 is Could ([mvp.md:122](../../product/mvp.md)); documents are mapped to unsupported ([kapso_webhook.py:63-64](../../../backend/app/channels/kapso_webhook.py)); a `numbers` family exists for list-style Slides ([numbers.tsx](../../../frontend/lib/post-render/families/numbers.tsx)).
- **Problem**: Owners have price lists as PDFs or photos. Today only up to 5 Products enter through the wizard, so the agents rarely know prices and the Owner must retype them.
- **Recommendation**: Accept a PDF or image document and extract Products with Gemini. Read them back for confirmation ("¿Las guardo así?"), then offer a design Carousel in the `numbers` family as a price list. Tier: Basic.
- **Impact**: A richer Catalog leads to better and more accurate Posts; moderate value.
- **Verifier note**: [user-flows.md](../../product/user-flows.md) lists documents under `unsupported_media` with this Could noted. Correctly framed as a planned Could with moderate value.

## Improve what exists

Ranked by impact against effort, from the audit synthesis ([summary.md](summary.md)). Costs are estimates; the model behind them is in [unit-economics.md](unit-economics.md).

| Feature | Why for the persona | Tier | Effort | Ids |
|---|---|---|---|---|
| Targeted revisions (text-only re-render, one-Slide redo) | "Cambiale el título" costs about US$0.47 and a minute today (estimate), and it changes Slides she liked | All | M | [AIQ-7](ai-quality.md), [COST-6](unit-economics.md), [MOD-6](models.md), PRD-16 |
| Offer a concrete first Post after the brand is confirmed | After 10-15 minutes of onboarding she gets a blank "¿En qué te puedo ayudar?" and doesn't know what to ask. This revises F1.10, so the team has to decide | All (activation) | S | PRD-5, [GRW-11](growth-pricing-market.md) |
| Keep photos sent before the wizard is finished | Her natural first move ("me llegó esta mesa") is dropped today | All | S | PRD-5 |
| An honest Spanish landing | The page is in English with US$ prices and a "Hi Neitor" prefill, and it promises scheduling, a weekly plan, 3 options and "your Instagram". A Spanish translation exists but is uncommitted, in a local worktree | All | S | [FE-3](frontend.md), [FE-4](frontend.md), PRD-6, [GRW-14](growth-pricing-market.md), [DOC-3](docs-process.md) |
| Failure UX | No [Reintentar] after a failed Post, a second request is refused, the video reply claims videos work, and photos sent as documents are rejected | All | S | PRD-14, [AIQ-16](ai-quality.md), [GAP-13](cross-cutting-gaps.md) |
| Voice note fallback | She lives in Voice notes. With no transcript she gets "no te entendí" | All | S-M | [AIQ-11](ai-quality.md), [MOD-5](models.md), [BUG-11](bugs-reliability.md) |
| Uruguayan commercial calendar in context | The model is forbidden to guess dates. The furniture research says Día de la Madre is the biggest date and price-led Black Friday may not fit | All | S | PRD-7 |
| Concrete CTAs: sales WhatsApp number and opening hours | Every call to action is a vague "escribinos" | All | S | [GAP-7](cross-cutting-gaps.md) |
| A wizard that works on phone data | The 3 s poll re-downloads images; uploads are raw 10 MB with no timeout; no autosave; tap targets under 48 px | All | S-M | [FE-6](frontend.md), [FE-7](frontend.md), [FE-12](frontend.md), [FE-13](frontend.md), [FE-14](frontend.md) |
| Consent check for photos with people | Customers' or staff's faces can end up in AI ads | All | S | [GAP-4](cross-cutting-gaps.md) |
| Memory across Posts (recent Posts, house style, pillar rotation) | After 10 Posts the hooks and CTAs repeat | Basic | M | [AIQ-17](ai-quality.md), [AIQ-18](ai-quality.md) |
| Alt text on every Post | Slide text lives only in the pixels | All | S | [GAP-5](cross-cutting-gaps.md) |
| Optional AI-scene disclosure, plus a record of which images are AI | Speaks to the "parece fake" fear, and to Ley 17.250 on misleading advertising | All | S | [GAP-6](cross-cutting-gaps.md) |

## New features

From the audit synthesis ([summary.md](summary.md)), in the synthesis's order.

| Feature | Why for the persona | Tier | Effort | Ids |
|---|---|---|---|---|
| Scheduling end to end (`scheduledFor` and timezone, webhooks, cancel, utility templates) | She's in the workshop at 19:00, and Basic sells scheduling | Basic | M | PRD-10, [GAP-11](cross-cutting-gaps.md) |
| Monday plan plus inactivity and commercial-date nudges (at most 2 a week, with a pause option) | Neitor is 100% reactive, which repeats her habit of abandoning Instagram. Needs templates (PRD-3) | Basic, with a Free teaser | M | PRD-9, [GRW-10](growth-pricing-market.md) |
| Results summary from Zernio analytics | She can't tell whether the US$29 works. Needs an ADR amending [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md) | Basic | M | PRD-11 |
| Demand capture (`request_feature`, a "Quiero Pro" prefill) | The pilot's best roadmap signal is lost today | All | S | [AIQ-20](ai-quality.md), [FE-17](frontend.md), [GRW-9](growth-pricing-market.md) |
| Reels v1 from her own videos | Workshop videos are what she has on her phone, and Reels are the reach format | Basic / Pro | M | PRD-19 |
| Pro v1: "your inbox in your WhatsApp" (comments and DMs forwarded with a suggested reply and [Responder] [Editar] [Ignorar], plus inquiry alerts) | Keeps the Owner in the loop ([ADR 0007](../../decisions/0007-approve-every-post.md)). Avoids competing with Meta's free agent. Has to fit Meta's 24 h and 7-day windows | Pro | L | PRD-21, [GRW-7](growth-pricing-market.md), [GAP-3](cross-cutting-gaps.md) |
| Testimonial Posts from customer photos, with consent | The most credible content she already receives on WhatsApp | Basic | S | PRD-17 |
| Stories plus a vertical "para tu estado" copy | Day-to-day updates live there, and Zernio supports Instagram Stories | Basic | M | PRD-18 |
| Price-list photo or PDF turned into Products plus a list Carousel | A richer Catalog means accurate prices in Posts | Basic | M | PRD-24 |
| Facebook and Google Business Profile cross-posting | Her customers are on Facebook and search locally. Adds a Zernio account fee | Pro | M | PRD-20 |
| "Borralo" after publishing | A safety net. Check that Zernio can delete first | All | S | PRD-22 |
| Staff contributors (they send material, the Owner approves) | Staff take the best workshop photos | Pro | M | PRD-23, [GAP-8](cross-cutting-gaps.md) |
| Read-only "Tus posts" page | History and permalinks for pilot reviews. Needs T19 first | All | L | [FE-18](frontend.md) |
| Real Takumi brand preview in the wizard | The delight moment would match the real output | All | M | [FE-16](frontend.md) |
| Mercado Libre Catalog import and sale events | Many sellers already keep a structured catalog there. Validate demand first | Pro | L | [GAP-10](cross-cutting-gaps.md) |
| Opt-in voice replies (TTS) | Fits a voice-first persona. After the pilot | All | M | [MOD-17](models.md) |
