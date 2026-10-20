# Frontend: landing, wizard and renderer

This doc covers the frontend dimension of the 2026-10-19 product and codebase audit of Neitor AI (see the [audit index](README.md) and the [cross-dimension summary](summary.md)): the public landing page, the onboarding wizard the Owner opens from a magic link (`/o/[token]`), and the Takumi render route that draws every designed Slide. The code was read at commit `dc0bc01`. An independent adversarial reviewer checked every finding against the code and the cited sources: "confirmed" means it held as written, and "adjusted" means the reviewer corrected its severity or details. The severity and recommendation below already include those corrections. Per the team rule, nothing here recommends frontend unit tests; Playwright E2E tests are allowed.

## Summary

For a hackathon build the frontend is solid. The landing is almost all server components, styling sits on design tokens, the wizard follows [web-app.md](../../design/web-app.md) closely (Instagram-first per [ADR 0032](../../decisions/0032-instagram-first-onboarding.md), an upload queue, resume from server state, Spanish error copy), and the render route ([route.ts](../../../frontend/app/api/render/route.ts)) is small and protected by a bearer secret.

The serious gaps appear once real Owners arrive:

- Every landing CTA (8 links) opens the shared Kapso sandbox number, which only answers registered phones, so a stranger gets no reply (FE-1).
- The live landing is in English and promises things that aren't built: Posts going to the Owner's own Instagram (they go to one demo account), scheduling, three options to pick from, and a weekly plan (FE-3, FE-4). A Spanish translation exists, but only as uncommitted work in another local worktree.
- There is no privacy policy, terms or data-deletion page, and Meta's App Review needs a privacy policy URL before any Owner who isn't an Instagram tester can connect Instagram (FE-2).
- Nothing measures the funnel or reports frontend errors (FE-8).
- Production and the carousel renderer run on a Vercel Hobby team, which is licensed for non-commercial use only (FE-9).

On the engineering side, the wizard's 3-second poll re-downloads images because every poll returns freshly signed URLs and `thumbnail_url` is always null (FE-6), and uploads send raw photos of up to 10 MB with no downscaling and no timeout (FE-7). Smaller items: tap targets below the team's own 48 px rule, no autosave inside a step, no timeouts in `lib/api.ts`, no frontend CI, and no OG image or `metadataBase`.

## Findings at a glance

Effort: S is under half a day, M is 1-2 days, L is about a week, XL is more than a week.

| Id | Severity | Effort | Finding |
|---|---|---|---|
| FE-1 | high | M | Every landing CTA opens the shared Kapso sandbox, so real visitors get no reply |
| FE-2 | high | M | No privacy policy, terms or data-deletion pages, which blocks Meta App Review and informed consent under Uruguayan law |
| FE-3 | medium | S | The live landing is in English for a Rioplatense persona; the Spanish translation sits uncommitted in another worktree |
| FE-4 | medium | S | The landing promises capabilities that aren't shipped, including publishing to the Owner's own Instagram |
| FE-5 | medium | S | The Instagram step strands Owners who aren't testers on an Instagram error page |
| FE-6 | medium | S | The wizard's 3-second poll re-downloads images because their URLs change on every poll |
| FE-7 | medium | M | Uploads send raw originals of up to 10 MB with no downscaling, no timeout and no automatic retry |
| FE-8 | medium | M | No funnel analytics and no frontend error monitoring |
| FE-9 | medium | S | The production frontend and the carousel renderer run on a non-commercial Vercel Hobby team |
| FE-12 | medium | M | No autosave inside a step, and the header back button breaks the hardware back stack |
| FE-15 | medium | M | No frontend CI: no lint, typecheck, build or E2E smoke test, even though a mock backend exists |
| FE-10 | low | M | Render path: one failed Slide throws away every paid AI scene; no retry |
| FE-11 | low | S | No OG image, `metadataBase`, robots or sitemap; shared links preview as plain text from a `*.vercel.app` domain |
| FE-13 | low | S | Tap targets and text sizes are below the team's 48 px rule for a 45+ persona |
| FE-14 | low | S | API calls have no timeouts; errors disappear as toasts; no root 404 or error page |
| FE-16 | low | M | The wizard's brand preview is a CSS mock that doesn't match the real Takumi designs |
| FE-17 | low | L | Pricing CTAs capture nothing: the Pro waitlist is a dead link, and there is no plan, usage or billing surface |
| FE-18 | low | L | A minimal read-only "Tus posts" page: history, status and links |
| FE-19 | low | S | Landing performance nits: Toaster in the root layout, slow hero entrance, unused theme hook |

## Key numbers

Values come from the audit's reading of the code at `dc0bc01` unless a source is linked. The poll re-download row is the auditor's estimate; the reviewer's lower, more realistic figure is in FE-6.

