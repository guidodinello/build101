# Backend architecture and code quality

This doc covers the backend's structure, durability, configuration, data model and code health. It is one dimension of the 2026-10-19 product and codebase audit (index in [README.md](./README.md), cross-dimension synthesis in [summary.md](summary.md)), read from the code at commit `dc0bc01`. An independent adversarial reviewer checked every finding against the code and the cited sources. "Adjusted" means the reviewer corrected the severity or details; the severity and recommendation shown here already include those corrections, and the verifier note says what changed.

## Summary

The backend is a well-kept modular monolith. Ruff is clean, the 591 non-live tests pass (95 more need a database and run in CI against Postgres 17), the ports and adapters are consistent, Pillow work is moved off the event loop, approval is decided in code ([ADR 0007](../../decisions/0007-approve-every-post.md)), and the Zernio idempotency and pending-publish handling is careful (audit observation, 2026-10-19).

The weak point is durability. The work an Owner cares about most runs as in-process `asyncio` tasks and in-memory state: posts and their JPEGs, the generation and publish runs, the daily limits, the webhook dedupe and the inbound messages. Railway redeploys on every push to `main`, overlaps the old and new containers, then sends SIGTERM, and nothing drains or requeues that work, so every deploy or out-of-memory restart silently loses in-flight posts, publishes and Owner messages (ARCH-1, ARCH-3). An interrupted `generate_brand` leaves the Business stuck in `generating_brand` forever (ARCH-2). The `posts`, `messages`, `agent_runs` and `jobs` tables needed to fix this already exist in the schema (9 of 19 tables are unused). The main recommendation is to bring T17, T19 and T30 forward and make the existing Postgres job runner crash-safe before the first real Owner (see [Path to durable state](#path-to-durable-state)).

Several settings that should be per Business are still global, and they block a multi-owner pilot: the single Zernio publish account ([ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md), ARCH-4), one Niche Report's trend notes injected into every Business and a hard-coded timezone (ARCH-10), and a free-tier limit that lives in memory (ARCH-5). Smaller themes: config falls back to mocks in production (ARCH-9), about 8 cross-continent DB sessions per turn with Railway in Virginia and Supabase in São Paulo (ARCH-6), import cycles between `conversation`, `posts` and `jobs` (ARCH-7), a 700-line `ChatHandler` (ARCH-14), and `how-it-works.md`, dated the day of the audit, which contradicts [ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md) (ARCH-15).

## Findings at a glance

Effort: S is under half a day, M is 1-2 days, L is about a week, XL is more than a week.

| Id | Severity | Effort | Finding |
|---|---|---|---|
| [ARCH-1](#arch-1-posts-their-images-and-the-generate-and-publish-runs-live-only-in-process-memory-so-every-deploy-or-crash-loses-them) | high | L | Posts, images and the generate and publish runs exist only in memory |
| [ARCH-2](#arch-2-an-interrupted-generate_brand-leaves-the-business-stuck-in-generating_brand-forever-with-no-message-to-the-owner-and-no-retry) | high | M | An interrupted `generate_brand` leaves the Business stuck forever |
| [ARCH-4](#arch-4-the-publish-target-is-one-global-zernio-account-adr-0024-so-every-pilot-owners-approved-post-goes-to-the-same-instagram) | high | L | One global Zernio publish account |
| [ARCH-3](#arch-3-inbound-whatsapp-messages-are-not-persisted-acknowledged-with-200-then-handled-in-a-backgroundtask-with-in-memory-dedupe) | medium | M | Inbound messages are not persisted; dedupe is in memory |
| [ARCH-5](#arch-5-usage-limits-live-in-memory-count-only-designs-and-dont-match-the-pricing-adr-free--3-posts-a-month) | medium | M | Limits live in memory, count only designs and don't match ADR 0031 |
| [ARCH-6](#arch-6-about-8-separate-db-sessions-per-owner-turn-each-crossing-virginia-to-são-paulo-add-an-estimated-3-4-s-of-latency) | medium | M | About 8 DB sessions per turn between Virginia and São Paulo (about 3-4 s, estimate) |
| [ARCH-7](#arch-7-no-single-composition-root-cache-singletons-two-lifespans-and-import-cycles-so-jobs-cant-reach-the-orchestrator-the-adr-0026-gap) | medium | M | No composition root; import cycles; jobs can't reach the orchestrator |
| [ARCH-8](#arch-8-a-durable-queue-path-for-the-job-runner-per-kind-slots-run_after-retries-heartbeats-and-periodic-jobs-plus-when-to-split-web-and-worker) | medium | M | Path to a durable job runner: slots, `run_after`, retries, heartbeats |
| [ARCH-9](#arch-9-config-falls-back-to-mocks-in-production-a-missing-env-var-makes-the-bot-tell-an-owner-a-post-is-live-with-a-mock-permalink) | medium | S | Config falls back to mocks in production |
| [ARCH-12](#arch-12-post-generation-has-no-overall-deadline-and-one-transient-render-error-throws-away-already-paid-ai-images) | medium | S | No generation deadline; one render error discards paid images |
| [ARCH-13](#arch-13-agent_runs-is-never-written-and-image-usage-is-thrown-away-so-there-is-no-per-business-cost-to-validate-the-us29-price) | medium | M | No per-Business cost to validate the US$29 price |
| [ARCH-15](#arch-15-architecture-docs-contradict-the-code-including-how-it-worksmd-dated-the-day-of-the-audit) | medium | S | Architecture docs contradict the code (`how-it-works.md`) |
| [ARCH-10](#arch-10-global-settings-that-should-be-per-business-one-niche-reports-trend-notes-go-to-every-business-and-the-timezone-is-hard-coded) | low | S | Global trend notes and a hard-coded timezone |
| [ARCH-11](#arch-11-process-memory-grows-without-bound-brand-photo-bytes-are-cached-forever-per-business-so-a-1-gb-instance-could-run-out-of-memory-at-a-few-dozen-active-owners) | low | S | The brand-photo cache grows without bound |
| [ARCH-14](#arch-14-chatpy-702-lines-is-a-god-class-and-the-posts-layer-is-typed-on-concrete-in-memory-stores) | low | M | A 702-line `ChatHandler`; consumers typed on the concrete in-memory stores |
| [ARCH-16](#arch-16-rls-is-disabled-on-18-of-19-public-tables-including-conversation_steps-owner_notes-and-magic_links) | low | S | RLS is disabled on 18 of 19 tables |
| [ARCH-17](#arch-17-the-schema-has-two-sources-of-truth-and-nothing-checks-them-against-each-other) | low | S | Two sources of truth for the schema, never compared |
| [ARCH-18](#arch-18-apionboardingpy-578-lines-mixes-routes-business-rules-owner-facing-copy-and-storage-io-and-holds-row-locks-across-http-calls) | low | S | `api/onboarding.py` mixes concerns and holds locks across HTTP calls |
| [ARCH-19](#arch-19-dead-settings-and-stale-until-t02t23-shims) | low | S | Dead settings and stale "until T02/T23" shims |

## Health, size and state numbers

**Health.** `uv run pytest` gives 591 passed and 95 skipped; the DB tests need `TEST_DATABASE_URL`, and CI runs them on Postgres 17. `ruff check` is clean (audit observation, 2026-10-19).

**Largest modules.** [conversation/chat.py](../../../backend/app/conversation/chat.py) has 702 lines, [api/onboarding.py](../../../backend/app/api/onboarding.py) 578, [posts/maker.py](../../../backend/app/posts/maker.py) 413 and [conversation/events.py](../../../backend/app/conversation/events.py) 325. The largest test file is [tests/test_chat_handler.py](../../../backend/tests/test_chat_handler.py), at 1038 lines (audit observation, 2026-10-19).

**Schema usage.** The migrations in [backend/migrations/versions/](../../../backend/migrations/versions) create 19 tables. 9 are unused: `offers`, `offer_products`, `content_plans`, `posts`, `post_revisions`, `post_variations`, `post_slides`, `messages` and `agent_runs` (audit observation, 2026-10-19).

**State lost on a deploy, restart or out-of-memory restart.**

| State | Where it lives today | Durable target |
|---|---|---|
| Posts and their JPEGs, status, approval | `InMemoryPosts` in [posts/store.py](../../../backend/app/posts/store.py) | `posts`, `post_slides`, plus a Storage `renders` bucket |
| Generation and publish runs | `asyncio` tasks at [posts/maker.py:199](../../../backend/app/posts/maker.py) and [posts/publish.py:110](../../../backend/app/posts/publish.py) | `jobs` (the `generate_post` and `publish_post` kinds are already allowed) |
| Served images | [media/public.py](../../../backend/app/media/public.py) (200 at most) | Storage public URLs |
| Daily design limit, per-sender generating guard | [posts/maker.py:105-106](../../../backend/app/posts/maker.py) | SQL over `posts` |
| Webhook dedupe, inbound message | [channels/inbound.py](../../../backend/app/channels/inbound.py), FastAPI `BackgroundTasks` | `messages` (unique `external_id`) |
| Running jobs on SIGTERM | [jobs/runner.py:81-86](../../../backend/app/jobs/runner.py) (cancelled, then failed after 5 min) | Requeue plus a heartbeat |
| Chat photos (30 min) and the photo batch (5 s) | [conversation/photos.py](../../../backend/app/conversation/photos.py), [conversation/chat.py](../../../backend/app/conversation/chat.py) | `brand_assets` (done) / a `run_after` job |

**DB sessions per Owner text turn (estimate).** Each row is one separate session opened during a single text turn.

| # | Call site | Queries |
|---|---|---|
| 1 | [conversation/onboarding.py:63](../../../backend/app/conversation/onboarding.py) | 1 (`FOR UPDATE`) |
| 2 | [conversation/library.py:35](../../../backend/app/conversation/library.py) | 3 |
| 3 | [conversation/library.py:76](../../../backend/app/conversation/library.py) | 1 |
| 4 | [conversation/history.py:92](../../../backend/app/conversation/history.py) | 1 |
| 5 | [conversation/context.py:62](../../../backend/app/conversation/context.py) | 3 |
| 6 | [conversation/notes.py:63](../../../backend/app/conversation/notes.py) | 1 |
| 7 | [conversation/history.py:113](../../../backend/app/conversation/history.py) | 1 |
| 8 | [conversation/history.py:104](../../../backend/app/conversation/history.py) | 1 insert plus commit |

About 8 sessions, each paying a pre-ping, BEGIN and END, plus about 12 queries, come to roughly 36 sequential round trips. At about 115 ms from Virginia to São Paulo ([economize.cloud latency table](https://www.economize.cloud/resources/aws/latency/us-east-1-vs-sa-east-1/), read 2026-10-19) that is about 4 s per turn. This is an estimate that assumes every round trip is sequential and pays the full cross-region latency; measure it with a per-turn timing log (ARCH-6).

**Memory per active Business (estimate).** About 12 MB of library photo bytes at onboarding (15 wizard uploads plus 24 Instagram imports at roughly 0.3 MB each), growing with every chat photo, plus up to about 20 MB of in-memory posts. That is about 20-30 MB per Business, so about 30-40 active Owners per 1 GB instance. `PublicImages` adds a global 40 MB. The reviewer notes the per-Business figure is somewhat high, because the photo store keeps references to the same bytes rather than copies (ARCH-11).

## Path to durable state

The step-by-step path from in-process work to durable jobs, combining this dimension's numbers with the first engineering item of the audit synthesis ([summary.md](summary.md)). It merges ARCH-1, ARCH-3 and ARCH-8 with [BUG-5](bugs-reliability.md), [BUG-14](bugs-reliability.md), [OPS-1](platform-ops.md), [OPS-6](platform-ops.md) and [SEC-12](security-privacy.md). The synthesis roadmap schedules Phase A in the first 30 days (to about 2026-11-18) as the largest single item, after the interim mitigations of the first week: `RAILWAY_DEPLOYMENT_DRAINING_SECONDS`, shutdown joins, Railway Watch Paths on `/backend/**` and no deploys during pilot hours ([BUG-2](bugs-reliability.md)).

### Phase A: before the first real Owner

- Start by adding `PostStore` and `PhotoStore` Protocols (ARCH-14) and a single composition root on `app.state` (ARCH-7). That lets jobs reach `notify` and finishes [ADR 0026](../../decisions/0026-owner-messages-from-the-orchestrator.md).
- Store posts and post slides in the DB, with full UUIDs plus `approved_at` and `approval_source`. Store scenes, copy and the brief too, which enables targeted revisions ([AIQ-7](ai-quality.md)). Renders go to Storage, with signed URLs or limits ([SEC-16](security-privacy.md)).
- Run generate and publish as jobs. The `jobs` table gets `attempts`, `run_after`, `heartbeat_at` and a `dedupe_key`, and each job kind gets its own slots. `generate_brand` reschedules itself instead of sleeping in a slot ([BUG-19](bugs-reliability.md)).
- Requeue a job on `CancelledError` and keep a heartbeat, so a stopped process puts its work back instead of leaving rows `running` (ARCH-2).
- Insert inbound messages with `ON CONFLICT (external_id)` before returning the 200, so inbound handling and dedupe are durable (ARCH-3).
- Set Railway's draining seconds (`RAILWAY_DEPLOYMENT_DRAINING_SECONDS`) so in-flight work can finish on a deploy.

### Phase B: when the triggers fire

Triggers: memory above about 70%, p95 queue wait above 30 s, or deploys that must not drop turns. Then run web and worker as separate services, take advisory locks per `business_id`, and move the photo debounce into the DB. The synthesis roadmap revisits the web and worker split in the 90-day window, only if its triggers fire.

### Phase C: optional

Move to [procrastinate](https://procrastinate.readthedocs.io/en/stable/) (psycopg3; read 2026-10-19), only if the runner outgrows about 300 lines.

## Findings

### ARCH-1: Posts, their images and the generate and publish runs live only in process memory, so every deploy or crash loses them

- **Severity**: high · **Effort**: L · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [posts/store.py:63-73](../../../backend/app/posts/store.py): `InMemoryPosts`, "until T19 moves them onto `posts`".
  - [posts/maker.py:105-106, 193-204, 198](../../../backend/app/posts/maker.py): the `_generating` and `_designs_today` guards are in memory; generation is a bare `asyncio.create_task`; `post_id = uuid4().hex[:8]`.
  - [posts/publish.py:108-113](../../../backend/app/posts/publish.py): publish is a bare `asyncio.create_task`.
  - [media/public.py:11-27](../../../backend/app/media/public.py): post JPEGs are served from an in-memory `OrderedDict`, lost on restart.
  - [main.py:28-38](../../../backend/app/main.py): the lifespan stops only the `JobRunner`; `PostMaker.join`, `PostPublisher.join` and `ChatHandler.join` are never awaited on shutdown.
  - [0001_initial.sql:168-209, 294-295](../../../backend/migrations/versions/0001_initial.sql): the `posts` table with `approved_at` and `ck_posts_approved_before_publish` is unused; `ck_jobs_kind` already allows `generate_post`, `revise_post` and `publish_post`.
  - [ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md), Consequences: "after a restart the conversation remembers a post that can no longer be approved".
  - [Railway: deployment teardown](https://docs.railway.com/deployments/deployment-teardown) (read 2026-10-19): "Once the new deployment is active, the previous deployment remains active for a configurable amount of time", then SIGTERM, then SIGKILL.
- **Problem**: Railway deploys on every push to `main` ([backend/README.md](../../../backend/README.md), Deploy). The old and new containers overlap, then the old one gets SIGTERM. Failure scenario: an Owner asks for a carousel at 18:02 and a teammate merges a PR at 18:03. The 30-90 s generation task dies with the old container, so the Owner gets no images and no `PostFailed`. If the images had already arrived, the Owner taps [Aprobar] on the new container and gets a `StaleButton`, because the post existed only in the old process. A publish that is mid-flight ends with an unknown outcome: the post may be live on Instagram, but nothing records it and the Owner is never told. [ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md) moved the history into Postgres, so the history now refers to posts that no longer exist. Nothing durably records who approved what, so [ADR 0007](../../decisions/0007-approve-every-post.md) ("nothing publishes without explicit approval") can't be proved after the fact, and the DB-level constraint `ck_posts_approved_before_publish` exists but is never exercised.
- **Recommendation**: Keep the plan: a `PostStore` Protocol with `DbPosts` on `posts` and `post_slides` with full UUIDs, renders uploaded to Storage, generate and publish as runner jobs, and `approved_at` plus `approval_source` recorded. Frame it as bringing T17, T19 and T30 ([tasks.md](../../implementation/tasks.md)) ahead of the pilot; the phases are in [Path to durable state](#path-to-durable-state). Cheap immediate mitigations: set `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` to about 120, await `PostMaker`, `PostPublisher` and `ChatHandler` `join()` with a timeout in the lifespan shutdown, and avoid deploying during Owner hours while posts live in memory.
- **Impact**: Removes the most likely pilot failure (lost or "zombie" posts after any deploy or out-of-memory restart), makes approvals auditable, and is the prerequisite for quotas (ARCH-5), the dashboard, scheduling (T30) and running more than one replica.
- **Verifier note**: The code claims check out: `InMemoryPosts` is at `store.py:63-111`, the guards are dicts, generation (`maker.py:199`) and publish (`publish.py:110`) are bare tasks, `post_id` has 8 hex characters, and `PublicImages` is an in-memory `OrderedDict`. `main.lifespan` only stops the runner and the router lifespan only closes the channel and publisher, so the maker, publisher and chat `join()` are never awaited. The Railway doc confirms overlap, SIGTERM, a draining window, then SIGKILL; community sources put the default draining at 0-3 s, so in-flight tasks die. Lowered from critical: it is a known, documented limitation ([backend/README.md](../../../backend/README.md) "One instance" lists exactly these losses, ADR 0030 Consequences handles it through `list_posts` and `unknown_post`, and T17/T19/T30 already plan the fix). A pending post lost to a deploy degrades to "regenerate it", and the Owner's photos are already persisted as Brand assets; the silent loss of an in-flight generation and an unrecorded mid-flight publish are the real harms. The auditor's side point about the 32-bit post id doubling as the Zernio idempotency key is valid (Zernio replays the original post for the same key within 24 h), but a collision is negligible at pilot volume.
- **Related**: [BUG-5](bugs-reliability.md), [BUG-14](bugs-reliability.md), [PRD-2](product.md), [OPS-1](platform-ops.md), [OPS-6](platform-ops.md), [GRW-1](growth-pricing-market.md), [SEC-12](security-privacy.md); ARCH-3 and ARCH-8 in this doc.

### ARCH-2: An interrupted `generate_brand` leaves the Business stuck in `generating_brand` forever, with no message to the Owner and no retry

- **Severity**: high · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [jobs/runner.py:81-86](../../../backend/app/jobs/runner.py): `stop()` cancels running tasks.
  - [jobs/runner.py:162-170](../../../backend/app/jobs/runner.py): `except Exception` does not catch `asyncio.CancelledError`, so the update at lines 171-183 never runs and the row stays `running`.
  - [jobs/runner.py:29, 88-109](../../../backend/app/jobs/runner.py): stale rows are failed only after 5 min, with no retries, and `fail_stale` never calls `_tell_owner`.
  - [jobs/brand.py:42-46](../../../backend/app/jobs/brand.py): `_resume` runs only on `Exception`, not on cancel or process death.
  - [conversation/brand.py:8](../../../backend/app/conversation/brand.py): `REVISABLE_STATES` excludes `generating_brand`, so `update_brand` cannot unstick it.
  - [tests/test_jobs.py:400-410](../../../backend/tests/test_jobs.py): `test_a_failed_first_brand_stays_generating`.
  - [jobs/brand.py:24, 117-137](../../../backend/app/jobs/brand.py): the job sleeps up to 60 s waiting for analyses, then runs the Strategist at high thinking, so the exposure window is 1-2 min per onboarding.
- **Problem**: The Owner submits the wizard and gets "armando tu marca" ([api/onboarding.py:350-355](../../../backend/app/api/onboarding.py)). If a deploy, restart or out-of-memory kill happens in the next 1-2 minutes, the `generate_brand` task is cancelled or killed. The row stays `running` until a stale check 5 or more minutes later marks it `failed`, with no notification and no requeue. `businesses.onboarding_state` stays `generating_brand`. The Owner never gets the Brand Brain summary or a [Reintentar] button. Their messages go to the orchestrator, whose context says `onboarding_state=generating_brand` and whose `update_brand` tool refuses with `brand_not_ready`. Someone has to fix the row by hand. `analyze_asset` and `import_instagram` jobs are lost silently in the same way.
- **Recommendation**: Cheapest first: in `fail_stale` (and at startup), for stale rows of kinds in `NOTIFY_ON_FAILURE`, send the same retry button, or requeue once automatically. Catch `asyncio.CancelledError` in `_run` and put the row back to `queued` (shielded) before re-raising. Let `stop()` drain for a timeout before cancelling, and set `RAILWAY_DEPLOYMENT_DRAINING_SECONDS`. Keep the existing first-brand test, which covers the button path, and add tests for cancel then requeue and for stale then notify. Heartbeats and attempts can come with ARCH-8.
- **Impact**: Removes the one onboarding dead end that needs manual DB surgery. Every Owner whose brand job overlaps a deploy is currently lost at the "aha" moment.
- **Verifier note**: The cancellation path is real: `JobRunner._run` catches only `Exception` (`runner.py:167`), so a `CancelledError` from `stop()` or a SIGKILL skips the status update; `fail_stale` marks the row failed only after `STALE_AFTER` (5 min), with no requeue and no `_tell_owner`; `_resume` runs only on `Exception` and only when `RESUME_STATE` was set by a revision; and `/complete` is idempotent (it returns `generating_brand`), so the Owner cannot unstick themselves. Two corrections. On the ordinary exception path a failed first brand is not a dead end: the runner sends `JOB_FAILED` with a `retry:{job_id}` button and `retry_failed` requeues it, so `test_a_failed_first_brand_stays_generating` is correct behaviour and does not encode the bug; the dead end is specific to cancellation or process death. And "critical" overstated it: the window is about 1-2 min per onboarding and only bites when a deploy lands inside it. The consequence (manual DB surgery at the "aha" moment) justifies high.
- **Related**: [BUG-4](bugs-reliability.md).

### ARCH-3: Inbound WhatsApp messages are not persisted: acknowledged with 200, then handled in a BackgroundTask, with in-memory dedupe

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [channels/router.py:109-117](../../../backend/app/channels/router.py): in-memory dedupe, then `background_tasks.add_task` and an immediate 200.
  - [channels/inbound.py:28-43](../../../backend/app/channels/inbound.py): `InMemoryDedupeStore`, "replaced by T02", although T02 is done.
  - [channels/inbound.py:16-18](../../../backend/app/channels/inbound.py): "T02 can back this with INSERT ... ON CONFLICT DO NOTHING on messages.external_id".
  - [0001_initial.sql:266-281](../../../backend/migrations/versions/0001_initial.sql): the `messages` table with `uq_messages_external_id`, never written.
  - [architecture/api.md:29](../../architecture/api.md): "not retried by Kapso (durable retry belongs to the job runner, T16)".
  - [conversation/chat.py:83-87, 241-264](../../../backend/app/conversation/chat.py): photo batches wait 5 s in memory before they are answered.
- **Problem**: Kapso stops retrying once it gets the 200. When the process dies after the 200 (a deploy, an out-of-memory kill, or a crash during the 5 s photo debounce or a 20-60 s LLM turn), the Owner's message disappears: no reply, and no record that it arrived. The dedupe set is also lost on restart, so a Kapso retry that crosses a restart is processed twice; for a `create_post` that means two paid generations. There is no inbound log either, so pilot support cannot answer "what did the Owner actually send?".
- **Recommendation**: Now: set `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` so in-flight webhook handling finishes on deploys. Next, with T19: replace `InMemoryDedupeStore` with `INSERT INTO messages ... ON CONFLICT (external_id) DO NOTHING` before the 200, add `processed_at`, and on startup replay recent unprocessed rows. That gives durable dedupe and a per-Business inbound log.
- **Impact**: No silently dropped Owner messages across deploys, no duplicate paid generations from retries, and a per-Business inbox log for support. Cost: one extra DB round trip per webhook, about 115 ms with today's topology (see ARCH-6).
- **Verifier note**: Confirmed in code: `router.py:109-117` dedupes in memory, schedules a `BackgroundTasks` handler and returns 200 at once; `InMemoryDedupeStore` still says "replaced by T02"; the `messages` table is never written. [integrations.md](../../architecture/integrations.md) confirms Kapso expects a 200 within 10 s and retries about twice. Lowered to medium for three reasons. Uvicorn's graceful shutdown waits for in-flight ASGI tasks, including `BackgroundTasks`, so a drain window already closes most of the deploy-time loss (the photo debounce timers are bare tasks and would still be lost). The double paid generation needs Kapso to retry a delivery whose 200 never arrived, which is rare. And "no record that it arrived" is partly wrong: completed Owner turns are stored in `conversation_steps` ([ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md)), though they are compacted over time and dropped turns leave no trace. Real, but a narrow window for a single-owner pilot.
- **Related**: [BUG-2](bugs-reliability.md), [BUG-5](bugs-reliability.md), [BUG-14](bugs-reliability.md), [OPS-1](platform-ops.md), [OPS-2](platform-ops.md), [OPS-6](platform-ops.md), [SEC-12](security-privacy.md); ARCH-1 and ARCH-8 in this doc.

### ARCH-4: The publish target is one global Zernio account (ADR 0024), so every pilot Owner's approved post goes to the same Instagram

- **Severity**: high · **Effort**: L · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [config.py:56-62](../../../backend/app/config.py): `ZERNIO_PROFILE_ID` and `ZERNIO_ACCOUNT_ID`, "the ids replace social_accounts until the database exists".
  - [conversation/factory.py:48-54, 72-74](../../../backend/app/conversation/factory.py): one `account_id` is passed to the `PostPublisher` for all senders.
  - [posts/publish.py:104-107](../../../backend/app/posts/publish.py).
  - [ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md), Consequences: "Every Business in the demo publishes to the same Instagram account".
  - [instagram/meta.py:15](../../../backend/app/instagram/meta.py): `SCOPES = 'instagram_business_basic'`, read only.
  - [0002_instagram_import.sql:6-9](../../../backend/migrations/versions/0002_instagram_import.sql): the unique key on `business_id`, `platform`, `provider` already allows a Meta row and a publisher row per Business.
  - [Meta: Instagram content publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing) (read 2026-10-19): Instagram Login supports publishing with `instagram_business_content_publish`, including carousels through `/media` and `/media_publish`.
- **Problem**: The product is moving to real Owners. The wizard already connects the Owner's own Instagram through our Meta app ([ADR 0028](../../decisions/0028-read-instagram-with-our-meta-app.md)), but only to read it; publishing still goes to `ZERNIO_ACCOUNT_ID`. With two pilot Owners, Owner B's "subilo" posts to Owner A's account (or the demo account). That is a trust and brand-safety incident, and it blocks roadmap Phase 1, "Run it on the pilot owner's real account every day" ([roadmap.md](../../roadmap.md)). The roadmap leaves "Zernio vs own Meta app for publishing" open until Phase 2.
- **Recommendation**: Before any second Owner, add a startup or publish-time guard that refuses to publish for any Business other than the one whose account `ZERNIO_ACCOUNT_ID` points at, so no random sandbox user can post to the pilot's account. To go multi-owner: add `instagram_business_content_publish` to the Meta scopes the wizard already requests, and implement a `MetaPublisher` behind `PublisherPort` that resolves the account from `social_accounts` per Business. Pilot Owners must be added as Instagram testers until App Review. This needs an ADR that supersedes [ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md) and amends [ADR 0008](../../decisions/0008-publishing-via-zernio.md).
- **Impact**: Unblocks a multi-owner pilot without cross-posting. If Meta publishing is chosen, it also removes a third-party dependency and its per-account pricing from the core loop.
- **Verifier note**: Confirmed: the single global `ZERNIO_ACCOUNT_ID` reaches the `PostPublisher` for every sender (`factory.py:48-74`, `publish.py:104-110`), the Meta scope is read only, migration 0002 allows a Meta row and a publisher row per Business, and Meta's Instagram Login supports publishing including carousels. But it is an explicit decision: ADR 0024 says every demo Business publishes to the same account, ADR 0028 already rejected a per-Business Zernio connect (two OAuth hops and a 2-account free tier), and roadmap Phase 1 is a pilot with one Owner, which the guard plus pointing the env id at that Owner's account covers. So high, not critical. The recommendation also has to account for Meta publishing, like the existing read scope, working only for accounts with a role on the app (Instagram testers) until App Review grants Advanced Access (ADR 0028, line 26): every pilot Owner must be an accepted tester, and scaling needs App Review plus Business Verification (roadmap Phase 2).
- **Related**: [BUG-1](bugs-reliability.md), [PRD-1](product.md), [SEC-2](security-privacy.md), [GRW-2](growth-pricing-market.md), [GAP-1](cross-cutting-gaps.md).

### ARCH-5: Usage limits live in memory, count only designs, and don't match the pricing ADR (Free = 3 posts a month)

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [posts/maker.py:186-195](../../../backend/app/posts/maker.py): a per-sender, per-day counter of `design` posts only, in a dict.
  - [config.py:44](../../../backend/app/config.py): `MAX_POSTS_PER_DAY = 5`, global.
  - [0001_initial.sql:20-21](../../../backend/migrations/versions/0001_initial.sql): `businesses.plan` (`free`) and `monthly_post_quota` (default 30, "not enforced"); neither is mapped in [db/models.py:24-46](../../../backend/app/db/models.py).
  - [ADR 0031](../../decisions/0031-pricing-free-basic-pro.md): Free is up to 3 posts or carousels a month, and "its post cap must be enforced in the backend once billing exists".
- **Problem**: Today a free Owner can generate up to 5 designed carousels a day, about 150 a month, against the 3 the pricing promises. The counter resets on every deploy, which happens on every push. "Photos"-style posts and caption remakes are not counted at all. The schema default (30 a month) contradicts ADR 0031 (3), so the plan has two sources of truth. Every Free Owner costs LLM, multi-image 2K Gemini generation and WhatsApp spend with no revenue, and no enforcement survives a restart.
- **Recommendation**: Treat it as billing preparation. Once posts are in the DB (ARCH-1), count posts per Business per month in `businesses.timezone` against a plan table in code (`free=3`), and return a `quota_reached` tool error that the orchestrator turns into an upgrade offer. Keep a per-day image-generation cap as the cost circuit breaker, persisted rather than in memory. Align or drop the `monthly_post_quota` default in the next migration.
- **Impact**: Caps the free tier's cost at the promised 3 posts (against up to about 150 today) and gives a natural upgrade moment in the chat.
- **Verifier note**: The code facts are right: only `design` posts are counted, per sender per day, in a dict that resets on deploy; 5 a day is about 150 a month; `plan` and `monthly_post_quota` are unmapped. But ADR 0031 Consequences explicitly defers the Free cap until billing exists (roadmap Phase 2), and there is no billing or Free tier in production yet; every pilot user is effectively free by design, so this is not a live pricing bug. Not counting "photos" posts and caption remakes is a reasonable cost choice, since they generate no images; it only matters for the "3 posts" promise. The schema default of 30 predates ADR 0031 and should be aligned.
- **Related**: [BUG-9](bugs-reliability.md), [COST-2](unit-economics.md), [GRW-3](growth-pricing-market.md), [SEC-4](security-privacy.md), [PRD-12](product.md).

### ARCH-6: About 8 separate DB sessions per Owner turn, each crossing Virginia to São Paulo, add an estimated 3-4 s of latency

- **Severity**: medium · **Effort**: M · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [ADR 0017](../../decisions/0017-backend-host-railway.md), line 37: Railway runs in us-east4 (Virginia) and Supabase in sa-east-1, so "every database round trip pays a cross-continent hop".
  - [db/session.py:16](../../../backend/app/db/session.py): `pool_pre_ping=True`, one extra round trip on every checkout.
  - Sessions per text turn: [conversation/onboarding.py:63](../../../backend/app/conversation/onboarding.py), [conversation/library.py:35, 76](../../../backend/app/conversation/library.py), [conversation/history.py:92, 113, 104](../../../backend/app/conversation/history.py), [conversation/context.py:62](../../../backend/app/conversation/context.py), [conversation/notes.py:63](../../../backend/app/conversation/notes.py).
  - [conversation/history.py:134-140](../../../backend/app/conversation/history.py): phone to `business_id` is cached forever; the other stores re-resolve `owner_phone` in every query.
  - [economize.cloud: us-east-1 vs sa-east-1 latency](https://www.economize.cloud/resources/aws/latency/us-east-1-vs-sa-east-1/) (read 2026-10-19): about 115 ms.
  - [Supabase: change project region](https://supabase.com/docs/guides/troubleshooting/change-project-region-eWJo5Z) (read 2026-10-19): the region is fixed; moving means a new project plus a restore.
- **Problem**: Each Owner text turn opens 8 sequential sessions with about 12 queries. Each session pays a pre-ping, BEGIN and COMMIT or ROLLBACK, for roughly 30-40 sequential round trips at about 115 ms each, or about 3.5-4.5 s spent before and after the Gemini call. This is an estimate and should be measured. The `owner_phone` to Business lookup is repeated in about 6 of the sessions: the tenant key in code is the phone string (`sender`), not `business_id`. `DbHistory` caches phone to `business_id` forever, so deleting and re-creating a pilot Business (a common reset) makes every later insert fail on a foreign key until restart, and the Owner gets `REPLY_FAILED`. The auditor also expected the 20 s holding message ("ya te digo") to fire more often than it needs to.
- **Recommendation**: Measure first: log `db_ms`, `llm_ms` and `send_ms` per turn. Then resolve a `TurnContext` (`business_id`, timezone, state) once in `OnboardingGate` and load the turn's read model in one session with a few queries. Key the stores by `business_id`, and drop the forever cache or invalidate it on a foreign-key error. Consider co-locating Supabase in us-east-1 while the data is small.
- **Impact**: Roughly 3-4 s less per WhatsApp reply (an estimate). That addresses the "slow to understand" complaint behind [ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md) and its trade-off that Owner turns take somewhat longer at medium thinking. Fewer pooled connections are held, too.
- **Verifier note**: The session count is accurate: a text turn opens 8 sessions (the `OnboardingGate` select-for-update, `library.photos`, `library.logo`, `history.get`, `contexts.load`, `notes.list`, `history.summary`, `history.extend`) with about 12-14 queries, and each checkout adds a ping. The pooler is in sa-east-1 and Railway in us-east4. At about 115 ms, 30-40 sequential round trips is plausibly 3-4.5 s, but unmeasured. The `DbHistory` cache bug is real but reachable only when a Business row is deleted and recreated, mostly in dev resets. Lowered to medium because the gain is an estimate, Gemini medium-thinking turns dominate latency, and the claim about "ya te digo" firing more often is speculative. On co-location: the backend and Gemini already process data in the US, so moving Supabase to us-east-1 adds little new residency exposure; still verify.
- **Related**: [BUG-20](bugs-reliability.md), [AIQ-9](ai-quality.md), [MOD-13](models.md), [OPS-10](platform-ops.md).

### ARCH-7: No single composition root: `@cache` singletons, two lifespans and import cycles, so jobs can't reach the orchestrator (the ADR 0026 gap)

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - Import cycles: [posts/maker.py:18-19](../../../backend/app/posts/maker.py) and [posts/publish.py:10-11](../../../backend/app/posts/publish.py) import `app.conversation.*`, while [conversation/chat.py:27-29](../../../backend/app/conversation/chat.py) imports `app.posts.*`; [jobs/brand.py:13-14](../../../backend/app/jobs/brand.py) imports `app.conversation.brand` and `history`, while [conversation/library.py:10](../../../backend/app/conversation/library.py) and [conversation/context.py:14](../../../backend/app/conversation/context.py) import `app.jobs.brand`.
  - [channels/router.py:11, 23-35](../../../backend/app/channels/router.py): the channel adapter module imports `conversation.factory` and owns the `@cache` singletons for the channel, the dedupe store and the handler.
  - [api/onboarding.py:20](../../../backend/app/api/onboarding.py) and [main.py:12](../../../backend/app/main.py): `get_channel` is imported from `channels.router`.
  - [main.py:28-38](../../../backend/app/main.py) and [channels/router.py:38-49](../../../backend/app/channels/router.py): two lifespans; the storage and Instagram `httpx` clients are never closed.
  - [jobs/setup.py:40](../../../backend/app/jobs/setup.py): a second `GeminiChat` for the runner; [jobs/runner.py:189-201](../../../backend/app/jobs/runner.py): job failures send fixed text, bypassing `ChatHandler.notify`.
  - [jobs/brand.py:84-86](../../../backend/app/jobs/brand.py): the brand summary is sent directly, and a note is written to `conversation_steps` outside the history lock.
  - [ADR 0026](../../decisions/0026-owner-messages-from-the-orchestrator.md), Decision: "job_failed ... until T19 gives jobs the chat handler".
- **Problem**: The wiring is split across [conversation/factory.py](../../../backend/app/conversation/factory.py), [jobs/setup.py](../../../backend/app/jobs/setup.py) and nine `@cache` getters, so the job runner is built without the `ChatHandler`. That is why job outcomes still bypass the orchestrator (the double-question bug ADR 0026 was written to fix), and why moving post generation onto the runner (ARCH-1) has nowhere clean to plug `notify` in. The cycles (conversation and posts, conversation and jobs, channels to conversation) mean `posts/` can't be tested or reused without the conversation package, and they make the coming T19 refactor riskier.
- **Recommendation**: Do it as the first step of T19. Add a single container built in `main.lifespan` and stored on `app.state`, give `JobContext` a `notify`, and turn job outcomes into events (`JobFailed`, `BrandSummaryReady`). Move shared types (events, `Photo`, `Approval`) and the brand repository helpers out of `conversation/`. An import-linter contract in CI is optional.
- **Impact**: Lets ADR 0026 finish and ARCH-1 land cleanly, and turns hidden global state into explicit wiring, so tests stop needing `dependency_overrides` tricks.
- **Verifier note**: Facts are accurate, with one correction: the import cycles are package-level layering cycles, not module-level ones. `app/conversation/__init__.py` is empty and no module imports a module that imports it back, so there is no runtime `ImportError` (examples: `posts.maker` to `conversation.events` and `photos`, `conversation.chat` to `posts.*`, `conversation.approval` to `posts.store`, `conversation.library` and `context` to `jobs.brand` to `conversation.brand` and `history`). There are about nine `@cache`/`lru_cache` getters, two lifespans merged by FastAPI, unclosed storage and Instagram clients, and the runner's own `GeminiChat` sending fixed `JOB_FAILED` and brand summary text. ADR 0026 itself defers the gap until T19, so it is planned, not hidden. Real debt that makes T19 and ARCH-1 harder, with no direct pilot impact: medium, not high.
- **Related**: ARCH-14 in this doc.

### ARCH-8: A durable-queue path for the job runner: per-kind slots, `run_after`, retries, heartbeats and periodic jobs, plus when to split web and worker

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [jobs/runner.py:26, 111-135](../../../backend/app/jobs/runner.py): one pool of 4 slots shared by every kind; claims have no `run_after` or priority.
  - [jobs/brand.py:117-137](../../../backend/app/jobs/brand.py): `generate_brand` sleeps in a slot for up to 60 s waiting for `analyze_asset` jobs that need slots.
  - [jobs/instagram.py:121](../../../backend/app/jobs/instagram.py): the import queues up to 24 `analyze_asset` jobs at its end, after `generate_brand` may already be queued.
  - [0001_initial.sql:283-299](../../../backend/migrations/versions/0001_initial.sql): `jobs` has no attempts, `run_after`, heartbeat or dedupe key.
  - [tasks.md:265](../../implementation/tasks.md): "the runner has no schedule yet", for the weekly Niche Report ([ADR 0025](../../decisions/0025-weekly-niche-report.md)).
  - [architecture/overview.md:190](../../architecture/overview.md): the production path is arq or procrastinate.
  - [procrastinate docs](https://procrastinate.readthedocs.io/en/stable/) (read 2026-10-19): retries, periodic tasks, queueing locks and stalled-job retry; the examples use Psycopg connectors.
- **Problem**: The `SKIP LOCKED` design is sound, but it lacks what pilot scale needs. Priority inversion: two Owners finishing the wizard together hold 2 of the 4 slots with `generate_brand` jobs that sleep, while up to about 78 analyses (15 uploads plus 24 Instagram imports each) share the remaining slots. At an estimated 7 s per analysis that takes well over the 60 s wait, so brands get written without photo analyses. Nothing exists for retries with backoff, delayed or scheduled jobs (T30 scheduling, Monday plans, the weekly Niche Report) or dedupe (one active `generate_brand` per Business).
- **Recommendation**: Phase A, when scheduling or the weekly report lands, or together with ARCH-2: add `attempts`, `max_attempts`, `run_after`, `heartbeat_at` and a `dedupe_key` with a partial unique index; claim by `run_after`; retry with backoff; make `generate_brand` reschedule itself instead of sleeping in a slot; use self-re-enqueuing periodic jobs. Keep Phase B (a web and worker split with advisory locks) behind the metric triggers in [Path to durable state](#path-to-durable-state).
- **Impact**: Brands keep their photo analyses under concurrency, scheduling and weekly jobs need no new infrastructure, and there is a clear, metric-triggered path to more than one replica without Redis.
- **Verifier note**: Accurate design facts: one pool of 4 slots, FIFO claims with no `run_after`, priority or attempts, no retry or heartbeat columns, `generate_brand` polling inside a slot, and `tasks.md:265` confirming the Niche Report needs a schedule. The priority-inversion scenario is overstated for the pilot. It needs two Owners finishing the wizard at the same time, and with the Instagram-first wizard ([ADR 0032](../../decisions/0032-instagram-first-onboarding.md)) `import_instagram` is queued at connect and wizard uploads queue analyses as they complete, so for one Owner most analyses are queued (FIFO) or done before `generate_brand` at `/complete`. The 7 s per analysis is unverified. The retry, heartbeat, `run_after` and periodic parts overlap ARCH-2 and are needed for planned features (T30, weekly reports), so the work is worth doing, but high was inflated for current scale.
- **Related**: [BUG-5](bugs-reliability.md), [BUG-14](bugs-reliability.md), [BUG-19](bugs-reliability.md), [OPS-1](platform-ops.md), [OPS-6](platform-ops.md), [SEC-12](security-privacy.md); ARCH-1 and ARCH-3 in this doc.

### ARCH-9: Config falls back to mocks in production: a missing env var makes the bot tell an Owner a post is live, with a MOCK permalink

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [config.py:11](../../../backend/app/config.py): `env: Literal["local", "prod"]` is never read anywhere in `app/`.
  - [config.py:26, 34, 58, 65](../../../backend/app/config.py): `IMAGE_GEN`, `RENDERER`, `PUBLISHER` and `INSTAGRAM` all default to `mock`.
  - [publishing/mock.py:9, 36-42](../../../backend/app/publishing/mock.py): `MockPublisher` returns `status='published'` with an `instagram.com/p/MOCK-...` permalink.
  - [conversation/factory.py:51-54](../../../backend/app/conversation/factory.py): `PUBLISHER=zernio` without `ZERNIO_ACCOUNT_ID` only logs a warning.
  - [conversation/factory.py:55-58, 100-101](../../../backend/app/conversation/factory.py): without `DATABASE_URL` the app silently runs with in-memory history and no `OnboardingGate`.
  - [main.py:58-60](../../../backend/app/main.py): `/health` always returns ok, even with the job runner off or the DB unreachable; [architecture/api.md:22](../../architecture/api.md) documents a different shape.
- **Problem**: Railway variables are set by hand ([backend/README.md](../../../backend/README.md): "settings live in the service, not in the repo"). If `PUBLISHER` is unset or renamed in production, an Owner who taps [Publicar ahora] gets an orchestrator message announcing the post as published, with a MOCK link, and nothing reaches Instagram. Missing image or renderer variables send placeholder images to a real Owner. A missing `DATABASE_URL` drops onboarding entirely. The Railway healthcheck gates deploys on `/health`, which passes in all of these states.
- **Recommendation**: Add a `Settings` `model_validator`: when `env == 'prod'`, reject mock adapters and require `DATABASE_URL`, `SUPABASE_*`, `GEMINI_API_KEY`, `KAPSO_*`, `PUBLIC_BACKEND_URL`, `RENDERER_URL`/`RENDERER_SECRET` and the publish target. Add a `/ready` endpoint (DB ping, runner started) and point the Railway healthcheck at it. Fix [backend/README.md](../../../backend/README.md) line 82 to list the explicit production values. Delete `zernio_profile_id`.
- **Impact**: Prevents the worst trust failure, telling an Owner a post is live when it isn't, and turns configuration mistakes into failed deploys instead of silent production behaviour.
- **Verifier note**: Confirmed: `Settings.env` is never read in `app/`, although [backend/README.md](../../../backend/README.md) line 73 says `ENV=prod` is already set in production; the four adapters default to `mock`; `chat.py` appends the mock permalink to the Owner message; without `DATABASE_URL` the gate is silently dropped; `/health` always returns `{status: 'ok'}`. Reaching the failure needs a production misconfiguration, and Railway service variables persist across deploys, so it happens mainly when an environment is recreated or a variable is renamed: medium is more honest than high. Two things raise its value: the fix is a few lines because `ENV=prod` already exists, and README line 82 ("carries the same value as local", while `.env.example` has `mock`) is itself an ambiguity that could put mocks in production. `PUBLISHER=zernio` without an account id fails safe (`need_ig`).
- **Related**: [OPS-5](platform-ops.md).

### ARCH-10: Global settings that should be per Business: one Niche Report's trend notes go to every Business, and the timezone is hard-coded

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [config.py:46-48](../../../backend/app/config.py): `NICHE_REPORT_PATH`, one file for the whole process.
  - [conversation/factory.py:59, 61, 96](../../../backend/app/conversation/factory.py): the same `trend_notes` go to `PostDrafter` and `ChatHandler` for every sender.
  - [conversation/context.py:111-112](../../../backend/app/conversation/context.py): rendered as `<trend_notes>` into every Business's system prompt.
  - [conversation/photos.py:8-9](../../../backend/app/conversation/photos.py): `LOCAL_TZ` hard-coded "until T02", while [db/models.py:37](../../../backend/app/db/models.py) and [0001_initial.sql:15](../../../backend/migrations/versions/0001_initial.sql) already store `businesses.timezone`.
  - [ADR 0025](../../decisions/0025-weekly-niche-report.md) and [tasks.md:265](../../implementation/tasks.md): `niche_reports` per Business planned for T19.
- **Problem**: The Niche Report is researched for one niche, solid-wood furniture ([open-questions.md:42](../../open-questions.md)). With `NICHE_REPORT_PATH` set, a second pilot Owner with a bakery or a clothing store gets furniture trends in both the orchestrator prompt and the post drafter, which degrades the copy for everyone outside that niche. The `<now>` block and post timestamps ignore `businesses.timezone`: harmless while every Owner is in Uruguay, wrong as soon as the LatAm expansion adds Mexico, Colombia or Chile.
- **Recommendation**: When T19 or the weekly job lands, store `niche_reports` per niche, select by business category, and send none when nothing matches, as ADR 0025 already plans. Replace `LOCAL_TZ` with `ZoneInfo(business.timezone)` in the same refactor. No action is needed before the pilot.
- **Impact**: Stops cross-niche contamination of every non-furniture pilot Owner's posts and removes a hidden blocker for the regional expansion.
- **Verifier note**: The code facts are true, but the contamination is not reachable in production today: `backend/out/` is in both [.gitignore](../../../.gitignore) and [backend/.dockerignore](../../../backend/.dockerignore), no report file is committed, and Railway builds from GitHub, so the image can't contain the file; `load_trend_notes` reads it at boot and would crash on a missing path, so trend notes are effectively off in production. Per-Business `niche_reports` are already planned (ADR 0025, `tasks.md:265`), and the prompts already say to use trend notes only "when they fit". The timezone part is, as the finding admits, harmless while the market is Uruguay.

### ARCH-11: Process memory grows without bound: brand-photo bytes are cached forever per Business, so a 1 GB instance could run out of memory at a few dozen active Owners

- **Severity**: low · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [conversation/library.py:31-32, 99-108](../../../backend/app/conversation/library.py): the `_images` and `_logos` dicts, never evicted, filled by every turn's `_refresh_library`.
  - [conversation/photos.py:54-55](../../../backend/app/conversation/photos.py): per-sender library and logo entries.
  - [posts/store.py:8, 63-84](../../../backend/app/posts/store.py): up to 10 posts per sender, each holding its JPEGs and source photos; no bound on senders.
  - [media/public.py:8](../../../backend/app/media/public.py): 200 JPEGs, "about 40 MB".
  - [media/images.py:11](../../../backend/app/media/images.py): references up to 1536 px, JPEG quality 90.
  - [ADR 0017](../../decisions/0017-backend-host-railway.md): Trial 1 GB RAM; Free 0.5 GB.
- **Problem**: Each Business's wizard photos (up to 15), Instagram imports (up to 24) and every chat photo it ever sent (kept as Brand assets under [ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md)) are downloaded and kept as bytes for the life of the process: roughly 12 MB per Business at onboarding, growing forever. Add up to 10 in-memory posts with their slides (roughly 20 MB) and the global 40 MB image cache. Estimate: about 20-30 MB per active Business, so about 30-40 active Owners exhaust 1 GB. An out-of-memory restart then triggers every loss in ARCH-1, ARCH-2 and ARCH-3.
- **Recommendation**: Bound the library cache with a byte-budget LRU or download on demand (the orchestrator only needs the descriptions), cap `<brand_photos>` to the newest or most relevant N, and drop `PublicImages` once renders move to Storage (ARCH-1).
- **Impact**: Pushes the out-of-memory ceiling from tens to hundreds of active Owners on the same instance, and keeps the prompt size flat as Owners send more photos.
- **Verifier note**: Real unbounded growth: `BrandLibrary._images` and `_logos` are never evicted, `InMemoryPosts` keeps up to 10 posts per sender with no bound on senders, and `PublicImages` holds 200 JPEGs. Correction: `InMemoryPhotos.set_library` stores references to the same bytes objects, not copies, so the per-Business estimate is somewhat high. At pilot scale (one to a few Owners) this is tens of MB, far below 1 GB, and ADR 0017 already says to move to Hobby (RAM up to 48 GB, billed per use) when memory runs out. A scaling concern, not a pilot risk. The growth of the `<brand_photos>` prompt block is a valid side point.
- **Related**: [BUG-12](bugs-reliability.md), [OPS-15](platform-ops.md), [COST-17](unit-economics.md), [AIQ-19](ai-quality.md).

### ARCH-12: Post generation has no overall deadline, and one transient render error throws away already-paid AI images

- **Severity**: medium · **Effort**: S · **Confidence**: medium · **Verified**: confirmed
- **Evidence**:
  - [imagegen/gemini.py:16, 20](../../../backend/app/imagegen/gemini.py): 120 s per attempt, 4 attempts with backoff, no wall-clock cap.
  - [carousel/generator.py:137-151](../../../backend/app/carousel/generator.py): a blocked or no-image result retries the whole call once more.
  - [carousel/generator.py:56-63](../../../backend/app/carousel/generator.py): the cover runs first, then the rest in parallel.
  - [posts/maker.py:225, 178-179, 249](../../../backend/app/posts/maker.py): no `asyncio.timeout` around `_render`, and the per-sender `_generating` guard is held until it ends.
  - [rendering/takumi.py:31-42](../../../backend/app/rendering/takumi.py) and [rendering/slides.py:40](../../../backend/app/rendering/slides.py): no retry, so one Vercel 5xx or cold-start timeout fails the post after N paid image generations.
  - [llm/client.py:224-243](../../../backend/app/llm/client.py): by contrast, the text client has a deliberate wall-clock deadline.
- **Problem**: In the worst case a design post can run for many minutes: up to 4 × 120 s plus a blocked-content retry, for the cover and then for the slides. During that time the Owner gets one "ya te digo", and every new request is refused with `generation_in_progress`. When generation succeeds but one Takumi render call fails transiently, the whole post fails: the 2K or 4K Gemini images already paid for are discarded, and a retry pays for them again.
- **Recommendation**: Wrap `PostMaker._render` in `asyncio.timeout(POST_DEADLINE_S)` (for example 240 s) and emit `PostFailed` with a `timeout` reason on expiry. Pass a remaining-time budget to the image adapter, or lower attempts to 2 for interactive posts. Retry the renderer once with jittered backoff on a 5xx or timeout. Persist the generated scenes (Storage, plus `post_slides.prompt` and usage) before rendering, so a render retry or a later "cambiá el título" re-renders without regenerating; the existing `CarouselGenerator.redo` already supports this shape.
- **Impact**: A bounded wait for the Owner, and no double payment for images on transient render failures.
- **Verifier note**: Verified: 120 s per attempt with `HttpRetryOptions(attempts=4)`, one more try on blocked or no-image results, the cover before the parallel slides, no overall timeout in `PostMaker._render` with the guard held until it ends, and no retry in `TakumiRenderer.render`, while `GeminiChat._create` does use `asyncio.wait_for` as a wall-clock deadline. Nuance: google-genai retries only 408, 429 and 5xx responses, so the 4 × 120 s worst case is theoretical, but no overall deadline exists.
- **Related**: [BUG-13](bugs-reliability.md), [FE-10](frontend.md).

### ARCH-13: `agent_runs` is never written and image usage is thrown away, so there is no per-Business cost to validate the US$29 price

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [llm/client.py:245-255](../../../backend/app/llm/client.py): tokens are only logged to stdout, and cached tokens are not logged.
  - [imagegen/gemini.py:121, 132-149](../../../backend/app/imagegen/gemini.py): `usage_counts` is computed.
  - [carousel/generator.py:20-30, 181-191](../../../backend/app/carousel/generator.py): usage is kept on `GeneratedSlide`, logged only when a carousel fails, never persisted.
  - [0001_initial.sql:301-319](../../../backend/migrations/versions/0001_initial.sql): `agent_runs` with `business_id`, `job_id`, tokens, `cache_read_tokens` and latency.
  - [architecture/overview.md:105](../../architecture/overview.md): "Every LLM call writes an agent_runs row".
  - [roadmap.md](../../roadmap.md), Pricing: "To validate: WhatsApp and LLM costs per active business must fit well under the Basic price".
- **Problem**: The pilot is supposed to validate unit economics ([ADR 0031](../../decisions/0031-pricing-free-basic-pro.md)), but no per-Business, per-agent record of LLM or image spend exists, and token counts live only in Railway logs, which rotate. Questions like "is implicit caching hitting on the orchestrator prefix?" or "what does a Free Owner cost a month?" can't be answered, and the Free cap (ARCH-5) can't be calibrated.
- **Recommendation**: Set a contextvar (`business_id`, `job_id`, agent) at the `ChatHandler` turn and `JobRunner._run` boundaries. In `GeminiChat._create` and `GeminiImageGen.generate`, push a record (agent, model, effort, input, output, thought and cached tokens, image count and size, latency, error) onto an in-process `asyncio.Queue`. A background writer batch-inserts into `agent_runs` every few seconds, so the turn pays no DB latency. Leave the input and output `jsonb` columns null by default to avoid storing Owner photos, with a DEBUG flag to store them. Add a SQL view of cost per Business per month using a price table in code.
- **Impact**: Real cost per Owner and per post during the pilot, a cache-hit rate to tune prompts, and the data to set the Free and Basic caps.
- **Verifier note**: Verified: nothing in `app/` writes `agent_runs` (no model is mapped and no insert exists), although `overview.md:105` claims it; `GeminiChat` logs input, output and thought tokens but not cached tokens; image `usage_counts` are only logged on failure. At one pilot Owner the Gemini billing console roughly equals per-Owner cost, which softens the urgency, but per-agent and per-post cost and the cache-hit rate still need this.
- **Related**: [COST-1](unit-economics.md), [MOD-3](models.md), [OPS-9](platform-ops.md), [DOC-7](docs-process.md), [AIQ-6](ai-quality.md).

### ARCH-14: `chat.py` (702 lines) is a god class, and the posts layer is typed on concrete in-memory stores

- **Severity**: low · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [conversation/chat.py:89-580](../../../backend/app/conversation/chat.py): `ChatHandler` does photo debounce, keep-alive and typing, the LLM tool loop, tool dispatch, approval offer tracking, context assembly, fallbacks and compaction scheduling.
  - [conversation/chat.py:276-309 and 334-386](../../../backend/app/conversation/chat.py): `_llm_turn` and `_event_turn` duplicate the refresh-library, recent/unseen, `step_with_photos`, keep-alive, converse, mark-seen, remember and offer sequence.
  - [conversation/chat.py:566-574](../../../backend/app/conversation/chat.py): `_update_brand` reaches through `self._buttons.brand`.
  - [conversation/chat.py:102, 105](../../../backend/app/conversation/chat.py), [posts/maker.py:85-87](../../../backend/app/posts/maker.py), [posts/publish.py:52](../../../backend/app/posts/publish.py) and [conversation/button_router.py:48](../../../backend/app/conversation/button_router.py): `InMemoryPhotos` and `InMemoryPosts` as concrete parameter types.
  - [conversation/history.py:32-47](../../../backend/app/conversation/history.py): the good precedent, a `History` Protocol with in-memory and DB implementations.
  - [tests/test_chat_handler.py](../../../backend/tests/test_chat_handler.py): 1038 lines, 55 tests against the whole class.
- **Problem**: Every change to the conversation goes through one 700-line class. ARCH-1 has to swap `InMemoryPosts` and `InMemoryPhotos` for DB stores, but four classes name the concrete in-memory types, so that swap touches every signature and test fake at once. The auditor also read the two turn paths as having drifted (one attaches photos and keep-alive conditionally, the other always); the reviewer showed that difference is deliberate (see the verifier note).
- **Recommendation**: As the first step of T19, add `PostStore` and `PhotoStore` Protocols and type the consumers on them, which is cheap and makes ARCH-1 a store swap. Split photo batching and tool dispatch out of `ChatHandler` only if T19 touches them. Keep `test_chat_handler.py` as the safety net.
- **Impact**: Makes ARCH-1 a store swap instead of a rewrite, removes the duplication between the two turn paths, and gives smaller units to test.
- **Verifier note**: Sizes are accurate (702 lines; 1038 test lines with 55 tests), and the concrete `InMemoryPhotos` and `InMemoryPosts` types appear in `ChatHandler`, `PostMaker`, `PostPublisher` and `ButtonRouter`, while `History` has a Protocol. But the "two turn paths have already drifted" claim is wrong: `_event_turn` attaches photos and keep-alive only for `PhotosReceived` by design, and its docstring explains why (other events have no Owner words and must not mark photos seen). Ordinary refactoring debt that becomes relevant with T19.
- **Related**: ARCH-7 in this doc.

### ARCH-15: Architecture docs contradict the code, including `how-it-works.md`, dated the day of the audit

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [how-it-works.md:167, 171](../../architecture/how-it-works.md): "the conversation and the posts live in memory" and "Conversation history (InMemoryHistory)", contradicted by [conversation/factory.py:56-58](../../../backend/app/conversation/factory.py) (`DbHistory` and `DbNotes`, [ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md)).
  - [how-it-works.md:105](../../architecture/how-it-works.md): "the two tools", while [conversation/tools.py](../../../backend/app/conversation/tools.py) declares 7 (`create_post`, `approve_post`, `revise_post`, `list_posts`, `remember`, `forget`, `update_brand`).
  - [overview.md:102](../../architecture/overview.md): "The orchestrator's tools *enqueue* jobs", while [posts/maker.py:199](../../../backend/app/posts/maker.py) and [posts/publish.py:110](../../../backend/app/posts/publish.py) use bare `asyncio` tasks.
  - [overview.md:104](../../architecture/overview.md): a lock "per business ID", while [conversation/history.py:58, 88](../../../backend/app/conversation/history.py) locks per phone.
  - [overview.md:105](../../architecture/overview.md): `agent_runs` logging, which is not implemented (ARCH-13).
  - [overview.md:225, 236, 242](../../architecture/overview.md): the layout lists `api/webhooks_whatsapp.py`, `dashboard.py`, `uploads.py`, `transcription/`, `db/repositories.py` and `seed.py`, which don't exist, and omits `posts/`, `rendering/`, `instagram/` and `onboarding/`.
  - [api.md:22](../../architecture/api.md): `/health` returns `{ok, version}`, while the code returns `{status: 'ok'}`; [api.md:31-35](../../architecture/api.md): a Zernio webhook that is not built.
- **Problem**: `how-it-works.md` says it "describes the code on main", and it is what new contributors and agents read first. It tells them history is lost on deploy and that there are two tools, both false since ADR 0030. That leads to wrong fixes, for example re-implementing persistence or missing the notes tools. `overview.md` presents planned design as present, which hides real gaps such as `agent_runs` and jobs for posts.
- **Recommendation**: Update `how-it-works.md` (the "What survives a restart" table, the tool list, the lock key) in the same PR as the next backend change. In `overview.md`, mark planned items explicitly ("planned: T19") and add the real packages. Fix the `/health` shape in `api.md` together with ARCH-9's `/ready`. Add a cheap CI guard: a pytest that asserts the tool names in `tools.TOOLS` appear in `docs/architecture/how-it-works.md`, so the most-read doc can't silently drift again.
- **Impact**: Contributors and AI agents work from accurate docs, which lowers the risk of regressions during the T19 refactor.
- **Verifier note**: Verified: `how-it-works.md` opens with "As of 2026-10-19. This describes the code on main" and was added on the audit date (#62); line 105 says two tools while `tools.py` declares 7; the "What survives a restart" table lists conversation history as `InMemoryHistory` and WhatsApp photos as memory-only, both wrong with `DATABASE_URL` set (`DbHistory`/`DbNotes`, and `PhotoKeeper` stores chat photos as Brand assets). The `overview.md` and `api.md` mismatches are as listed.
- **Related**: [DOC-17](docs-process.md), [DOC-10](docs-process.md).

### ARCH-16: RLS is disabled on 18 of 19 public tables, including `conversation_steps`, `owner_notes` and `magic_links`

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [ADR 0003](../../decisions/0003-database-supabase-sqlalchemy.md), lines 13 and 19: "RLS off for the demo"; "turn RLS on first".
  - [0002_instagram_import.sql:11-13](../../../backend/migrations/versions/0002_instagram_import.sql): RLS is enabled only on `social_accounts`.
  - [0001_initial.sql](../../../backend/migrations/versions/0001_initial.sql): no `enable row level security` for any other table; [0003_conversation_memory.sql:4-23](../../../backend/migrations/versions/0003_conversation_memory.sql): `conversation_steps` and `owner_notes` without RLS.
  - [Supabase: row level security](https://supabase.com/docs/guides/database/postgres/row-level-security) (read 2026-10-19): "A table in an exposed schema without RLS is readable and writable by any role with a grant on it".
- **Problem**: Supabase exposes the `public` schema through its Data API. Today the only defence is that nobody ever holds or leaks the project's publishable (anon) key. If it leaks, or someone later adds supabase-js to the frontend, every Owner's conversation history, notes, Brand Brain and job payloads are readable and writable. Migration 0002 already shows that enabling RLS without policies costs the backend nothing, because it connects as the table owner.
- **Recommendation**: In the next migration, enable RLS on every public table and revoke the `anon` and `authenticated` grants, mirroring 0002. Optionally add a CI check on `pg_class.relrowsecurity`. Do it at the latest before any client talks to Supabase directly.
- **Impact**: Closes a whole-database exposure path for the cost of one migration; required before any frontend talks to Supabase directly.
- **Verifier note**: Facts are correct (19 tables, RLS only on `social_accounts`), but this is a deliberate decision: ADR 0003 makes the backend the only database client (service role key, RLS off for the demo) and says to turn RLS on first if a client ever talks to the DB. The frontend doesn't use Supabase at all (no supabase-js and no anon key in [frontend/.env.example](../../../frontend/.env.example)), and the backend's service role key bypasses RLS anyway. Supabase's doc says default anon grants on new public tables vary by project, so exposure is not certain; the only path is someone obtaining the unused anon key. Cheap, real defence in depth, but low severity in this dimension. (The security dimension's [SEC-1](security-privacy.md) confirmed the anon grants with the live advisor and rates the merged item high.)
- **Related**: [SEC-1](security-privacy.md).

### ARCH-17: The schema has two sources of truth and nothing checks them against each other

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [db/models.py:1-5](../../../backend/app/db/models.py): models are written by hand "when a task starts writing" a table; 10 of 19 tables are mapped.
  - [migrations/env.py:16](../../../backend/migrations/env.py): `target_metadata=None`, so no autogenerate or compare.
  - [0001_initial.py:44-46](../../../backend/migrations/versions/0001_initial.py): raw SQL split on the regex `;\s*$`, which breaks on a DO block or a function body.
  - [0001_initial.sql:20-21](../../../backend/migrations/versions/0001_initial.sql) against [db/models.py:24-46](../../../backend/app/db/models.py): `plan` and `monthly_post_quota` are not mapped.
- **Problem**: A typo or missing column in `models.py` surfaces only at runtime, on the code path that touches it. T19 is about to map 5-6 more tables (`posts`, `post_slides`, `post_revisions`, `messages`, `agent_runs`), which multiplies the drift risk. The regex splitter will mis-split the first PL/pgSQL function or DO block, for example a future `updated_at` trigger.
- **Recommendation**: Add one DB test (it runs in CI with `TEST_DATABASE_URL`) that compares `Base.metadata` columns, types and nullability with `information_schema.columns` for each mapped table after applying the migrations, using `alembic.autogenerate.compare_metadata` against the migrated DB. For new migrations, use `op.execute` per statement in the `.py` file, or pass whole files to `connection.exec_driver_sql` with asyncpg's simple-query protocol, instead of the regex.
- **Impact**: Catches model and schema drift in CI before the large T19 mapping work.
- **Verifier note**: Verified: `target_metadata=None`, 10 of 19 tables mapped, `businesses.plan` and `monthly_post_quota` unmapped, and all three migration `.py` files split SQL with `re.split(r';\s*$', MULTILINE)`, which would mis-split a DO block or a plpgsql function body.
- **Related**: [OPS-7](platform-ops.md).

### ARCH-18: `api/onboarding.py` (578 lines) mixes routes, business rules, Owner-facing copy and storage I/O, and holds row locks across HTTP calls

- **Severity**: low · **Effort**: S · **Confidence**: medium · **Verified**: confirmed
- **Evidence**:
  - [api/onboarding.py:49-64](../../../backend/app/api/onboarding.py): Rioplatense Owner-facing strings inside the API module, outside [copy/messages_es.py](../../../backend/app/copy/messages_es.py).
  - [api/onboarding.py:269-288](../../../backend/app/api/onboarding.py): the Business row `FOR UPDATE` is held across `storage.create_signed_upload_url`, a cross-continent HTTP call, so 15 parallel photo tickets serialize behind it.
  - [api/onboarding.py:404-406, 359-392](../../../backend/app/api/onboarding.py): the asset row is locked across a download, Pillow processing and 2 uploads.
  - [api/onboarding.py:463-541](../../../backend/app/api/onboarding.py): `_state` re-runs 4 queries and re-signs every asset URL after every PUT.
- **Problem**: Every wizard save re-signs all asset URLs and re-reads everything. Uploading many photos serializes on a lock held during Supabase HTTP calls. The wizard's copy is split across two places, so tone changes miss half of it. The module is hard to extend for the planned dashboard (`/api/b/{token}`), which reuses uploads.
- **Recommendation**: Move `_state`, `_finish_upload`, `_check_complete` and `_photos_holding_a_slot` into `app/onboarding/service.py` and keep the routes thin, so the dashboard reuses them. Move the strings into `messages_es` (or a `copy/web_es.py`). In `request_upload`, compute the slot count under the lock, insert the `uploading` row, commit, and only then call Storage for the signed URL (deleting the row if signing fails). Return only the changed slice from PUTs, or cache signed URLs for their TTL.
- **Impact**: A faster wizard with parallel uploads, one copy deck, and reusable onboarding services for the dashboard.
- **Verifier note**: Verified: the strings, the `FOR UPDATE` held across the signed-upload call before committing, and the asset lock across download, Pillow work and uploads (per asset, so contention is minimal). One correction: `_state` signs URLs in one batched `create_signed_urls` call, not one call per asset. Low impact for the wizard.

### ARCH-19: Dead settings and stale "until T02/T23" shims

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [config.py:11, 61, 56-57](../../../backend/app/config.py): `env` is unused, `zernio_profile_id` is unused, and the comment says "until the database exists" although the DB exists.
  - [conversation/photos.py:8, 37](../../../backend/app/conversation/photos.py): "Until T02", although T02 is done and `businesses.timezone` exists.
  - [copy/messages_es.py:23-24](../../../backend/app/copy/messages_es.py): "until T02 a photo is only kept for 30 minutes", although [ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md) keeps chat photos as Brand assets.
  - [channels/inbound.py:29, 47](../../../backend/app/channels/inbound.py): "replaced by T02" and "Placeholder until the conversation router (T23)".
  - [imagegen/factory.py:20-21](../../../backend/app/imagegen/factory.py) and [channels/factory.py:19-20](../../../backend/app/channels/factory.py): `Literal` options `openai` and `simulator` that raise `NotImplementedError` at boot.
- **Problem**: Comments that describe a state of the system that no longer exists mislead readers and coding agents, the same problem as ARCH-15 at code level. Settings that accept values that only crash (`IMAGE_GEN=openai`, `WHATSAPP_CHANNEL=simulator`) are traps in the Railway dashboard.
- **Recommendation**: Remove `env` (or use it for ARCH-9) and `zernio_profile_id`. Drop the `openai` and `simulator` `Literal` values until T43 and T21 exist, so pydantic rejects them at load. Rewrite the stale comments to reference current tickets with `TODO(T19)`, per the team's comment rule, or delete them.
- **Impact**: A small cleanup with fewer misleading signals, done alongside the T19 refactor.
- **Verifier note**: Verified: `Settings.env` is unused in `app/`, `zernio_profile_id` is referenced only in `config.py`, the config, photos, `messages_es` and inbound comments are stale, and `IMAGE_GEN=openai` and `WHATSAPP_CHANNEL=simulator` pass validation, then raise `NotImplementedError` when the handler is built at boot.
