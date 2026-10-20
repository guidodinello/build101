# Cross-cutting gaps

This doc collects what fell between the other dimensions of the 2026-10-19 product and codebase audit of Neitor AI (index in [README.md](README.md), cross-dimension overview in [summary.md](summary.md)). After the 11 dimension audits, a completeness critic looked for areas none of them owned: platform decisions that cut across several findings, third-party terms, and the legal and commercial setup. The code was read at commit `dc0bc01`. Each finding was checked by an independent adversarial reviewer against the code and the cited sources: "confirmed" means it held as written, and "adjusted" means the reviewer corrected its severity or details. The severity and recommendation below already include those corrections. The ids keep the critic's numbering; there is no GAP-12 in the verified set.

## Summary

The 11 dimensions examined code paths in depth, but no auditor took on cross-cutting platform decisions, third-party terms, or the legal and commercial setup. Five gaps stand out:

- **No one checked which Instagram connection the product should use** (GAP-1). Fixing per-Owner publishing ([ARCH-4](backend-architecture.md), [BUG-1](bugs-reliability.md)) adds a Zernio OAuth hop on top of the own Meta app of [ADR 0028](../../decisions/0028-read-instagram-with-our-meta-app.md). Zernio's current spec and pricing already cover importing the account, publishing, the inbox (DMs and comments) and insights, all under a Meta app that has passed review. That would remove the App Review blocker behind [FE-5](frontend.md), [PRD-13](product.md) and [OPS-3](platform-ops.md), and make Pro buildable now, if Zernio confirms there is no add-on charge.
- **Third-party terms were not read against the design** (GAP-2). The Niche Analyst caches Google Search grounding output and sends it to every Business. The Gemini terms forbid that, and the per-niche sharing proposed in [COST-9](unit-economics.md) would make it worse.
- **Meta's messaging rules were never applied end to end** (GAP-3, GAP-11): the Instagram 24-hour reply window and WhatsApp templates for messages to the Owner, for Pro and for scheduling.
- **The legal and commercial setup is missing** (GAP-9, GAP-4, GAP-6): nothing on the legal entity, IVA or CFE e-invoicing needed to charge, nothing on consent for real people's photos (`has_people` is computed and then ignored), and nothing on how AI scenes are disclosed under Uruguay's advertising law.
- **Output accessibility and identity** (GAP-5, GAP-8): published Posts never get alt text, although Zernio accepts it, and the one-phone-one-Business identity model blocks staff, agencies and Owners with more than one Business.

Smaller items: CTAs with no concrete contact (GAP-7), Mercado Libre as the missing LatAm integration (GAP-10), and photos sent as documents (GAP-13). The backend test suite is healthy: 591 passed, 0 failed and 95 DB tests skipped locally (they need `TEST_DATABASE_URL`), and those run in CI with a Postgres service (audit observation, 2026-10-19), so test health is not a gap.

## Findings at a glance

Effort: S is under half a day, M is 1-2 days, L is about a week, and XL is more than a week.

| Id | Severity | Effort | Finding |
|---|---|---|---|
| GAP-1 | high | M | Decide on one Instagram connection: per-Owner publishing plus ADR 0028 means two OAuth hops and an App Review; Zernio's current API already covers import, publish, inbox and insights |
| GAP-2 | medium | S | The Niche Report caches Google Search grounding output and sends it to every Business, which conflicts with the Gemini API grounding terms |
| GAP-3 | medium | M | Pro under Meta's messaging rules: the 24 h Instagram reply window, templates for alerts to the Owner, and "sale alerts" with no Instagram signal |
| GAP-4 | medium | S | Photos with people go into AI scenes and get published: `has_people` is computed and never used, and no consent is recorded |
| GAP-9 | medium | M | No plan for the legal entity, IVA or CFE e-invoicing needed to charge Uruguayan businesses |
| GAP-11 | medium | M | Scheduling end to end: Zernio already schedules, but the confirmation, the failure and any cancellation have to reach the Owner outside the 24 h window |
| GAP-5 | low | S | Published Posts have no alt text, and Carousel text is baked into the images; Zernio and Instagram both accept alt text |
| GAP-6 | low | S | AI scenes: no disclosure option, no record of which images are AI, and no check of Instagram's AI label, against Uruguay's misleading-advertising rule |
| GAP-7 | low | M | Calls to action point nowhere (no sales WhatsApp, address or hours collected), and there is no way to measure inquiries |
| GAP-8 | low | M | The identity model is one phone, one Business, which blocks staff, agencies, Owners with two businesses and phone changes |
| GAP-10 | low | L | Mercado Libre is the missing LatAm integration: a Catalog with prices, and real sale and question events |
| GAP-13 | low | S | Photos sent "as a document" to keep quality are rejected, and the reply says videos are understood |

## Instagram capabilities: today's plan against Zernio

What the product plans to build itself, against what Zernio's API already offers, from the [Zernio OpenAPI spec](https://docs.zernio.com/api/openapi) v1.295.0 and the [Zernio pricing page](https://zernio.com/pricing) (both read 2026-10-19).