| Item | Value |
|---|---|
| Landing CTAs that open the sandbox wa.me link | 8: hero, header, pricing (x3), footer (x2), final CTA ([cta-link.tsx:31](../../../frontend/components/landing/cta-link.tsx)) |
| Wizard steps and required inputs | 6 steps ([onboarding.ts:3-10](../../../frontend/lib/onboarding.ts)). Required: name, category, one-liner, at least 1 Product name, at least 3 photos, at least 1 color (unless there is no brand), 1-3 words, goal (plus an emoji if tone is shown) |
| Tap targets against the 48 px spec | photo ✕ 32 px, color ✕ 28 px, header back 40 px, WhatsApp pill 40 px (FE-13) |
| Upload size | originals up to 10 MB each, up to 15 photos plus 5 photos for each of 5 Products; the backend only uses references of 1536 px or less and 1080×1350 Posts ([images.py:10-11](../../../backend/app/media/images.py)) |
| Poll re-download (estimate) | a poll every 3 s while analysis runs (4 concurrent jobs); 24 Instagram imports at about 150-300 KB is about 5 MB per poll; after a reload, the Owner's own photos add up to 15 × 3-8 MB; over 20-80 polls that is tens to hundreds of MB. Assumes a full Instagram import and a reload mid-analysis |
| Vercel Hobby limits ([Vercel Hobby plan](https://vercel.com/docs/plans/hobby), read 2026-10-19) | non-commercial use only; 4 CPU-hours of Active CPU; 1 hour of runtime logs; Web Analytics 50k page views and no custom events ([Vercel Analytics limits](https://vercel.com/docs/analytics/limits-and-pricing), read 2026-10-19). Pro is US$20 per developer seat per month, about US$40 for 2 |
| Analytics options | Vercel Web Analytics on Hobby: page views only. PostHog free tier: 1M events and 5k replays a month, per a third-party source ([Userpilot on PostHog pricing](https://userpilot.com/blog/posthog-pricing/), read 2026-10-19; the reviewer confirmed the figures) |
| Payments | Stripe is not available in Uruguay ([Stripe global availability](https://stripe.com/global), read 2026-10-19); Mercado Pago Uruguay supports subscriptions ([Mercado Pago Suscripciones](https://www.mercadopago.com.uy/developers/es/docs/subscriptions/resources/tutorial-videos), read 2026-10-19) |

## Findings

### FE-1: Every landing CTA opens the shared Kapso sandbox, so real visitors get no reply

- **Severity**: high · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [whatsapp.ts:1-3](../../../frontend/lib/whatsapp.ts) builds `WHATSAPP_START_URL` from `NEXT_PUBLIC_WHATSAPP_URL` plus the prefill "Hi Neitor".
  - [cta-link.tsx:31](../../../frontend/components/landing/cta-link.tsx): every `CtaLink` defaults to that URL; there are 8 WhatsApp CTAs across the hero, header, pricing (x3), footer (x2) and final CTA.
  - [PRODUCT.md:36](../../../PRODUCT.md): the CTA is "the shared Kapso sandbox number, which only answers phones with an active sandbox session".
  - [frontend/README.md:56](../../../frontend/README.md): production `NEXT_PUBLIC_WHATSAPP_URL` is a wa.me link to a +56 (Chilean) number.
  - [open-questions.md:24-25](../../open-questions.md): a free US number and the recipient limit are still open questions.
  - [Kapso: use the sandbox for testing](https://docs.kapso.ai/docs/how-to/whatsapp/use-sandbox-for-testing.md) (read 2026-10-19): sessions are per registered number, sending to an unregistered number fails with "Active sandbox session required to send messages", inbound messages route only to the active session, and "Multiple recipients" is listed as unsupported.
- **Problem**: A Uruguayan Owner who taps "Get started on WhatsApp" lands in a chat with a Chilean sandbox number, sends "Hi Neitor", and gets nothing back, because the backend can't reply to a phone that hasn't activated a sandbox session. Nothing captures the lead and the page gives no explanation, so each landing visit is lost. Pilot Owners recruited in person also have to be registered by hand, and that step is documented nowhere in the frontend.
- **Recommendation**: Keep the `NEXT_PUBLIC_SIGNUP_MODE=waitlist|whatsapp` idea, but make it as small as possible: a Spanish form (name, WhatsApp number, Instagram handle) posting to `POST /api/leads`, or even a prefilled mailto or Google Form, until the Phase 2 production number exists. Flip to `whatsapp` mode when the number is live. Separately, confirm with Kapso whether one project can hold several active sandbox sessions before recruiting a second pilot Owner.
- **Impact**: Turns a 0% landing-to-conversation rate for strangers into captured leads, and avoids a first impression of "the bot is dead" with prospects and investors.
- **Verifier note**: The code claims hold, and the reviewer counted the same 8 CTAs (hero, header, 3 pricing, the footer `CtaLink`, a footer text link, the final CTA). Severity drops from critical to high: the team already documents the limitation ([PRODUCT.md](../../../PRODUCT.md) Positioning; [README.md:13](../../../README.md)), and [roadmap.md](../../roadmap.md) makes Phase 1 a pilot with one Owner, which the sandbox supports, with "a production WhatsApp number" in Phase 2. The real cost today is a "dead bot" impression on judges, investors and organic visitors, not a blocked pilot. Because the sandbox doesn't support multiple recipients, a pilot with more than one Owner is itself blocked, which matters more than the landing.
- **Related**: [PRD-3](product.md), [OPS-3](platform-ops.md), [DOC-1](docs-process.md), [GRW-9](growth-pricing-market.md)

### FE-2: No privacy policy, terms or data-deletion pages, which blocks Meta App Review and informed consent under Uruguayan law

- **Severity**: high · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [frontend/app/](../../../frontend/app) holds only `page.tsx`, `o/`, `api/`, `dev/` and `mock-api/`: no privacy, terms or deletion route.
  - [site-footer.tsx:5-11 and :40-45](../../../frontend/components/landing/site-footer.tsx): the footer links only to product anchors and WhatsApp.
  - [business-step.tsx:63-70](../../../frontend/components/onboarding/steps/business-step.tsx) and [instagram-step.tsx:101-111](../../../frontend/components/onboarding/steps/instagram-step.tsx): the wizard collects Business data, photos and an Instagram token with no consent or notice text.
  - A grep for privacy, deletion, deauthorize and habeas in `backend/app` and `docs` finds nothing (audit observation, 2026-10-19).
  - [ADR 0028:26](../../decisions/0028-read-instagram-with-our-meta-app.md): serving non-testers needs Advanced Access, App Review and Business Verification.
  - [Meta: Instagram Platform App Review](https://developers.facebook.com/documentation/instagram-platform/app-review.md) (read 2026-10-19): "Privacy Policy URL – The privacy policy URL that your app users can visit" is a required app setting.
  - [Ley 18.331](https://www.bps.gub.uy/bps/file/10816/25/ley-18.331---habeas-data.pdf) (read 2026-10-19): art. 4 C says consent must be "libre, inequívoca, específica e informada", and databases must be registered with the URCDP.
- **Problem**: The Meta app can't pass App Review without a privacy policy URL, so the Instagram connect (wizard step 2) stays limited to manually added testers. Owners hand over photos, Business details, their Instagram account and Voice notes, all processed by Google Gemini, Supabase, Kapso and Meta, Zernio, Vercel and Railway. No page says what is stored, why, for how long, or how to delete it, so under Ley 18.331 that consent is not "informed". A paid product ([ADR 0031](../../decisions/0031-pricing-free-basic-pro.md)) also needs terms.
- **Recommendation**: Before onboarding any Owner outside the team, and as a prerequisite for the Phase 2 App Review: add static Spanish `/privacidad` and `/terminos` pages linked from the footer, plus a one-line notice on wizard step 1 and on the Instagram step. List the processors (Google Gemini, Supabase, Kapso and Meta, Zernio, Vercel, Railway), retention, and a "borrar mis datos" path. Point the Meta app's Privacy Policy and data-deletion URLs at them. Get advice on URCDP database registration rather than relying on the consent framing.
- **Impact**: Unblocks App Review, the only path to connecting Instagram for Owners outside the team. Removes legal exposure before the first paid Owner and builds trust with a persona who fears losing control of their account.
- **Verifier note**: Confirmed: no such route, footer, notice text or doc exists, and Meta's page lists the Privacy Policy URL as required. Severity drops from critical to high because App Review is explicitly Phase 2 in [roadmap.md](../../roadmap.md) (it also needs Business Verification), and the Phase 1 pilot is one Owner who can be added as an Instagram tester, so nothing is blocked today. The legal framing needs nuance: Ley 18.331 exempts data processed under a contractual relationship from prior consent, so the firmer obligations are the duty to inform and URCDP registration. A short notice plus a policy page is still cheap and needed before any non-team Owner or payment.
- **Related**: [SEC-3](security-privacy.md), [SEC-6](security-privacy.md), [PRD-8](product.md), [DOC-5](docs-process.md), [GAP-4](cross-cutting-gaps.md)

### FE-3: The live landing is in English for a Rioplatense persona; the Spanish translation sits uncommitted in another worktree

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [page.tsx:14-23](../../../frontend/app/page.tsx) sets an English title, description and OG data, and line 31 sets `lang="en"` on the wrapper.
  - [layout.tsx:28](../../../frontend/app/layout.tsx) sets `html lang="es"` and lines 16-19 a Spanish default description, so the two disagree.
  - [hero.tsx:8](../../../frontend/components/landing/hero.tsx) says "Speaks your Spanish" in English, and line 17 shows chat timestamps such as "11:41 PM".
  - [PRODUCT.md:13 and :41](../../../PRODUCT.md): the landing is in English "for hackathon judges".
  - [mvp.md:131](../../product/mvp.md): "languages other than Spanish" are out of scope.
  - The `mojarra` worktree holds 17 modified files (PRODUCT.md, `frontend/README.md`, `page.tsx`, 13 landing components and `whatsapp.ts`, whose prefill becomes "Hola Neitor") on an unmerged Spanish-landing branch, never committed (audit observation with `git status`, 2026-10-19).
  - [comparison-section.tsx:24](../../../frontend/components/landing/comparison-section.tsx): a `min-w-165` table forces sideways scrolling on phones.
- **Problem**: The landing's main reader is now a Uruguayan Owner in their 50s, and it addresses them in English, with US-style 12-hour times and a 660 px comparison table that scrolls sideways on a phone. A team memory note reportedly says the translation shipped, but it only exists as uncommitted local changes, so docs, memory and production disagree. Prices are only in US$, with no peso reference.
- **Recommendation**: Coordinate with whoever owns the `mojarra` worktree, rebase it onto `main` (after #56), review and merge it. Drop `lang="en"`, set Spanish OG data and the `es_UY` locale, and use 24-hour times. Update PRODUCT.md's "landing is in English" line. Stacked comparison cards below `md` and a peso reference are optional polish.
- **Impact**: A precondition for any organic or referral conversion from the target persona, and the work is mostly done already.
- **Verifier note**: Confirmed: English metadata and `lang="en"` on the wrapper against `html lang="es"`, English hero copy and "11:41 PM", and 17 uncommitted files in `mojarra`. That branch is based on `0813ac8` (#55), before #56, so it needs a rebase, and it may be another session's active work. The English landing is a deliberate, documented choice for judges and investors. The comparison table is wrapped in `overflow-x-auto`, so it scrolls inside its own box, not the page, which is minor. The claim that team memory says the translation shipped could not be verified. Severity drops to medium: Owners currently enter through WhatsApp, not the landing, and strangers can't use the product yet (FE-1).
- **Related**: [PRD-6](product.md), [GRW-14](growth-pricing-market.md), [DOC-3](docs-process.md), [GRW-9](growth-pricing-market.md)

### FE-4: The landing promises capabilities that aren't shipped, including publishing to the Owner's own Instagram

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [pricing-section.tsx:67](../../../frontend/components/landing/pricing-section.tsx) "Published to your Instagram", :78 "A weekly content plan", :79 "Publish now or schedule on Instagram".
  - [hero.tsx:33](../../../frontend/components/landing/hero.tsx): "posts it to your Instagram".
  - [approval-demo.tsx:75](../../../frontend/components/landing/approval-demo.tsx): "It goes live Saturday at 10:00"; [how-it-works.tsx:96](../../../frontend/components/landing/how-it-works.tsx): "Three options… Pick the one you like", and :130 "Scheduled for Saturday 10:00".
  - [faq-section.tsx:18](../../../frontend/components/landing/faq-section.tsx): "learns… from every correction you make", which [roadmap.md](../../roadmap.md) lists as Phase 1.
  - [factory.py:48](../../../backend/app/conversation/factory.py): the publishing account comes from the env var `ZERNIO_ACCOUNT_ID`, one demo account per [ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md).
  - [zernio.py:121-122](../../../backend/app/publishing/zernio.py): scheduling raises `NotImplementedError`.
  - [conversation-design.md:47](../../product/conversation-design.md): Variations are still a draft.
- **Problem**: With real Owners, an approved Post goes to the demo account, not theirs. Scheduling and the weekly plan don't exist, and the three-option picker is a draft. PRODUCT.md forbids fabricated social proof, and the same reasoning covers fabricated capabilities. An Owner who signs up because of these promises will feel misled on the first Post, which undermines the "you stay in control" positioning.
- **Recommendation**: Add "pronto" labels (the existing `<Label>`) to scheduling and the weekly plan. Change the demo endings to "Publicado ✓" instead of scheduled. Leave the FAQ line, or soften it to "from what you tell me". Don't build a `capabilities.ts` registry for 4 strings. Track per-Business publishing ([ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md)) as the real pilot prerequisite in the backend audit.
- **Impact**: Avoids churn and refund disputes from the first paying Owners, and keeps the landing honest for investors.
- **Verifier note**: Mostly confirmed. The approval flow also returns `scheduling_not_available`, the prompts say "Never say a post was scheduled", and no weekly-plan code exists. One correction: the FAQ claim about learning from every correction is partly shipped through Owner notes ([ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md): remember and forget tools that the Post drafter reads). The landing mirrors [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md)'s tier contents and PRODUCT.md's MVP list, so this is a gap between the plan and what is built, not invented copy. Severity drops to medium: the per-Business publishing gap is a backend pilot blocker covered elsewhere, and in-person pilot Owners can have expectations set directly.
- **Related**: [PRD-6](product.md), [GRW-14](growth-pricing-market.md), [DOC-3](docs-process.md), [GRW-9](growth-pricing-market.md)

### FE-5: The Instagram step strands Owners who aren't testers on an Instagram error page

- **Severity**: medium · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [onboarding.ts:3-10](../../../frontend/lib/onboarding.ts): Instagram is step 2.
  - [instagram-step.tsx:37-47](../../../frontend/components/onboarding/steps/instagram-step.tsx): `connect()` calls `window.location.assign(auth_url)`, and :65-72 make "Conectar Instagram" the primary orange CTA.
  - [ADR 0028:26](../../decisions/0028-read-instagram-with-our-meta-app.md): "In development mode it works only for accounts added as Instagram testers".
  - [A craft3-instagramFeed issue](https://github.com/wearealloy/craft3-instagramFeed/issues/1) (read 2026-10-19): users without a role get the OAuthException "Insufficient developer role" on the authorize page instead of being redirected.
  - [Chatwoot: Instagram via Instagram Business Login](https://developers.chatwoot.com/self-hosted/configuration/features/integrations/instagram-via-instagram-business-login.md) (read 2026-10-19): the fix is to add the account in App Roles.
- **Problem**: Until App Review passes (blocked by FE-2), any pilot Owner not added as a tester taps the main CTA and lands on an Instagram error inside WhatsApp's in-app browser. The callback never fires, so the wizard's `connected=0` error state never shows. A 50-something Owner has no obvious way back, and the onboarding is abandoned at step 2 of 6.
- **Recommendation**: Add "invitar como Instagram tester y aceptar la invitación" to the pilot onboarding checklist. The cheapest code guard is a backend flag such as `INSTAGRAM_CONNECT_ALLOWLIST` (phones or Business ids): when the Owner isn't on it, `OnboardingState` reports Instagram as unavailable and the wizard skips straight to Products. Smoke-test the real connect inside WhatsApp's in-app browser on iOS and Android.
- **Impact**: Removes a likely drop-off at step 2 for every Owner who isn't a tester during the pilot.
- **Verifier note**: The code matches, and ADR 0028 and [integrations.md](../../architecture/integrations.md) confirm only accepted testers work in development mode. The "Insufficient developer role" reports are community sources, not official Meta docs. The step has a visible skip ("No tengo, o lo hago después") and the in-app browser has a back button, so the auditor's "100% drop-off" is overstated. The team already documents "add the account as Instagram Tester" in [demo-plan.md](../../demo-plan.md) and integrations.md, and the Phase 1 pilot is one Owner who will be invited. The risk is real once several Owners onboard before App Review.
- **Related**: [PRD-13](product.md)

### FE-6: The wizard's 3-second poll re-downloads images because their URLs change on every poll

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [photos-step.tsx:21](../../../frontend/components/onboarding/steps/photos-step.tsx) sets `POLL_MS = 3000`; :48-55 poll the full state while any photo isn't analyzed; :220-225 `mergeAssets` replaces every asset with the fresh copy; :197 renders Instagram imports with `src={asset.thumbnail_url ?? asset.url}`, and :144 renders the Owner's photos with `previews[asset.id]` first, then the same fallback.
  - [onboarding.py:500-502](../../../backend/app/api/onboarding.py) calls `create_signed_urls` on every GET (Supabase signed tokens differ per call), :565 always sets `thumbnail_url=None`, and :41 sets `SIGNED_URL_TTL_S = 3600`.
  - [brand-step.tsx:43](../../../frontend/components/onboarding/steps/brand-step.tsx): the brand preview also uses the full original.
  - [runner.py:26](../../../backend/app/jobs/runner.py): 4 concurrent analysis jobs, so polling runs for minutes with 15 uploads plus 24 Instagram imports.
- **Problem**: Each poll returns new signed URLs, so every `<img>` gets a new `src` and the browser fetches it again. That covers Instagram imports always, and the Owner's own photos after a reload. Thumbnails about 110 px wide load originals of up to 10 MB. On a prepaid Uruguayan data plan this can burn tens to hundreds of MB during one onboarding (auditor's estimate; the reviewer's realistic worst case is tens of MB, see the verifier note), and the grid flickers and lags.
- **Recommendation**: Frontend first (S): in `mergeAssets`, keep the existing `url` for asset ids already in state and copy only the status fields (`analyzed`, `status`, `archived`). Backend (S): fill `thumbnail_url` with a signed URL of the existing 1536 px `-llm.jpg` copy, or a smaller thumbnail, for the grids and the brand preview. A lighter status-only poll endpoint is optional.
- **Impact**: Cuts wizard image traffic by roughly 10-100x during analysis (estimate), renders the grid faster on 4G, and spends fewer Supabase egress bytes.
- **Verifier note**: The mechanism is confirmed, but two details are overstated. Photos uploaded in the current session render from `previews[asset.id]`, local blob URLs, so they are not re-downloaded; only photos loaded after a page reload use the signed original. Instagram imports, which do re-download on every poll, are Instagram's JPEGs of about 1080-1440 px (a few hundred KB), not 10 MB originals. A realistic worst case is about 24 images × ~250 KB × ~15-25 polls, so tens of MB (estimate). Wasteful and flickery, but bounded to one step of a one-time onboarding.

### FE-7: Uploads send raw originals of up to 10 MB with no downscaling, no timeout and no automatic retry

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [upload.ts:3](../../../frontend/lib/upload.ts) sets `MAX_PHOTO_BYTES` to 10 MB, :5 accepts HEIC, and :61-83 send the original file through an XHR PUT with no `xhr.timeout`.
  - [use-photo-uploads.ts:40-45](../../../frontend/components/onboarding/use-photo-uploads.ts) rely on `beforeunload`, which mobile in-app browsers mostly ignore, and :103-109 retry only on a manual tap.
  - [uploads.py:15](../../../backend/app/onboarding/uploads.py): `MAX_PIXELS` is 60 MP, so larger photos are rejected as unreadable.
  - [images.py:10-11](../../../backend/app/media/images.py): everything downstream uses 1080×1350 Posts and 1536 px references.
  - [heic-normalize on libraries.io](https://libraries.io/npm/heic-normalize) (read 2026-10-19): Safari 17+ decodes HEIC natively; Chrome, Firefox and Edge can't.
- **Problem**: Nothing downstream uses more than 1536 px, yet the Owner uploads 3-8 MB originals, up to 15 of them plus Product photos, from a phone on mobile data with 3 uploads in parallel. Photos over 10 MB or 60 MP hit a dead-end "Probá con otra". A stalled connection (the Owner switches to WhatsApp, the phone sleeps) leaves a spinner with no timeout, and "Siguiente" stays blocked ("Esperá un toque…"). Originals also keep EXIF GPS data showing where the Owner lives or works.
- **Recommendation**: Downscale in the browser before requesting the upload ticket: `createImageBitmap(file, {imageOrientation: 'from-image'})`, longest side 2048 px, `canvas.toBlob('image/jpeg', 0.85)`, falling back to the original if decoding fails (for example HEIC on Chrome). Apply the 10 MB check after resizing. Set `xhr.timeout` to about 60 s and auto-retry once on `online`. Check manually on a real iPhone and an Android phone; Playwright device emulation is optional.
- **Impact**: Roughly 5-10x less upload data and time per photo (estimate), no rejections for very large photos, fewer stuck wizards, and GPS data stripped.
- **Verifier note**: Confirmed. Corrections: the 60 MP cap's comment says "A 50 MP phone photo fits", and phones save 12-24 MP binned images by default, so rejections for 50-200 MP photos are rare edge cases that usually also exceed 10 MB. EXIF GPS stays only in the private Storage original; published images are re-encoded (`to_post_image` and the Takumi renderer), so nothing leaks publicly. A stalled XHR on a lost connection usually fires `onerror` eventually, but a timeout is still sensible. Severity drops to medium: a one-time onboarding of 3-15 photos for a one-Owner pilot.

### FE-8: No funnel analytics and no frontend error monitoring

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [package.json:11-26](../../../frontend/package.json) has no analytics or Sentry dependency, and a grep for analytics, posthog, gtag or speed-insights in `app`, `components` and `lib` finds nothing (audit observation, 2026-10-19).
  - [error.tsx:7-19](../../../frontend/app/o/[token]/error.tsx): the wizard's error boundary neither logs nor reports.
  - [frontend/README.md:32](../../../frontend/README.md): the project is on a Hobby team; [Vercel Hobby plan](https://vercel.com/docs/plans/hobby) (read 2026-10-19): runtime logs are kept 1 hour.
  - [Vercel Analytics limits](https://vercel.com/docs/analytics/limits-and-pricing) (read 2026-10-19): Hobby has 50k page-view events and no custom events.
  - [Userpilot on PostHog pricing](https://userpilot.com/blog/posthog-pricing/) (read 2026-10-19, third-party): the PostHog free tier has 1M events and 5k replays a month; verify on PostHog's own pricing page.
  - [mvp.md:131](../../product/mvp.md): the "analytics" Won't is an Owner-facing feature, not our own funnel.
- **Problem**: The team can't answer how many visitors tap the CTA, which of the 6 steps Owners abandon, whether "Son 5 minutos" is true, how often uploads or Instagram connects fail, or whether `/api/render` throws. An SSR or render error is gone from Vercel logs within an hour. The pilot's success metric (Owner hours) needs this instrumentation.
- **Recommendation**: Small and staged. Add PostHog (free tier, no PII, hashed token) with `landing_cta_click{placement}`, `wizard_step_view` and submit, `upload_failed` and `ig_connect` events. Add an `instrumentation.ts` `onRequestError` hook plus Sentry's free tier, or at least `console.error` in `error.tsx` so failures reach Vercel logs. A per-placement WhatsApp prefill for attribution is a good cheap addition.
- **Impact**: A step-level drop-off view of the 6-step wizard within days of the pilot, and render or SSR failures that are visible instead of silent.
- **Verifier note**: Confirmed, including the Vercel limits and PostHog's free tier. Internal funnel tracking doesn't contradict the mvp.md Won't. Severity drops to medium: the Phase 1 pilot is one Owner the team can watch directly, so step-level funnel data matters mostly for Phase 2. Renderer failures already show up in backend logs as `RendererError`, so they aren't fully silent.
- **Related**: [GRW-1](growth-pricing-market.md), [DOC-9](docs-process.md)

### FE-9: The production frontend and the carousel renderer run on a non-commercial Vercel Hobby team

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [frontend/README.md:32](../../../frontend/README.md): the `neitorai` project sits on a Hobby team.
  - [route.ts:13-33](../../../frontend/app/api/render/route.ts): every designed Slide is rendered here ([ADR 0029](../../decisions/0029-designed-slides-ai-scene-code-layout.md)).
  - [Vercel Hobby plan](https://vercel.com/docs/plans/hobby) (read 2026-10-19): "the Hobby plan restricts users to non-commercial, personal use only"; 4 CPU-hours of Active CPU; 1 hour of runtime logs; no team collaboration; over the limit, wait 30 days. Pro developer seats cost US$20 per user per month.
- **Problem**: Charging US$29 or US$49 ([ADR 0031](../../decisions/0031-pricing-free-basic-pro.md)) on Hobby breaks Vercel's fair-use terms, and the account could be paused. Every Carousel depends on `/api/render`, so a pause or quota exhaustion (a 30-day lockout on Hobby) stops all designed Posts, not just the landing. One-hour logs and no team seats also hurt two-person on-call.
- **Recommendation**: Upgrade the team to Vercel Pro (about US$40 a month for 2 seats, with Spend Management on) before charging any Owner, or earlier for 1-day logs and collaboration during the pilot. This needs an ADR (it changes the hosting plan behind [ADR 0004](../../decisions/0004-frontend-nextjs-vercel.md)). Consider moving the renderer to Railway only if Vercel cost or latency becomes a problem; that would need an ADR amending ADR 0004 and [ADR 0029](../../decisions/0029-designed-slides-ai-scene-code-layout.md).
- **Impact**: Removes the risk of a sudden outage of all Carousel generation, and buys 1-day logs and collaboration for about US$40 a month.
- **Verifier note**: Facts confirmed against Vercel's Hobby page. Quota exhaustion is unlikely: renders take tens of ms against 1M invocations and 4 CPU-hours. The real risk is the terms of service once the product earns money, and billing is Phase 2 and a Won't for the MVP. Medium now, high just before the first paying Owner.
- **Related**: [OPS-3](platform-ops.md), [OPS-7](platform-ops.md), [OPS-12](platform-ops.md), [COST-10](unit-economics.md)

### FE-10: Render path: one failed Slide throws away every paid AI scene; no retry

- **Severity**: low · **Effort**: M · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [takumi.py:8-9](../../../backend/app/rendering/takumi.py) sets a 30 s timeout to cover a Vercel cold start, and :31-42 make a single attempt that raises `RendererError`.
  - [slides.py:40](../../../backend/app/rendering/slides.py): `asyncio.gather` of N parallel renders, so one failure fails all.
  - [maker.py:319-334](../../../backend/app/posts/maker.py): scenes are generated with Gemini at 2K before rendering, and the panorama at 4K ([generator.py:18](../../../backend/app/carousel/generator.py)).
  - [route.ts:24-32](../../../frontend/app/api/render/route.ts): one Slide per request; fonts are loaded per instance in [fonts.ts:21-38](../../../frontend/lib/post-render/fonts.ts).
- **Problem**: A Carousel of up to 10 Slides makes up to 10 parallel Vercel invocations. A single 5xx or cold-start timeout fails the whole Post after every scene has already been paid for. The Owner waits again and the scenes are regenerated at full image cost.
- **Recommendation**: Retry 5xx responses and timeouts in `TakumiRenderer.render` up to 2 times with jittered backoff (S). Optionally keep the generated scenes on the Post so a re-render reuses them. Do not add a batch endpoint: it breaks the 4.5 MB body-limit design in [ADR 0029](../../decisions/0029-designed-slides-ai-scene-code-layout.md).
- **Impact**: Fewer wasted image generations (each failure currently discards N 2K or 4K scenes) and fewer "algo salió mal" moments mid-demo.
- **Verifier note**: Confirmed: one attempt, `gather` fails the whole Post, and `maker.py` has no catch or fallback after the scenes are generated. The auditor's original `POST /api/render/batch` idea contradicts a documented constraint: requests carry scenes as base64, and ADR 0029:26 (each scene resized to 1080×1350 first) and [integrations.md:341](../../architecture/integrations.md) ("one slide per request stays far under it") keep each request under Vercel's 4.5 MB body limit; ten scenes plus the logo would approach or exceed it. The money at stake is small (integrations.md: about $0.05 per 2K Slide and $0.113 per panorama, so roughly $0.50 or less for a 10-Slide Carousel), and Vercel 5xx errors are rare. The main cost is the Owner waiting again.
- **Related**: [BUG-13](bugs-reliability.md), [ARCH-12](backend-architecture.md)

### FE-11: No OG image, metadataBase, robots or sitemap; shared links preview as plain text from a vercel.app domain

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [layout.tsx:16-19](../../../frontend/app/layout.tsx): no `metadataBase`, no icons or apple-touch-icon.
  - [page.tsx:18-22](../../../frontend/app/page.tsx): `openGraph` has no images.
  - [frontend/app/](../../../frontend/app) has no `opengraph-image`, `robots.ts`, `sitemap.ts` or manifest, and `frontend/public/` doesn't exist.
  - [messages_es.py:68-76](../../../backend/app/copy/messages_es.py): the magic link is sent as a bare URL.
  - [how-it-works.tsx:42](../../../frontend/components/landing/how-it-works.tsx): the mock link card shows "neitor.ai", not the real `neitorai.vercel.app`.
- **Problem**: WhatsApp is the product's whole distribution channel. When an Owner shares the landing, the preview has no image or brand. A bare `neitorai.vercel.app/o/…` link arriving from a +56 number looks like phishing to a cautious 50-something Owner, which lowers the wizard open rate.
- **Recommendation**: Add `app/opengraph-image.tsx` and `metadataBase` for the landing (S). For rich magic-link previews, also send `preview_url: true` on the link messages in the backend and give `/o/[token]` its own OG metadata. Buy a short custom domain before Phase 2 and use it in `FRONTEND_URL`. Fix the mock card to show the real domain.
- **Impact**: More trustworthy previews for every shared link, and for magic links once `preview_url` is set, which should raise the wizard open rate.
- **Verifier note**: The missing files are confirmed, but the main mechanism was wrong. The magic link goes out through `KapsoChannel` as a text message with no `preview_url`, and Meta's Cloud API docs (re-read 2026-10-19) say that when `preview_url` is omitted "The WhatsApp client renders a clickable link instead", so the magic link never shows a preview whatever the OG tags. OG tags only matter when a person shares the landing URL. The wizard page already sets `robots {index: false}`, so a `robots.ts` for `/o/` adds little. The "neitor.ai" mock card shows a domain the team may not own.

### FE-12: No autosave inside a step, and the header back button breaks the hardware back stack

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [web-app.md:11](../../design/web-app.md): "Autosave every step; returning to the link resumes where the owner left".
  - [wizard.tsx:56](../../../frontend/components/onboarding/wizard.tsx): `<Screen key={step}/>` remounts, so local state is lost, and :47-50 `goTo` always calls `pushState`.
  - [wizard-step.tsx:48](../../../frontend/components/onboarding/wizard-step.tsx): the back arrow calls `goTo(previous)`, adding a new history entry.
  - [products-step.tsx:47-53](../../../frontend/components/onboarding/steps/products-step.tsx): Product drafts exist only in memory until "Siguiente".
- **Problem**: Saving only happens on "Siguiente". An Owner who types up to 5 Products with prices and then taps the back arrow, switches to WhatsApp (the OS may kill the in-app tab) or loses signal, loses everything typed. Because the back arrow pushes history, Android's back gesture afterwards moves "forward" to the step just left, which confuses the persona.
- **Recommendation**: Persist each step's draft to `sessionStorage`, keyed by token and step, on change (wrapped in try/catch); restore it on mount and clear it after a successful save. When the previous history entry is the previous step, have the back arrow call `history.back()`; otherwise use `replaceState`. If a step's data is valid, save it before navigating back.
- **Impact**: Fewer abandoned wizards from lost input, which matters most on the longest step (Products).
- **Verifier note**: Verified as written: the design doc's principle 3 asks for autosave on every step, the remount drops local state, and the back arrow's extra history entry sends the hardware or gesture back to the step just left. The failure scenarios are reachable, and the `sessionStorage` draft plus `history.back()` fix fits.

### FE-13: Tap targets and text sizes are below the team's 48 px rule for a 45+ persona

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [web-app.md:10](../../design/web-app.md): "Big tap targets (≥ 48 px)".
  - [photo-tile.tsx:26](../../../frontend/components/onboarding/photo-tile.tsx): the photo ✕ is `size-8` (32 px), on tiles of about 72 px in the `grid-cols-4` of [product-photos.tsx:96](../../../frontend/components/onboarding/product-photos.tsx).
  - [brand-step.tsx:269](../../../frontend/components/onboarding/steps/brand-step.tsx): the color ✕ is `size-7` (28 px).
  - [wizard-step.tsx:47](../../../frontend/components/onboarding/wizard-step.tsx): the back button is 40 px, and :70 the WhatsApp pill is `h-10`.
  - [photos-step.tsx:214](../../../frontend/components/onboarding/steps/photos-step.tsx): "Mirando…" at 11 px; [product-photos.tsx:120](../../../frontend/components/onboarding/product-photos.tsx): "Sumar" at `text-xs`; many 13 px helper texts.
- **Problem**: On a Product tile about 72 px wide, a 32 px ✕ covers nearly half the photo, so mis-taps can delete photos, and deletion has no undo. Status text at 11-13 px is hard to read for Owners in their 50s in daylight.
- **Recommendation**: Expand icon-button hit areas to 44-48 px with a `::after` pseudo-element, raise status chips and helper text to 14-15 px, and consider a 3-column Product photo grid. An undo toast is optional.
- **Impact**: More legible status for the core persona and fewer accidental taps; matches the team's own spec.
- **Verifier note**: The sizes are accurate (Product tiles are about 73 px inside the 480 px max column). The accidental-deletion scenario is weak: `PhotoTile`'s image has no click handler, so Owners have no reason to tap tiles, scrolling doesn't fire clicks, and a deleted photo is archived and can be re-added. This is spec compliance and legibility polish, not a pilot risk.

### FE-14: API calls have no timeouts; errors disappear as toasts; no root 404 or error page

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [api.ts:128-151](../../../frontend/lib/api.ts): `fetch` with no `AbortSignal`, on both the server and the client.
  - [page.tsx:11-18](../../../frontend/app/o/[token]/page.tsx): the wizard's SSR `getState` waits on Railway; with no timeout the skeleton can hang up to the 300 s Hobby function limit.
  - [business-step.tsx:56-57](../../../frontend/components/onboarding/steps/business-step.tsx): save errors appear only through `toast.error`, which auto-dismisses.
  - [frontend/app/](../../../frontend/app) has no `not-found.tsx` or `global-error.tsx`, so a broken link such as `/o/` shows Next's English 404.
  - [expired-link.tsx:13](../../../frontend/components/onboarding/expired-link.tsx): the wa.me link has no `?text=link`, although the copy tells the Owner to write "link".
- **Problem**: When the single backend instance ([ADR 0005](../../decisions/0005-single-instance-in-process-jobs.md)) hiccups, or mobile data is flaky, the Owner sees an endless skeleton or a "Siguiente" spinner. When an error does appear, it vanishes after about 4 s. Mistyped paths land on an English 404.
- **Recommendation**: Add `AbortSignal.timeout` (about 10 s on the server, 15 s on the client) mapped to a Spanish `ApiError`. Show save errors inline with `role=alert`. Prefill `?text=link` on the expired-link button. Add a small Spanish `not-found.tsx`.
- **Impact**: Turns silent hangs into recoverable states during the pilot, at almost no cost.
- **Verifier note**: Confirmed, with mitigations the auditor missed. The wizard's [error.tsx](../../../frontend/app/o/[token]/error.tsx) shows a Spanish retry screen for thrown SSR errors. A truncated or wrong token makes the backend return 404, which `isLinkInvalid` maps to the Spanish `ExpiredLink` screen; only paths like `/o/` with no token, or unknown routes, reach Next's English 404. Hangs need the single backend to accept the connection and then stall: possible but rare (Hobby's 300 s maximum function duration is confirmed). All small polish.

### FE-15: No frontend CI: no lint, typecheck, build or E2E smoke test, even though a mock backend exists

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [ci.yml:33-54](../../../.github/workflows/ci.yml): the paths filters cover only Markdown, workflows and the backend; there is no frontend job.
  - [package.json:5-10](../../../frontend/package.json): only `dev`, `build`, `start` and `lint` scripts.
  - [mock-backend.ts:1-40](../../../frontend/lib/mock-backend.ts) and the [mock-api route.ts:7-47](../../../frontend/app/mock-api/[...path]/route.ts): a full in-memory implementation of the onboarding contract already exists.
- **Problem**: A TypeScript or build error in the shared render route or the wizard is only caught by Vercel's preview build, which isn't a required check. Any regression in the 6-step wizard (the Must path) goes unnoticed until an Owner hits it. Playwright E2E is allowed by the team rules but not used.
- **Recommendation**: Add a `frontend` paths filter and job to `ci.yml`: `npm ci`, eslint, `tsc --noEmit`, `next build`. Add one Playwright smoke spec at a 390×844 viewport that runs `next start` with `ENABLE_MOCK_API=true` and completes `/o/demo` end to end (upload 3 fixture photos, pick colors, finish), checks that `/o/vencido` shows the expired screen, and asserts every landing CTA `href`. Add the job to the `ci` gate's `needs`.
- **Impact**: Catches wizard or renderer regressions before they reach production, using the mock that already exists.
- **Verifier note**: Verified. The `ci.yml` header already says "Add the frontend job in its own PR and list it in the CI gate's needs:", so this is planned but not done. The recommendation fits the existing gate pattern.
- **Related**: [OPS-13](platform-ops.md), [OPS-14](platform-ops.md), [OPS-16](platform-ops.md), [OPS-17](platform-ops.md), [SEC-17](security-privacy.md), [DOC-13](docs-process.md)

### FE-16: The wizard's brand preview is a CSS mock that doesn't match the real Takumi designs

- **Severity**: low · **Effort**: M · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [post-preview.tsx:17-66](../../../frontend/components/onboarding/post-preview.tsx): a photo on a colored frame plus a caption.
  - [editorial.tsx](../../../frontend/lib/post-render/families/editorial.tsx), [numbers.tsx](../../../frontend/lib/post-render/families/numbers.tsx) and [panorama.tsx](../../../frontend/lib/post-render/families/panorama.tsx): the real templates, with headlines, kicker, counters and a logo chip.
  - [web-app.md](../../design/web-app.md): "Seeing their brand appear is the delight moment".
- **Problem**: The Owner approves their colors and logo against a mockup, then receives designed Slides in WhatsApp that look different, so expectations break at the first Post. The renderer already produces the real look in tens of milliseconds, with no AI cost.
- **Recommendation**: Treat it as a later delight item. Once the pilot shows "not like us" complaints on the first Post, add a backend-proxied, token-scoped preview that renders one editorial cover from the Owner's photo, logo and colors, debounced on color changes. Keep the CSS mock as the instant fallback.
- **Impact**: A stronger "this is my brand" moment at the end of onboarding, and fewer "not like us" corrections on the first Post.
- **Verifier note**: Confirmed that the preview is a CSS mock labelled "Ejemplo". But many Posts use the `photos` style (the Owner's photo resized, plus the logo), which the mock roughly matches. Designed Slides vary across families and sit over AI scenes, not the raw photo, so one editorial render wouldn't match every Post either. Reasonable, but a nice-to-have for a 2-person team, and it needs a new token-scoped endpoint that proxies to the secret-protected renderer.

### FE-17: Pricing CTAs capture nothing: the Pro waitlist is a dead link, and there is no plan, usage or billing surface

- **Severity**: low · **Effort**: L · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [pricing-section.tsx:63, :75, :85](../../../frontend/components/landing/pricing-section.tsx): Free, Basic and "Join the Pro list" all open the same "Hi Neitor" wa.me link.
  - [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md): Pro is a waitlist, and the Free cap must be enforced once billing exists.
  - [mvp.md:106-107](../../product/mvp.md): F7.3 (plans in the data model) is a Should, and F7.4 (billing) is a Won't for the MVP.
  - [Stripe global availability](https://stripe.com/global) (read 2026-10-19): Uruguay is not listed; only Brazil and Mexico in Latin America.
  - [Mercado Pago Suscripciones](https://www.mercadopago.com.uy/developers/es/docs/subscriptions/resources/tutorial-videos) (read 2026-10-19): Mercado Pago Uruguay supports recurring subscriptions.
- **Problem**: Pro-waitlist intent is lost, Basic intent can't be told apart from Free, and once the 3-Post Free cap is enforced the Owner has no place to see "2 de 3 posts este mes" or pay US$29. Stripe, the default choice, isn't available to Uruguayan merchants.
- **Recommendation**: Now (S): a per-plan prefill ("Hola Neitor, quiero el plan Pro") stored as `businesses.plan_interest`, or collected through FE-1's lead form. Phase 2: a usage and plan page with a Mercado Pago Suscripciones (preapproval) checkout, sent by the bot when the Free cap is hit.
- **Impact**: A measurable Pro demand signal before building Pro, and a working path to the first US$29.
- **Verifier note**: Confirmed: the three plan CTAs are indistinguishable, Stripe lists only Brazil and Mexico in Latin America, and Mercado Pago's Uruguay docs list Suscripciones. But billing is F7.4 Won't and listed under "Explicitly out of scope" in mvp.md, and roadmap Phase 2 already holds "Billing + tiers" and Mercado Pago. With strangers unable to reach the bot (FE-1), the demand signal lost today is close to zero.
- **Related**: [AIQ-20](ai-quality.md), [GRW-9](growth-pricing-market.md), [GAP-9](cross-cutting-gaps.md), [PRD-12](product.md)

### FE-18: A minimal read-only "Tus posts" page: history, status and links

- **Severity**: low · **Effort**: L · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [frontend/README.md:3](../../../frontend/README.md): the dashboard `/b/[token]` is planned, not built.
  - [mvp.md](../../product/mvp.md): F6.3, a read-only dashboard, is a Should.
  - [Dashboard.dc.html](../../design/mockups/Dashboard.dc.html): a mockup exists.
- **Problem**: Owners have no way to see what was published, what is pending Approval, or the Instagram permalinks, except by scrolling WhatsApp. Pilot interviews and the "hours saved" metric would benefit from a shared view the team can open alongside the Owner.
- **Recommendation**: Persist Posts (T17, T19) first. Then ship the read-only Inicio tab of `/b/[token]` (brand summary plus Posts with status and permalink) as a server component reusing `ScreenLayout` and the magic-link auth, and keep Approvals in WhatsApp ([ADR 0007](../../decisions/0007-approve-every-post.md)).
- **Impact**: Low effort per screen given the existing primitives; supports pilot reviews and later billing.
- **Verifier note**: It is planned, not new (F6.3, the README and the mockup). The auditor missed a hard dependency: Posts and their images still live in memory (`conversation/factory.py` builds `InMemoryPosts`; [ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md) Consequences: "Posts and their images still live in memory (T17, T19)"), so a history and status page has nothing durable to read until Posts are persisted. The auditor's original title ("Speed up") was odd, since nothing is built yet.

### FE-19: Landing performance nits: Toaster in the root layout, slow hero entrance, unused theme hook

- **Severity**: low · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [layout.tsx:33](../../../frontend/app/layout.tsx): the sonner `Toaster` plus the next-themes `useTheme` ship on the static landing, which never toasts.
  - [sonner.tsx:3-8](../../../frontend/components/ui/sonner.tsx): `useTheme` without a `ThemeProvider`.
  - [hero.tsx:30](../../../frontend/components/landing/hero.tsx): the bubble with the primary CTA starts at opacity 0 and appears after a .35 s delay plus a .7 s animation; :74 shows `ApprovalDemo` after 1.05 s.
- **Problem**: The landing is otherwise lean (server components, `next/image` with blur placeholders, `next/font`). It still ships client JS it doesn't need, and the primary CTA is invisible for about 0.4-1 s on first paint on slow phones.
- **Recommendation**: Move `<Toaster>` into an `app/o/[token]/layout.tsx` and remove the next-themes import from `sonner.tsx`. Let the primary CTA bubble animate with transform only (no opacity 0), or drop its delay.
- **Impact**: Small JS savings and an immediately tappable CTA; low priority.
- **Verifier note**: Partly confirmed. The layout mounts the `Toaster` on every route, the landing never toasts, and the hero CTA bubble does start at opacity 0 with the stated delay and animation (motion-safe only). But the layout already passes `theme="light"`, and `sonner.tsx` spreads its props after its own theme, so the `useTheme()` call is dead code rather than a theming bug. The JS saving (sonner plus next-themes) is a few KB.
