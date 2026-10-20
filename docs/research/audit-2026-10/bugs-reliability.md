# Bugs and reliability

This doc covers concrete bugs and reliability failures in the backend: what breaks, the exact scenario in which an Owner hits it, and the fix. It is one dimension of the 2026-10-19 product and codebase audit (index in [README.md](./README.md), cross-dimension synthesis in [summary.md](summary.md)), read from the code at commit `dc0bc01`. An independent adversarial reviewer checked every finding against the code and the cited sources. "Adjusted" means the reviewer corrected the severity or details; the severity and recommendation shown here already include those corrections, and the verifier note says what changed. Each Problem keeps the concrete failure scenario.

## Summary

The backend code is careful. Its approval logic follows [ADR 0007](../../decisions/0007-approve-every-post.md) closely: event turns cannot publish, approvals are computed in code, idempotency keys are used, and the photo debounce is designed with care. The non-live suite passes (591 passed, 95 DB tests skipped locally and run in CI against Postgres), and ruff is clean (audit observation, 2026-10-19).

The big pilot risks come from state, not logic:

- Posts, photos, post images, the webhook dedupe, the daily caps and in-flight generations, publishes and turns all live in one process. Railway kills that process with 0 s of draining on every deploy, and the team ships several PRs a day, so Owner messages get lost without a trace, buttons go stale, brand onboarding gets stuck and paid generations are thrown away (BUG-2, BUG-4, BUG-5).
- Two issues touch correctness directly. Every Business publishes to the single Zernio account in env ([ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md)), which is cross-tenant once a second Owner exists (BUG-1). And a post being revised stays approvable, so "subilo" can publish the version the Owner asked to change (BUG-3).
- WhatsApp's 24-hour window is not handled for the wizard: links last 7 days, so the brand summary can be silently rejected and the Business never reaches `active` (BUG-6).
- Smaller items: reactions get answered with "no te entiendo" (BUG-7), a photo plus text race (BUG-8), caps that are not real caps (BUG-9), `publish_pending` that never resolves (BUG-10), the missing Voice note fallback (BUG-11), and unbounded memory on a 1 GB Trial instance (BUG-12).

## Findings at a glance

Effort: S is under half a day, M is 1-2 days, L is about a week, XL is more than a week.