| Capability | Today's plan | Already available via Zernio |
|---|---|---|
| Import the Owner's Instagram Posts | Own Meta app ([ADR 0028](../../decisions/0028-read-instagram-with-our-meta-app.md)), testers only until App Review | `GET /v1/posts?source=external`, ~12 months, captions + `mediaItems` + `isAiGenerated` |
| Publish to the Owner's Instagram | One global account ([ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md)) | Per-profile `connect_url` (already coded, unused) |
| Comments and DMs (Pro) | Own Meta app, needs App Review for 2 permissions | `/v1/inbox/*`, webhooks `comment.received` and `message.received`, included per the pricing page |
| Insights (Pro) | Own Meta app | Analytics endpoints, included per the pricing page |
| Alt text | Not sent | `mediaItems[].altText`, max 1000 chars |
| Scheduling | `NotImplementedError` | `scheduledFor` + `timezone`, webhooks `post.published` and `post.failed`, `DELETE /v1/posts/{id}` |

Caveat from verification (GAP-1): spec v1.295.0 still tags Messages, Comments, Reviews and Mentions "Requires Inbox addon", and `/v1/analytics` still answers 402 for legacy plans ("included by default on usage-based plans"). "Included per the pricing page" therefore needs written confirmation from Zernio for our usage-based plan.

## Findings

### GAP-1: Decide on one Instagram connection; Zernio's current API already covers import, publish, inbox and insights

