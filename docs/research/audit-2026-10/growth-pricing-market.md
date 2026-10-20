# Growth, pricing and market

This doc covers Neitor AI's positioning against competitors, its pricing and packaging, the go-to-market channels for the persona, the retention and attribution loops, and the market and platform risks. It is part of the 2026-10-19 audit (index in [README.md](README.md), cross-dimension synthesis in [summary.md](summary.md)); the code was read at commit `dc0bc01`. An independent adversarial reviewer checked each finding against the code and the cited sources. "Adjusted" means the reviewer corrected its severity or details; the severity and recommendation shown here already include those corrections. Because much of this dimension is strategy, each finding has a **Basis** line saying which parts are evidence and which are hypotheses.

## Summary

- **The positioning is still differentiated in Uruguay, but the moat claim in the docs is out of date.** Neitor is a marketing Agency inside WhatsApp, in Rioplatense Spanish, that publishes only after the Owner's Approval. [Postou.ai](https://postou.ai/) in Brazil already runs the same WhatsApp loop (Voice note in, art and caption back, approve, auto-publish) at R$49 for 12 Posts and says it serves 30,000+ businesses (vendor claim, read 2026-10-19). Google's Pomelli is free in 170+ countries, though English-only and with no publishing. Meta's Business Agent now briefs owners on WhatsApp, and Meta says it will later add market research and competitive intelligence, which makes Meta the Channel, the publishing target and a competitor at once (GRW-4, GRW-18).
- **The headline price is fine; packaging and economics are the weak spots.** US$29 sits between DIY tools (free to about US$32) and a freelance community manager (US$80–150 a month junior in Argentina; more in Uruguay is a hypothesis). But there are no Post caps, the Free tier isn't enforced, prices are in USD without IVA, there is no annual plan, and Pro sells DM replies, which Meta is commoditizing (GRW-3, GRW-5, GRW-6, GRW-7, GRW-13).
- **Growth is blocked first by engineering facts.** The CTA points at the shared Kapso sandbox number, every Post publishes to one demo Instagram account, Posts live in memory, no events are logged, and the first WhatsApp message (where an ad or referral source would arrive) is discarded. A pilot can't measure activation, approval rate or retention (GRW-1, GRW-2, GRW-9).
- **The best-CAC path for this persona** (hypothesis) is founder-led concierge onboarding of the curated furniture list, then click-to-WhatsApp ads (which open Meta's 72-hour free messaging window), then accountants, suppliers, ADIMAU, and freelance community managers as resellers (GRW-8, GRW-15).
- **Vertical packs** (niche, calendar and templates) are the scalable unit for expansion: Argentina next, Mexico after, Brazil last (GRW-12, GRW-17).

## Findings at a glance

Effort: S is under half a day, M is 1-2 days, L is about a week, XL is more than a week.

| Id | Severity | Effort | Finding |
|---|---|---|---|
| GRW-1 | high | M | The pilot can't measure anything: Posts are in memory and no events are logged |
| GRW-2 | high | L | The funnel is closed: the CTA is the Kapso sandbox and every Post publishes to one demo Instagram account |
| GRW-4 | high | S | The competitive "gap" in the docs is outdated: a WhatsApp-native Post agent already exists (Postou.ai), and Pomelli and Meta are closing in |
| GRW-3 | medium | S | Free-tier and plan limits aren't enforced; one free Owner could cost about US$50 a month |
| GRW-5 | medium | S | Basic and Pro have no Post limits or add-ons: package by volume and price against unit cost |
| GRW-6 | medium | M | Price in pesos with IVA included and collect through Mercado Pago Suscripciones inside WhatsApp (Stripe can't serve Uruguay) |
| GRW-7 | medium | S | Pro's headline features (comment and DM replies) are being commoditized by Meta Business Agent: reposition Pro around results |
| GRW-8 | medium | M | GTM: rank channels by CAC for a 50-something, phone-first Owner, starting with founder-led concierge and click-to-WhatsApp ads |
| GRW-9 | medium | S | No attribution and no referral loop: the first message is discarded and every CTA is identical |
| GRW-10 | medium | M | No retention loop: proactive messages are "Won't", so the product only works when the Owner remembers it |
| GRW-11 | medium | S | Activation: after the brand is confirmed, offer a concrete first Post instead of an open question |
| GRW-12 | medium | M | Vertical packs don't scale yet: one global furniture Niche Report feeds every Business |
| GRW-14 | medium | S | The Owner-facing landing is in English and built for judges; add a Spanish page for Owners |
| GRW-18 | medium | L | Moats and platform risk: Meta is the Channel, the publishing target and a competitor |
| GRW-19 | medium | S | WhatsApp service messages are billed since 2026-10-01: each Carousel Slide is a paid message once past 1,000 a month per number |
| GRW-13 | low | S | Add an annual plan, founding-customer pricing and a reverse trial |
| GRW-15 | low | L | Turn the real competitor, freelance community managers, into a channel with an agency plan |
| GRW-16 | low | S | Free tier as a growth loop: an opt-in "Hecho con Neitor" credit and a share prompt after publishing |
| GRW-17 | low | L | Expansion order: Argentina next, then Mexico; Brazil last |

## Market and cost numbers

### Competitive price map

Prices read 2026-10-19. Where the auditor recorded only a site name and no URL, the source is shown as inline code.

| Alternative | Price a month | Volume and notes | Source |
|---|---|---|---|
| Neitor | Free / US$29 / US$49 | Free = 3 Posts; Basic and Pro uncapped | [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md) |
| Postou.ai (Brazil, WhatsApp-native) | R$49 / R$99 / R$149 | 12 / 35 / 80 Posts; R$0.99 3-day trial; claims 30k businesses (vendor claim) | [postou.ai](https://postou.ai/) |
| Predis.ai | ~US$32 Core (sources conflict, US$19–32) | Dashboard | [admakeai.com](https://admakeai.com/alternatives-to/predis-ai/pricing) |
| Sintra | US$97 monthly, US$54 a month annual | 250 credits | [eesel.ai](https://www.eesel.ai/blog/sintra-ai-pricing) |
| Metricool | Free (20 Posts) / €16+ | Scheduler with AI | [socialk.it](https://socialk.it/es/pricing/metricool) |
| Canva Pro | ~US$13–18 (sources conflict) | DIY | `spendfigo`, `miracamp` (no URL recorded) |
| Google Pomelli | Free (beta, 300 images a month) | English-only, no publishing | [aihola.com](https://aihola.com/article/pomelli-expands-170-countries) |
| Meta Business Agent | Free to start, then US$2 per 1M tokens; subscriptions coming | Customer-facing, plus an owner briefing | [whatsappbusiness.com](https://whatsappbusiness.com/blog/introducing-meta-business-agent-ai/), [zernio.com](https://zernio.com/blog/meta-business-agent-pricing) |
| ChatGPT Go (Uruguay) | US$7.50 (~$U 300) at launch | Generic | `elobservador.com.uy` (no URL recorded) |
| Freelance community manager (Argentina), 1 network | US$80–150 junior / 180–350 senior / 350–800 agency | 12 Posts plus DM replies | [tarifario.info](https://tarifario.info/redes-sociales/) (September 2026) |
| Community manager employee (Uruguay), junior | UYU 35–45k (~US$870–1,120) | Salary | `coderhouse.com` (no URL recorded) |

### Estimated variable cost per Basic Owner

A hypothesis for 12 Posts a month, to validate once GRW-1 metering exists. The full cost model is in [unit-economics.md](unit-economics.md).

| Line | US$ a month (estimate) |
|---|---|
| Images (6 single × ~US$0.06 + 6 Carousels × ~US$0.35, × 1.5 for redos) | ~3.7 |
| Text LLM (`gemini-3.8-flash`; its price doubles on 2027-01-01 per [gemini-api.md:33](../gemini-api.md)) | ~0.5–1.5 |
| WhatsApp service messages (~200 × ~US$0.008, past 1,000 per number) | ~1.6 |
| Zernio publishing (accounts 3–10) | 6.0 |
| Kapso Pro (US$25, shared) plus payment fees (~5%) | ~1.5–2.5 |
| **Total** | **~13–15**: about 50% gross margin at US$29; about 40% at $U 1,190 with IVA included (~US$24 net); about 65–70% once publishing moves to Neitor's own Meta app |

The reviewer found the total plausible only with Zernio's US$6 per account included, and recomputed image cost at about US$3, LLM at about US$1 and WhatsApp at about US$2–3 a month (GRW-5, GRW-19).

### Proposed packaging

A hypothesis to test in the pilot; any change to the plans needs an ADR revising [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md).

| Plan | Price (IVA included) | Posts a month | Notes |
|---|---|---|---|
| Gratis | $U 0 | 3 | Opt-in "Hecho con @neitor.ai" caption credit (GRW-16); reverse trial of 14 days of Básico |
| Básico | $U 1,190 a month, $U 11,900 a year | 12 | Weekly plan, scheduling; founder price $U 990 locked for 12 months |
| Pro | $U 1,990 a month | 30 | Reels, Insights summary, attribution, multiple accounts, sale alerts |
| Extra pack | $U 290 | +5 | Sold in the chat when the quota runs out |
| Agencia (later) | ~60% of Básico per Business | Per Business | For community managers |

Exchange rate: US$1 = UYU 40.24 ([Infobae, 2026-08-06](https://www.infobae.com/noticias/2026/08/06/dolar-hoy-en-uruguay-cotizacion-de-cierre-del-6-de-agosto/), read 2026-10-19).

## Findings

### GRW-1: The pilot can't measure anything: Posts are in memory and no events are logged

- **Severity**: high · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**: `InMemoryPosts` keeps "Posts sent to the Owner ... until T19 moves them onto `posts`" ([store.py:63-64](../../../backend/app/posts/store.py)); a `posts` table with `approved_at`, `published_at` and `revision` exists but no code writes to it ([0001_initial.sql:168](../../../backend/migrations/versions/0001_initial.sql)); an `agent_runs` table with tokens and latency exists, and nothing in `backend/app` writes to it (0001_initial.sql:301); the daily design counter is an in-process dict ([maker.py:106](../../../backend/app/posts/maker.py)); the roadmap says "log every correction the owner makes", and its success metric is self-reported "hours per week" ([roadmap.md:9,21](../../roadmap.md)); "No customers, testimonials, metrics" ([PRODUCT.md:48](../../../PRODUCT.md)).
- **Basis**: evidence.
- **Problem**: Phase 1's whole purpose is to learn from real Owners, but every Post, Approval, revision, discard and publish lives in an in-memory store that a deploy or restart wipes. There is no event log, and per-call cost (`usage`) only goes to log lines. So the team can't compute activation, weekly active Owners, approval rate, revision rate, cost per approved Post or retention. Without them, pricing ([ADR 0031](../../decisions/0031-pricing-free-basic-pro.md)) and churn can't be validated, and there is no evidence for investors. The roadmap's success metric ("hours per week" saved) is self-reported and can't be instrumented.
- **Recommendation**: Persist Posts (T19), add an append-only events table, write `agent_runs` from `llm/client.py` and `imagegen`, and add a weekly metrics view. `conversation_steps` cannot serve as the log because compaction deletes rows. Treat this as a pre-pilot prerequisite (high), not critical.
- **Impact**: Without this, a 2–4 week pilot yields anecdotes only. With it, the team can decide pricing caps, the Free tier's size and model spend with data, and SMB SaaS benchmarks of 2–5% monthly churn (vendor sources) become something to measure against.
- **Verifier note**: Nothing in `backend/app` writes `posts`, `post_revisions` or `agent_runs`; per-call usage only reaches log lines ([client.py:245-253](../../../backend/app/llm/client.py), [gemini.py:121](../../../backend/app/imagegen/gemini.py)). Missed by the auditor: `conversation_steps` is persisted ([ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md), `DbHistory`) and holds system-event lines ("[post ... approved]", "[post ... published]"), but it is not usable as an event log because compaction deletes old rows ([history.py:129](../../../backend/app/conversation/history.py)). Not critical: the product is pre-pilot, T19 is already planned, and nothing a real pilot depends on is lost yet.
- **Related**: [PRD-2](product.md), [ARCH-1](backend-architecture.md), [BUG-5](bugs-reliability.md), [OPS-1](platform-ops.md), [FE-8](frontend.md), [DOC-9](docs-process.md), [COST-1](unit-economics.md)

### GRW-2: The funnel is closed: the CTA is the Kapso sandbox and every Post publishes to one demo Instagram account

- **Severity**: high · **Effort**: L · **Confidence**: high · **Verified**: adjusted
- **Evidence**: the CTA is the shared Kapso sandbox number, "which only answers phones with an active sandbox session" ([PRODUCT.md:36](../../../PRODUCT.md)); "Every Business in the demo publishes to the same Instagram account" ([ADR 0024:15,21](../../decisions/0024-mvp-single-demo-instagram-account.md)); one `ZERNIO_ACCOUNT_ID` from env ([config.py:56-62](../../../backend/app/config.py)); production needs Business Verification, an own number and templates, and App Review for `instagram_business_basic` has not started ([open-questions.md:18,92](../../open-questions.md)); App Review and Business Verification sit in Phase 2 ([roadmap.md:26](../../roadmap.md)).
- **Basis**: evidence.
- **Problem**: No Owner who finds Neitor organically, from an ad or from a referral can start, and a real pilot Owner's approved Post would go to the demo account, not hers. Every GTM channel below (click-to-WhatsApp ads, referrals, partners) depends on a production WhatsApp number, per-Business Instagram connections and Meta App Review. Meta Business Verification and App Review have multi-week lead times that sit on the critical path.
- **Recommendation**: For the pilot: (a) move a production WhatsApp number via Kapso (Kapso Free includes 1 connected number) into Phase 1, with a payment method on file; (b) expose Zernio `ensure_profile` / `connect_url` per Business and read ids from `social_accounts` (ADR 0024's own reversal path), budgeting US$6 per account for accounts 3–10; (c) add pilot Owners as Instagram testers for the import. Start Business Verification and App Review for `instagram_business_basic` now, in parallel, because of their lead time. Request `content_publish` only if publishing moves off Zernio.
- **Impact**: This is the hard gate on the first paying customer. Every week of delay to verification and App Review pushes revenue back a week.
- **Verifier note**: `ensure_profile` and `connect_url` exist but nothing exposes them. Overstated parts: (1) per-Business publishing through Zernio does not need Neitor's own App Review, since Zernio's Meta app is already reviewed; it is unblocked by exposing `connect_url` and paying about US$6 per account ([social-publishing-apis.md:23](../social-publishing-apis.md)). (2) App Review for `instagram_business_basic` gates only the [ADR 0028](../../decisions/0028-read-instagram-with-our-meta-app.md) import, and pilot Owners can be Instagram testers in dev mode meanwhile; `instagram_business_content_publish` is needed only if publishing leaves Zernio. (3) Third-party sources the reviewer read (no URL recorded) say Business Verification is not required to run a production Cloud API number; an unverified account is limited to about 250 business-initiated conversations a day, so it is not a hard gate for a small pilot. (4) A single-Owner Phase 1 pilot ([roadmap.md:7](../../roadmap.md)) can point `ZERNIO_ACCOUNT_ID` at that Owner's account. A known, documented limitation rather than a discovery; high because it gates any multi-Owner pilot and all GTM.
- **Related**: [PRD-1](product.md), [PRD-3](product.md), [BUG-1](bugs-reliability.md), [ARCH-4](backend-architecture.md), [SEC-2](security-privacy.md), [GAP-1](cross-cutting-gaps.md)

### GRW-3: Free-tier and plan limits aren't enforced; one free Owner could cost about US$50 a month

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**: the free cap "must be enforced in the backend once billing exists" ([ADR 0031:25](../../decisions/0031-pricing-free-basic-pro.md)); `plan` and `monthly_post_quota` are "future billing, not enforced" ([0001_initial.sql:20-21](../../../backend/migrations/versions/0001_initial.sql)); the `Business` ORM model doesn't map them ([models.py:24-46](../../../backend/app/db/models.py)); the only cap is 5 designs a day per sender, in memory, reset on restart ([config.py:44](../../../backend/app/config.py), [maker.py:186-191](../../../backend/app/posts/maker.py)); about US$0.30–0.40 per 5-Slide Carousel ([ADR 0022:31](../../decisions/0022-carousels-in-mvp.md)); Zernio US$6 a month per account for accounts 3–10 ([social-publishing-apis.md:23](../social-publishing-apis.md)).
- **Basis**: evidence for the code; the cost figures are estimates from ADR numbers.
- **Problem**: The landing promises "Up to 3 posts or carousels a month", but the only guard is 5 designs a day, kept in a dict that a deploy resets. That allows about 150 designs a month per Owner, or roughly US$45–60 in image generation alone for a heavy free user (estimate), before LLM and WhatsApp costs. With per-Business Zernio connections, each free Owner who connects Instagram also takes a paid US$6-a-month publishing slot. Opening click-to-WhatsApp ads or referrals to an uncapped free tier is a cost risk.
- **Recommendation**: Before the production number opens to the public: map `plan` and `monthly_post_quota`, change the default to 3 for Free, count a Post when it is sent, enforce the quota from the DB, and add a Spanish quota-reached message with an upgrade path. Decide whether Free Owners get a Zernio slot (US$6 a month) or a download-to-post fallback.
- **Impact**: Caps the cost of each free user at about US$1–2.5 a month (estimate), and makes Free a safe acquisition channel to put ad spend behind.
- **Verifier note**: Nothing reads `plan` or `monthly_post_quota`. The only guard is the in-process dict ([maker.py:186-195](../../../backend/app/posts/maker.py)), and remakes also count. Missed detail: the DB default for `monthly_post_quota` is 30 (0001_initial.sql:21), not the advertised 3, so mapping the column alone would be wrong. The US$45–60 is a worst case that assumes every one of 150 designs is a 5-Slide Carousel at ADR 0022's US$0.30–0.40; single-image Posts cost about US$0.05–0.06. Today the public cannot reach Neitor (GRW-2), and ADR 0031:25 already defers enforcement to billing, so this is a launch prerequisite, not a live exposure.
- **Related**: [PRD-12](product.md), [COST-2](unit-economics.md), [ARCH-5](backend-architecture.md), [BUG-9](bugs-reliability.md), [SEC-4](security-privacy.md)

### GRW-4: The competitive "gap" in the docs is outdated: a WhatsApp-native Post agent already exists (Postou.ai), and Pomelli and Meta are closing in

- **Severity**: high · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**: "No result described an assistant that takes the owner's instructions over WhatsApp and acts for the business" ([competitive-landscape.md:45](../competitive-landscape.md)); "The gap" ([competitors.md:29](../../competitors.md)); Postou.ai, "Seu designer de Instagram no WhatsApp": Voice note to art, caption and hashtags, approve or change in WhatsApp, "O post vai direto pro seu Instagram — feed e stories", R$49 for 12 Posts, R$99 for 35, R$149 for 80, R$0.99 for 3 days, claims 30,000+ businesses ([postou.ai](https://postou.ai/), read 2026-10-19, vendor claim); Pomelli in 170+ countries since March 2026, free in beta ([aihola.com](https://aihola.com/article/pomelli-expands-170-countries), read 2026-10-19), English-only, no direct publishing, Photoshoot product images on Nano Banana ([aitoolanalysis.com](https://aitoolanalysis.com/pomelli-review/), read 2026-10-19); Meta Business Agent's owner "morning briefing" on the WhatsApp Business app and Instagram Pro, future "market research" and "competitive intelligence", free to start then paid ([WhatsApp Business blog, 2026-06-03](https://whatsappbusiness.com/blog/introducing-meta-business-agent-ai/), read 2026-10-19); a Spanish photo-to-Post agent that publishes to Instagram, web-based ([Social Agent AI](https://socialagentai.app/), read 2026-10-19).
- **Basis**: evidence; competitor numbers are vendor claims.
- **Problem**: The pitch and [competitors.md](../../competitors.md) say nobody takes the Owner's instructions over WhatsApp. That is no longer true. Postou.ai runs Neitor's core loop in Brazil at about a third of Neitor's price per Post and says it has tens of thousands of customers. Google gives away brand-DNA campaign generation, and Meta is moving its agent toward the owner. Investors and judges who search will find these. The defensible difference has to be stated around things the others don't do.
- **Recommendation**: Update [competitors.md](../../competitors.md) and [competitive-landscape.md](../competitive-landscape.md) with Postou.ai, Social Agent AI, Pomelli (with its March 2026 expansion and Photoshoot) and the Meta Business Agent owner briefing. Restate the differentiation as: (1) the Owner's real Product, never altered, in designed Carousels with code-set text ([ADR 0027](../../decisions/0027-owner-logo-stamped-in-code.md), [ADR 0029](../../decisions/0029-designed-slides-ai-scene-code-layout.md)); (2) a Brand Brain built automatically from the Owner's Instagram ([ADR 0028](../../decisions/0028-read-instagram-with-our-meta-app.md)); (3) local depth: Rioplatense voice, Uruguayan commercial calendar, Niche Reports ([ADR 0025](../../decisions/0025-weekly-niche-report.md)); (4) one account manager with a team behind it, plus a weekly plan (proactive, not prompt-driven). Copy two of Postou's tactics worth testing: per-tier Post counts and a near-free short trial. Sign up for Postou's R$0.99 trial to benchmark output quality, latency and flow.
- **Impact**: Avoids a credibility hit with investors and judges, and points the roadmap at what can't be copied quickly.
- **Verifier note**: Postou.ai verified on 2026-10-19, including "2 meses grátis" on annual billing and a claimed "+30 mil empresários" (vendor claim); R$49 for 12 Posts is roughly US$9, about a third of what Neitor would charge per Post if Basic were 12 Posts. Pomelli: March 2026 expansion, free beta with 300 images a month, Photoshoot on Nano Banana; English-only support unconfirmed. The docs' "gap" claims and [PRODUCT.md:21](../../../PRODUCT.md) ("Every competitor makes the owner operate software or talks to customers") are now false. Social Agent AI was not re-checked. The proposed differentiators map to real ADRs (0027, 0028, 0029, 0025).

### GRW-5: Basic and Pro have no Post limits or add-ons: package by volume and price against unit cost

- **Severity**: medium · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: Basic and Pro have no Post counts, and limits are "still open" ([ADR 0031:14-18,26](../../decisions/0031-pricing-free-basic-pro.md)); "posts per month on Basic and Pro?" ([open-questions.md:113](../../open-questions.md)); `DEFAULT_POSTS_PER_WEEK = 3` ([brand_strategist.py:24](../../../backend/app/agents/brand_strategist.py)); costs per active Business "must fit well under the Basic price", not yet validated ([roadmap.md:50](../../roadmap.md)); Postou 12 / 35 / 80 Posts at R$49 / 99 / 149 ([postou.ai](https://postou.ai/), read 2026-10-19); Predis Core about US$32 a month ([admakeai.com](https://admakeai.com/alternatives-to/predis-ai/pricing), read 2026-10-19); Sintra US$97 monthly, US$54 a month annual, 250 credits ([eesel.ai](https://www.eesel.ai/blog/sintra-ai-pricing), read 2026-10-19); 1 network, 12 Posts a month plus DM replies: junior freelance US$80–150, senior US$180–350, agency US$350–800 ([tarifario.info](https://tarifario.info/redes-sociales/), read 2026-10-19, updated September 2026).
- **Basis**: evidence for competitor pricing; the cost model is a hypothesis to validate with GRW-1.
- **Problem**: An open-ended "posts and carousels" promise at US$29 has no ceiling on cost. The auditor's estimate for a Basic Owner making 12 Posts (half of them 5-Slide Carousels, 1.5× regeneration) is about US$13–15 a month in variable cost (see the cost table above): roughly 50% gross margin, which falls as volume grows or as `gemini-3.8-flash` prices double on 2027-01-01 ([gemini-api.md:33](../gemini-api.md)). Competitors and the human alternative all price per Post, so Owners already think in Posts per month.
- **Recommendation**: Keep the per-tier Post counts (Free 3, Basic about 12, Pro about 30), count a Post when it is sent with bounded redos, and offer an extra-Posts pack. Anchor on a local community-manager price only after checking Uruguayan rates (the cited figures are Argentine juniors at US$80–150). Postou sells 12 Posts for about US$9, so the copy must justify Neitor's premium. Post counts per plan need an ADR revising [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md).
- **Impact**: Protects gross margin at about 50–65% (estimate), adds expansion revenue from heavy users, and gives the Free to Basic upgrade a concrete trigger ("te quedaste sin posts").
- **Verifier note**: The US$13–15 estimate is plausible only with Zernio's US$6 per account included; image cost for 12 Posts at 1.5× regeneration is about US$3, plus LLM about US$1 and WhatsApp about US$2–3. Correction: tarifario.info is about Argentina, where junior freelancers charge US$80–150 for 12 Posts, so "US$150+" is the top of the junior range, not the floor, and Uruguayan rates are unverified. An already-open pricing question with no billing yet, so medium, not high.
- **Related**: [PRD-12](product.md), [GAP-9](cross-cutting-gaps.md)

### GRW-6: Price in pesos with IVA included and collect through Mercado Pago Suscripciones inside WhatsApp (Stripe can't serve Uruguay)

- **Severity**: medium · **Effort**: M · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: prices are "US$0/US$29/US$49 / month", billed monthly, with no VAT shown ([pricing-section.tsx:57,62-84](../../../frontend/components/landing/pricing-section.tsx)); "billing (Mercado Pago / Stripe)" ([plan.md:104](../../implementation/plan.md)); Mercado Pago only for the sales flow, billing in Phase 2 ([roadmap.md:29-30](../../roadmap.md)); Stripe supports Brazil and Mexico, not Uruguay, Argentina or Chile ([Stripe global](https://stripe.com/global), read 2026-10-19); Mercado Pago subscriptions in Uruguay take card, debit, account money, Abitab and Red Pagos, work without an MP account, with weekly, monthly or annual frequency, a free-trial period and automatic retries ([Mercado Pago subscriptions](https://www.mercadopago.com.uy/developers/es/docs/subscriptions/overview), read 2026-10-19); Literal E small firms pay a fixed IVA mínimo and don't deduct real purchase IVA, with thresholds that conflict across sources ([ivacalculator.com](https://ivacalculator.com/uruguay/iva-minimo-pequenas-empresas/), read 2026-10-19); US$1 = UYU 40.24 ([Infobae](https://www.infobae.com/noticias/2026/08/06/dolar-hoy-en-uruguay-cotizacion-de-cierre-del-6-de-agosto/), read 2026-10-19).
- **Basis**: evidence for the payment rails; that IVA-inclusive pricing converts better is a hypothesis.
- **Problem**: Many of the persona's Businesses are micro firms on Literal E that can't recover IVA. "US$29" plus 22% IVA is really about $U 1,423, which isn't what the page shows. Stripe, listed in the plan, isn't available to a Uruguayan, Argentine or Chilean merchant. Card-only USD billing also excludes Owners who pay through Mercado Pago balance or cash networks like Abitab and Red Pagos.
- **Recommendation**: When billing is built (Phase 2), use Mercado Pago Suscripciones as the primary rail for Uruguay and Argentina, linked from the chat, with a webhook updating `businesses.plan`. Show peso prices with IVA included on the Owner-facing Spanish page. The peso price, and the effective net price change, need an ADR revising [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md) after an accountant confirms IVA and e-factura. Mention Stripe via a US entity as the alternative to weigh, not as impossible.
- **Impact**: Removes a roughly 22% surprise at checkout and lets Owners without cards pay. Pricing in pesos also reads as "local", which is the brand's main promise.
- **Verifier note**: The arithmetic is right: 29 × 1.22 × 40.24 ≈ $U 1,424, and $U 1,190 ≈ US$24 net of IVA. Overstated: "Stripe can't serve Uruguay" ignores the common Stripe Atlas or US-entity route, which can charge Uruguayan cards in USD. Whether 22% IVA applies depends on Neitor's own tax regime; a Literal E seller doesn't add IVA separately. There is no checkout yet, so the "22% surprise at checkout" is hypothetical. The English USD landing is a deliberate choice for judges ([PRODUCT.md:13](../../../PRODUCT.md)). $U 1,190 is also a roughly 17% net price cut against ADR 0031, which needs an ADR update.
- **Related**: [PRD-12](product.md), [GAP-9](cross-cutting-gaps.md)

### GRW-7: Pro's headline features (comment and DM replies) are being commoditized by Meta Business Agent: reposition Pro around results

- **Severity**: medium · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: Pro is replies to comments and DMs, sale alerts and a weekly results summary ([ADR 0031:18](../../decisions/0031-pricing-free-basic-pro.md)); the three Pro-only bullets are all marked "soon" ([pricing-section.tsx:88-90](../../../frontend/components/landing/pricing-section.tsx)); DMs make the product "partly customer-facing, a crowded space" ([ADR 0013:18](../../decisions/0013-focus-marketing.md)); Business Agent answers questions, recommends catalog products and closes sales, "Getting started with the Business Agent is free", expanding to businesses of all sizes globally ([WhatsApp Business blog](https://whatsappbusiness.com/blog/introducing-meta-business-agent-ai/), read 2026-10-19); Business Agent billed at US$2.00 per 1M tokens since 2026-08-01 ([Zernio blog](https://zernio.com/blog/meta-business-agent-pricing), read 2026-10-19).
- **Basis**: evidence.
- **Problem**: The US$20 step from Basic to Pro rests mostly on comment and DM replies, which Meta now offers natively and free to start across WhatsApp. Building and maintaining a DM agent means competing with the platform owner on its own surface, and LatAm WhatsApp sales bots (Leadsales, Yavendio, Agenteala) already crowd the space.
- **Recommendation**: Treat this as a watch item: before building the Instagram DM and comment agent, re-check whether Meta's agent covers Instagram. Make Pro lead with volume, Reels ([ADR 0012](../../decisions/0012-catalog-content-dashboard-reels.md)), the Insights weekly summary and per-Post attribution, and keep DM replies as a later add-on. Use the Pro waitlist (GRW-9) to ask which feature drives demand.
- **Impact**: Keeps Pro's price premium defensible while avoiding the most commoditized and highest-support feature on the roadmap.
- **Verifier note**: The Meta post (2026-06-03) covers customer chats on WhatsApp and Messenger and says paid subscriptions are coming. Not supported: Neitor's Pro feature is replies to Instagram comments and DMs ([ADR 0013](../../decisions/0013-focus-marketing.md), [ADR 0015](../../decisions/0015-instagram-login.md)), and the Meta post does not confirm Instagram DM or comment support for the agent; Instagram Pro is named only for the owner briefing. So the auditor's "extending to Instagram DMs" is unsubstantiated, and the overlap is weaker than stated. Parts of the repositioning are already planned: Reels in ADR 0012 and roadmap Phase 1, the weekly results summary in Pro (ADR 0031:18). Pushing the Brand Brain into Meta Business Agent assumes an integration path that is unverified for small businesses.
- **Related**: [PRD-21](product.md), [GAP-3](cross-cutting-gaps.md)

### GRW-8: GTM: rank channels by CAC for a 50-something, phone-first Owner, starting with founder-led concierge and click-to-WhatsApp ads

- **Severity**: medium · **Effort**: M · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: a ready list of curated furniture peers (Marvic, Samic, Diseño Montevideo, Lais, the Constituyente design stores) ([furniture-decor-uruguay.md:29-34](../furniture-decor-uruguay.md)); Pronto Maderas co-sponsors the 2026 national furniture design contest (furniture-decor-uruguay.md:36); since 2026-10-01, messages inside the 72-hour free entry point window from click-to-WhatsApp ads are not charged ([EngageLab](https://www.engagelab.com/blog/whatsapp-business-api-pricing), read 2026-10-19); LatAm click-to-WhatsApp cost per conversation US$1–3 ([Aurora Inbox](https://www.aurorainbox.com/en/2026/05/13/what-is-click-to-whatsapp-ads/), read 2026-10-19, vendor claim, unverified); 2.63M Instagram users in Uruguay, 74% of the population, September 2026 ([NapoleonCat](https://napoleoncat.com/stats/instagram-users-in-uruguay/), read 2026-10-19); ADIMAU represents micro, small and medium wood-industry firms ([La Mañana](https://www.xn--lamaana-7za.uy/?p=66438), read 2026-10-19); ANDE digital-transformation vouchers, call closing 2026-10-20, examples are ERP and CRM ([Revista Cero](https://www.revistacero.com.uy/ande-presenta-vouchers-transformacion-digital-pymes/), read 2026-10-19).
- **Basis**: the channel ranking is a hypothesis; the cost mechanics are evidence.
- **Problem**: There is no GTM plan in the docs. The persona doesn't search for SaaS, doesn't trust ads that lead to web dashboards, and decides through people she already trusts: her accountant, suppliers, peers. A landing page plus "Get started" won't reach her.
- **Recommendation**: Write a short GTM doc after the production number exists: founder-led concierge with 10–20 owner-run shops, filtering out chains and conflicts with the demo Business; a small click-to-WhatsApp test (about US$300) measuring cost per activated Owner; then accountant and supplier partners. Treat every CAC figure as a hypothesis until GRW-1 and GRW-9 attribution exists. The ranked channels are in [Go-to-market channels](#go-to-market-channels-hypothesis) below.
- **Impact**: An expected cost of under US$30 per activated Owner for concierge and partners, versus paid-only acquisition (hypothesis). Produces the first 10–30 reference customers and testimonials the landing currently can't show.
- **Verifier note**: A grep of the docs for GTM, acquisition, referral and click-to-WhatsApp found nothing (audit observation, 2026-10-19). Caveats: (1) ads, partners and referrals all depend on a production number (GRW-2). (2) The free entry-point window is 72 h per EngageLab, while a summary of Meta's own page said "up to 7 days", so the sources conflict. (3) "Under US$30 per activated Owner" and US$1–3 per conversation are unsupported hypotheses. (4) The peer list ([furniture-decor-uruguay.md:25-34](../furniture-decor-uruguay.md)) includes Kave Home and Viasono, which are not small owner-run businesses, and the listed peers are direct competitors of a teammate's demo furniture Business, which could be a conflict. (5) ANDE's call closes 2026-10-20 and its examples are ERP and CRM. A sensible sequence, but a plan recommendation rather than a defect, so medium.

### GRW-9: No attribution and no referral loop: the first message is discarded and every CTA is identical

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**: in state `new` the first message's text is ignored and only the welcome is sent ([onboarding.py:76-80](../../../backend/app/conversation/onboarding.py)); every CTA prefills the same English text "Hi Neitor" ([whatsapp.ts:3](../../../frontend/lib/whatsapp.ts)); the default href ([cta-link.tsx:31](../../../frontend/components/landing/cta-link.tsx)) means "Try it free", "Get started" and "Join the Pro list" all open the same chat ([pricing-section.tsx:63,75,85](../../../frontend/components/landing/pricing-section.tsx)); `InboundMessage` keeps `raw`, where a click-to-WhatsApp ad's referral payload would arrive ([base.py:55](../../../backend/app/channels/base.py)); no analytics on the landing ([layout.tsx:25-37](../../../frontend/app/layout.tsx)).
- **Basis**: evidence; the referral-rate target is a hypothesis.
- **Problem**: A Pro waitlist sign-up is indistinguishable from a free sign-up, so the Pro waitlist the ADR promises doesn't exist. No source is recorded (landing, ad, referral, partner), so cost per channel can't be computed. And no mechanism exists for a happy Owner to bring another, even though WhatsApp-native products spread by forwarding.
- **Recommendation**: Give each CTA a distinct Spanish prefill with a ref code (at minimum web-free versus web-pro). Parse it in the `new` branch into a `businesses.acquisition_source` column, and store Pro-intent sign-ups as a real waitlist. Verify that Kapso forwards the click-to-WhatsApp referral before relying on it. Add privacy-light landing analytics. Build the in-chat referral loop after the production number and billing exist.
- **Impact**: Makes CAC per channel measurable (GRW-8), creates a real Pro waitlist with a demand signal, and adds a near-zero-cost acquisition loop. A referral rate of 0.2 per active Owner is a reasonable test target (hypothesis).
- **Verifier note**: `OnboardingGate` sends only the welcome and stores no source ([onboarding.py:77-80](../../../backend/app/conversation/onboarding.py)). The Pro waitlist promised by [ADR 0031:24](../../decisions/0031-pricing-free-basic-pro.md) doesn't exist, and the landing has no analytics package ([package.json](../../../frontend/package.json)). Caveats: Kapso delivers its own v2 payload ([open-questions.md:26](../../open-questions.md)), so whether a click-to-WhatsApp `referral` object reaches `raw` is unverified. No real traffic is possible until the production number exists, so high was inflated. The 0.2 referral target is a guess.
- **Related**: [AIQ-20](ai-quality.md), [FE-17](frontend.md), [FE-1](frontend.md), [FE-3](frontend.md)

### GRW-10: No retention loop: proactive messages are "Won't", so the product only works when the Owner remembers it

- **Severity**: medium · **Effort**: M · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: F1.8, proactive messages outside the 24 h window, is Won't ([mvp.md:36](../../product/mvp.md)); "The weekly run is silent: the Owner sees the report only when they ask" ([ADR 0025:20](../../decisions/0025-weekly-niche-report.md)); a weekly plan every Monday is a Phase 1 Should ([roadmap.md:10](../../roadmap.md)); approved templates are needed, for example "tu plan de la semana está listo" ([open-questions.md:18](../../open-questions.md)); per-message pricing, with marketing and utility templates charged per delivered message ([WhatsApp pricing](https://developers.facebook.com/docs/whatsapp/pricing), read 2026-10-19).
- **Basis**: the habit-loop risk is a hypothesis; the template requirement and pricing are evidence.
- **Problem**: Everything that would bring an Owner back (the Monday plan, the Niche Report, "hoy es buen día para subir") is either silent or needs the Owner to write first. For a busy 52-year-old Owner whose current behavior is posting "when she can", a purely reactive assistant reproduces that behavior. Retention will decay, and churn will look like a quality problem when it is a habit problem.
- **Recommendation**: Keep (a) the Monday plan template already planned in Phase 1, and add (b) an inactivity nudge and (c) a commercial-date nudge, capped at 2 a week with a pause option. Budget about US$0.3–0.8 per Owner per month depending on Meta's category, and submit the Monday plan as utility where Meta allows.
- **Impact**: The main lever on WAO and W4 retention (GRW-1). Expect a measurable lift in approved Posts per week; it is the agency feel ("they text me first") the positioning promises.
- **Verifier note**: Partly mis-framed. F1.8 is "Won't (demo)", scoped to the hackathon, not a product decision. The roadmap already has the Monday plan in Phase 1, and [plan.md:104](../../implementation/plan.md) lists approved templates for proactive messages; the silent Niche Report is an MVP consequence of F1.8. What is new is the re-engagement nudge, the commercial-date nudge and the frequency cap. Cost is understated: a "Hace 7 días que no subimos nada" nudge is likely marketing category, about US$0.085 per message for Rest of Latin America per a reseller's October 2026 rate card (no URL recorded). Two a week is about US$0.70 per Owner per month, not "cents"; a utility-classified Monday plan is about US$0.013.
- **Related**: [PRD-9](product.md)

### GRW-11: Activation: after the brand is confirmed, offer a concrete first Post instead of an open question

- **Severity**: medium · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: `READY_OPEN_CHAT = '¡Listo, ya conozco tu marca! ¿En qué te puedo ayudar hoy?'` ([messages_es.py:32](../../../backend/app/copy/messages_es.py)); F1.10 is a deliberate Must: open chat instead of offering the plan ([mvp.md:38](../../product/mvp.md)); the Owner reaches the brand step with real imported photos ([ADR 0032:29](../../decisions/0032-instagram-first-onboarding.md)); recent media is imported at onboarding ([instagram.py:86](../../../backend/app/jobs/instagram.py)).
- **Basis**: hypothesis; it challenges the F1.10 decision.
- **Problem**: Time to first value decides activation. Right after onboarding the Owner already has imported Instagram photos and Products, but gets a blank "¿En qué te puedo ayudar hoy?". A non-technical Owner often doesn't know what to ask, and the session ends before any Post is made.
- **Recommendation**: Change [events.md:16](../../../backend/app/conversation/prompts/events.md) (and the fallback) so that after brand confirmation the Orchestrator offers one concrete first Post from an imported or uploaded photo, with the open chat kept as the fallback. This needs a team decision recorded as a revision of F1.10 in [mvp.md](../../product/mvp.md); measure first-session Approval once events exist.
- **Impact**: Plausibly moves first-session activation from a minority to most Owners (hypothesis). The single largest leverage point on paid conversion for a 3-Post Free tier.
- **Verifier note**: The behavior is real and deliberate (F1.10 Must; [agents.md:387](../../architecture/agents.md)). The evidence location is off: `READY_OPEN_CHAT` is only the fallback ([events.py:307](../../../backend/app/conversation/events.py)); the live message is written by the Orchestrator following events.md:16 ("Say you know their brand now and ask what you can help with today... Never propose a plan or a post by yourself"). The A/B test needs GRW-1 instrumentation first. The activation-lift claim is unsupported.
- **Related**: [PRD-5](product.md)

### GRW-12: Vertical packs don't scale yet: one global furniture Niche Report feeds every Business

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Status (2026-10-20)**: partly fixed, by [#63](https://github.com/guidodinello/build101/pull/63); details in [status.md](status.md).
- **Evidence**: trend notes load once from the global `NICHE_REPORT_PATH` ([factory.py:59,114-120](../../../backend/app/conversation/factory.py)); the same `trend_notes` go into every Post's prompt ([drafts.py:68-70,170-172](../../../backend/app/posts/drafts.py)); exactly one hard-coded niche, `curated-wood-furniture-uy` ([niches.py:19-46](../../../backend/app/agents/data/niches.py)); the wizard offers Muebles y deco, Gastronomía, Indumentaria, Belleza and Servicios ([categories.ts:11-46](../../../frontend/lib/categories.ts)); the report is per Business ([ADR 0025:18](../../decisions/0025-weekly-niche-report.md)).
- **Basis**: evidence.
- **Problem**: If `NICHE_REPORT_PATH` is set, a hair salon or pasta shop onboarded through the wizard gets furniture trend notes (illustrative examples: "wood grain", "cómo cuidar la madera"; the report's real content is generated at run time) in its copy and image prompts, which breaks the "sounds like us" promise. And adding a vertical means a code change plus a manual research doc, while this is the unit that should scale expansion.
- **Recommendation**: Before onboarding non-furniture Owners with `NICHE_REPORT_PATH` set, either leave it unset or select trend notes per Business (by category or niche) and pass them per call. Move niches to data and store reports per niche and city, as T19 and ADR 0025 intend. Add vertical packs only when a second vertical has real pilots.
- **Impact**: Fixes a cross-vertical quality bug before the pilot widens, and turns each new vertical into about 1 day of work instead of a sprint (estimate).
- **Verifier note**: The same notes also go into every chat context ([chat.py:443](../../../backend/app/conversation/chat.py)). Mitigations the auditor missed: `NICHE_REPORT_PATH` is off by default (commented out in [backend/.env.example:50](../../../backend/.env.example)); [config.py](../../../backend/app/config.py) marks it interim "until the weekly job saves them in niche_reports (T19)"; and [draft.md:9](../../../backend/app/posts/prompts/draft.md) tells the model to use trend notes only "when they fit the brief and the photos" and never for facts ([knowledge.md:8](../../../backend/app/conversation/prompts/knowledge.md) is similar). So the bleed happens only when the env var is set and a non-furniture Business onboards, and the prompt partly guards against it. The pilot persona is furniture.
- **Related**: [PRD-4](product.md), [AIQ-12](ai-quality.md)

### GRW-13: Add an annual plan, founding-customer pricing and a reverse trial

- **Severity**: low · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: "billed monthly" ([ADR 0031:12](../../decisions/0031-pricing-free-basic-pro.md), [pricing-section.tsx:57](../../../frontend/components/landing/pricing-section.tsx)); "Annual billing or launch discounts?" ([open-questions.md:113](../../open-questions.md)); SMB SaaS monthly churn is typically 2–5%, and monthly plans churn 2–3× more than annual ([UserJot](https://userjot.com/blog/saas-churn-rate-benchmarks), read 2026-10-19, vendor sources); Postou offers "2 meses grátis" on annual billing and a R$0.99 3-day trial ([postou.ai](https://postou.ai/), read 2026-10-19).
- **Basis**: the churn ratios are secondary vendor data; the reverse-trial benefit is a hypothesis.
- **Problem**: Monthly-only billing for micro businesses maximizes churn, and the 3-Post Free tier shows one-off Posts, not the weekly rhythm that is Basic's real value. Pilot Owners also have no reason to commit early.
- **Recommendation**: Answer [open-questions.md:113](../../open-questions.md) when billing is designed: annual at about 10× monthly, a founding-customer price for the first cohort, and a time-boxed Basic trial tested against plain Free once GRW-1 metrics exist. The plan changes need an ADR revising [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md).
- **Impact**: Annual billing can halve churn for the cohort that takes it (hypothesis). The reverse trial shows the habit loop (GRW-10) before asking for money.
- **Verifier note**: Mercado Pago supports annual frequency and trials (verified). "Halve churn" and the reverse-trial benefit are hypotheses. No billing exists yet and the question is already tracked, so low, not medium.
- **Related**: [PRD-12](product.md), [GAP-9](cross-cutting-gaps.md)

### GRW-14: The Owner-facing landing is in English and built for judges; add a Spanish page for Owners

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Status (2026-10-20)**: partly fixed, by [#157](https://github.com/guidodinello/build101/pull/157); details in [status.md](status.md).
- **Evidence**: "the landing copy is in English for them", meaning judges and investors ([PRODUCT.md:13](../../../PRODUCT.md)); "Hi, I'm Neitor. Your marketing agency, living in your WhatsApp." ([hero.tsx:22](../../../frontend/components/landing/hero.tsx)); a Spanish meta description over English content, with `lang="es"` ([layout.tsx:16-19](../../../frontend/app/layout.tsx)); the English prefill "Hi Neitor" ([whatsapp.ts:3](../../../frontend/lib/whatsapp.ts)).
- **Basis**: evidence.
- **Problem**: Every non-ad channel (partners, referrals, press, Google) sends the persona to the landing, where she reads English, US$ prices and "Join the Pro list". That contradicts the "speaks your Spanish" promise on the same page.
- **Recommendation**: Make the root page Rioplatense Spanish for Owners (prices in pesos, a "Hecho en Uruguay" trust line, real pilot Posts once permitted, an FAQ on Instagram safety) and move the English version to `/en` for investors. Pass `?ref=` through to the WhatsApp prefill (GRW-9).
- **Impact**: Removes a conversion leak on every non-ad channel; low effort.
- **Verifier note**: The `lang="es"` with English content is a real accessibility and SEO mismatch. The English landing is a deliberate choice for judges and investors (PRODUCT.md:13,41), and the finding acknowledges this; it contradicts the Owner-facing promise once real Owners are acquired. Timing is tied to the production number.
- **Related**: [PRD-6](product.md), [FE-3](frontend.md), [FE-4](frontend.md), [DOC-3](docs-process.md)

### GRW-15: Turn the real competitor, freelance community managers, into a channel with an agency plan

- **Severity**: low · **Effort**: L · **Confidence**: low · **Verified**: adjusted
- **Evidence**: freelance community managers and small agencies are "the real competitor for budget" ([competitors.md:25](../../competitors.md)); a junior freelance community manager charges US$80–150 per network per month for 12 Posts plus replies ([tarifario.info](https://tarifario.info/redes-sociales/), read 2026-10-19); junior freelancers in Argentina charge ARS 150–250k a month for 12–15 Canva Posts ([sodi.com.ar](https://sodi.com.ar/blog/cuanto-cuesta-community-manager-argentina), read 2026-10-19); Postou has an "Agência" plan at R$149 for 80 Posts ([postou.ai](https://postou.ai/), read 2026-10-19); Metricool Advanced covers 15 brands with post approval ([socialk.it](https://socialk.it/es/pricing/metricool), read 2026-10-19).
- **Basis**: hypothesis.
- **Problem**: Community managers already sell to Neitor's persona and earn little per client. Today Neitor can only replace them, never arm them. Each community manager could bring 5–20 Owners whose Approvals Neitor already handles over WhatsApp.
- **Recommendation**: Park this as a Phase 2+ hypothesis. Meanwhile, ask pilot Owners whether they use a community manager, and interview 3–5 freelancers about co-selling before designing an agency plan.
- **Impact**: A low-CAC channel at scale (one sale brings many accounts), and it defuses the "AI is taking my job" objection from the people Owners trust for marketing.
- **Verifier note**: The tarifario.info rates are Argentine (September 2026). This is a low-confidence, L-effort, post-pilot idea that depends on a dashboard and user accounts that don't exist ([plan.md:107](../../implementation/plan.md); dashboard not built) and on multi-Business management. Medium overstated it for a 2-person pre-pilot team.

### GRW-16: Free tier as a growth loop: an opt-in "Hecho con Neitor" credit and a share prompt after publishing

- **Severity**: low · **Effort**: S · **Confidence**: low · **Verified**: adjusted
- **Evidence**: Free is 3 Posts a month, no card ([ADR 0031:16](../../decisions/0031-pricing-free-basic-pro.md)); the code-rendered chrome already controls every pixel of the Slide ([chrome.tsx:26-80](../../../frontend/lib/post-render/chrome.tsx)); the originality rule targets reposts, and the Owner's own photos count as original ([instagram-content-trends.md:10](../instagram-content-trends.md)); the persona fears Posts that look "not like us" ([idea.md:28](../../idea.md)).
- **Basis**: hypothesis.
- **Problem**: Free Posts reach the Owner's followers, many of whom are other local business owners, but carry no path back to Neitor. A visible watermark on the image, though, would undercut the persona's top fear (looking fake or "not like us").
- **Recommendation**: Offer the "Hecho con @neitor" caption line as a genuine opt-in, for example in exchange for +1 free Post, shown in the caption before Aprobar so the [ADR 0007](../../decisions/0007-approve-every-post.md) Approval covers it. Pair it with the post-publish share prompt once the referral codes from GRW-9 exist.
- **Impact**: Adds compounding reach at about zero cost. Measure sign-ups per 100 Free Posts.
- **Verifier note**: The auditor's original recommendation made the caption credit default-on for Free and removable only by paying or referring, which is opt-out and partly a paywall, contradicting the title and touching the same "not like us" fear; the recommendation above is the corrected opt-in version. The existence of the @neitor.ai handle is unverified, and the effect size is a hypothesis.

### GRW-17: Expansion order: Argentina next, then Mexico; Brazil last

- **Severity**: low · **Effort**: L · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: Uruguay has 2.63M Instagram users, a small market ([NapoleonCat](https://napoleoncat.com/stats/instagram-users-in-uruguay/), read 2026-10-19); mipymes are 99.58% of Uruguayan firms, and micro firms in commerce are 33.4% ([INE](https://www.gub.uy/instituto-nacional-estadistica/comunicacion/noticias/empresas-mpymes), read 2026-10-19); Argentine junior community managers charge US$80–150 a month, a lower price ceiling ([tarifario.info](https://tarifario.info/redes-sociales/), read 2026-10-19); Postou is an entrenched WhatsApp-native competitor in Brazil at R$49 ([postou.ai](https://postou.ai/), read 2026-10-19); Meta charges "AI Providers" per non-template message only in Brazil ([WhatsApp AI providers pricing](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers/), read 2026-10-19); Stripe is available in Mexico and Brazil, not Argentina or Chile ([Stripe global](https://stripe.com/global), read 2026-10-19).
- **Basis**: market sizing is partly evidence; the order is a hypothesis.
- **Problem**: Uruguay is a good beachhead but too small to sustain a venture-scale business alone, and the copy, prompts and templates are hard-wired to Rioplatense Spanish. Picking the next market badly (Brazil's incumbent, extra Meta charges and Portuguese) would waste the team's two people.
- **Recommendation**: Record the order as a hypothesis in roadmap Phase 3: Argentina first, sharing voice and Mercado Pago. Revisit after about 50 paying Uruguayan Owners. Don't add a locale field until a second locale is actually scheduled.
- **Impact**: Each Spanish-speaking market reuses about 80% of the stack (estimate). The auditor also argued that making locale a field now avoids a rewrite later; the reviewer called that premature (see below).
- **Verifier note**: The auditor dated Meta's Brazil AI-provider charge from 2026-05-13; the reviewer read 2026-03-11 on the same page. That page defines AI Providers as LLM, generative-AI and general-purpose assistant providers, and doesn't settle whether a business-specific marketing assistant counts, so the point is uncertain. The work is L effort and months away; for a 2-person team that hasn't run its first multi-Owner pilot, the auditor's "make locale a Business field now" is premature (YAGNI). Not medium.

### GRW-18: Moats and platform risk: Meta is the Channel, the publishing target and a competitor

- **Severity**: medium · **Effort**: L · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: Meta's January 2026 policy: an AI that is the core product can be barred, and "Meta decides what counts" ([competitive-landscape.md:41](../competitive-landscape.md)); whether the policy allows Neitor isn't confirmed ([open-questions.md:17](../../open-questions.md)); an owner-facing briefing, with future market research and competitive intelligence ([WhatsApp Business blog](https://whatsappbusiness.com/blog/introducing-meta-business-agent-ai/), read 2026-10-19); "The report reflects what websites and the web show, not measured engagement" ([ADR 0025:30](../../decisions/0025-weekly-niche-report.md)); brand voice learning from corrections is planned ([roadmap.md:12](../../roadmap.md)).
- **Basis**: the strategic analysis is a hypothesis; the platform facts are evidence.
- **Problem**: Neitor's value sits entirely on Meta surfaces (WhatsApp in, Instagram out), and Meta is moving toward owner-facing AI. The current defensibility (prompts plus Gemini plus templates) is copyable in weeks, as Postou shows. Without a data or relationship moat, a Meta feature launch or a policy reading could erase the product.
- **Recommendation**: Add to the roadmap: collect the Owner's email in the wizard (a cheap hedge) and, once Insights are read, aggregate engagement by niche and city. Keep the already-planned items, and get the WhatsApp terms read ([open-questions.md:17](../../open-questions.md)) before the production number goes public.
- **Impact**: Lowers existential platform risk and builds the asset investors will ask about ("why won't Meta just do this?").
- **Verifier note**: Several of the auditor's moats are already planned: correction-learned voice (roadmap.md:12), the web-chat simulator (T21, [open-questions.md:9](../../open-questions.md)), Facebook publishing (roadmap Phase 3), and reading the WhatsApp terms before launch. Genuinely new: aggregated anonymized engagement by niche and city (needs Insights first), collecting the Owner's email at onboarding, and Google Business Profile publishing as a hedge. The strategic risk is real; the actions are long-term.

### GRW-19: WhatsApp service messages are billed since 2026-10-01: each Carousel Slide is a paid message once past 1,000 a month per number

- **Severity**: medium · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**: each business phone number gets 1,000 free service messages a month, Meta charges from the 1,001st, and with no payment method delivery stops after the free tier ([WhatsApp pricing](https://developers.facebook.com/docs/whatsapp/pricing), read 2026-10-19); service messages are charged at the market's utility rate after the allowance (Brazil US$0.0068, Mexico US$0.0085), and click-to-WhatsApp 72 h windows are free ([EngageLab](https://www.engagelab.com/blog/whatsapp-business-api-pricing), read 2026-10-19); one WhatsApp image message per Slide, with the caption on the first and a separate text only when it is too long ([maker.py:391-398](../../../backend/app/posts/maker.py)), plus the Orchestrator's message with buttons; Kapso Free plan: 2,000 messages a month ([ADR 0020:14](../../decisions/0020-whatsapp-via-kapso.md)); WhatsApp costs per Business still to validate ([roadmap.md:50](../../roadmap.md)).
- **Basis**: evidence for the policy; Uruguay's Rest of Latin America rate is not verified, and the per-Owner costs are estimates.
- **Problem**: Pricing and docs assume in-window replies are free, but Meta resumed charging service messages on 2026-10-01 beyond 1,000 a month per number. A 5-Slide Carousel with a revision is about 15 messages, and an active Owner is about 150–250 a month. Past the first 5–7 active Owners, every Owner adds an estimated US$1.5–2.5 a month, and a production number without a payment method would stop delivering. Kapso's free 2,000-message plan also runs out at about 10 Owners.
- **Recommendation**: Before the production number: put a payment method on Kapso or Meta billing, add about US$2–3 per active Owner per month for WhatsApp to the cost model (GRW-5), and upgrade from Kapso Free (2,000 messages a month) at around 10 active Owners. Consider cheaper previews (merge buttons with the caption message; send a contact sheet only for 6+ Slides) without hurting Slide-by-Slide review.
- **Impact**: Saves an estimated US$1–2 per Owner per month (about 5–8% of Básico revenue) and avoids silent delivery failure at scale.
- **Verifier note**: Meta's page confirms the 2026-10-01 change, the 1,000 free messages per number (shared by all Owners) and that delivery stops without a payment method on file (deadline 2026-09-30). Rest of Latin America's utility rate is about US$0.013 per message for October 2026 per Gallabox (a reseller, no URL recorded; Meta's own Uruguay row not confirmed; it was US$0.0113 in October 2025), so 150–250 messages a month is about US$2–3 per Owner, slightly above the auditor's US$1.5–2.5. Slides go one image message each with the caption on the first ([maker.py:376-399](../../../backend/app/posts/maker.py)), plus Orchestrator messages with buttons. Corrections: the docs don't explicitly assume in-window replies are free (roadmap.md:50 lists WhatsApp cost as "to validate"), and none of this applies until the production number exists. A contact-sheet preview reduces message count but trades off how well the Owner can review each Slide before approving.
- **Related**: [COST-7](unit-economics.md)

## Pricing hypotheses

From the audit synthesis ([summary.md](summary.md)). The price points, packaging and trial mechanics are **hypotheses** to test in the pilot; the payment-rail facts are **evidence** (read 2026-10-19). Any change to the plans needs an ADR next to or revising [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md).

- **Package by Post count** (GRW-5): Free 3, Basic about 12, Pro about 30, plus an extra pack of 5 Posts for $U 290 sold in the chat when the quota runs out. Count a Post when it is sent, with a bounded number of redos.
- **Price in pesos with IVA included on the Owner-facing page** (GRW-6, GRW-13):
  - Básico $U 1,190 a month or $U 11,900 a year.
  - A founder price of $U 990, locked for 12 months.
  - Pro $U 1,990.
  - $U 1,190 is about US$24 net, roughly 17% below ADR 0031's price. It is only safe after the cost levers in [unit-economics.md](unit-economics.md), and it needs an ADR.
- **Trials and Free**:
  - A 14-day trial of Básico that falls back to Free.
  - Connect a Free Owner to Zernio only at their first approved publish.
  - The "Hecho con @neitor" caption credit must be a genuine opt-in, for example in exchange for +1 Post, never on by default (GRW-16).
- **Pro**: lead with volume, Reels, results and attribution. Keep the Owner-in-the-loop inbox for later and do not build autonomous DM replies (GRW-7, [PRD-21](product.md)).
- **Payments and legal**:
  - Use Mercado Pago Suscripciones: card, account money, Abitab and Red Pagos, and buyers need no Mercado Pago account ([Mercado Pago subscriptions](https://www.mercadopago.com.uy/developers/es/docs/subscriptions/overview), read 2026-10-19, evidence). Stripe does not serve Uruguayan merchants except through a US entity ([Stripe global](https://stripe.com/global), read 2026-10-19, evidence).
  - Before the first charge: choose the legal entity (Uruguayan SAS or foreign company), register the RUT with DGI and BPS, and pick a CFE e-invoicing provider triggered from the payment webhook ([GAP-9](cross-cutting-gaps.md)).
  - Record all of this in an ADR next to ADR 0031 ([GAP-9](cross-cutting-gaps.md), [PRD-12](product.md), [FE-17](frontend.md)).

## Go-to-market channels (hypothesis)

Ranked by expected CAC. The **ranking is a hypothesis** (GRW-8); the cost mechanics cited are **evidence**, with the conflicts noted.

1. **Founder-led concierge onboarding** of 10-20 owner-run furniture and decor shops in Montevideo. The list already exists in [furniture-decor-uruguay.md](../furniture-decor-uruguay.md); filter out chains and anyone who competes with the demo Business.
2. **A click-to-WhatsApp ad test** of about US$300 once the production number is live, measuring the cost per activated Owner. The free entry-point window is 72 h per [EngageLab](https://www.engagelab.com/blog/whatsapp-business-api-pricing) (read 2026-10-19) and up to 7 days per a summary of Meta's own page, so the sources conflict.
3. **People she already trusts**: accountants, suppliers (Pronto Maderas), and ADIMAU ([La Mañana](https://www.xn--lamaana-7za.uy/?p=66438), read 2026-10-19).
4. **An in-chat referral loop** and the opt-in caption credit, after billing exists (GRW-9, GRW-16).
5. **Freelance community managers as resellers**, in Phase 2 or later (GRW-15).

Prerequisites:

- A distinct Spanish prefill with a ref code for each CTA, stored in `businesses.acquisition_source` (GRW-9).
- A check that Kapso forwards the click-to-WhatsApp referral payload (GRW-9).

## Competitive threats

The docs' claim that nobody else works inside WhatsApp is now false; [competitors.md](../../competitors.md) and [competitive-landscape.md](../competitive-landscape.md) need updating (GRW-4). The "What it does" column is **evidence** (vendor claims flagged, read 2026-10-19); the "Response" column is the audit's recommendation.

| Threat | What it does | Response |
|---|---|---|
| Postou.ai (Brazil) | The same loop: Voice note to art and caption, approve in WhatsApp, publish to feed and Stories. R$49 for 12 Posts (about US$9). Claims 30k+ businesses, a vendor claim ([postou.ai](https://postou.ai/)) | Benchmark it through the R$0.99 trial. Copy the per-tier Post counts and the cheap trial. Differentiate on the real Product never being altered, designed Carousels and the Brand Brain built from Instagram |
| Google Pomelli | Free, 170+ countries, brand-DNA campaigns, Photoshoot on Nano Banana. English only, no publishing ([aihola.com](https://aihola.com/article/pomelli-expands-170-countries), [aitoolanalysis.com](https://aitoolanalysis.com/pomelli-review/)) | Spanish, publishing, and living in WhatsApp |
| Meta Business Agent | A customer-facing agent that is free to start. An owner briefing on WhatsApp Business and Instagram Pro. Market research announced for later ([WhatsApp Business blog](https://whatsappbusiness.com/blog/introducing-meta-business-agent-ai/)) | Meta is the Channel, the publishing target and a competitor. Don't compete on DMs. Hedge by collecting the Owner's email and adding Google Business Profile. Read the WhatsApp AI-provider terms before the production number (GRW-18) |
| Social Agent AI, Predis (~US$32), Sintra (US$54-97), Metricool, Canva (~US$13-18) | Web dashboards (see the [price map](#competitive-price-map)) | Having no dashboard is the point |
| Freelance community managers | US$80-150 a month junior in Argentina ([tarifario.info](https://tarifario.info/redes-sociales/)); Uruguayan rates unverified | Use as the price anchor; later, a channel (GRW-15) |

## Expansion order

A **hypothesis** (GRW-17); the market facts behind it are evidence, cited in GRW-17.

- **Argentina next**, because it shares the Rioplatense voice and Mercado Pago.
- **Then Mexico.**
- **Brazil last**: Postou is the incumbent, it needs Portuguese, and Meta charges AI providers per message there (whether Neitor counts as an AI provider is uncertain).
- Revisit after about 50 paying Owners in Uruguay. Don't add a locale field until a second locale is actually scheduled.

## Metrics to instrument

The definitions are the audit's proposal (GRW-1, [FE-8](frontend.md), [DOC-9](docs-process.md)); the targets are **hypotheses**, and the churn benchmark is secondary vendor data ([UserJot](https://userjot.com/blog/saas-churn-rate-benchmarks), read 2026-10-19).

1. **Activation**: % of new Owners with a first Post published within 7 days of their first message. Sub-funnel: first message, wizard completed, brand confirmed, first Post sent, approved, published.
2. **WAO** (weekly active Owners): Businesses with at least one approved Post in the ISO week.
3. **Approved Posts per WAO per week** (target: 2 or more).
4. **Quality of output**: first-pass approval rate, revisions per approved Post, discard rate.
5. **Retention**: W4 and W8 WAO cohort retention, then monthly paid logo churn (SMB benchmark: 2-5% a month).
6. **Supporting metrics**: cost per approved Post, time to first Post, cost per activated Owner by acquisition source, wizard drop-off per step, WhatsApp messages per Business.

### Infrastructure the metrics need

- An append-only events table. `conversation_steps` can't serve, because compaction deletes rows (GRW-1).
- `agent_runs` written on every LLM and image call ([COST-1](unit-economics.md)).
- PostHog on the landing and wizard, with no PII ([FE-8](frontend.md)).
- A weekly SQL view.
- A before-and-after interview for the "hours saved" metric.