| Id | Severity | Effort | Finding |
|---|---|---|---|
| [BUG-1](#bug-1-every-businesss-approved-post-is-published-to-the-one-zernio-account-in-env) | high | M | Every Business's approved post goes to the Zernio account in env |
| [BUG-2](#bug-2-deploys-silently-drop-in-flight-owner-turns-post-generations-and-publishes-railway-gives-0-s-to-drain) | high | M | Deploys drop in-flight turns, generations and publishes (0 s drain) |
| [BUG-5](#bug-5-posts-chat-photos-and-served-post-images-are-in-process-memory-after-a-deploy-approvals-stop-working-and-image-fetches-404) | high | L | In-memory posts and images: approvals stop working and fetches 404 after a deploy |
| [BUG-3](#bug-3-revising-a-post-leaves-the-old-version-approvable-so-subilo-publishes-the-version-the-owner-asked-to-change) | medium | S | A post under revision stays approvable |
| [BUG-4](#bug-4-jobs-interrupted-by-a-restart-fail-silently-an-interrupted-generate_brand-leaves-the-business-stuck-in-generating_brand) | medium | S | Jobs interrupted by a restart fail silently; the brand gets stuck |
| [BUG-6](#bug-6-the-brand-summary-is-sent-outside-whatsapps-24-h-window-when-the-wizard-is-finished-more-than-a-day-after-the-link-the-business-never-becomes-active) | medium | S | The brand summary is sent outside the 24 h window |
| [BUG-7](#bug-7-whatsapp-reactions-get-a-no-te-entiendo-reply-and-any-button-sticker-or-reaction-swallows-the-pending-photo-batch) | medium | S | Reactions get "no te entiendo"; buttons swallow the photo batch |
| [BUG-10](#bug-10-publish_pending-is-a-dead-end-no-follow-up-check-so-the-owner-never-gets-the-link-or-the-failure) | medium | S | `publish_pending` is a dead end |
| [BUG-11](#bug-11-voice-notes-without-a-kapso-transcript-are-rejected-the-gemini-fallback-from-adr-0021-isnt-built) | medium | S | Voice notes without a Kapso transcript are rejected |
| [BUG-13](#bug-13-no-wall-clock-bound-on-a-posts-generation-one-slow-gemini-image-call-blocks-the-owner-for-many-minutes) | medium | S | No wall-clock bound on generation |
| [BUG-8](#bug-8-photo-plus-text-race-a-text-sent-right-after-a-photo-is-answered-without-the-photo-then-the-photo-gets-its-own-reply) | low | S | A photo plus text race produces two contradictory replies |
| [BUG-9](#bug-9-generation-caps-arent-caps-in-memory-reset-on-deploy-count-posts-not-images-consumed-by-failures-the-free-tiers-3-a-month-isnt-enforced) | low | M | The generation caps aren't real caps |
| [BUG-12](#bug-12-unbounded-in-process-caches-on-a-1-gb-railway-trial-service-risk-out-of-memory-restarts) | low | S | Unbounded caches on a 1 GB Trial instance |
| [BUG-14](#bug-14-chat-photo-ids-restart-at-f1-after-every-deploy-while-the-history-that-cites-them-persists) | low | S | Chat photo ids restart after a deploy |
| [BUG-15](#bug-15-a-send-failure-mid-post-throws-away-a-finished-paid-post-and-tells-the-model-nothing-arrived) | low | S | A send failure mid-post throws away a finished, paid post |
| [BUG-16](#bug-16-a-429-on-a-chat-turn-fails-at-once-and-photo-albums-fan-out-unbounded-concurrent-llm-calls) | low | S | A 429 fails at once; albums fan out unbounded LLM calls |
| [BUG-17](#bug-17-replies-over-whatsapps-4096-character-limit-are-dropped-after-being-stored-as-delivered) | low | S | Replies over 4,096 characters are dropped after being stored as sent |
| [BUG-18](#bug-18-wizard-put-brand-and-preferences-can-overwrite-the-instagram-imports-onboarding_data-lost-update) | low | S | Wizard saves can overwrite the Instagram import's data |
| [BUG-19](#bug-19-job-slots-and-db-connections-can-be-starved-by-sleeping-or-io-bound-holders) | low | S | Job slots and DB connections are starved by sleeping holders |
| [BUG-20](#bug-20-dbhistory-caches-business-ids-forever-so-resetting-a-testers-business-breaks-their-chat-until-a-restart) | low | S | `DbHistory` caches business ids forever |

## Test status, deploy losses and limits

**Test status (2026-10-19, local).** `uv run pytest -m 'not live'` gives 591 passed, 0 failed, 95 skipped. All skips are DB tests that need `TEST_DATABASE_URL`; CI runs them against Postgres 17. `uv run ruff check .` is clean (audit observation, 2026-10-19).

**What a deploy loses.** Railway's default draining is 0 s (SIGKILL right after SIGTERM), and the old and new instances overlap briefly ([Railway: deployments reference](https://docs.railway.com/reference/deployments), read 2026-10-19).

| State | Where it lives | Effect of a deploy |
|---|---|---|
| Owner turn in progress (`BackgroundTask`) | memory ([channels/router.py](../../../backend/app/channels/router.py)) | lost; Kapso already got its 200, so it never retries |
| Post generation and publish tasks | memory ([posts/maker.py](../../../backend/app/posts/maker.py), [posts/publish.py](../../../backend/app/posts/publish.py)) | lost; the Owner was told "lo armo ⏳" or "lo subo ⏳" |
| Posts (approval state, listed and offered) | memory ([posts/store.py](../../../backend/app/posts/store.py)) | buttons go stale; "subilo" finds nothing to publish |
| Post JPEGs at `/media/*` | memory ([media/public.py](../../../backend/app/media/public.py)) | 404 for Kapso and Zernio fetches routed to the new instance |
| Chat photos `f1`..`fN` | memory, counter resets ([conversation/photos.py](../../../backend/app/conversation/photos.py)) | ids are reused against the persisted history |
| Daily design cap | memory ([posts/maker.py](../../../backend/app/posts/maker.py)) | resets to 0 |
| Webhook dedupe | memory ([channels/inbound.py](../../../backend/app/channels/inbound.py)) | duplicate turns possible during the overlap |
| Jobs rows | Postgres ([jobs/runner.py](../../../backend/app/jobs/runner.py)) | marked failed after 5 min; no retry, no message |
| History, notes, summary, Brand Brain | Postgres | kept |

**Cost exposure from the caps (BUG-9), an estimate.** 5 designs a day × up to 10 slides × US$0.0504 per 2K image ([image-generation-providers.md](../image-generation-providers.md)) is about US$2.5 per Owner per day, assuming a deliberately heavy user who maxes out every design. The auditor added "more with 4K panoramas (US$0.113 each)"; the reviewer corrected that a panorama is one 4K image sliced into every slide, so it costs less than 10 × 2K images. The counter resets on every deploy.

**Worst-case generation time (BUG-13), an estimate.** 4 attempts × 120 s per image, plus backoff, is about 8 min per slide call. The auditor put one carousel at 15-30 min (with the safety retry, plus the cover and then the rest of the slides) while the Owner is blocked; the reviewer corrected it to about 16 min during a Gemini outage, because the safety retry fires only on fast blocked or no-image responses.

**Platform limits checked 2026-10-19.**

- WhatsApp text body: 4096 characters ([Meta: text messages](https://developers.facebook.com/docs/whatsapp/cloud-api/messages/text-messages), read 2026-10-19).
- Messages outside the 24 h window: templates only ([Meta: send messages](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages), read 2026-10-19).
- Railway Trial: 1 GB RAM per service ([Railway: plans](https://docs.railway.com/reference/pricing/plans), read 2026-10-19).
- Railway default draining: 0 s ([Railway: deployments reference](https://docs.railway.com/reference/deployments), read 2026-10-19).

## Findings

### BUG-1: Every Business's approved post is published to the one Zernio account in env

- **Severity**: high · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [conversation/factory.py:48-54](../../../backend/app/conversation/factory.py): one global `account_id = settings.zernio_account_id`.
  - [conversation/factory.py:72-74](../../../backend/app/conversation/factory.py): the `PostPublisher` is built once with that `account_id` for all senders.
  - [posts/publish.py:103-113](../../../backend/app/posts/publish.py): `_start` uses `self._account_id`, never the sender's Business.
  - [posts/publish.py:146-148](../../../backend/app/posts/publish.py): `publish(account_id, caption, media, ...)`.
  - [config.py:56-62](../../../backend/app/config.py): "The MVP publishes to one demo Instagram account (ADR 0024)".
  - [product/mvp.md:46](../../product/mvp.md): F2.3, publishing still goes to one demo account from env.
  - [roadmap.md:7-9](../../roadmap.md): the Phase 1 pilot runs "on the pilot owner's real account".
- **Problem**: Nothing ties the publish target to the Business that owns the post; the wizard's Instagram connect ([ADR 0028](../../decisions/0028-read-instagram-with-our-meta-app.md)) only reads the account. Failure: pilot Owner B approves a post, it goes live on `ZERNIO_ACCOUNT_ID` (the demo account, or Owner A's real account if it was set for the first pilot), and B receives the permalink of someone else's profile. This is a known decision ([ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md)), but it is only safe while exactly one Business exists. Worse, as the reviewer found, `OnboardingGate` has no sender allowlist, so anyone who messages the bot gets a Business and, after the wizard, can approve posts onto that account.
- **Recommendation**: Before `ZERNIO_ACCOUNT_ID` is set to a real Owner's account, add a code guard in `PostPublisher._start`: refuse with `need_ig` unless the post's sender equals a configured `ZERNIO_OWNER_PHONE` (or Business id). An allowlist of pilot phones in `OnboardingGate` also works. Per-Business publishing (`social_accounts` with `provider='zernio'`, plus exposing `connect_url`) is the Phase 2 reversal that ADR 0024 already describes. Recording the guard needs an ADR: an amendment to [ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md).
- **Impact**: Prevents publishing one client's content on another client's Instagram, which would end trust in the product. The guard is a 1-hour change.
- **Verifier note**: The code claim holds (`factory.py:48-74` builds one `PostPublisher` with the env account, and `publish.py:103-113` publishes every sender's post to it), but ADR 0024 records it as a deliberate decision, repeated in `mvp.md` F2.3, and roadmap Phase 1 is a pilot with one Owner. The reviewer found it worse than the auditor said: `OnboardingGate` ([conversation/onboarding.py:61-94](../../../backend/app/conversation/onboarding.py)) has no sender allowlist, so once `ZERNIO_ACCOUNT_ID` points at the pilot Owner's real account, any team test, demo or second Owner publishes onto that Owner's Instagram. A known limitation with a cheap guard: high rather than critical, becoming critical as soon as a second Business can reach approval while the env points at a real account. Migration 0002's unique key (`business_id`, `platform`, `provider`) and the unexposed `ensure_profile` and `connect_url` are as cited.
- **Related**: [ARCH-4](backend-architecture.md), [PRD-1](product.md), [SEC-2](security-privacy.md), [GRW-2](growth-pricing-market.md), [GAP-1](cross-cutting-gaps.md).

### BUG-2: Deploys silently drop in-flight Owner turns, post generations and publishes (Railway gives 0 s to drain)

- **Severity**: high · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [Railway: deployments reference](https://docs.railway.com/reference/deployments) (read 2026-10-19): "By default, it is given 0 seconds to gracefully shutdown before being forcefully stopped with a SIGKILL"; old and new deployments overlap briefly.
  - [Dockerfile:34-35](../../../backend/Dockerfile): uvicorn runs as PID 1 and gets SIGTERM, with no graceful timeout configured.
  - [channels/router.py:72-80, 116](../../../backend/app/channels/router.py): the turn runs as a `BackgroundTask` after the 200, so Kapso never retries it.
  - [posts/maker.py:199-204](../../../backend/app/posts/maker.py): generation is a bare `asyncio` task.
  - [posts/publish.py:110-112](../../../backend/app/posts/publish.py): publish is a bare `asyncio` task.
  - [channels/router.py:38-49](../../../backend/app/channels/router.py): shutdown closes HTTP clients only; `PostMaker`, `PostPublisher` and `ChatHandler` `join()` are never awaited.
  - [main.py:36-38](../../../backend/app/main.py) and [jobs/runner.py:81-86](../../../backend/app/jobs/runner.py): `stop()` cancels running jobs instead of draining them.
  - [channels/inbound.py:28-43](../../../backend/app/channels/inbound.py): the dedupe store is in memory and empty on the new instance.
- **Problem**: On every redeploy the old container is SIGKILLed right after SIGTERM, so nothing in flight survives. Failures: (a) the Owner writes "armame un post con la mesa"; the webhook was already answered with 200 and the 5-26 s LLM turn is killed, so there is no reply and no retry. (b) The Owner was told "¡Dale! Lo armo ⏳"; the 60-90 s carousel is killed, so neither the post nor a failure message arrives, and the paid images are wasted. (c) A publish is killed after Zernio accepted it, so the Owner never gets the link. (d) During the overlap the new instance has an empty dedupe store, so a Kapso redelivery runs the turn twice (two `create_post` calls, double image cost).
- **Recommendation**: (1) Today: set `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` (for example 150) and leave uvicorn's default unbounded graceful wait, or set `--timeout-graceful-shutdown` just under the draining time. (2) In the lifespan shutdown, stop the `JobRunner` poller first, then await `PostMaker.join()`, `PostPublisher.join()`, `ChatHandler.join()` and the running jobs under a timeout, instead of cancelling; close the HTTP clients only after that. (3) Later: a dedupe and inbox backed by the `messages` table, which survives a restart. (4) Until then, avoid deploying during pilot hours.
- **Impact**: Removes silent message loss, the most damaging failure for a WhatsApp-only product. Each lost carousel wastes about US$0.25-0.50 of images (estimate, at US$0.0504 per 2K image).
- **Verifier note**: Railway's docs, re-checked on 2026-10-19, confirm the 0 s default, the `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` setting and the brief overlap, and the code matches. Deploys are frequent (about 40 commits on 2026-10-17 and 26 on 2026-10-18; audit observation from git history), so the exposure is real. Lowered from critical: only work in flight at deploy time is lost, the Owner can re-ask, and one env var fixes most of it. Correction: uvicorn already waits for in-flight requests on SIGTERM, including Starlette `BackgroundTasks`, because it has no graceful timeout by default, so the draining variable alone protects webhook turns; the bare `asyncio` tasks and job cancellation still need explicit handling in the lifespan. Sub-claim (d) needs Kapso to retry a delivery it already got a 200 for, which is rare. Also, `messages.business_id` is NOT NULL, so persisting inbound messages first needs the Business to exist (the gate creates it).
- **Related**: [ARCH-3](backend-architecture.md), [OPS-2](platform-ops.md), [OPS-6](platform-ops.md).

### BUG-3: Revising a post leaves the old version approvable, so "subilo" publishes the version the Owner asked to change

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [posts/maker.py:131-157](../../../backend/app/posts/maker.py): `revise_post` starts the remake but never changes `old.status`.
  - [posts/maker.py:366-374](../../../backend/app/posts/maker.py): the old post is marked `replaced` only when the revision finishes, and only if it is still `APPROVABLE`.
  - [posts/store.py:23](../../../backend/app/posts/store.py): `APPROVABLE` is `pending_approval` and `approved`.
  - [conversation/approval.py:148-150](../../../backend/app/conversation/approval.py): "subilo" with one pending post approves it.
  - [conversation/button_router.py:110-115, 134-138](../../../backend/app/conversation/button_router.py): [Aprobar] and [Publicar ahora] still accept the old post.
  - [posts/publish.py:79-89](../../../backend/app/posts/publish.py): approve only checks `APPROVABLE` and the `Approval` id.
- **Problem**: Failure: the Owner taps [Aprobar] on post A ($12.900) and gets [Publicar ahora]. They write "pará, cambiá el precio a $11.900", so `revise_post(A)` starts a 60-90 s generation, but A stays `approved`. The impatient Owner writes "dale subilo": `decide()` sees one pending post (A), `approve_post` publishes A with the old price, and the model cannot name B because it doesn't exist yet. Revision B then arrives, `_keep` sees A is no longer approvable and leaves B pending; if the Owner approves B, two posts of the same product are live, one with the wrong price. Tapping the old buttons during the revision gives the same result, and `create_post(replaces=...)` has the same hole.
- **Recommendation**: Mark the old post `revising` synchronously in `PostMaker._start` whenever a remake or `replaces` is set, and exclude `revising` from `APPROVABLE` and from the `post_approve` and `post_publish` button guards. Return `revision_in_progress` to the model and the buttons. On `PostFailed`, restore the previous status. Add backend tests for "subilo" and for the old [Publicar ahora] button during a revision.
- **Impact**: Stops wrong prices or text from going public and prevents duplicate posts on the Owner's Instagram. This is the exact [ADR 0007](../../decisions/0007-approve-every-post.md) trust promise.
- **Verifier note**: The code gap is real: neither `revise_post` nor `create_post(replaces)` touches the old post's status, `APPROVABLE` includes `approved`, and `_post_publish` and `decide()` still accept the old post, with no check for a revision in progress. Two things narrow the scenario. "subilo cuando esté" contains a time word, so it is classified `approve_later` and nothing is published. On the "subilo" text path the model has just been told the revision is generating, so publishing depends on the model; the tap on the old [Publicar ahora] button is the code-only path. A caption-only revision is quick (no image generation). The outcome can be bad (a wrong price live), but it needs the Owner to approve inside the revision window right after asking for a change: medium, not high. The suggested fix is right and small.
- **Related**: [AIQ-8](ai-quality.md), [AIQ-1](ai-quality.md).

### BUG-4: Jobs interrupted by a restart fail silently; an interrupted `generate_brand` leaves the Business stuck in `generating_brand`

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [jobs/runner.py:88-109](../../../backend/app/jobs/runner.py): `fail_stale` marks rows failed with no `_tell_owner` and no requeue.
  - [jobs/runner.py:162-170](../../../backend/app/jobs/runner.py): `except Exception` does not catch `CancelledError` (and a SIGKILL runs nothing).
  - [jobs/brand.py:40-46, 90-98](../../../backend/app/jobs/brand.py): `_resume` only runs in `except Exception`, and only when `RESUME_STATE` is set.
  - [conversation/brand.py:8, 39-61](../../../backend/app/conversation/brand.py): `update_brand` refuses unless the state is `awaiting_brand_confirmation` or `active`.
  - [api/onboarding.py:350-355](../../../backend/app/api/onboarding.py): wizard completion sets `generating_brand` and queues the job.
  - [copy/messages_es.py:30](../../../backend/app/copy/messages_es.py): the Owner was promised "en un minuto te cuento lo que entendí".
- **Problem**: Failure: the Owner submits the wizard, and a deploy lands during the job's 60 s wait for analyses plus the Brand Strategist call. The row stays `running`, and 5 minutes later the new process marks it "interrupted by a restart" without telling anyone. `onboarding_state` stays `generating_brand` forever: no summary, no [Reintentar] button, the `brand_ok` and `brand_fix` buttons are stale, and `update_brand` returns `brand_not_ready`. An interrupted `update_brand` revision is stuck the same way, because `RESUME_STATE` is never applied. An interrupted `import_instagram` leaves the wizard saying "connected" while the Brand Brain is built without Instagram data. [ADR 0005](../../decisions/0005-single-instance-in-process-jobs.md) accepted that "a restart loses running jobs", but not that the Owner is never told.
- **Recommendation**: In `fail_stale`, select the stale rows and requeue each idempotent job once, tracking attempts in the payload. On the second failure, call `_tell_owner` and run `generate_brand`'s `_resume`. Add a startup sweep that requeues `generate_brand` for any Business in `generating_brand` with no queued or running brand job. Catch `CancelledError` in `generate_brand` to run `_resume` before re-raising.
- **Impact**: Without this, every deploy during an onboarding can strand a new Owner at their first impression, which is fatal for pilot conversion.
- **Verifier note**: Confirmed in code: `fail_stale` is a bulk UPDATE with no `_tell_owner` and no requeue; in Python 3.13 `CancelledError` is a `BaseException`, so `except Exception` in `_run` and in `generate_brand` misses it and `runner.stop()` leaves the row `running`; nothing sweeps Businesses stuck in `generating_brand` (only the two places that set it exist); `update_brand` refuses outside `REVISABLE_STATES`. One thing softens it: `OnboardingGate` hands every state past `awaiting_web_form` to the chat, so the Owner can still chat and make posts (`PostMaker` just runs without a Brand Brain). They lose the summary, the confirmation and brand edits, with no recovery short of a manual DB fix. It needs a deploy inside the 1-2 minute brand window, plausible given how often the team deploys but rare for any one Owner: medium.
- **Related**: [ARCH-2](backend-architecture.md).

### BUG-5: Posts, chat photos and served post images are in process memory: after a deploy, approvals stop working and image fetches 404

- **Severity**: high · **Effort**: L · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [conversation/factory.py:47](../../../backend/app/conversation/factory.py): `InMemoryPhotos()`, `InMemoryPosts()`.
  - [posts/store.py:63-73](../../../backend/app/posts/store.py): posts, listed and offered live only in this process.
  - [media/public.py:11-27](../../../backend/app/media/public.py): post JPEGs are served from memory, "lost on restart".
  - [conversation/button_router.py:154-156](../../../backend/app/conversation/button_router.py): an unknown post id becomes `StaleButton`.
  - [posts/publish.py:134, 143-145](../../../backend/app/posts/publish.py): Zernio fetches images from `PUBLIC_BACKEND_URL/media/*`.
  - [channels/router.py:98-100](../../../backend/app/channels/router.py): delivery-status webhooks are ignored, so failed media sends are invisible.
  - [backend/README.md:101](../../../backend/README.md): known; T19, T30 and T17 are planned in [tasks.md](../../implementation/tasks.md).
- **Problem**: Failure: a post is sent at 18:00 and a deploy happens at 18:05. At 18:20 the Owner taps [Aprobar] and gets "Ese botón ya no está activo"; "subilo" returns `no_pending_post`. The Owner has to regenerate (paid again), while the persisted history ([ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md)) still talks about a post id that no longer exists. During the deploy overlap, Kapso and Zernio fetches of `/media/{token}.jpg` created by the old instance hit the new one and get a 404: WhatsApp image delivery then fails asynchronously without notice, and an in-progress publish fails at Instagram's media fetch. The fix is already planned (T19, T30, T17); the case here is to pull it forward as a pilot blocker.
- **Recommendation**: Ship before the pilot: store posts in the existing `posts` table behind the `InMemoryPosts` interface, keep listed and offered in `conversation_state`, and upload renders to a Supabase `renders` bucket served by long-lived signed URLs. The phased plan is in [Path to durable state](backend-architecture.md#path-to-durable-state).
- **Impact**: Every deploy currently invalidates every pending approval. With an estimated 3-5 deploys a day, most posts not approved within minutes are lost.
- **Verifier note**: Verified: `factory.py:47` creates the in-memory stores, `PublicImages` is in memory, an unknown post id becomes `StaleButton`, Zernio fetches from `PUBLIC_BACKEND_URL`, and the router ignores status webhooks. [backend/README.md](../../../backend/README.md) "One instance" already documents it, and T19/T17/T30 plan the fix, so the auditor framed it correctly as pulling planned work forward. The persisted history does keep citing post ids that no longer exist, and the pace of commits and deploys supports treating it as a pilot blocker.
- **Related**: [ARCH-1](backend-architecture.md), [ARCH-3](backend-architecture.md), [ARCH-8](backend-architecture.md), [PRD-2](product.md), [OPS-1](platform-ops.md), [OPS-6](platform-ops.md), [GRW-1](growth-pricing-market.md), [SEC-12](security-privacy.md); BUG-14 in this doc.

### BUG-6: The brand summary is sent outside WhatsApp's 24 h window when the wizard is finished more than a day after the link; the Business never becomes active

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [onboarding/links.py:9](../../../backend/app/onboarding/links.py): the magic link is valid for 7 days.
  - [api/onboarding.py:354-355, 456-460](../../../backend/app/api/onboarding.py): `BRAND_GENERATING` is sent free-form, and a failure is only logged.
  - [jobs/brand.py:79-86](../../../backend/app/jobs/brand.py): the state is committed to `awaiting_brand_confirmation` before `send_brand_summary`, which raises on rejection.
  - [jobs/runner.py:189-201](../../../backend/app/jobs/runner.py): the failure notice is free-form too.
  - [conversation/context.py:105](../../../backend/app/conversation/context.py): `<brand_summary_sent>` is rendered whether or not it was delivered.
  - [architecture/integrations.md:58](../../architecture/integrations.md): assumes "Job results arrive within minutes, so they are fine".
  - [product/mvp.md:36](../../product/mvp.md): F1.8 templates are Won't.
  - [Meta: send messages](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages) (read 2026-10-19): "When the window closes, you can only send pre-approved template messages".
- **Problem**: Failure: the Owner gets the link on Monday and finishes the wizard on Wednesday night. `BRAND_GENERATING` is rejected (logged only). Brand v1 is saved and the state set to `awaiting_brand_confirmation`, then `send_brand_summary` raises `ChannelError`, the job fails, and the `JOB_FAILED` notice is rejected too. The Owner sees "Seguimos por WhatsApp" and then silence. When they write again, the orchestrator is told the summary was sent, the "Sí, es mi marca" buttons never arrive, and the state never reaches `active`. A [Reintentar], if it ever arrived, would rerun the whole Brand Strategist. This challenges the docs' "within minutes" assumption, which holds for chat-triggered jobs but not for a 7-day link.
- **Recommendation**: Prefill the done-screen CTA (`whatsapp_url` plus `?text=Listo`) so the Owner's tap reopens the window; [done-screen.tsx](../../../frontend/components/onboarding/done-screen.tsx) already has a "Volver a WhatsApp" CTA to build on. Store the latest summary as pending in `conversation_state`, and resend it with its buttons at the start of the next inbound turn if delivery wasn't confirmed. Consume Kapso status webhooks, or at least log 131047 failures. Store `last_inbound_at` to decide before sending proactive messages. Add a utility template later (F1.8).
- **Impact**: Recovers onboardings that would otherwise end in silence. Finishing the form the next day is a common pattern for busy shop Owners.
- **Verifier note**: The gap is real (7-day link, free-form brand messages, no tracking of the 24 h window, F1.8 templates are Won't, and `integrations.md:58` assumes minutes). Three corrections. (1) The mechanism is probably different: on the Cloud API, which Kapso proxies, a send outside the window (error 131047) is commonly accepted and then reported as a `failed` status webhook, not a synchronous error. If so, `send_brand_summary` does not raise, the job "succeeds", no `JOB_FAILED` is attempted, and [channels/router.py:98-100](../../../backend/app/channels/router.py) drops the failure silently: the same silence for the Owner, with nothing in the logs. (2) The state matters less than claimed: only the `brand_ok` button reads `awaiting_brand_confirmation`, while chat, posts and `update_brand` all work there, so the Business is not blocked. (3) The done screen already has a "Volver a WhatsApp" CTA pointing at `whatsapp_url` (`wa.me` without prefilled text), so the recommendation should build on it.

### BUG-7: WhatsApp reactions get a "no te entiendo" reply, and any button, sticker or reaction swallows the pending photo batch

- **Severity**: medium · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [channels/kapso_webhook.py:33-64](../../../backend/app/channels/kapso_webhook.py): no `reaction` case, so it falls to `kind='other'`.
  - [channels/kapso_webhook.py:21](../../../backend/app/channels/kapso_webhook.py): a Kapso batch envelope (`batch: true`, `data: [...]`) would be dropped as unparseable.
  - [conversation/chat.py:148](../../../backend/app/conversation/chat.py): `_take_batch` runs for every non-image kind.
  - [conversation/chat.py:190-201](../../../backend/app/conversation/chat.py): the button, other and unclear-audio paths ignore the taken photos.
  - [conversation/events.py:100-103](../../../backend/app/conversation/events.py) and [prompts/events.md:12](../../../backend/app/conversation/prompts/events.md): unsupported means "ask them to write it".
  - [Kapso: message events](https://docs.kapso.ai/docs/platform/webhooks/message-events.md) (read 2026-10-19): lists the `reaction` message type with the payload `{type: 'reaction', reaction: {message_id, emoji}}`.
- **Problem**: (a) The bot asks "¿Lo subo?" and the Owner reacts 👍, a very common gesture for a WhatsApp user in their 50s. That becomes `UnsupportedMedia`, the bot replies that it only understands text, audio and photos, and nothing is published. (b) The Owner sends 3 photos and, within the 5 s debounce, taps [Publicar ahora] on the previous post or sends a sticker or reaction. The photo batch is popped and its timer cancelled, so the photos get no immediate acknowledgement.
- **Recommendation**: Parse `reaction` as its own kind and stay silent by default (mark it read). Optionally, treat a `YES_EMOJI` reaction on the stored "¿Lo subo?" message (keep the wamid returned by `send_text` and `send_buttons`) as the explicit yes through `decide()`, consistent with [ADR 0007](../../decisions/0007-approve-every-post.md). Call `_take_batch` only for text and transcribed audio. If webhook buffering is ever enabled, handle the batch envelope.
- **Impact**: Removes a jarring "no te entiendo" on the most natural approval gesture, and makes sure photos always get an answer.
- **Verifier note**: The reaction part is confirmed: Kapso's doc lists the `reaction` type, `parse_message` has no case for it, it becomes `UnsupportedMedia`, and the events prompt tells the model to say it only understands text, audio and photos. Two sub-claims are overstated. The batch envelope only appears when buffering is enabled for the webhook, which is opt-in, and the payload shape was confirmed on 2026-10-17 without it: a configuration caveat, not a current bug. And the photos are not "never acknowledged": `_take_batch` drops only the debounce batch, the photos stay in `InMemoryPhotos` (and `PhotoKeeper` stores them as Brand assets), and they show up as unseen recent photos on the Owner's next text turn. Only the immediate acknowledgement is lost, and only when a button or sticker arrives within the 5 s debounce.

### BUG-8: Photo plus text race: a text sent right after a photo is answered without the photo, then the photo gets its own reply

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [conversation/chat.py:204-228](../../../backend/app/conversation/chat.py): the photo is downloaded (2 Kapso GETs) and resized before it is added to the batch.
  - [conversation/chat.py:141-149](../../../backend/app/conversation/chat.py): the text handler takes the batch immediately.
  - [conversation/chat.py:233-239](../../../backend/app/conversation/chat.py): `_take_batch` returns `[]` when no batch is registered yet.
- **Problem**: Failure: the Owner sends a photo of a sideboard, then "armame un post con esta" about 1 s later. The photo is not in `_batches` until its 1-4 s download and Pillow resize finish. The text turn runs without it ("¿Qué foto querés usar?"), and 5 s later a `PhotosReceived` turn sends "¡Buenísima! ¿Armo un post con esta foto?". The Owner gets two contradictory replies on the core flow.
- **Recommendation**: Register the batch, with an in-flight download counter or `Event`, before the first `await` in `_photo_arrived`. Have text and audio turns wait briefly (capped at about 10-15 s) for in-flight downloads before `_take_batch`. Add a backend test with a slow fake `download_media`.
- **Impact**: A cleaner core "photo, then ask for a post" interaction, without double replies or wasted LLM turns.
- **Verifier note**: The race is real: `_photo_arrived` awaits `download_media` and `prepare_reference` before registering the batch, and the text handler takes the batch right away. The impact is smaller than claimed: the `PhotosReceived` event prompt ([prompts/events.md](../../../backend/app/conversation/prompts/events.md)) says that if the Owner already asked for a post before sending the photos, the bot should create it right away, so the second reply usually starts the post instead of asking. The result is one awkward extra message ("¿qué foto?", then "dale, lo armo"), not an extra round trip, and it requires the text to land inside the download window.

### BUG-9: Generation caps aren't caps: in memory, reset on deploy, count posts not images, consumed by failures; the Free tier's 3 a month isn't enforced

- **Severity**: low · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [posts/maker.py:105-106](../../../backend/app/posts/maker.py): the `_designs_today` dict is in memory.
  - [posts/maker.py:185-195](../../../backend/app/posts/maker.py): counted at the start, never refunded, one count per design regardless of slides.
  - [carousel/schemas.py:5](../../../backend/app/carousel/schemas.py): `MAX_SLIDES = 10`.
  - [config.py:44](../../../backend/app/config.py): `max_posts_per_day = 5`.
  - [architecture/agents.md:426](../../architecture/agents.md): the spec says `MAX_POSTS_PER_DAY` counts "image generations".
  - [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md): the Free cap "must be enforced in the backend once billing exists".
  - [0001_initial.sql:301](../../../backend/migrations/versions/0001_initial.sql): `agent_runs` (image generation usage) exists, but nothing writes it.
  - [image-generation-providers.md:28](../image-generation-providers.md): US$0.0504 per 2K image.
- **Problem**: A Free Owner can make 5 ten-slide designs a day: 50 images, about US$2.5 a day (estimate). Every deploy resets the counter. Meanwhile a paying Owner who hits two Gemini 503 failures has only 3 designs left that day, because failures consume the cap. There is no monthly count anywhere, so the Free tier in [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md) (3 posts a month) cannot be honoured in the pilot.
- **Recommendation**: Write an `agent_runs` row per image call (`business_id`, usage). Derive the daily cap (Montevideo time) from it, count images rather than designs, and skip failed generations. Add the monthly Free-tier count and a `businesses.plan` column when billing work starts, as ADR 0031 plans.
- **Impact**: Caps the cost per Free Owner and makes unit economics measurable before billing.
- **Verifier note**: The cap mechanics are confirmed, and the price checks out against the Gemini API pricing page on `ai.google.dev` (read 2026-10-19: US$0.0504 per 2K image for `gemini-nano-banana-2.1`), so 50 images is about US$2.5. Corrections: "more with 4K panoramas" is wrong, because a panorama is one 4K image (US$0.113) sliced into every slide ([carousel/generator.py:112-135](../../../backend/app/carousel/generator.py)), cheaper than 10 × 2K (US$0.50). And ADR 0031 explicitly defers the Free cap until billing exists, so a missing monthly cap during the pilot is a planned gap, not a bug. The worst case of about US$2.5 per Owner per day takes a deliberately heavy user and is negligible for a few pilot Owners; the finding's value is cost visibility and cap correctness before billing.
- **Related**: [ARCH-5](backend-architecture.md), [COST-2](unit-economics.md), [GRW-3](growth-pricing-market.md), [SEC-4](security-privacy.md), [PRD-12](product.md).

### BUG-10: `publish_pending` is a dead end: no follow-up check, so the Owner never gets the link or the failure

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [publishing/zernio.py:152-181](../../../backend/app/publishing/zernio.py): polls for at most 90 s, then returns pending.
  - [publishing/zernio.py:15-17](../../../backend/app/publishing/zernio.py): a live test showed Instagram answering "publishing" while processing.
  - [posts/publish.py:178-181](../../../backend/app/posts/publish.py): the status is set to `publish_pending`, and nothing is scheduled after.
  - [publishing/base.py:17-21](../../../backend/app/publishing/base.py): relies on "the webhook (T29) or a later status check", and neither exists.
  - [posts/store.py:21](../../../backend/app/posts/store.py): `BUSY` posts are never retried or evicted.
- **Problem**: Failure: an 8-slide carousel is still processing after 90 s, so the Owner reads "Instagram lo está procesando, en un ratito aparece". If Zernio then ends in `failed` (for example because an image URL 404s after a deploy, see BUG-5), the Owner believes it is live. If it does go live, the permalink is never sent. Either way the post stays `BUSY` forever, so [Reintentar] is never offered.
- **Recommendation**: Queue `check_publish` jobs at increasing delays that GET `/posts/{external_post_id}` with the existing parsing and emit `Published` or `PublishFailed`. Add the T29 webhook later as the fast path. This depends on posts being persisted (BUG-5) so that the check survives a deploy.
- **Impact**: Closes the publish loop, the product's payoff moment, and catches silent failures.
- **Verifier note**: Verified: `ZernioPublisher._wait_for_outcome` polls for up to 90 s and returns pending, `PostPublisher._finish` schedules nothing, neither the T29 webhook nor a later check exists, and `publish_pending` is `BUSY`, so the post is never retried or evicted and "subilo" returns `post_not_pending`. The live-test comment shows the path is reachable. T57 in [tasks.md](../../implementation/tasks.md) accepts this for now ("the Owner learns the final state from Instagram until the webhook, T29"): a known gap, but it falls on the product's payoff moment.

### BUG-11: Voice notes without a Kapso transcript are rejected; the Gemini fallback from ADR 0021 isn't built

- **Severity**: medium · **Effort**: S · **Confidence**: medium · **Verified**: confirmed
- **Evidence**:
  - [conversation/chat.py:178-191](../../../backend/app/conversation/chat.py): "TranscriberPort isn't built yet, so no transcript = unclear".
  - [channels/kapso_webhook.py:46-59](../../../backend/app/channels/kapso_webhook.py): the transcript is taken only from `kapso.transcript`.
  - [conversation/onboarding.py:119-125](../../../backend/app/conversation/onboarding.py): the Business name from a Voice note also depends on the provider transcript.
  - [ADR 0021](../../decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md).
  - [open-questions.md](../../open-questions.md): Kapso transcript quality and plan limits are still unchecked.
- **Problem**: The persona lives in Voice notes. If Kapso returns no transcript (plan limits, long audio, a transient issue), a clear 60-90 s note like "armame un post del aparador de roble a 12.900 con envío gratis" gets "No te llegué a entender el audio 🙈", and the Owner has to repeat it, maybe by typing, which they avoid. During onboarding, the welcome is sent again.
- **Recommendation**: Implement `TranscriberPort` with Gemini audio input as ADR 0021 describes (a `TRANSCRIBE_FALLBACK` switch and a verbatim Rioplatense prompt), and use it whenever `provider_transcript` is empty. Log how often it fires, and compare the quality of both transcripts on real pilot audio.
- **Impact**: Protects the primary input mode of the target persona.
- **Verifier note**: Verified: no `TranscriberPort`, so a Voice note without a transcript becomes `AudioUnclear`; the webhook reads only `kapso.transcript.text`; a Business name sent by Voice note with no transcript gets the welcome again. ADR 0021 specifies the fallback, and [product/mvp.md](../../product/mvp.md) F1.7 (Voice notes, with the fallback) is a Must. `open-questions.md:29` still lists Rioplatense quality and Kapso plan limits as unchecked. For a persona that lives in Voice notes, medium is fair.
- **Related**: [AIQ-11](ai-quality.md), [MOD-5](models.md).

### BUG-12: Unbounded in-process caches on a 1 GB Railway Trial service risk out-of-memory restarts

- **Severity**: low · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [conversation/library.py:31-32, 60, 99-108](../../../backend/app/conversation/library.py): every library photo of every Business is downloaded on the first turn and kept forever.
  - [conversation/photo_keeper.py:36-43](../../../backend/app/conversation/photo_keeper.py): every chat photo becomes a Brand asset, so the library grows without bound.
  - [conversation/photos.py:52-55](../../../backend/app/conversation/photos.py): per-sender library and logo dicts are never evicted.
  - [posts/store.py:8, 66-68](../../../backend/app/posts/store.py): up to 10 posts per sender holding slide JPEGs plus source photos.
  - [media/public.py:8](../../../backend/app/media/public.py): 200 JPEGs (about 40 MB).
  - [conversation/chat.py:682-686](../../../backend/app/conversation/chat.py): every brand photo is listed in every turn's context.
  - [Railway: plans](https://docs.railway.com/reference/pricing/plans) (read 2026-10-19): Trial has 1 GB RAM per service; [open-questions.md](../../open-questions.md) says the service runs on the full Trial.
- **Problem**: Rough estimate: 30 active Owners × about 50 library photos (15 wizard, 24 Instagram, plus chat) × about 400 KB ≈ 600 MB. Add posts, `PublicImages` and Pillow decode spikes (a 12 MP photo decodes to about 36 MB of RGB) and the service runs out of memory. Railway restarts it, which also wipes every in-memory post and turn (BUG-2, BUG-5). The `<brand_photos>` block also grows with every photo the Owner ever sent, adding tokens to every turn.
- **Recommendation**: Low priority for the pilot: move to Hobby before the Trial ends (already planned in [ADR 0017](../../decisions/0017-backend-host-railway.md)). Before scaling past a handful of Owners, add an LRU byte cap to `BrandLibrary`, fetch bytes lazily only for photos actually attached, limit `<brand_photos>` to the N most recent or relevant, and log RSS.
- **Impact**: Avoids crash-restarts that multiply every other state-loss bug, and trims per-turn tokens.
- **Verifier note**: The facts hold: `BrandLibrary._images` and `_logos` are never evicted, every ready library photo is downloaded on a turn as a 1536 px agent copy, `InMemoryPhotos` has no idle expiry, `PublicImages` is capped at 200, and Railway's plans page confirms 1 GB per service on Trial and 0.5 GB on Free. But the 600 MB estimate assumes about 30 active Owners; at pilot scale (one to a few Owners × about 50 photos × about 300 KB) it is tens of MB, and ADR 0017 already says to move to Hobby on memory pressure or when the Trial ends. The Trial also runs out (30 days or the US$5 grant, from about 2026-10-18), which is the more pressing hosting risk. The growing `<brand_photos>` block is a real, minor token cost.
- **Related**: [ARCH-11](backend-architecture.md), [OPS-15](platform-ops.md), [COST-17](unit-economics.md), [AIQ-19](ai-quality.md).

### BUG-13: No wall-clock bound on a post's generation; one slow Gemini image call blocks the Owner for many minutes

- **Severity**: medium · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [imagegen/gemini.py:16, 20](../../../backend/app/imagegen/gemini.py): 120 s per attempt, 4 attempts (429 and 5xx retried), backoff up to 30 s.
  - [imagegen/gemini.py:49, 78-84](../../../backend/app/imagegen/gemini.py): one global `Semaphore(4)` shared by all Owners.
  - [carousel/generator.py:56-63, 137-151](../../../backend/app/carousel/generator.py): the cover is generated first, then the rest; a safety block doubles the calls.
  - [posts/maker.py:178-179, 193, 248-249](../../../backend/app/posts/maker.py): `generation_in_progress` is held until the task ends.
- **Problem**: Under Gemini image overload (503s or timeouts), each slide can take about 4 × 120 s plus backoff, roughly 8 min. Because the cover is generated first and then the rest, a 5-slide design can hang for many minutes (the auditor estimated 15-30 min including the blocked-content retry; the reviewer corrected it to about 16 min). The Owner who was told "lo armo ⏳" hears nothing, and every new request gets "Estoy terminando otro post". Other Owners' slides wait behind the same 4 permits.
- **Recommendation**: Wrap `PostMaker._render`/`_generate` in `asyncio.wait_for` (about 240-300 s) and raise `PostFailed`, with the existing retry path. Lower the image adapter to 2 attempts with a 60-90 s timeout. Send one "sigue armándose" note at around 90 s. Consider a per-sender limit on image calls so one carousel can't take all 4 permits.
- **Impact**: Bounds the worst-case wait and keeps one Owner's carousel from blocking the others.
- **Verifier note**: Partly confirmed, worst case overstated. `gemini.py` sets a 120 s timeout with `HttpRetryOptions(attempts=4, max_delay=30)`, and the installed google-genai retries 408, 429, 5xx and `httpx` timeouts, so one slide can take about 8 min. With the cover first and the rest in parallel, a design can hang for about 16 min during an outage, with `generation_in_progress` held and the global `Semaphore(4)` shared by every Owner. The "up to twice that" from the blocked-content retry is wrong: it fires only on safety blocks or no-image responses, which come back fast. About 16 min of unbounded silence is still worth fixing.
- **Related**: [ARCH-12](backend-architecture.md), [FE-10](frontend.md).

### BUG-14: Chat photo ids restart at `f1` after every deploy while the history that cites them persists

- **Severity**: low · **Effort**: S · **Confidence**: medium · **Verified**: confirmed
- **Evidence**:
  - [conversation/photos.py:33, 57-63](../../../backend/app/conversation/photos.py): `next_number` starts at 1 per process.
  - [conversation/photos.py:39-41](../../../backend/app/conversation/photos.py): the docstring promises ids are "never reused".
  - [conversation/chat.py:629-634](../../../backend/app/conversation/chat.py): stored user steps carry `[fotos f1 f2]`.
  - [conversation/events.py:23-28](../../../backend/app/conversation/events.py): post notes cite photo ids.
  - [conversation/history.py:76-81](../../../backend/app/conversation/history.py): the history is persisted ([ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md)).
- **Problem**: Before a deploy, `f3` was the sideboard. After the deploy the counter restarts, and a new photo of a table eventually becomes `f3`. The Owner asks "hacé otro como el de ayer con la foto del aparador". The model reads `[post … from photos f3]` in the history, calls `create_post(asset_ids=['f3'])`, and `find()` resolves it to today's table, so the post is built on the wrong product.
- **Recommendation**: Prefix chat photo ids with a per-process epoch (for example `f7a-3`), seed the counter from a persisted count, or reference chat photos by their `b` ids once `PhotoKeeper` stores them.
- **Impact**: Avoids wrong-product posts and wasted generations after deploys.
- **Verifier note**: Verified: the counter restarts per process despite the docstring, and the persisted history carries the old ids. The scenario is narrow: `find()` resolves only photos from the last 30 minutes plus library `b` ids, so an old `f` id returns `unknown_asset` unless enough new photos arrived after a restart to reuse that number within 30 minutes. Real but rare: low is right.
- **Related**: [ARCH-1](backend-architecture.md), [ARCH-3](backend-architecture.md), [ARCH-8](backend-architecture.md), [OPS-1](platform-ops.md), [OPS-6](platform-ops.md), [SEC-12](security-privacy.md); BUG-5 in this doc.

### BUG-15: A send failure mid-post throws away a finished, paid post and tells the model nothing arrived

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [posts/maker.py:226-227](../../../backend/app/posts/maker.py): `_send` runs before `_keep`.
  - [posts/maker.py:391-398](../../../backend/app/posts/maker.py): images are sent one by one with no retry.
  - [posts/maker.py:244-247](../../../backend/app/posts/maker.py): any exception becomes `PostFailed`.
  - [conversation/events.py:43-48](../../../backend/app/conversation/events.py): the note says "Nothing reached the Owner".
- **Problem**: Failure: a 6-slide carousel is generated (about US$0.30) and Kapso returns a 5xx on slide 4. Slides 1-3 are already on the Owner's phone, without buttons. The post is never stored, so it can't be approved, and the daily slot is used. The model then says "no pude armarlo" while 3 slides are visible.
- **Recommendation**: Store the post (status `sending`) before sending, retry each send once, and on failure emit a distinct event with a resend action that reuses the stored images.
- **Impact**: Saves paid generations and avoids a misleading message.
- **Verifier note**: Verified: `_send` runs before `_keep`, sends with no retry, and any exception becomes `PostFailed` with the "Nothing reached the Owner" note; the post is never stored and the daily slot stays used. The cost is right: 6 × US$0.0504 ≈ US$0.30. A Kapso 5xx in the middle of a carousel is uncommon, so low.
- **Related**: [COST-13](unit-economics.md).

### BUG-16: A 429 on a chat turn fails at once, and photo albums fan out unbounded concurrent LLM calls

- **Severity**: low · **Effort**: S · **Confidence**: medium · **Verified**: confirmed
- **Evidence**:
  - [llm/client.py:31-37](../../../backend/app/llm/client.py): 429 is excluded from retries (to avoid a 19 h `Retry-After`).
  - [llm/client.py:240-243](../../../backend/app/llm/client.py): any error becomes `LLMError`.
  - [conversation/chat.py:221-222](../../../backend/app/conversation/chat.py): one `PhotoKeeper` `analyze_photo` task per photo, with no limit.
  - [conversation/chat.py:295-297](../../../backend/app/conversation/chat.py): `LLMError` becomes `REPLY_FAILED`.
- **Problem**: A 10-photo album starts 10 concurrent Asset Analyst calls, plus the orchestrator turn and the drafter. A per-minute quota 429 then makes the Owner get "se me trabó algo, ¿me lo mandás de nuevo?", and some photos never get descriptions.
- **Recommendation**: Make sure the production Gemini key is on a billed tier, both for quota and so Owner data isn't used for training. Then add a small semaphore around `PhotoKeeper` analyses, and optionally retry a 429 once when `Retry-After` is 10 s or less.
- **Impact**: Fewer spurious failure replies at peak moments (album uploads).
- **Verifier note**: Verified: 429 is removed from the retry codes on purpose (the SDK honours a 19 h `Retry-After`), errors become `REPLY_FAILED`, and `PhotoKeeper` starts one analysis per photo with no limit. The same code comment says a daily-quota 429 was hit on 2026-10-18 and that latencies were measured on the free tier. Whether a 10-photo album triggers a 429 depends on the key's tier: on a billed tier the per-minute limits are far above this load; on the free tier, Owner photos may also be used for training ([image-generation-providers.md](../image-generation-providers.md)). The most valuable part of the recommendation is confirming the production key is billed.
- **Related**: [SEC-11](security-privacy.md), [MOD-10](models.md).

### BUG-17: Replies over WhatsApp's 4096-character limit are dropped after being stored as delivered

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [conversation/chat.py:306](../../../backend/app/conversation/chat.py): the turn is written to the history before sending.
  - [conversation/chat.py:156-157](../../../backend/app/conversation/chat.py): `send_text` with no length check.
  - [conversation/chat.py:637-648](../../../backend/app/conversation/chat.py): only the 1024-character buttons-body limit is handled.
  - [channels/kapso.py:50-51](../../../backend/app/channels/kapso.py).
  - [Meta: text messages](https://developers.facebook.com/docs/whatsapp/cloud-api/messages/text-messages) (read 2026-10-19): text body "Maximum 4096 characters".
- **Problem**: Failure: the Owner asks "pasame todos los textos de los posts" and the model writes about 5,000 characters. Kapso returns a 400, and the `ChannelError` is only logged in `run_handler`. The Owner sees nothing, while the history records the answer as sent.
- **Recommendation**: In `send_text`, split long text on paragraph boundaries into chunks of at most 4000 characters, and catch `ChannelError` around the reply send in `ChatHandler.handle` to attempt `REPLY_FAILED`.
- **Impact**: Removes a silent no-reply case.
- **Verifier note**: Verified: `_llm_turn` stores the turn (`_remember_turn`) before `handle()` calls `send_text`, `KapsoChannel.send_text` has no length check, only the 1024-character limit on button bodies and image captions is handled, and a `ChannelError` propagates to `run_handler`, which only logs it. The conversation rules ask for short replies, so a reply over 4,000 characters is rare: low.

### BUG-18: Wizard PUT `/brand` and `/preferences` can overwrite the Instagram import's `onboarding_data` (lost update)

- **Severity**: low · **Effort**: S · **Confidence**: medium · **Verified**: confirmed
- **Evidence**:
  - [api/onboarding.py:234-236](../../../backend/app/api/onboarding.py): a read-modify-write of the JSONB loaded at request start.
  - [api/onboarding.py:248-250](../../../backend/app/api/onboarding.py): the same for preferences.
  - [jobs/instagram.py:96-101, 122](../../../backend/app/jobs/instagram.py): the import job writes `onboarding_data['instagram']` the same way.
- **Problem**: If the import job commits `instagram` while a PUT `/brand` is between its SELECT and its commit, the PUT writes back a dict without `instagram`. The Brand Brain is then built without the Instagram data that [ADR 0032](../../decisions/0032-instagram-first-onboarding.md) is built around, and nobody notices. The window is narrow but real, because the import runs while the Owner fills in the next steps.
- **Recommendation**: Update keys atomically (`onboarding_data = onboarding_data || jsonb_build_object(...)`), take `SELECT … FOR UPDATE` in both writers, or move the import summary to its own column.
- **Impact**: Protects the Instagram-first onboarding's main input.
- **Verifier note**: Verified: `save_brand` and `save_preferences` read-modify-write `onboarding_data` from the Business loaded at request start, with no row lock, and the import job rewrites the whole dict after reading the row fresh. The window is one request's duration, made a little longer by the cross-continent round trips to Supabase: narrow but reachable while the import runs and the Owner moves through the steps. Low.

### BUG-19: Job slots and DB connections can be starved by sleeping or I/O-bound holders

- **Severity**: low · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [jobs/runner.py:26](../../../backend/app/jobs/runner.py): 4 job slots.
  - [jobs/brand.py:24, 117-137](../../../backend/app/jobs/brand.py): `generate_brand` holds a slot for up to 60 s polling for input jobs.
  - [api/onboarding.py:296-309, 359-392, 400-409](../../../backend/app/api/onboarding.py): the asset row `FOR UPDATE` plus a pooled connection are held across a Storage download, Pillow and two uploads.
  - [db/session.py:14-16](../../../backend/app/db/session.py): the default pool (5 plus 10 overflow, 30 s timeout) on Supabase's session pooler.
- **Problem**: If 4 Owners finish the wizard within a minute, 4 `generate_brand` jobs fill every slot while waiting for `analyze_asset` jobs that cannot start, so all 4 Brand Brains are built without photo analyses after 60 s. Separately, about 5 Owners uploading 3 photos each hold 15 connections for seconds at a time, so webhook DB calls wait or time out and Owners get `REPLY_FAILED`.
- **Recommendation**: Low priority. In `/complete`, mark the asset `processing` and commit before the Storage and Pillow work, then finish in a short second transaction. If concurrent onboardings grow, let `generate_brand` requeue itself with a `not_before` instead of polling inside a slot (Phase A in [Path to durable state](backend-architecture.md#path-to-durable-state)).
- **Impact**: Keeps Brand Brain quality and chat latency stable under concurrent onboardings.
- **Verifier note**: The slot starvation is mostly unreachable as described: `run_due` claims queued jobs FIFO by `created_at` ([jobs/runner.py:117-123](../../../backend/app/jobs/runner.py)), and `analyze_asset` jobs are queued as each upload completes (`_finish_upload`), before `/complete` queues `generate_brand`, so the input jobs get slots first. Only the analyses an import creates as it finishes, after `/complete`, could wait behind 4 simultaneous `generate_brand` jobs, which needs 4 Owners finishing within a minute, and even then `generate_brand` proceeds after 60 s. The connection-holding part is real: `/complete` keeps a row lock and a pooled connection across the download, Pillow and two uploads, with the default 5 plus 10 pool and a 30 s timeout. At pilot concurrency that is a latency risk, not an outage.
- **Related**: [ARCH-8](backend-architecture.md).

### BUG-20: `DbHistory` caches business ids forever, so resetting a tester's Business breaks their chat until a restart

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [conversation/history.py:86](../../../backend/app/conversation/history.py): the `_business_ids` dict is never invalidated.
  - [conversation/history.py:134-140](../../../backend/app/conversation/history.py): the cached id is reused for every insert.
- **Problem**: Failure: during the pilot the team deletes a test Business to rerun onboarding, and the gate recreates it with a new id. `DbHistory.extend` keeps inserting `conversation_steps` rows with the old id, which raises a foreign-key violation (`SQLAlchemyError`), so every message gets `REPLY_FAILED` until the next deploy.
- **Recommendation**: Drop the cache (it saves one indexed lookup), or evict the entry on `IntegrityError` and retry once.
- **Impact**: Avoids a confusing outage during pilot resets and support work.
- **Verifier note**: Verified: `_business_ids` is never invalidated, and `conversation_steps.business_id` has a foreign key with `on delete cascade` ([0003_conversation_memory.sql](../../../backend/migrations/versions/0003_conversation_memory.sql)), so after a Business is deleted and recreated, `extend()` inserts with the stale id and gets an `IntegrityError`; `handle()` catches it as a `SQLAlchemyError` and sends `REPLY_FAILED` on every turn until a restart. It only happens after a manual reset, plausible for testers during the pilot: low.
- **Related**: [ARCH-6](backend-architecture.md), [OPS-10](platform-ops.md).