- **Severity**: high · **Effort**: M · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [zernio.py:85-111](../../../backend/app/publishing/zernio.py): `ensure_profile` and `connect_url` per Business already exist but are unused for real Owners.
  - [ADR 0028:10-11](../../decisions/0028-read-instagram-with-our-meta-app.md): Zernio was rejected on spec v1.292.0 (25 Posts, an Analytics add-on answering 402).
  - [ADR 0028:14](../../decisions/0028-read-instagram-with-our-meta-app.md): per-Business Zernio connect was rejected for "two OAuth hops".
  - [ADR 0028:26](../../decisions/0028-read-instagram-with-our-meta-app.md): the own app serves only testers until Advanced Access, App Review and Business Verification are done.
  - [roadmap.md:11, 26-27](../../roadmap.md): Pro replies are planned "through our own Meta app", and App Review and the Zernio-against-own-app decision are deferred to Phase 2.
  - [Zernio OpenAPI v1.295.0](https://docs.zernio.com/api/openapi) (read 2026-10-19), `GET /v1/posts?source=external`: "posts synced from the platform (existing/historical posts that were published outside Zernio) ... up to the last ~12 months per account"; `ExternalPostSummary` has `content`, `mediaItems` and `isAiGenerated`.
  - [Zernio OpenAPI](https://docs.zernio.com/api/openapi) connect scopes (read 2026-10-19): Instagram Login requests `instagram_business_content_publish`, `_manage_insights`, `_manage_comments`, `_manage_messages` and `_basic`.
  - [Zernio pricing](https://zernio.com/pricing) (read 2026-10-19): "Every feature is included on every account"; DMs and comments included; 3-10 accounts at US$6, 11-100 at US$3.
- **Problem**: Three findings point at the same decision without naming it: [ARCH-4](backend-architecture.md), [BUG-1](bugs-reliability.md) and [PRD-1](product.md) (Posts go to one shared account), [FE-5](frontend.md) and [PRD-13](product.md) (only Instagram testers can connect), and [OPS-3](platform-ops.md) (Meta review). Fixing per-Owner publishing on Zernio means each Owner also connects Zernio, so they make two Instagram OAuth trips: our app for the import, then Zernio to publish. Our own app still cannot serve non-tester Owners until App Review and Business Verification are done, and those need the privacy policy and deletion callback that don't exist yet ([FE-2](frontend.md), [SEC-6](security-privacy.md)). ADR 0028 rejected Zernio on a spec that has since changed: the API now returns about 12 months of external Posts with captions and Carousel items.
- **Recommendation**: Needs an ADR now, before the pilot, that picks one Instagram connection per Owner and would supersede parts of [ADR 0015](../../decisions/0015-instagram-login.md), [ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md) and [ADR 0028](../../decisions/0028-read-instagram-with-our-meta-app.md). Lean toward Zernio-only: connect in the wizard, import via `GET /v1/posts?source=external` (plus `POST /v1/posts/sync-external`), publish to the Owner's account, and collect bio and website in the wizard. Make it conditional on Zernio confirming in writing that, on our usage-based plan, Inbox (comments and DMs) and external-post sync carry no add-on or 402; the spec still says "Requires Inbox addon". Keep our own Meta app as option B and plan for App Review if Zernio cannot confirm.
- **Impact**: Unblocks real non-tester Owners weeks earlier (no Meta App Review on the critical path), one connect step instead of two for a 50+ phone-first Owner, and makes Pro ([GRW-7](growth-pricing-market.md), [PRD-21](product.md)) buildable without new permissions. Zernio's per-account fee ([COST-3](unit-economics.md)) becomes the only Instagram cost line.
- **Verifier note**: The reviewer checked Zernio OpenAPI v1.295.0 directly: `GET /v1/posts` takes `source=external` and its only error responses are 400 and 401 (no 402), and connect supports `headless=true`. [Pricing](https://zernio.com/pricing) (read 2026-10-19) gives 1-2 accounts free, 3-10 at US$6 and 11-100 at US$3. Two corrections. (1) The claim that the pricing page "now says there are no add-ons" is partly wrong: ADR 0028 already quoted "No add-ons" and flagged that it contradicted the spec; v1.295.0 still tags Messages, Comments, Reviews and Mentions "Requires Inbox addon", and `/v1/analytics` still answers 402 on legacy plans. What is actually new or missed is `GET /v1/posts?source=external`. (2) Option A drops bio and website, which ADR 0028 relied on and Zernio does not return, so keeping them as wizard fields is needed. Severity stays high because this is the gating decision for publishing to real Owners; for a single-tester pilot it is friction, not a hard blocker.
- **Related**: [PRD-1](product.md), [BUG-1](bugs-reliability.md), [ARCH-4](backend-architecture.md), [SEC-2](security-privacy.md), [GRW-2](growth-pricing-market.md), [COST-3](unit-economics.md), [FE-5](frontend.md), [PRD-13](product.md), [OPS-3](platform-ops.md). The synthesis ([summary.md](summary.md)) reconciles this with COST-3: use Zernio as the single connection for the pilot and roughly the first 20 accounts, only if Zernio confirms in writing; until then connect an Owner to Zernio only at their first approved publish; start Meta App Review anyway, and revisit own-app publishing once Zernio fees pass about US$100 a month.

### GAP-2: The Niche Report caches Google Search grounding output and sends it to every Business, which conflicts with the Gemini API grounding terms

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [niche_analyst.py:27](../../../backend/app/agents/niche_analyst.py): `TOOLS` is `url_context` plus `google_search`.
  - [niche_analyst.py:128-135](../../../backend/app/agents/niche_analyst.py): one grounded call produces the report.
  - [niche_cli.py:34](../../../backend/app/agents/niche_cli.py): the report is written to a JSON file.
  - [factory.py:59, 114-120](../../../backend/app/conversation/factory.py): one saved report becomes trend notes for every Business's Posts.
  - [ADR 0025:20](../../decisions/0025-weekly-niche-report.md): an on-demand report shown to the Owner in WhatsApp is planned (F3.7).
  - [ADR 0025:24-31](../../decisions/0025-weekly-niche-report.md): the consequences never mention the grounding terms.
  - [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms) (read 2026-10-19), Grounding with Google Search: Grounded Results may only be displayed with the associated Search Suggestions to the end user who submitted the prompt; no caching, syndicating or modifying.
- **Problem**: The grounded output is generated once by a CLI and stored. It is then rewritten into trend notes, mixed into Post prompts, and indirectly published for every Business. Owners never see Search Suggestions, and in WhatsApp they cannot be shown. That is caching, modifying and syndicating Grounded Results to users who did not submit the prompt. [COST-9](unit-economics.md) proposes sharing one report per niche across Businesses, which would make this worse. [AIQ-12](ai-quality.md) covers only staleness.
- **Recommendation**: Remove `google_search` from the Niche Analyst while its output is stored or reused, and keep `url_context` over the curated niche sites in [ADR 0025](../../decisions/0025-weekly-niche-report.md). The grounding display and caching terms should be recorded in ADR 0025 (needs an ADR update) and in the [configure-dependency](../../../.claude/skills/configure-dependency/SKILL.md) checklist. If live search is wanted later, use a search API whose licence allows storage and derived use.
- **Impact**: Removes a terms violation that could get the single Google project (text, images and transcription, [MOD-10](models.md)) suspended. The Search grounding fees go away too.
- **Verifier note**: The code matches, and the reviewer re-read the terms: "You will not, and will not allow your end user or any third party to, cache, frame, syndicate, resell, analyze, train on, or otherwise learn from Grounded Results", and you "will not modify, or intersperse any other content with" them. The only storage allowed is up to 2 years for display evaluation or end-user chat history; resubmitting is allowed only via a function call for a refined result, after which the interim results must be deleted. The terms page says nothing about URL context. Severity lowered from high: today the report is produced only by a manual CLI and `NICHE_REPORT_PATH` is optional, so it is a design-level compliance issue in a Should feature. Suspension of the whole Google project is possible but speculative. The fix stays small.
- **Related**: [COST-9](unit-economics.md), [AIQ-12](ai-quality.md), [MOD-9](models.md).

### GAP-3: Pro under Meta's messaging rules: the 24 h Instagram reply window, templates for alerts to the Owner, and "sale alerts" with no Instagram signal

- **Severity**: medium · **Effort**: M · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [pricing-section.tsx:88-89](../../../frontend/components/landing/pricing-section.tsx): "Replies to comments and DMs" and "Sale alerts on WhatsApp" are marked soon.
  - [roadmap.md:11](../../roadmap.md): a sales flow and a WhatsApp alert to the Owner on each sale.
  - [mvp.md:36](../../product/mvp.md): F1.8, proactive messages outside 24 h need approved templates, is Won't.
  - [integrations.md:258](../../architecture/integrations.md): `manage_comments` and `manage_messages` are not requested.
  - [Meta Messenger Platform policy](https://developers.facebook.com/docs/messenger-platform/policy/policy-overview) (read 2026-10-19), which covers the Instagram Messaging API: the window "For most user actions, it lasts 24 hours"; the Human Agent tag lets businesses "manually respond ... within a separate 7-day period"; automated chats must disclose "When required by applicable law".
- **Problem**: [PRD-21](product.md) and [GRW-7](growth-pricing-market.md) cover how Pro is positioned, but nobody tested whether it can work. An Instagram DM reply has to go out within 24 h of the customer's last message. The Human Agent tag extends that to 7 days, but only for manual replies. So a reply drafted by AI and approved by the Owner in WhatsApp is only sendable if the Owner approves it within the window. The alert that asks for that Approval usually lands outside the Owner's own 24 h WhatsApp window, so it needs an approved, paid utility template, and none exist (F1.8 Won't, [SEC-14](security-privacy.md)). The source for "sale alerts" is not built: Instagram emits no sale event for a Montevideo shop. The landing still promises both.
- **Recommendation**: Before building Pro's Phase 1 items, write a short feasibility spec covering: the source of DM and comment events (Zernio webhooks or our own app); utility templates for Owner alerts, which need the production number from [plan.md](../../implementation/plan.md) item 4; expiry of drafts before the 24 h Instagram window closes, and whether Owner-approved drafts qualify for the Human Agent tag; and defining a "sale" as a payment through the planned Mercado Pago link flow, or renaming the feature to inquiry alerts until that exists.
- **Impact**: Avoids selling a Pro feature that cannot meet Meta's windows. It also prices the template cost into Pro, roughly one utility template per alert, which sets the US$49 margin.
- **Verifier note**: The reviewer checked the Meta policy and confirmed the quotes; the constraints on Owner alerts outside the 24 h WhatsApp window and on DM reply windows are real, and Pro is in roadmap Phase 1, so this matters soon. Three corrections. (1) "Before collecting waitlist money" was wrong: Pro is a "Join the Pro list" waitlist that takes no payment. (2) Approved templates are already planned in plan.md item 4 ("own number + approved templates for proactive messages"), and they need a production WhatsApp number, not the shared Kapso sandbox. (3) "Sale alerts have no source" overstated it: the roadmap ties sales to the bot's own DM sales flow plus Mercado Pago payment links (Phase 2); the weaker point is that this source is not built yet.
- **Related**: [PRD-21](product.md), [GRW-7](growth-pricing-market.md), [SEC-14](security-privacy.md).

### GAP-4: Photos with people go into AI scenes and get published: `has_people` is never used, and no consent is recorded

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [schemas.py:21](../../../backend/app/agents/schemas.py): `has_people: bool`.
  - [asset_analyst.md:12](../../../backend/app/agents/prompts/asset_analyst.md): `has_people` is anyone visible, even partly.
  - [library.py:129-132](../../../backend/app/conversation/library.py): `describe()` exposes only the Product and the description; `has_people` never reaches the Orchestrator.
  - [instagram.py:109-111](../../../backend/app/jobs/instagram.py): up to 24 imported Instagram images ([config.py:70](../../../backend/app/config.py), `instagram_import_max_images`) become ready photo Brand assets automatically.
  - [tools.py:33-39](../../../backend/app/conversation/tools.py): style `design` generates new images from any asset id.
  - [categories.ts:33](../../../frontend/lib/categories.ts): Belleza, where nails and hair photos always show people.
  - [Ley 18.331](https://www.impo.com.uy/bases/leyes/18331-2008) (read 2026-10-19), art. 4 D ("Dato personal: información de cualquier tipo referida a personas físicas ... determinables") and art. 9 (consent "libre, previo, expreso e informado, el que deberá documentarse").
- **Problem**: Every chat photo and every imported Instagram photo becomes a reference the Orchestrator can pick, including shots of customers, staff, children or a client's living room. The image model is then asked to place "the product" in a new scene, so a real person's likeness can end up in an AI-altered ad on Instagram with no consent on record. The Asset Analyst already detects people, but nothing reads the flag. In Belleza the product is work on a person's body, so every photo has a person in it.
- **Recommendation**: Expose `has_people` in `<brand_photos>` and have the Orchestrator ask once, for either style, before using a photo with people ("¿Tenés permiso de las personas que salen?"), and record the answer as an Owner note. Add "do not include people unless the Owner asked" to the scene rules for `design`. Add a Terms clause that the Owner warrants rights to the photos they send. Imported Instagram photos with people can stay as Brand assets but go through the same check before use.
- **Impact**: Removes the most likely real-world complaint against a pilot Owner, and against Neitor: a customer's face in an ad. It also avoids Gemini safety blocks and paid retries on photos with people.
- **Verifier note**: The code matches: a grep finds no use of `has_people` outside tests and docs, and `FIXED_RULES` never mentions people. Severity lowered from high: (a) the Owner chooses the photos and approves every Post ([ADR 0007](../../decisions/0007-approve-every-post.md)), so the Owner is the controller for their own Instagram and Neitor acts for them; (b) the same consent question applies to `photos`-style Posts and to the Owner's own Instagram history, regardless of AI; (c) the pilot vertical is furniture, where people are incidental. Banning `has_people` photos from `design` by default would also block most Belleza Posts, which contradicts the finding's own Belleza point; hence "ask once" rather than a ban.
- **Related**: [SEC-3](security-privacy.md), [FE-2](frontend.md), [PRD-8](product.md), [SEC-6](security-privacy.md), [DOC-5](docs-process.md) (merged in the synthesis under the privacy, terms and consent item).

### GAP-9: No plan for the legal entity, IVA or CFE e-invoicing needed to charge Uruguayan businesses

- **Severity**: medium · **Effort**: M · **Confidence**: medium · **Verified**: confirmed
- **Evidence**:
  - No mention of factura, CFE, DGI, RUT or a legal entity anywhere in `docs/`, [PRODUCT.md](../../../PRODUCT.md) or [README.md](../../../README.md) (grep, audit observation, 2026-10-19).
  - [roadmap.md:29-30](../../roadmap.md): Mercado Pago links, billing and tiers; [plan.md:104](../../implementation/plan.md): billing via Mercado Pago or Stripe.
  - [Edicom](https://edicomgroup.com/es/blog/como-es-la-factura-electronica-en-uruguay) (read 2026-10-19): "deben emitir CFE todos los contribuyentes del Impuesto al Valor Agregado (IVA)"; new taxpayers "deberán emitir CFE desde el momento de su inscripción, sin plazos de adaptación"; IVA mínimo (Literal E) is included.
- **Problem**: [GRW-6](growth-pricing-market.md) covers prices in pesos with IVA included and collection through Mercado Pago. Charging Uruguayan businesses also needs an entity with a RUT, IVA on the subscription, and an electronic invoice (CFE) for every charge. Business customers need the e-factura to deduct IVA. Mercado Pago collects money but does not issue CFEs. None of this is planned, and it decides whether the US$29 is gross or net of 22% IVA.
- **Recommendation**: Before the first paid Owner: choose the entity (a Uruguayan SAS or a foreign company, with an accountant), register with DGI and BPS, and pick a CFE provider that has an API. Issue the CFE automatically from the Mercado Pago payment webhook and send the PDF in WhatsApp. This needs an ADR next to [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md), and an entry in the pilot-readiness gate ([DOC-1](docs-process.md)).
- **Impact**: Avoids a compliance blocker on day one of revenue, and gets the margin math right: US$29 including IVA leaves about US$23.8.
- **Verifier note**: Confirmed. A grep of docs, PRODUCT.md, README.md and AGENTS.md finds nothing on entity, IVA, CFE, DGI or RUT; the only hit for "factura" is an out-of-scope chat example. ADR 0031 prices in USD without saying whether IVA is included. The reviewer checked the rule (Edicom, plus secondary sources citing DGI Res. 2389/2023 and 2548/2023): since 2025-01-01, IVA taxpayers, including IVA mínimo, are electronic issuers from registration; Monotributo and a few others are excluded. The 22% math is right (29 / 1.22 = US$23.77). Not urgent for a free pilot, but it blocks the first paid Owner, and the entity choice changes the result; an accountant should confirm.
- **Related**: [GRW-6](growth-pricing-market.md), [PRD-12](product.md), [FE-17](frontend.md).

### GAP-11: Scheduling end to end: the confirmation, the failure and any cancellation have to reach the Owner outside the 24 h window

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [zernio.py:121-122](../../../backend/app/publishing/zernio.py): `raise NotImplementedError('scheduling is T30's Should part')`.
  - [mvp.md:86](../../product/mvp.md) (F5.3, provider-side scheduling: Should) and [mvp.md:36](../../product/mvp.md) (F1.8 templates: Won't).
  - [messages_es.py:83-84](../../../backend/app/copy/messages_es.py): `published()` is a free-form message.
  - [Zernio create post](https://docs.zernio.com/posts/create-post) (read 2026-10-19): `scheduledFor` ("When to publish") and `timezone` ("IANA timezone ... used to interpret a scheduledFor"); the webhooks `post.published`, `post.failed` and `post.cancelled` and `DELETE /v1/posts/{postId}` are in the [OpenAPI spec](https://docs.zernio.com/api/openapi) (read 2026-10-19).
- **Problem**: [PRD-10](product.md) covers that "subilo mañana a la tarde" is refused today. The hard part is not the scheduling itself, since Zernio takes `scheduledFor` and `timezone`. It is everything after: a Post scheduled for tomorrow 19:00 usually goes out after the Owner's 24 h WhatsApp window has closed. The "¡Publicado! 🎉 link" message, or the failure notice, can then only go as a template, so the Owner hears nothing, or the send fails. [BUG-10](bugs-reliability.md) is the same problem for `publish_pending`. There is also no "cancelalo" path to Zernio.
- **Recommendation**: Implement `when=` with `scheduledFor` and `timezone=Business.timezone`, and keep the Zernio post id on the Post. Handle the `post.published` and `post.failed` webhooks instead of polling. Get two utility templates approved ("Tu post ya está publicado: {link}" and "No pude publicar tu post, ¿lo reintento?"), and send a free-form message instead when the window is still open. Add a `cancel_post` tool that calls `DELETE /v1/posts/{id}`. Resolve "mañana a la tarde" to a concrete time and confirm it ("Lo subo mañana 19:00, ¿dale?").
- **Impact**: Delivers a feature sold in Basic with S-M effort, and closes BUG-10's silent outcomes with the same webhook and template work.
- **Verifier note**: Verified; the landing's Basic plan advertises "Publish now or schedule on Instagram" while F5.3 and F5.6 are Should. `DELETE /v1/posts/{postId}` deletes scheduled Posts ("Upload quota is automatically refunded for draft and scheduled posts"); published Posts need Unpublish. Whether a confirmation lands outside the window depends on timing ("usually"). Overlap to note: the Zernio webhook (T29: `post.published`/`post.failed`) is already planned in [integrations.md](../../architecture/integrations.md), and templates are planned in [plan.md](../../implementation/plan.md) item 4, which needs a production number rather than the Kapso sandbox. The new contribution is tying those together for scheduling, plus the cancel path.
- **Related**: [PRD-10](product.md), [BUG-10](bugs-reliability.md).

### GAP-5: Published Posts have no alt text, and Carousel text is baked into the images

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [zernio.py:123-128](../../../backend/app/publishing/zernio.py): `mediaItems` carry only `type` and `url`.
  - [draft.md:18](../../../backend/app/posts/prompts/draft.md): the Slide kicker, headline and body, so the Post's message lives inside the image.
  - [Zernio OpenAPI v1.295.0](https://docs.zernio.com/api/openapi) (read 2026-10-19), `MediaItem.altText`: "Accessibility alternative text for an image ... Instagram (feed images only, not Reels/Stories)", maxLength 1000.
  - [Instagram IG User Media reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media) (read 2026-10-19), `alt_text`: "Alternative text, up to 1000 character, for an image" ... "Only supported on a single image or image media in a carousel".
  - [PRODUCT.md](../../../PRODUCT.md): the "Accessibility & Inclusion" section covers the web UI only.
- **Problem**: Neitor's designed Carousels put headlines, numbers and calls to action into pixels. Screen-reader users, including older followers who use VoiceOver or TalkBack zoom, get Instagram's automatic description at best, and that misses the text. No dimension looked at the accessibility of the output; [FE-13](frontend.md) covers only the wizard.
- **Recommendation**: Add an alt field per Slide to the drafter output, build the alt text in code from the kicker, headline and body plus a short scene description, and send `mediaItems[i].altText`. For `photos` Posts, use the Asset Analyst description when one exists.
- **Impact**: Makes every Post readable for blind and low-vision followers at almost no cost. It is also a differentiator worth a line on the landing.
- **Verifier note**: Confirmed against the code, the Zernio spec and the Instagram reference. Everything is true as stated, but it is an inclusivity improvement with no functional or business risk, so severity was lowered to low. Effort is still S.

### GAP-6: AI scenes: no disclosure option, no record of which images are AI, and no check of Instagram's AI label

- **Severity**: low · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [prompts.py:3-8](../../../backend/app/carousel/prompts.py): `FIXED_RULES`, where the product is meant to stay unchanged; enforcement is prompt-only (see [AIQ-2](ai-quality.md)).
  - [tools.py:33-39](../../../backend/app/conversation/tools.py): "design: new images made from the photos".
  - [Ley 17.250 art. 24](https://impo.com.uy/bases/leyes-originales/17250-2000/24) (read 2026-10-19): "Queda prohibida cualquier publicidad engañosa", including by omission of essential data about "naturaleza, cantidad, origen".
  - [Zernio OpenAPI](https://docs.zernio.com/api/openapi) (read 2026-10-19), `ExternalPostSummary.isAiGenerated`: "whether Instagram labeled the media as AI-generated".
  - [PRODUCT.md](../../../PRODUCT.md) (Users): the Owner "fears posts that look fake or 'not like us'".
- **Problem**: For furniture, buyers judge scale, finish and color from the photo. An AI room that makes a two-seat sofa look like a three-seat one, or oak look like walnut, is the kind of omission or misrepresentation art. 24 targets, and the advertiser is the Owner. Nobody covered the legal and brand side. Nothing records which published images are generated, Owners get no option for a discreet "Imagen ambientada" note, and nobody checks whether Instagram labels these Posts as AI, which is exactly the "parece fake" fear in the persona.
- **Recommendation**: Store provenance per image (`ai_scene` or `owner_photo`) with the Post when Posts are persisted. Offer an optional "Ambientación generada con IA" line as a brand setting. Add a Terms clause that the Owner is the advertiser and checks product accuracy before approving. Put the anti-distortion effort into [AIQ-2](ai-quality.md) (checks that the product is unchanged), not into reading Instagram's AI label.
- **Impact**: Cuts legal and trust risk for pilot Owners at near-zero cost, and turns the "fake" fear into a visible setting the Owner controls.
- **Verifier note**: Partly true. Nothing persists whether an image is AI or an Owner photo (Posts are kept in `InMemoryPosts`), and the Ley 17.250 citation is accurate. But ambient staging is standard in furniture advertising, and every Post is reviewed and approved by the Owner ([ADR 0007](../../decisions/0007-approve-every-post.md)), who is the advertiser. The real legal risk is distortion of the product, which is AIQ-2, not the absence of a disclosure. Monitoring `isAiGenerated` is unlikely to be useful: Slides are re-rendered to JPEG by Takumi, which probably drops the C2PA/IPTC markers Meta uses to apply its label, and the field is read only through external-post sync. A modest trust and UX addition, not a medium legal gap.
- **Related**: [AIQ-2](ai-quality.md).

### GAP-7: Calls to action point nowhere, and there is no way to measure inquiries; add a tracked link-in-bio page

- **Severity**: low · **Effort**: M · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [schemas.py:30-37](../../../backend/app/onboarding/schemas.py): `BusinessInput` has name, category, one_liner, description, location, website and instagram_handle, but no sales phone, address or hours.
  - [brand_strategist.md:29](../../../backend/app/agents/prompts/brand_strategist.md): CTAs like "Escribinos por WhatsApp".
  - [draft.md:7](../../../backend/app/posts/prompts/draft.md): never invent addresses, so the CTA stays vague.
  - [open-questions.md:117](../../open-questions.md): "do we pull Instagram insights to show 'this post brought N messages'?"
- **Problem**: Small businesses in LatAm sell over WhatsApp, but Neitor never asks for the Business's sales number, address or opening hours. Every call to action is a vague "escribinos", and the drafter is right not to invent the missing facts. [PRD-11](product.md) proposes results through Instagram Insights, which needs scopes, and [GRW-9](growth-pricing-market.md) covers Neitor's own acquisition attribution. Nothing measures what the Owner actually cares about: how many people asked about a Product.
- **Recommendation**: Add an optional "WhatsApp de ventas" (defaulting to the Owner's number) and opening hours to the business step and the Brand Brain facts, so CTAs can name a concrete wa.me contact. Treat the tracked link-in-bio page as a pilot experiment: ask pilot Owners whether "N personas consultaron" would matter to them before building it.
- **Impact**: Gives Basic a results story with no Meta App Review, which helps retention and the Pro upsell. CTAs become specific and actionable.
- **Verifier note**: Partly true. `BusinessInput` has no sales phone or hours, but it does have `location` (the wizard asks "¿Dónde están? (opcional)"), and draft.md lets the drafter use the location from the Brand Brain. Owner notes can also carry facts like opening hours. The Owner's WhatsApp number (`owner_phone`) is already known and, for this persona, is often the sales line, and Instagram business profiles have their own WhatsApp contact button. So "CTAs point nowhere" is overstated. Collecting a sales WhatsApp and hours is a cheap improvement; the link-in-bio page is a plausible M-size idea, but it is new surface for a 2-person team and should be validated first. The open question at open-questions.md:117 already covers measuring results.

### GAP-8: The identity model is one phone, one Business; cheap to prepare now, a migration later

- **Severity**: low · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [0001_initial.sql:24](../../../backend/migrations/versions/0001_initial.sql): constraint `uq_businesses_owner_phone unique (owner_phone)`.
  - [library.py:36, 81, 123](../../../backend/app/conversation/library.py), [notes.py:67, 74, 88](../../../backend/app/conversation/notes.py), [onboarding.py:65](../../../backend/app/conversation/onboarding.py) and [queue.py:45](../../../backend/app/jobs/queue.py): every lookup is by `owner_phone`.
  - [mvp.md:104](../../product/mvp.md) (F7.1, one Business per WhatsApp number) and [mvp.md:107](../../product/mvp.md) (F7.4, roles: Won't).
- **Problem**: Three proposals from other auditors can't work on this schema: [PRD-23](product.md) (staff send photos), [GRW-15](growth-pricing-market.md) (an agency plan where one community manager runs many Businesses) and the "multiple accounts" tier in [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md). An Owner with a furniture store and a second brand cannot onboard both, and an Owner who changes phones loses their Business. Every query keys on the sender's phone, so the change gets more expensive as more call sites copy the pattern.
- **Recommendation**: Don't add a members table before demand exists. Do route every `owner_phone` lookup through one `resolve_business(sender)` helper now (S effort), so adding members or roles later touches one place. Revisit F7.1 and F7.4 when a pilot Owner actually asks for staff or a second Business.
- **Impact**: Unlocks staff, agency and multi-brand revenue without a data migration under load, and gives phone-change recovery.
- **Verifier note**: Facts confirmed, with about 31 `owner_phone` references across `backend/app`. The finding's own citations show this is a deliberate product decision: F7.1 is a Must and F7.4 roles are Won't, and ADR 0031 leaves multiple accounts to a later tier. With a one-Owner pilot, staff, agency and multi-brand needs are speculative, and a phone change can be handled by an operator updating one column. "Cheap to fix now" is optimistic: a members table plus a resolver replacing about 31 call sites, plus approval rules, is M. A centralised sender-to-Business helper is still worth having, because it keeps the later migration small.
- **Related**: [PRD-23](product.md).

### GAP-10: Mercado Libre is the missing LatAm integration: a Catalog with prices, and real sale and question events

- **Severity**: low · **Effort**: L · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [furniture-decor-uruguay.md:52](../furniture-decor-uruguay.md): Mercado Libre's "Hogar, muebles y jardín" grew 108% at Christmas 2023.
  - No Mercado Libre or Tiendanube integration in the docs or code; the only mention is Mercado Pago payment links at [roadmap.md:29](../../roadmap.md) (audit observation, 2026-10-19).
  - [Mercado Libre notifications](https://developers.mercadolibre.com.ar/en_us/products-receive-notifications) (read 2026-10-19): the topics `orders_v2` ("creation and changes to any of confirmed sales"), `questions`, `items` and `messages`.
- **Problem**: [AIQ-4](ai-quality.md) found the drafter never sees the Catalog, and [PRD-24](product.md) proposes reading price lists from a photo. Many Uruguayan furniture and home sellers already keep a structured catalog on Mercado Libre, with photos, prices and descriptions, and that is also where real sales and buyer questions happen. Pro's sale alerts (GAP-3) have no built source yet.
- **Recommendation**: Ask pilot Owners whether they keep a Mercado Libre catalog. Only if several do, prototype a read-only item import (title, price, pictures) into Products and Brand assets. Leave the `orders_v2` and `questions` events for Pro, after the DM sales flow exists.
- **Impact**: Accurate prices and specs in Posts (fewer AIQ-4 errors), faster onboarding, and a real sales signal that gives Pro something concrete to sell.
- **Verifier note**: A valid new idea: nothing about Mercado Libre or Tiendanube is in the code or decisions, and the notification topics exist. Two corrections. "Pro's sale alerts have no source anywhere else" overstated it: the roadmap's source is the bot's own DM sales flow with Mercado Pago payment links. And it is an L-effort integration whose value depends on how many pilot Owners actually sell on Mercado Libre, which the finding itself says to validate first. As an unvalidated, later-phase idea for a 2-person team, it is low priority, not medium.

### GAP-13: Photos sent "as a document" to keep quality are rejected, and the reply says videos are understood

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [kapso_webhook.py:63-64](../../../backend/app/channels/kapso_webhook.py): any type other than text, button, image, audio or album becomes kind `other`, documents included.
  - [messages_es.py:15-17](../../../backend/app/copy/messages_es.py): `UNSUPPORTED_MEDIA` says "solo entiendo texto, audios, fotos y videos".
  - [events.py:299](../../../backend/app/conversation/events.py): that reply is sent for unsupported media.
- **Problem**: WhatsApp compresses normal photos. Owners who care about quality, or whose photographer sends originals, often forward photos as documents (JPEG or HEIC files). Those arrive as `document` and are rejected, even though full-quality input is what the 2K scenes and "photos as they are" Posts need. The rejection message also claims videos are understood, and they are not ([PRD-19](product.md)).
- **Recommendation**: Parse `document` messages whose `mime_type` is `image/*` (jpeg, png, webp, heic) as kind `image`, using the same download path, then downscale to the existing limits. Change `UNSUPPORTED_MEDIA` to drop "videos" until Reels exist.
- **Impact**: Better input quality for the Posts that matter most, and one fewer false promise in the copy.
- **Verifier note**: Verified: `parse_message` handles only text, interactive `button_reply`, image, audio and the album marker, so `document` and `video` fall through to `other`, and a video is rejected with a message claiming videos are understood. The fix is cheap: `pillow-heif` is already a dependency ([images.py](../../../backend/app/media/images.py) registers the HEIF opener) and [uploads.py](../../../backend/app/onboarding/uploads.py) handles `image/heic`, so routing `image/*` documents through the image path is S. Low is right; WhatsApp's HD photo option also reduces how often Owners send photos as documents.
- **Related**: [PRD-14](product.md), [AIQ-16](ai-quality.md).
