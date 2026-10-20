# Docs, decisions and engineering process

This doc covers the docs and process dimension of the 2026-10-19 product and codebase audit of Neitor AI (see the [audit index](README.md) and the [cross-dimension summary](summary.md)): how well `docs/`, the ADRs, the agent instructions and the engineering workflow (issues, PRs, CI, review, nightly routines) match the system that is actually running, and what is missing before a pilot with real Owners. The code was read at commit `dc0bc01`. An independent adversarial reviewer checked every finding against the code and the cited sources: "confirmed" means it held as written, and "adjusted" means the reviewer corrected its severity or details. The severity and recommendation below already include those corrections. Recommendations that need a decision say so and point at the related ADR; this doc changes no ADR.

## Summary

The docs are thorough and kept up to date (about 6,400 lines, many sources dated), and the engineering basics are in place: Conventional Commits, PR-only merges behind a `CI` check, backend ruff and pytest in CI (591 passed and 95 skipped locally, ruff clean; audit observation, 2026-10-19), and nightly routines.

The problem is that the docs still describe the planned hackathon system, not the one that is running:

- 27 of the 32 ADRs still say "proposed" although they are merged and live in production, and the code-review skill only checks "accepted" ADRs (DOC-2).
- Several ADR decisions are not built as written (Variations, the OpenAI image fallback, the Gemini voice-note fallback), and the ADRs don't say so; keeping Posts in memory has no ADR at all (DOC-2).
- The "contract" docs (overview, agents, data-model) list modules, tables and logging that don't exist (DOC-10), and the newest doc, [how-it-works.md](../../architecture/how-it-works.md), gets conversation persistence wrong (DOC-17).
- Public promises (landing, PRODUCT.md, README) run ahead of what is built (DOC-3).

The bigger gap is that nothing turns the move from hackathon to pilot into gates (DOC-1): the shared Kapso sandbox number supports one recipient, every Post publishes to one demo Instagram account ([ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md)), the Meta app only serves testers, pending Posts are lost on each deploy, and there is no privacy policy, runbook, per-Owner cost tracking, prompt-change process or pilot-feedback loop.

On the process side: issues are almost unused (2 ever; 1 of 56 merged PRs links one), PRs run past 3k lines and are self-merged without a second review, the Tenki review skips prompt (`.md`) and migration (`.sql`) changes, there is no frontend CI job, and the nightly routines are waiting on three untriaged PRs and read outdated docs.

## Findings at a glance

Effort: S is under half a day, M is 1-2 days, L is about a week, XL is more than a week.

| Id | Severity | Effort | Finding |
|---|---|---|---|
| DOC-1 | high | M | No pilot-readiness gate: pilot blockers are scattered across ADRs, READMEs and open questions |
| DOC-2 | medium | S | ADR hygiene: 27 of 32 ADRs say "proposed" though they run in production, and unbuilt decisions have no record |
| DOC-3 | medium | S | Public promises (landing, PRODUCT.md, README) don't match what is built, and the landing is in English for a Montevideo Owner |
| DOC-4 | medium | M | Developing on real WhatsApp means taking production offline; no staging environment |
| DOC-5 | medium | S | No privacy policy or data-handling doc, and the Gemini billing tier is undocumented, while Owner photos, voice and Instagram tokens are processed |
| DOC-6 | medium | M | No runbook, incident playbook or pilot-support guide, and logs can't drive alerts |
| DOC-7 | medium | M | Per-Owner cost tracking (F7.2, a Must) was never built, so unit economics and the Free tier can't be checked |
| DOC-8 | medium | M | No prompt or model change process; evals are 9 manual live tests with no recorded results |
| DOC-9 | medium | S | No mechanism to capture pilot-Owner feedback and corrections |
| DOC-10 | medium | M | The architecture "contracts" describe the target design, not the system, and AGENTS.md calls them the source of truth |
| DOC-11 | medium | S | Issues are almost unused, the PR template lacks ticket, docs and deploy checks, and PRs are very large |
| DOC-13 | medium | S | Review and CI blind spots: Tenki skips prompts and migrations, no frontend CI, Dependabot ignores uv and npm |
| DOC-18 | medium | S | Trend notes depend on a local file path, and there is no "how to add a niche or category" guide |
| DOC-12 | low | S | Nightly routines are waiting on untriaged PRs and read stale docs |
| DOC-14 | low | S | Self-merge with no second human review, including on the Approval and publishing guard |
| DOC-15 | low | S | open-questions.md is stuck in hackathon framing, with resolved and obsolete items not closed |
| DOC-16 | low | S | Env var docs are split across three places and have drifted from the code |
| DOC-17 | low | S | how-it-works.md says conversation history is lost on restart; the code persists it |
| DOC-19 | low | S | No release notes or deploy traceability |
| DOC-20 | low | S | Glossary drift: built concepts are missing, and unbuilt or legacy ones remain |
| DOC-21 | low | S | Small broken or incorrect references the docs check doesn't catch |

## Key numbers

Counts are audit observations from 2026-10-19 (the repo at `dc0bc01`, `gh` queries, a local test run) unless a source is linked. Where the reviewer corrected the auditor's count, both are shown.

| Metric | Value |
|---|---|
| ADRs: accepted / proposed / superseded | 2 / 27 / 3 (0009, 0010, 0014) of 32; two of the proposed ones (0024, 0028) are also partly superseded ([decisions/README.md:22-53](../../decisions/README.md)). The auditor counted 28 proposed and one partial supersession; the reviewer counted 27, and a re-read of the index shows two partial supersessions |
| ADR decisions not built as written, with no note in the ADR | 3: Variations ([ADR 0018](../../decisions/0018-ai-image-generation-service.md)), the OpenAI image fallback ([ADR 0019](../../decisions/0019-image-provider-gemini.md)), the Gemini voice-note fallback ([ADR 0021](../../decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md)); plus "Posts in memory" with no ADR |
| Tables in data-model.md / in migrations / mapped in `models.py` | 20 / 19 (no `niche_reports`) / 10 (the auditor counted 11) |
| Merged PRs / linking an issue / with a review approval | 56 (the auditor counted 58) / 1 (#60) / 0 |
| GitHub issues ever | 2 (#57 bug, #58 nightly-idea) |
| Largest PRs (additions) | #28 3,308 · #53 3,114 · #15 2,850 · #54 2,693 · #32 2,676 (ignoring the lockfile-heavy #12 and #13) |
| Open nightly PRs the product-research routine is waiting on | 3 (#37, #42, #47); the `nightly-bug` label was never created |
| Prompt files / commits touching prompts | 13 / 14 (in about 3 days) |
| Live eval tests (manual, not in CI) | 9 (5 conversation scenarios) |
| Backend tests (non-live, local run) | 591 passed, 95 skipped; ruff clean |
| Code vs docs size | backend app about 9.6k LOC, backend tests about 9.5k, frontend about 6.4k, docs about 6.4k lines |
| CI jobs | markdownlint, docs-index, actionlint, backend; no frontend job ([ci.yml](../../../.github/workflows/ci.yml)) |
| Env vars in setup.md not read by `config.py` | 20 (including `TRANSCRIBE_*`, `OPENAI_*`, `META_*`, `MAX_CONCURRENT_JOBS`) |
| Config vars missing from setup.md's table | 8 (including `RENDERER`, `RENDERER_URL`, `RENDERER_SECRET`, `GEMINI_IMAGE_SIZE`) |

## Doc and code contradictions

Every place where the audit found the docs (or a process rule) saying one thing and the code, the repo or the team's practice doing another. Each row cites both sides; the last column is the finding that covers it. Rows marked FE come from the [frontend doc](frontend.md).

| Topic | What the docs say | What the code or practice shows | Finding |
|---|---|---|---|
| ADR status | [AGENTS.md:69](../../../AGENTS.md): status is "proposed (open in a PR) or accepted (agreed by the team)", so a merged ADR should be accepted | [decisions/README.md:22-53](../../decisions/README.md): only 0001 and 0017 are accepted; 27 merged, running ADRs still say "proposed" | DOC-2 |
| Which ADRs reviews check | [code-review SKILL.md:16,21](../../../.claude/skills/code-review/SKILL.md) and [AGENTS.md:96](../../../AGENTS.md) review against "accepted ADRs"; [nightly-product-research.md:27](../../../.claude/routines/nightly-product-research.md) scores ideas against "the accepted ADRs" | Only 2 ADRs are accepted, so [ADR 0007](../../decisions/0007-approve-every-post.md) (approve every Post) is outside the review skill's ADR set | DOC-2 |
| ADR index | [decisions/README.md:31](../../decisions/README.md): 0010 is "superseded" without naming its successor | [ADR 0010](../../decisions/0010-anthropic-sdk-own-orchestration.md)'s own file names [ADR 0023](../../decisions/0023-gemini-text-llm.md) | DOC-2 |
| Variations | [ADR 0018:18](../../decisions/0018-ai-image-generation-service.md): "Each request produces several variations"; [agents.md:403,430](../../architecture/agents.md): `pick_variation`, `variation_choice`; [glossary.md:94,98-101](../../glossary.md): a Post is "the Variation the Owner picked"; [how-it-works.tsx:96](../../../frontend/components/landing/how-it-works.tsx): "Three options… Pick the one you like" | No file in `backend/app` mentions "variation"; [tasks.md:128](../../implementation/tasks.md): `create_post` takes a style (`photos` or `design`) instead; Variations remain an open task (T26, [tasks.md:177](../../implementation/tasks.md)) | DOC-2, DOC-3, DOC-10, DOC-20 |
| Image fallback | [ADR 0019:22](../../decisions/0019-image-provider-gemini.md): an OpenAI fallback | [imagegen/factory.py:20-21](../../../backend/app/imagegen/factory.py): `NotImplementedError` ("task T43") | DOC-2 |
| Voice-note fallback | [ADR 0021:22](../../decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md): a Gemini fallback; [README.md:37](../../../README.md): the stack row claims it | [chat.py:179-180](../../../backend/app/conversation/chat.py): "TranscriberPort isn't built yet, so no transcript = unclear" | DOC-2, DOC-3 |
| Transcription module | [overview.md:103](../../architecture/overview.md): a `TranscriberPort`; [api.md:263](../../architecture/api.md): `app/transcription/base.py` | No transcription module exists in `backend/app` | DOC-10 |
| Agent run log | [overview.md:105](../../architecture/overview.md): "Every LLM call writes an agent_runs row"; [mvp.md:105](../../product/mvp.md): F7.2 agent run log is a Must | [llm/client.py:245-255](../../../backend/app/llm/client.py) only logs usage, with no `business_id`; [imagegen/gemini.py:121](../../../backend/app/imagegen/gemini.py) keeps image usage in memory; [tasks.md:39,101](../../implementation/tasks.md): "agent_runs is still not written (T10)"; the table exists unused ([0001_initial.sql:301](../../../backend/migrations/versions/0001_initial.sql)) | DOC-7, DOC-10 |
| Repo layout | [overview.md:220-245](../../architecture/overview.md) lists `api/webhooks_whatsapp.py`, `dashboard.py`, `agents/copywriter.py`, `art_director.py`, `text_checker.py`, `transcription/`, `channels/simulator.py`, `db/repositories.py`, `seed.py` | None of these exist; the list omits `rendering/`, `instagram/`, `posts/`, `onboarding/` and `log_redaction.py` | DOC-10 |
| Schema | [data-model.md:3](../../architecture/data-model.md) calls itself "the current schema", 20 tables including `niche_reports` (line 214) | Migrations create 19 tables (no `niche_reports`); [models.py](../../../backend/app/db/models.py) maps 10; `posts`, `post_revisions`, `post_variations`, `messages` and `agent_runs` are never written | DOC-10, DOC-18 |
| Agent roster | [agents.md:7-18](../../architecture/agents.md): Copywriter, Art Director and Feedback Classifier, and the orchestrator at thinking `low` | The built drafter is the Post drafter ([drafts.py:22](../../../backend/app/posts/drafts.py)); [chat.py:69](../../../backend/app/conversation/chat.py) sets `OWNER_THINKING='medium'` | DOC-10 |
| Contracts as truth | [AGENTS.md:123](../../../AGENTS.md): "Contracts are the source of truth: api.md, agents.md, data-model.md" | The rows above: the three contracts describe the target design, not the running code | DOC-10 |
| Conversation persistence | [how-it-works.md:167,171](../../architecture/how-it-works.md): the conversation lives in memory and is lost on every restart; "Conversation history (InMemoryHistory)" | [factory.py:55-58](../../../backend/app/conversation/factory.py) uses `DbHistory` and `DbNotes` whenever `DATABASE_URL` is set, as [ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md) (line 12) says | DOC-17 |
| ADR link label | [backend/README.md:101](../../../backend/README.md) labels the history link "ADR 0028" | The link points to ADR 0030 | DOC-17 |
| WhatsApp simulator and dashboard | [AGENTS.md:128](../../../AGENTS.md): "Keep the WhatsApp simulator … working: they are the demo fallback"; [mvp.md:96](../../product/mvp.md): F6.2 simulator is a Must; [AGENTS.md:17](../../../AGENTS.md) and [nightly-bug-hunt.md:12](../../../.claude/routines/nightly-bug-hunt.md) describe a frontend with a "dashboard, WhatsApp simulator" | [channels/factory.py:19-20](../../../backend/app/channels/factory.py): the simulator raises `NotImplementedError` ("task T21"); [frontend/README.md:3](../../../frontend/README.md): the dashboard is planned, not built | DOC-4, DOC-12, DOC-21 |
| Preview deployments | [frontend/README.md:51,55](../../../frontend/README.md): Preview deployments use the production Railway backend as `NEXT_PUBLIC_API_URL` | Production `FRONTEND_ORIGINS` allows only the production frontend origin ([backend/README.md](../../../backend/README.md) table; CORS in [main.py:42-48](../../../backend/app/main.py)), so a preview's browser calls fail CORS instead of reaching production | DOC-4 |
| Scheduling and weekly plan | [PRODUCT.md:32](../../../PRODUCT.md) lists both as MVP capabilities; [pricing-section.tsx:78-79](../../../frontend/components/landing/pricing-section.tsx) puts them in Basic; [how-it-works.tsx:130](../../../frontend/components/landing/how-it-works.tsx): "Scheduled for Saturday 10:00"; [README.md:5](../../../README.md)'s "Still to build" omits scheduling | [rules.md:2](../../../backend/app/conversation/prompts/rules.md): "scheduling isn't built yet"; [zernio.py:121-122](../../../backend/app/publishing/zernio.py): scheduling raises `NotImplementedError`; no weekly-plan code exists | DOC-3, FE-4 |
| Publishing account | [pricing-section.tsx:67](../../../frontend/components/landing/pricing-section.tsx): "Published to your Instagram"; [faq-section.tsx:13-14](../../../frontend/components/landing/faq-section.tsx): "You connect your account" | [ADR 0024:21](../../decisions/0024-mvp-single-demo-instagram-account.md): every Business publishes to one demo account; [config.py:56-62](../../../backend/app/config.py) reads `ZERNIO_ACCOUNT_ID` from env. The FAQ line is accurate for the Instagram import ([ADR 0028](../../decisions/0028-read-instagram-with-our-meta-app.md), [ADR 0032](../../decisions/0032-instagram-first-onboarding.md)), not for publishing | DOC-3, FE-4 |
| Free tier | [PRODUCT.md:35](../../../PRODUCT.md) and the landing advertise Free as up to 3 Posts or Carousels a month | [config.py:44](../../../backend/app/config.py) only caps 5 designs a day; [ADR 0031:25](../../decisions/0031-pricing-free-basic-pro.md) defers enforcement until billing exists | DOC-1, DOC-7 |
| Landing language | [PRODUCT.md:13](../../../PRODUCT.md): the landing is in English for hackathon judges; [mvp.md:131](../../product/mvp.md): languages other than Spanish are out of scope; [layout.tsx:28](../../../frontend/app/layout.tsx): `lang="es"` | The landing renders in English ([page.tsx](../../../frontend/app/page.tsx)) and its CTA pre-types "Hi Neitor" ([whatsapp.ts:3](../../../frontend/lib/whatsapp.ts)) | DOC-3, FE-3 |
| Wizard autosave (FE) | [web-app.md:11](../../design/web-app.md): "Autosave every step" | [wizard.tsx:56](../../../frontend/components/onboarding/wizard.tsx) remounts each step and drops unsaved input; saving happens only on "Siguiente" | FE-12 |
| Tap targets (FE) | [web-app.md:10](../../design/web-app.md): "Big tap targets (≥ 48 px)" | 28-40 px buttons in [photo-tile.tsx:26](../../../frontend/components/onboarding/photo-tile.tsx), [brand-step.tsx:269](../../../frontend/components/onboarding/steps/brand-step.tsx) and [wizard-step.tsx:47,70](../../../frontend/components/onboarding/wizard-step.tsx) | FE-13 |
| Env vars documented but unread | [setup.md:39,43-44,58,68-72](../../implementation/setup.md) list `TRANSCRIBE_FALLBACK`, `OPENAI_*`, `MAX_CONCURRENT_JOBS` and `META_*` | [config.py](../../../backend/app/config.py) reads none of them; `MAX_CONCURRENT_JOBS` is hardcoded at [runner.py:26](../../../backend/app/jobs/runner.py); the `META_*` rows sit in a table labeled "Plan B only" | DOC-16 |
| Env vars read but undocumented | setup.md's table omits `RENDERER`, `RENDERER_URL`, `RENDERER_SECRET`, `GEMINI_IMAGE_SIZE` and `NICHE_REPORT_PATH` | [config.py:30,34-36,48](../../../backend/app/config.py) reads them; only [backend/README.md:80](../../../backend/README.md) documents the renderer | DOC-16 |
| `.env.example` | [backend/.env.example](../../../backend/.env.example) is the developer's env template | `KAPSO_BASE_URL` and `ZERNIO_BASE_URL` ([config.py:54,60](../../../backend/app/config.py)) are missing from it (both have defaults) | DOC-16 |
| Stale config comments | [config.py:42,56-57](../../../backend/app/config.py): "until Supabase Storage (T17)", "until the database exists" | The database exists and conversation memory already uses it ([factory.py:55-58](../../../backend/app/conversation/factory.py)) | DOC-16 |
| Trend notes file | [config.py:46-48](../../../backend/app/config.py): a report saved by the CLI at `out/niche-report.json` is the trend notes | [backend/.dockerignore](../../../backend/.dockerignore) excludes `out/`, so that file can never exist in the production image | DOC-18 |
| Weekly Niche Report | [ADR 0025](../../decisions/0025-weekly-niche-report.md): a weekly run per niche | [tasks.md:261](../../implementation/tasks.md): T58, the weekly job, is not built; `niche_reports` is in no migration | DOC-18 |
| Gemini billing | [ADR 0019:30](../../decisions/0019-image-provider-gemini.md): "Real Owner photos are never sent to Gemini without billing enabled" | [open-questions.md:42](../../open-questions.md): "the key is on the Free Tier" (2026-10-18); [tasks.md:46,128](../../implementation/tasks.md): runs measured "on the free tier"; nothing records the production project's billing | DOC-5 |
| Business definition | [glossary.md:15](../../glossary.md): the Business "whose day-to-day operations the assistant helps with" | [ADR 0013](../../decisions/0013-focus-marketing.md) narrowed the product to marketing | DOC-20 |
| Small PRs | [AGENTS.md:84](../../../AGENTS.md): "Keep PRs small" | #28 +3,308, #53 +3,114, #15 +2,850, #54 +2,693, #32 +2,676 (`gh pr list`) | DOC-11 |
| Issues | [AGENTS.md:29,42,75-77](../../../AGENTS.md): issues are steps 1 and 4 of the loop; [implementation/README.md:3](../../implementation/README.md): "Tasks here become GitHub issues when work starts" | 2 issues ever; only #60 of 56 merged PRs contains "Closes #" (`gh issue list`, `gh pr list`) | DOC-11 |
| Open questions upkeep | [AGENTS.md:67](../../../AGENTS.md): "Tick resolved items in open-questions.md" | [open-questions.md:56-57](../../open-questions.md) keeps Text Checker items although [ADR 0029:20](../../decisions/0029-designed-slides-ai-scene-code-layout.md) says "The Text Checker is dropped"; :3 still says "To decide before the hackathon" | DOC-15 |
| Kapso number questions | [open-questions.md:24-25](../../open-questions.md): the dedicated number and the recipient limit are unanswered | In practice the CTA is the sandbox ([PRODUCT.md:36](../../../PRODUCT.md)), and [Kapso's sandbox docs](https://docs.kapso.ai/docs/how-to/whatsapp/use-sandbox-for-testing.md) (read 2026-10-19) say multiple recipients aren't supported | DOC-15 |
| Roadmap phases | [roadmap.md](../../roadmap.md) Phase 1: "run it on the pilot owner's real account" | The same roadmap puts the own WhatsApp number and App Review in Phase 2 | DOC-1 |
| CI description | [AGENTS.md:21](../../../AGENTS.md): CI is markdownlint, the docs index and actionlint | [ci.yml](../../../.github/workflows/ci.yml) also runs a backend job | DOC-13 |
| Dependabot | [dependabot.yml:1-3](../../../.github/dependabot.yml): add uv and the frontend's ecosystem "when those projects get a manifest" | [backend/pyproject.toml](../../../backend/pyproject.toml) and [frontend/package.json](../../../frontend/package.json) exist; Dependabot still covers only GitHub Actions | DOC-13 |
| Skills index link | [.claude/skills/README.md:33](../../../.claude/skills/README.md) links use-railway to `docs/decisions/0012-backend-host-railway.md` | That file doesn't exist: 0012 is the catalog ADR ([ADR 0012](../../decisions/0012-catalog-content-dashboard-reels.md)) and Railway is [ADR 0017](../../decisions/0017-backend-host-railway.md) | DOC-21 |
| Vercel project | [frontend/README.md:37](../../../frontend/README.md): `vercel link --project build101` | [frontend/README.md:32](../../../frontend/README.md): the project is `neitorai` | DOC-21 |
| Index dates | [architecture/README.md:8-12](../../architecture/README.md), [product/README.md:7-10](../../product/README.md), [implementation/README.md:7-9](../../implementation/README.md): files dated 2026-10-17 | Those files last changed on 2026-10-18 and 2026-10-19 (`git log`) | DOC-21 |
| Build backend | [.claude/rules/python.md](../../../.claude/rules/python.md) project table: build backend "TBD" | [backend/pyproject.toml:20-21](../../../backend/pyproject.toml) uses hatchling | DOC-21 |

## Findings

### DOC-1: No pilot-readiness gate: pilot blockers are scattered across ADRs, READMEs and open questions

- **Severity**: high · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [roadmap.md:7-21](../../roadmap.md): Phase 1 "Pilot" is a feature list with no readiness gates.
  - [plan.md:98-107](../../implementation/plan.md): the post-hackathon order puts Should features before persistence, an own number and billing.
  - [mvp.md:3,144-148](../../product/mvp.md): scope and definition of done are still for the 24-hour hackathon and demo day.
  - [ADR 0024:21](../../decisions/0024-mvp-single-demo-instagram-account.md): "Every Business in the demo publishes to the same Instagram account".
  - [ADR 0008:17](../../decisions/0008-publishing-via-zernio.md): Zernio's free tier is 2 connected accounts for the whole team.
  - [PRODUCT.md:36](../../../PRODUCT.md) and [README.md:13](../../../README.md): the CTA is the shared Kapso sandbox number.
  - [Kapso: use the sandbox for testing](https://docs.kapso.ai/docs/how-to/whatsapp/use-sandbox-for-testing.md) (read 2026-10-19): "Multiple recipients aren't supported" and "The sandbox is for testing message flows, not production features".
  - [open-questions.md:92](../../open-questions.md): our Meta app reads only Instagram testers until App Review.
  - [how-it-works.md:177](../../architecture/how-it-works.md): a redeploy while a Post is waiting means it can no longer be approved or published.
  - [open-questions.md:17-18,42](../../open-questions.md): the WhatsApp policy check, the own number, and the Gemini key on the Free Tier.
  - [ADR 0031:25](../../decisions/0031-pricing-free-basic-pro.md): the Free-tier cap is not enforced; [config.py:44](../../../backend/app/config.py) only caps 5 designs a day.
- **Problem**: The product is about to pilot with real Owners, but the docs that set scope ([mvp.md](../../product/mvp.md), [plan.md](../../implementation/plan.md), [ADR 0016](../../decisions/0016-demo-scope-one-post.md)) are written for the hackathon demo. The things that stop a real pilot are spread across eight places and nobody owns them as a list: (1) the WhatsApp entry point is a sandbox that serves one registered phone; (2) every Business publishes to the same demo Instagram account; (3) the Instagram import works only for Meta app testers; (4) pending Posts and their images vanish on every Railway deploy; (5) the Gemini key's billing tier is unconfirmed; (6) the Meta WhatsApp AI-assistant policy check is still open; (7) the advertised Free tier (3 a month) is not enforced. Failure scenarios: a second pilot Owner taps "Get started on WhatsApp" on the landing and gets nothing back, or an Owner approves a Post and it appears on the team's demo Instagram account instead of theirs.
- **Recommendation**: Write `docs/product/pilot.md` with a go/no-go checklist, giving each gate an owner and a date. Gates: (1) a WhatsApp number that can serve every pilot Owner plus both builders (an own number on Kapso, or Meta direct); (2) publishing to each Owner's own account; (3) pilot Owners added as Instagram testers; (4) Posts and images persisted (T17, T19), or a rule of no deploys while a Post is pending; (5) Gemini billing confirmed and recorded; (6) the WhatsApp AI-assistant policy checked; (7) a runbook and a feedback loop. For a single-Owner pilot, connect the Owner's Instagram in Zernio (within the 2 free accounts) and set `ZERNIO_ACCOUNT_ID` as a stopgap. Moving to several Owners needs an ADR superseding [ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md). Leave Free-tier enforcement out of the gates. Fix roadmap Phases 1 and 2 so the own number sits in the pilot phase. Link pilot.md from the root README.md and [docs/README.md](../../README.md), and mark mvp.md and plan.md as hackathon-era.
- **Impact**: Stops the pilot from launching on a channel that can't take a second Owner and a publisher that posts to the wrong account, and avoids a wasted first week and a broken first impression with each real Owner.
- **Verifier note**: All seven blockers check out (Kapso's sandbox page, ADR 0024 with [config.py:56-62](../../../backend/app/config.py), open-questions, `store.py` keeping Posts in memory), and no pilot plan exists anywhere. The roadmap also contradicts itself: Phase 1 says "run it on the pilot owner's real account", but the own WhatsApp number and App Review sit in Phase 2. Severity drops from critical to high: this is a planning gap, not a defect that can harm Owners or publish without Approval, and Phase 1 is "Pilot with one owner", which stopgaps can serve. The Free-tier cap is not a pilot gate: billing is Phase 2 and nobody can pay yet.
- **Related**: [PRD-3](product.md), [FE-1](frontend.md), [OPS-3](platform-ops.md)

### DOC-2: ADR hygiene: 27 of 32 ADRs say "proposed" though they run in production, and unbuilt decisions have no record

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [decisions/README.md:22-53](../../decisions/README.md): only 0001 and 0017 are accepted; 0009, 0010 and 0014 are superseded; the other 27 are proposed.
  - [AGENTS.md:69](../../../AGENTS.md): status is "proposed (open in a PR) or accepted (agreed by the team)", so a merged ADR should be accepted; [AGENTS.md:114](../../../AGENTS.md): "Decisions are ADRs, never buried in PR comments".
  - [ADR 0018:18](../../decisions/0018-ai-image-generation-service.md): "Each request produces several variations", against no "variation" in `backend/app` and [tasks.md:128](../../implementation/tasks.md), where `create_post` takes a style (`photos` or `design`) instead.
  - [ADR 0019:22](../../decisions/0019-image-provider-gemini.md): an OpenAI fallback, against [imagegen/factory.py:20-21](../../../backend/app/imagegen/factory.py) (`NotImplementedError`, "task T43").
  - [ADR 0021:22](../../decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md): a Gemini fallback, against [chat.py:179-180](../../../backend/app/conversation/chat.py) ("TranscriberPort isn't built yet, so no transcript = unclear").
  - [ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md) Consequences: "Posts and their images still live in memory (T17, T19)", a task-level shortcut with no ADR.
  - [decisions/README.md:31](../../decisions/README.md): 0010 "superseded" without naming 0023.
  - [nightly-product-research.md:27](../../../.claude/routines/nightly-product-research.md): scores ideas against "the accepted ADRs".
- **Problem**: Readers can't tell from the status which decisions are live. The nightly routine and the code-review skill both check work against "accepted" ADRs, and only 2 are accepted. Three ADR decisions are not built as written (no Variations, neither fallback) and the ADRs don't say so. One architectural shortcut (Posts in memory) exists only in tasks.md. [ADR 0016](../../decisions/0016-demo-scope-one-post.md)'s hackathon demo scope still governs priorities after the hackathon.
- **Recommendation**: One ADR sweep PR, which needs a team decision: flip the merged and running ADRs to accepted, and adopt "merge = accepted". Add "As built" notes to ADRs 0018, 0019 and 0021 saying Variations, the OpenAI fallback and the Gemini transcriber are not built yet, each with its task id. Separately, the team decides whether Variations stay (T26) or are dropped; only if they are dropped, write the ADR and update the landing, mvp.md and the glossary. Record "Posts in memory until T17/T19" as a dated temporary decision. Extend [check_docs_index.py](../../../scripts/check_docs_index.py) to compare each ADR's Status line with its index row.
- **Impact**: Restores the ADR log as the single source of "what is decided", which the code-review skill, the nightly agents and new engineers all depend on, and prevents rebuilding dropped designs such as Variations or `pick_variation`.
- **Verifier note**: The status claim holds with one count off: 27 are proposed, not 28 (2 accepted, 3 superseded, 27 proposed). The consequence is worse than stated: [code-review SKILL.md:16,21](../../../.claude/skills/code-review/SKILL.md) and [AGENTS.md:96](../../../AGENTS.md) review against "accepted ADRs" only, so [ADR 0007](../../decisions/0007-approve-every-post.md) (approve every Post) is outside the code-review skill's ADR set. The "reversed without a record" framing is overstated: Variations are a planned, open task (T26 at [tasks.md:177](../../implementation/tasks.md), `pick_variation` in [agents.md:403](../../architecture/agents.md), [open-questions.md:37-38](../../open-questions.md)), the OpenAI fallback is deferred task T43, and the Gemini transcriber is unbuilt and says so in `chat.py`. These are unbuilt work, not reversed decisions, and an ADR saying "no Variations" would be a product decision the team hasn't made (the landing still promises "Three options"). ADR 0010's own file does name 0023; only the index row omits the link.

### DOC-3: Public promises (landing, PRODUCT.md, README) don't match what is built, and the landing is in English for a Montevideo Owner

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [PRODUCT.md:13 and :41](../../../PRODUCT.md): "landing copy is in English for" hackathon judges.
  - [layout.tsx:28](../../../frontend/app/layout.tsx): `lang="es"` on an English landing, so screen readers use a Spanish voice.
  - [whatsapp.ts:3](../../../frontend/lib/whatsapp.ts): the WhatsApp CTA pre-types "Hi Neitor" in English.
  - [how-it-works.tsx:96](../../../frontend/components/landing/how-it-works.tsx): "Three options from your photos. Pick the one you like", although Variations are not built; :130 "Scheduled for Saturday 10:00", against [rules.md:2](../../../backend/app/conversation/prompts/rules.md) ("scheduling isn't built yet").
  - [pricing-section.tsx:78-79](../../../frontend/components/landing/pricing-section.tsx): Basic includes "A weekly content plan" and scheduling; neither is built ([README.md:5](../../../README.md) lists the weekly plan as still to build but omits scheduling).
  - [faq-section.tsx:13-14](../../../frontend/components/landing/faq-section.tsx): "You connect your account", while publishing goes to the demo account ([ADR 0024:21](../../decisions/0024-mvp-single-demo-instagram-account.md)).
  - [PRODUCT.md:32](../../../PRODUCT.md): lists scheduling and the weekly plan as MVP capabilities.
  - [README.md:37](../../../README.md): the stack row claims a Gemini fallback for Voice notes that isn't built.
- **Problem**: PRODUCT.md is the brief the impeccable skill uses to write landing copy. It still targets hackathon judges and lists unbuilt features as MVP, so its drift turns into public promises: Variations, scheduling, a weekly plan, and posting to "your" Instagram. A Spanish-speaking Owner in their 50s lands on an English page whose CTA sends "Hi Neitor" to a Spanish bot. During a paid pilot, promising scheduling that the bot then says isn't available undermines trust.
- **Recommendation**: Add a Shipped / Coming / Not planned table to PRODUCT.md and use it to gate landing claims. Mark scheduling, the weekly plan and Variations "pronto", or remove them. Change the Free card's "Published to your Instagram" until per-Owner publishing exists. Decide the landing language for Uruguay (Spanish at `/`, English optional). Set `lang` per route and pre-type "Hola Neitor". Update README.md's "Still to build" and its stack row.
- **Impact**: Avoids over-promising to paying pilot Owners, is likely to raise landing-to-WhatsApp conversion for the target persona, and fixes an accessibility defect.
- **Verifier note**: Every cited mismatch checks out, and README.md's "Still to build" omits scheduling. Severity drops to medium: pilot Owners are recruited by hand rather than through the landing, there is no billing so nobody is paying for the promised features, and the `lang` mismatch is a real but minor accessibility defect. The FAQ line about connecting on Instagram's login page is accurate for the Instagram import ([ADR 0028](../../decisions/0028-read-instagram-with-our-meta-app.md), [ADR 0032](../../decisions/0032-instagram-first-onboarding.md)), though not for publishing.
- **Related**: [FE-3](frontend.md), [FE-4](frontend.md), [PRD-6](product.md), [GRW-14](growth-pricing-market.md)

### DOC-4: Developing on real WhatsApp means taking production offline; no staging environment

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [backend/README.md:107-109](../../../backend/README.md): "Point the number at one backend at a time", and step 1 is "pause the Railway webhook".
  - [open-questions.md:9](../../open-questions.md): local WhatsApp development is unresolved.
  - [channels/factory.py:19-20](../../../backend/app/channels/factory.py): the simulator raises `NotImplementedError` ("task T21").
  - [mvp.md:96](../../product/mvp.md): the F6.2 simulator is a Must, the "dev + demo fallback".
  - [AGENTS.md:128](../../../AGENTS.md): "Keep the WhatsApp simulator … working: they are the demo fallback"; it doesn't exist.
  - [frontend/README.md:51,55](../../../frontend/README.md): Preview deployments use the production Railway backend as `NEXT_PUBLIC_API_URL`.
- **Problem**: There is one WhatsApp number, one backend environment and one database. To test a conversation change on a real phone, a developer pauses the production Kapso webhook and points it at a laptop tunnel. During the pilot, Owners' messages would then reach a dev machine, or nothing.
- **Recommendation**: Once the pilot moves to its own WhatsApp number (DOC-1), keep the Kapso sandbox as the dev and staging number with its own webhook. Add a Railway staging environment with a separate Supabase project or branch, point Vercel Preview's `NEXT_PUBLIC_API_URL` at staging, and add staging's preview origins to its CORS list. Alternatively, build T21's simulator. Add "never repoint the production webhook during the pilot" to backend/README.md and the runbook.
- **Impact**: Removes a direct path to pilot outages caused by routine development, and keeps test data out of the production database.
- **Verifier note**: The core claim holds: local WhatsApp development pauses the production webhook ([backend/README.md:107-113](../../../backend/README.md)), the simulator isn't built, and there is one backend, one database and one number. The auditor's preview claim was wrong: production `FRONTEND_ORIGINS` is only the production frontend origin (backend/README.md table; CORS in [main.py:42-48](../../../backend/app/main.py)), and the wizard calls the API from client components through `lib/api.ts`, so a Vercel preview's browser writes fail CORS instead of reaching the production database. Previews are broken for wizard testing, not a data-pollution path. Severity drops to medium: a real outage risk during the pilot, avoidable by discipline in the short term.
- **Related**: [OPS-8](platform-ops.md)

### DOC-5: No privacy policy or data-handling doc, and the Gemini billing tier is undocumented, while Owner photos, voice and Instagram tokens are processed

- **Severity**: medium · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - [site-footer.tsx:5-11](../../../frontend/components/landing/site-footer.tsx): the footer links are product anchors only, with no privacy or terms.
  - A grep over `docs/`, README.md and AGENTS.md finds no privacy, data retention or deletion doc (audit observation, 2026-10-19).
  - [Meta: App Review submission guide](https://developers.facebook.com/docs/app-review/submission-guide) (read 2026-10-19): a privacy policy URL is a required app setting for App Review.
  - [open-questions.md:92](../../open-questions.md): App Review is needed to read any non-tester Owner's account.
  - [Gemini API terms](https://ai.google.dev/gemini-api/terms) (read 2026-10-19): for Unpaid Services, content is used to improve products and "human reviewers may read, annotate, and process your API input and output".
  - [open-questions.md:42](../../open-questions.md): "the key is on the Free Tier" (2026-10-18); [tasks.md:46,128](../../implementation/tasks.md): runs measured "on the free tier".
  - [ADR 0019:30](../../decisions/0019-image-provider-gemini.md): "Real Owner photos are never sent to Gemini without billing enabled".
  - [0002_instagram_import.sql](../../../backend/migrations/versions/0002_instagram_import.sql): stores `social_accounts.access_token`.
  - [URCDP resolution 867/010](https://www.gub.uy/unidad-reguladora-control-datos-personales/sites/unidad-reguladora-control-datos-personales/files/documentos/normativa/resolucion-867-010_0.pdf) (read 2026-10-19): under Ley 18.331 every private database must be registered with the URCDP; the current procedure was not verified.
- **Problem**: Pilot Owners will send product photos, Voice notes and Instagram access to six processors (Google, Kapso, Zernio, Supabase, Railway, Vercel) with no published policy. App Review can't be submitted without a privacy policy URL. The docs last recorded the Gemini key on the Free Tier, which would let Google use and human-review Owners' photos, contrary to ADR 0019:30, and nothing records whether that changed.
- **Recommendation**: Publish a short Spanish `/privacidad` page linked from the footer and the wizard. Cover what is collected, the processors (Google, Kapso, Zernio, Supabase, Railway, Vercel, Meta), retention, and how to request deletion, so it can also serve as Meta's privacy and data-deletion URL. Record in [setup.md](../../implementation/setup.md) which Google project the production `GEMINI_API_KEY` belongs to, its billing status and the date checked, and use a separate key for any free-tier local experiments. Confirm whether the Owners' database must be registered with the URCDP before App Review or a wider launch.
- **Impact**: Unblocks Meta App Review, protects Owners' data from being used for training, and lowers legal risk in Uruguay before real personal data flows.
- **Verifier note**: Confirmed: no privacy policy or terms anywhere, Meta lists the Privacy Policy URL as required, the Gemini terms for Unpaid Services say what the finding quotes, and the Instagram token is stored (`0002_instagram_import.sql:3`). The training risk is less certain than stated: [Google's Gemini API pricing page](https://ai.google.dev/gemini-api/docs/pricing) (read 2026-10-19) lists no free tier for Nano Banana 2.1, so a key that generates images in production must have billing linked, and the 2026-10-18 Free Tier note may refer to a different, local key. Still, tasks.md records vision and text runs "on the free tier" and nothing records the production project's billing, so recording it is the right fix. App Review is Phase 2, and a tester-only pilot does not strictly need it.
- **Related**: [SEC-3](security-privacy.md), [SEC-6](security-privacy.md), [FE-2](frontend.md), [PRD-8](product.md), [GAP-4](cross-cutting-gaps.md)

### DOC-6: No runbook, incident playbook or pilot-support guide, and logs can't drive alerts

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - A grep for runbook, incident, on-call, sentry, uptime or alert across `docs/`, README.md, backend/README.md and frontend/README.md finds no ops doc (audit observation, 2026-10-19).
  - [backend/pyproject.toml:6-18](../../../backend/pyproject.toml) and [frontend/package.json](../../../frontend/package.json): no error tracking such as Sentry.
  - [backend/README.md:88-99](../../../backend/README.md): "Logs and checks" and "Rollback" are the only ops content; :93 says Railway tags every line `level=error`, "known noise: read the message text"; :105 says a mismatched Kapso webhook secret gives 401s on every delivery.
  - [store.py:15](../../../backend/app/posts/store.py): `publish_pending` means "the post may be live, never report a failure", with no documented follow-up.
  - [open-questions.md:93](../../open-questions.md): the Instagram long-lived token expires in 60 days and is not refreshed.
- **Problem**: Two builders will support real Owners, but nothing says what to do when the bot goes silent. Possible causes include a paused or mis-secreted Kapso webhook, a Gemini 429 or 503, renderer 503s from a missing `RENDER_SECRET`, Zernio stuck in `publish_pending`, stuck jobs, expired magic links, a redeploy losing a pending Post, or the 60-day Instagram token expiring. There is no error tracking, and every log line is `level=error`, so no alert can be meaningful. Owners will find failures before the team does.
- **Recommendation**: Write `docs/operations/runbook.md` (symptom, check, fix, Spanish message to the Owner) for: webhook paused or wrong secret, Gemini 429 or 503, renderer 503, `publish_pending`, a stuck or failed job, an expired magic link, a lost pending Post after a deploy, and an expiring Instagram token. Send logs to stdout with real levels, or as JSON, so Railway can alert on ERROR. Add Sentry, or at least an uptime check on `/health` and `/api/render`.
- **Impact**: Shorter time to detect and resolve each pilot incident (from "an Owner complains" to minutes), and fewer Owners churning after a silent failure.
- **Verifier note**: Confirmed: the grep matches are only incidental words in AGENTS.md, agents.md and tasks.md. Every line is tagged `level=error` because [main.py:20](../../../backend/app/main.py) logs through `basicConfig`, which writes to stderr. Severity drops to medium: for a 2-4 week pilot with one or a few hand-held Owners the builders watch closely, and the fixes are cheap. Still worth doing before the pilot.
- **Related**: [OPS-4](platform-ops.md), [OPS-11](platform-ops.md), [OPS-5](platform-ops.md)

### DOC-7: Per-Owner cost tracking (F7.2, a Must) was never built, so unit economics and the Free tier can't be checked

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [mvp.md:105](../../product/mvp.md): F7.2 agent run log is a Must.
  - [overview.md:105](../../architecture/overview.md): "Every LLM call writes an agent_runs row".
  - [llm/client.py:245-255](../../../backend/app/llm/client.py): usage only goes to `logger.info`, with no `business_id`.
  - [imagegen/gemini.py:121](../../../backend/app/imagegen/gemini.py): image usage is returned in memory, never persisted.
  - [tasks.md:39,101](../../implementation/tasks.md): "agent_runs is still not written (T10)".
  - [0001_initial.sql:301](../../../backend/migrations/versions/0001_initial.sql): the `agent_runs` table exists, unused.
  - [ADR 0019:28](../../decisions/0019-image-provider-gemini.md): "Cost per variation is measured, not assumed".
  - [roadmap.md:50](../../roadmap.md): "To validate: WhatsApp and LLM costs per active business must fit well under the Basic price".
  - [ADR 0031:25](../../decisions/0031-pricing-free-basic-pro.md): the Free cap is to be enforced once billing exists.
- **Problem**: Pricing (Free with 3 Posts, Basic US$29) was set with no measured cost per Owner. The docs give rough estimates only: about $0.05 per 2K image, $0.30-0.40 per 5-Slide Carousel, $0.113 per 4K panorama, plus orchestrator, compaction, asset-analysis and Niche Analyst calls. Since `MAX_POSTS_PER_DAY=5` is the only cap, a free Owner can trigger about 150 designs a month (5 a day × 30). Without `agent_runs` there is no way to know cost per Owner or per Post, or which agent dominates.
- **Recommendation**: Write `agent_runs` rows from the LLM client and the image adapter: `business_id`, agent, model, image size, token counts by type, latency, error. Compute USD from a dated price table in code that already includes the 2027-01-01 Flash price change. Add a `cost_per_business_month` view and a short `docs/operations/costs.md`. Review it weekly in the pilot, and use it to set the Free and Basic caps and to test 1K against 2K images and thinking levels.
- **Impact**: Turns pricing and model choices into measured decisions, and catches a runaway free Owner before the bill does.
- **Verifier note**: Confirmed; image usage is logged only when a Carousel fails ([generator.py:188](../../../backend/app/carousel/generator.py)). [Google's Gemini API pricing page](https://ai.google.dev/gemini-api/docs/pricing) (read 2026-10-19) confirms the cost figures: Nano Banana 2.1 is $0.0336 at 1K, $0.0504 at 2K and $0.113 at 4K. It also shows gemini-3.8-flash doubling on 2027-01-01 ($0.75 to $1.50 input and $3.75 to $7.50 output per 1M tokens), which makes a dated price table more important. Corrections: per-call text token data already exists in Railway logs, just without `business_id`, and the auditor's "20-50% savings" claim is unsupported. Severity medium: pilot spend is small in absolute terms, so this is pricing-validation infrastructure, not a pilot blocker.
- **Related**: [COST-1](unit-economics.md), [MOD-3](models.md), [ARCH-13](backend-architecture.md), [OPS-9](platform-ops.md), [AIQ-6](ai-quality.md)

### DOC-8: No prompt or model change process; evals are 9 manual live tests with no recorded results

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [backend/app/conversation/prompts/](../../../backend/app/conversation/prompts) and the other `backend/app/**/prompts/*.md` folders: 13 prompt files, changed in 14 commits over 3 days (`git log`, audit observation, 2026-10-19).
  - [test_conversation_live.py:146-188](../../../backend/tests/test_conversation_live.py): 5 scenarios, plus 1 test each in the post_drafter, gemini_chat, niche_analyst and gemini live suites.
  - [pyproject.toml:43](../../../backend/pyproject.toml): `addopts -m 'not live'`, so they never run in CI.
  - [plan.md:105](../../implementation/plan.md): "Evals for each agent (golden briefs -> graded outputs) before changing prompts or models" is deferred to post-hackathon.
  - [AGENTS.md:127](../../../AGENTS.md): the only rule is to check the Gemini docs before changing a model.
  - [config.py:28,40](../../../backend/app/config.py): model ids switchable by env var, with no record.
  - [tenki-review.yml:15-21](../../../.github/workflows/tenki-review.yml): `.md` files don't trigger AI review, so prompt-only PRs get none.
- **Problem**: Prompts are the product's behaviour (Approval answers, Rioplatense tone, no invented facts), yet a prompt or model change ships without any eval evidence or AI review. Nothing records which prompt or model version produced a given Owner conversation. No eval covers Carousels, designed Slides, Voice-note transcripts or the "never invent prices" rule ([AGENTS.md:131](../../../AGENTS.md)).
- **Recommendation**: Add a "Changing a prompt or model" checklist to [workflow.md](../../workflow.md): run `uv run pytest -m live -k <area>` and paste the result in the PR. Add a `workflow_dispatch` evals workflow. Grow a small golden set from pilot transcripts, for example "dale" after "¿Lo subo?", a price in a Voice note, a caption-only edit, and a Carousel. Log the model and a prompt hash once `agent_runs` exists. Add `backend/**/prompts/*.md` to Tenki's paths.
- **Impact**: Catches regressions such as Approval misfires or invented prices before Owners see them, and makes model swaps (for example cheaper Flash tiers) safe to try.
- **Verifier note**: Confirmed (13 prompt files, 14 commits between 10-17 and 10-19; Tenki's filter covers only `.py`, `.ts`, `.tsx`, `.js`, `.jsx`). Severity drops to medium: [ADR 0007](../../decisions/0007-approve-every-post.md) is enforced in code, so a prompt regression can't publish without Approval; the worst cases are tone, invented facts and misread intent. Pilot volume is small, and `conversation_steps` already keeps every turn for review.
- **Related**: [AIQ-5](ai-quality.md), [MOD-4](models.md), [OPS-14](platform-ops.md)

### DOC-9: No mechanism to capture pilot-Owner feedback and corrections

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [roadmap.md:9](../../roadmap.md): "log every correction the owner makes"; :12 "Brand voice learns from corrections"; :21 the success metric is hours per week before and after, with no measurement defined.
  - [.github/ISSUE_TEMPLATE/idea.md](../../../.github/ISSUE_TEMPLATE/idea.md): the only issue template.
  - `gh label list`: no feedback or pilot label (audit observation, 2026-10-19).
  - [0003_conversation_memory.sql:4](../../../backend/migrations/versions/0003_conversation_memory.sql): `conversation_steps` already persists every turn per Business.
- **Problem**: The pilot's purpose is learning, but nothing says how an Owner's complaint, a discarded Post, a "cambiá el texto" or a `revise_post` call becomes an issue or a metric. There is no baseline interview for the hours-per-week metric. Feedback will live in WhatsApp chats and memory, which goes against [AGENTS.md:111](../../../AGENTS.md) ("docs/ is the shared memory").
- **Recommendation**: Add a pilot-feedback issue template and `docs/product/pilot-feedback.md`. That doc sets a weekly review of `conversation_steps` (discards, remakes, time to Approval, unclear Voice notes), a before-and-after interview for hours per week, and the rule that confirmed patterns become issues or eval cases. Keep raw transcripts out of the public repo.
- **Impact**: Turns the 2-4 week pilot into a prioritized backlog and evidence for pricing and positioning, instead of anecdotes.
- **Verifier note**: Confirmed. The raw data exists in `conversation_steps`, but no review or measurement process does. Severity is medium rather than high: it is a cheap process doc, and the data is already captured.
- **Related**: [GRW-1](growth-pricing-market.md), [FE-8](frontend.md)

### DOC-10: The architecture "contracts" describe the target design, not the system, and AGENTS.md calls them the source of truth

- **Severity**: medium · **Effort**: M · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [AGENTS.md:123](../../../AGENTS.md): "Contracts are the source of truth: api.md, agents.md, data-model.md".
  - [overview.md:103](../../architecture/overview.md): `TranscriberPort`, not built; :105 `agent_runs` on every LLM call, not built.
  - [overview.md:220-245](../../architecture/overview.md): the repo layout lists `api/webhooks_whatsapp.py`, `dashboard.py`, `agents/copywriter.py`, `art_director.py`, `text_checker.py`, `transcription/`, `channels/simulator.py`, `db/repositories.py` and `seed.py`, none of which exist, and omits `rendering/`, `instagram/`, `posts/`, `onboarding/` and `log_redaction.py`.
  - [data-model.md:3](../../architecture/data-model.md): "the current schema", against [models.py](../../../backend/app/db/models.py), which maps 10 tables; `posts`, `post_revisions`, `post_variations`, `messages` and `agent_runs` are never written, and `niche_reports` (data-model.md:214) is in no migration.
  - [agents.md:7-18](../../architecture/agents.md): a roster of Copywriter, Art Director and Feedback Classifier, while the built drafter is the Post drafter in [drafts.py:22](../../../backend/app/posts/drafts.py); the orchestrator is listed at `low`, against [chat.py:69](../../../backend/app/conversation/chat.py) `OWNER_THINKING='medium'`.
  - [agents.md:403,430](../../architecture/agents.md): `pick_variation`, `variation_choice`.
  - [api.md:263](../../architecture/api.md): `app/transcription/base.py`.
  - [docs/README.md:9-22](../../README.md): the reading order omits how-it-works.md, the only as-built doc.
- **Problem**: A new engineer, an AI agent or the nightly bug hunt (which compares code with data-model.md) starts from overview.md and agents.md and gets a different system from the one running. AGENTS.md tells them that when code and docs disagree they must "fix one", so these docs invite either rebuilding dropped designs or endless doc patches. The architecture index dates ([architecture/README.md:8-12](../../architecture/README.md), 2026-10-17) hide that the files were patched later.
- **Recommendation**: Make how-it-works.md first in docs/README.md's reading order, add Built and Planned markers to the contract docs, regenerate the repo tree from the filesystem, split data-model.md into used and unused tables, and reword AGENTS.md:123. After DOC-17's fix, how-it-works.md should be the single as-built reference.
- **Impact**: Cuts onboarding time and wrong-direction work for humans and agents, and makes the nightly bug hunt's drift checks meaningful.
- **Verifier note**: Confirmed in full. Small correction: `db/models.py` maps 10 tables, not 11. Severity drops to medium: it misleads people and agents but has no runtime impact, and it is partly mitigated because how-it-works.md is listed first in the [architecture index](../../architecture/README.md).
- **Related**: [ARCH-15](backend-architecture.md)

### DOC-11: Issues are almost unused, the PR template lacks ticket, docs and deploy checks, and PRs are very large

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - `gh issue list --state all`: 2 issues ever, #57 and #58 (audit observation, 2026-10-19).
  - `gh pr list --state merged`: only #60 of 56 merged PRs contains "Closes #" (audit observation, 2026-10-19).
  - [AGENTS.md:29,42,75-77](../../../AGENTS.md): issues are steps 1 and 4 of the loop.
  - [implementation/README.md:3](../../implementation/README.md): "Tasks here become GitHub issues when work starts".
  - [pull_request_template.md:1-5](../../../.github/pull_request_template.md): only What, Why and Notes.
  - PR sizes (`gh pr list`, audit observation, 2026-10-19): #28 +3,308, #53 +3,114, #54 +2,693, #32 +2,676, #15 +2,850, against [AGENTS.md:84](../../../AGENTS.md) "Keep PRs small".
  - [tasks.md](../../implementation/tasks.md): 325 lines with inline "Built" notes and no status column.
- **Problem**: Work is tracked in a 325-line Markdown file with as-built notes mixed into the plan, so nobody can see what is open, who owns it or what is blocked. PRs routinely run past 2.5k lines, which neither a one-shot Tenki review nor a human can review well. Nothing in the PR flow asks about env vars to set on Railway or Vercel, migration order, docs updated (AGENTS.md step 7) or Owner-facing copy changes.
- **Recommendation**: A "Pilot" GitHub Project or milestone, issues for the remaining work, and a PR template with `Closes #`, docs-updated, ADR link, deploy notes, prompt and model eval evidence, and Owner-facing copy checks. Add a soft PR size limit.
- **Impact**: Gives a 2-person team one view of pilot work and reviewable PRs, and makes the "every PR links its ticket" standard enforceable.
- **Verifier note**: Confirmed, with small number corrections: 56 merged PRs, not 58, and the size list ignores the 13k lockfile-heavy #12 and #13. AGENTS.md says to keep PRs small and link the issue, and the team-wide standard requires a ticket link in every PR.

### DOC-12: Nightly routines are waiting on untriaged PRs and read stale docs

- **Severity**: low · **Effort**: S · **Confidence**: medium · **Verified**: adjusted
- **Evidence**:
  - `gh issue view 58`: "No PR tonight: the ideas that fit the MVP are either already open as nightly PRs (#37 …, #42 …, #47 …)" (audit observation, 2026-10-19).
  - `gh pr list --state open`: #42 (CI green, open since 2026-10-18 06:07 UTC), #47 (draft, adds code enforcement of "never invent prices", open since 2026-10-18 07:32 UTC), #37 untriaged.
  - [nightly-product-research.md:16](../../../.claude/routines/nightly-product-research.md): orients on tasks.md and mvp.md; :27 scores fit with "accepted ADRs".
  - [nightly-bug-hunt.md:12](../../../.claude/routines/nightly-bug-hunt.md): says the frontend has a "dashboard, WhatsApp simulator"; :16 reads data-model.md and overview.md as contracts; :46 creates the `nightly-bug` label on first use, and no such label exists (`gh label list`, audit observation, 2026-10-19), so the bug hunt has never opened a PR or issue.
  - [routines/README.md:12](../../../.claude/routines/README.md): closing a nightly PR is the rejection signal.
- **Problem**: The routines rely on the team merging or closing their PRs, and nobody has yet, so product research now ends with "no PR tonight". One of the waiting PRs (#47) is a direct guard for a golden rule. The bug hunt reads stale contracts and has filed nothing so far, and because it files nothing when it finds nothing, a silent failure can't be told apart from a clean night.
- **Recommendation**: Triage nightly PRs within a day or two: merge or close each with a one-line reason, starting with #42 and #47. Point both prompts at how-it-works.md and backend/README.md, and fix the frontend description. Have the bug hunt post a short run summary even when it finds nothing. Consider running product research weekly.
- **Impact**: Turns about 60 agent runs a month into reviewed improvements, and ships the fact guard (#47) and the hashtag cap (#42) that resolve [open-questions.md:40](../../open-questions.md).
- **Verifier note**: Partly true but premature. The routines were backed up in the repo on 2026-10-18 (commit `6584e58`), and the first nightly PR, #37, opened at 05:02 UTC that day. The bug hunt (08:00 UTC daily) has had about two runs, and #37, #42 and #47 are about 1.5 days old, from a hackathon weekend, so "has never produced anything" and "paid runs producing nothing" overstate it. Valid: issue #58 shows product research stopped because those PRs were still open, the bug-hunt prompt describes a frontend that doesn't exist, and both prompts read target-design docs (data-model.md, overview.md, mvp.md, tasks.md).

### DOC-13: Review and CI blind spots: Tenki skips prompts and migrations, no frontend CI, Dependabot ignores uv and npm

- **Severity**: medium · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [tenki-review.yml:15-21](../../../.github/workflows/tenki-review.yml): triggers only on `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, so prompt `.md` and migration `.sql` changes get no AI review; :46-48 one review per PR, so pushes after the first aren't re-reviewed.
  - [ci.yml:6-7](../../../.github/workflows/ci.yml): "Add the frontend job in its own PR"; :146-151 the CI gate needs no frontend job.
  - [README.md:58](../../../README.md): frontend lint and build are a manual step.
  - [ADR 0029](../../decisions/0029-designed-slides-ai-scene-code-layout.md): the frontend `/api/render` route renders every designed Slide.
  - [dependabot.yml:1-3](../../../.github/dependabot.yml): "add uv … and the frontend's ecosystem when those projects get a manifest"; both have manifests now.
  - [frontend/package.json](../../../frontend/package.json): `next` pinned to 16.4.2 exactly, with no automated security bumps.
  - [AGENTS.md:21](../../../AGENTS.md): describes CI as markdownlint, docs index and actionlint, omitting the backend job.
- **Problem**: The highest-risk changes for Owners (prompt edits, schema migrations) skip AI review. The frontend, now in the Post-rendering hot path, has no lint, type or build gate on PRs, so a backend PR that changes the render spec can merge while the frontend side breaks. Next.js and Python dependency security fixes arrive only if someone remembers.
- **Recommendation**: Add backend prompt `.md` and migration `.sql` paths to Tenki's trigger. Add a frontend CI job (`npm ci`, `npm run lint`, `npm run build`, which includes the type check) to the CI gate, or require the Vercel preview check in the ruleset. Add Dependabot entries for uv (`/backend`) and npm (`/frontend`), grouped weekly. Fix AGENTS.md:21.
- **Impact**: Closes the review gap on behaviour-defining files and catches render-route breakage before Vercel production.
- **Verifier note**: Confirmed. A mitigation the auditor missed: Vercel builds a preview for every pushed branch ([frontend/README.md](../../../frontend/README.md)), `next build` type-checks, and `next.config.ts` has no `ignoreBuildErrors`, so a broken frontend build already shows as a Vercel deployment status on the PR. It just isn't required by the ruleset, and lint doesn't run there.
- **Related**: [FE-15](frontend.md), [OPS-13](platform-ops.md), [OPS-14](platform-ops.md), [OPS-16](platform-ops.md), [OPS-17](platform-ops.md), [SEC-17](security-privacy.md)

### DOC-14: Self-merge with no second human review, including on the Approval and publishing guard

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [AGENTS.md:97](../../../AGENTS.md): "Approvals are not required: authors may merge their own PRs"; [workflow.md:61](../../workflow.md) says the same.
  - `gh pr list --state merged`: `reviewDecision` is empty on all 56 merged PRs, and 54 were merged by their author (audit observation, 2026-10-19).
  - There is no `CODEOWNERS` file in `.github/`, `docs/` or the repo root (audit observation, 2026-10-19).
  - [approval.py](../../../backend/app/conversation/approval.py) and [publish.py](../../../backend/app/posts/publish.py): the code enforcing [ADR 0007](../../decisions/0007-approve-every-post.md).
  - [AGENTS.md:117](../../../AGENTS.md): "AI output is reviewed by a human".
- **Problem**: Self-merge was fine for a 24-hour hackathon. In a pilot, a single unreviewed change to Approval matching, publish idempotency or a migration can publish without Approval or corrupt Owner data, which breaks the product's core promise ([PRODUCT.md:56](../../../PRODUCT.md)). Today the only reviewer is the author plus a one-shot AI review.
- **Recommendation**: Optional hardening for the pilot: add CODEOWNERS for `approval.py`, `posts/`, `publishing/`, `migrations/` and the prompts, and require a code-owner review only on those paths. Keep self-merge elsewhere.
- **Impact**: Adds a second pair of eyes exactly where a mistake breaks "nothing publishes without Aprobar", at almost no cost to speed.
- **Verifier note**: Facts confirmed, with one count corrected: 54 PRs (not 56) were merged by their author. Severity drops to low: Approval is enforced in deterministic code with unit tests ([tasks.md:201,325](../../implementation/tasks.md)), CI must pass, and code PRs get a Tenki review. The remaining risk is a logic bug that slips past tests and AI review, so code-owner review on a few paths is a cheap hardening step, not a pressing gap.

### DOC-15: open-questions.md is stuck in hackathon framing, with resolved and obsolete items not closed

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [open-questions.md:3](../../open-questions.md): "To decide before the hackathon"; :6 hackathon rules; :10 demo materials.
  - [open-questions.md:24-25](../../open-questions.md): the dedicated number and recipient limit are unanswered, though in practice the CTA is the sandbox ([PRODUCT.md:36](../../../PRODUCT.md)) and Kapso's docs say it serves a single recipient.
  - [open-questions.md:30](../../open-questions.md): "If any of these fails within the hour".
  - [open-questions.md:37-38](../../open-questions.md): the Variations count and pick, open but unbuilt.
  - [open-questions.md:56-57](../../open-questions.md): Text Checker accuracy and fallback, although [ADR 0029](../../decisions/0029-designed-slides-ai-scene-code-layout.md) dropped the Text Checker.
  - [open-questions.md:40](../../open-questions.md): hashtags, answered by open PR #42.
  - [open-questions.md:76](../../open-questions.md): Zernio connect params, moot under [ADR 0024](../../decisions/0024-mvp-single-demo-instagram-account.md); :103 "before the hackathon".
- **Problem**: The risk register no longer reflects real risks. Pilot blockers sit next to obsolete hackathon checks, and [AGENTS.md:67](../../../AGENTS.md) ("tick resolved items") isn't followed. The nightly research agent reads this file to pick ideas.
- **Recommendation**: Archive the hackathon-only items. Tick the obsolete Text Checker items, citing ADR 0029. Answer the Kapso recipient-limit question from Kapso's docs. Move the pilot blockers into the DOC-1 checklist and link them from here.
- **Impact**: One accurate risk list for the pilot and better input for the nightly agents.
- **Verifier note**: Confirmed, including that ADR 0029:20 says "The Text Checker is dropped" and that hashtags are pending PR #42. It is docs hygiene with limited impact, so severity drops to low; pilot blockers are better consolidated under DOC-1.

### DOC-16: Env var docs are split across three places and have drifted from the code

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [setup.md:39](../../implementation/setup.md) `TRANSCRIBE_FALLBACK`, :43-44 `OPENAI_*`, :58 `MAX_CONCURRENT_JOBS` (hardcoded at [runner.py:26](../../../backend/app/jobs/runner.py)), :68-72 `META_*`: none read by [config.py](../../../backend/app/config.py).
  - [config.py:30,34-36](../../../backend/app/config.py): `GEMINI_IMAGE_SIZE`, `RENDERER`, `RENDERER_URL`, `RENDERER_SECRET` are missing from setup.md's table; only [backend/README.md:80](../../../backend/README.md) has the renderer.
  - [config.py:48,54,60](../../../backend/app/config.py): `NICHE_REPORT_PATH`, `KAPSO_BASE_URL` and `ZERNIO_BASE_URL`; the auditor listed all three as missing from [backend/.env.example](../../../backend/.env.example), but only the last two are (`NICHE_REPORT_PATH` is at line 50, commented out).
  - [config.py:42,56-57](../../../backend/app/config.py): stale comments ("until Supabase Storage (T17)", "until the database exists"); the auditor also cited :46-47.
- **Problem**: Someone setting up a new environment (staging, DOC-4) from setup.md misses the renderer variables, so designed Posts silently come out as bare scenes with `RENDERER=mock`. They also set variables that do nothing. There are three overlapping sources: setup.md, backend/README.md and `.env.example`.
- **Recommendation**: Make `backend/.env.example` the complete list, with a pytest that checks every `Settings` field appears there. In setup.md, add the renderer, image-size and niche-report variables, and mark the variables that aren't built yet (`TRANSCRIBE_*`, `OPENAI_*`, `MAX_CONCURRENT_JOBS`) as not read by the code. Fix the stale comments in `config.py`.
- **Impact**: Faster, correct environment setup, which the staging environment and any new engineer need.
- **Verifier note**: Partly confirmed: the unread and missing variables and the stale comments at `config.py:42,56-57` are real, and `KAPSO_BASE_URL` and `ZERNIO_BASE_URL` are missing from `.env.example` (both have defaults). Corrections: `NICHE_REPORT_PATH` is in `.env.example`, commented out with an example; the `META_*` variables sit in a clearly labeled "Plan B only" table, not among live settings; and the renderer variables are in backend/README.md's production table, so a production or staging setup following that README would not miss them.

### DOC-17: how-it-works.md says conversation history is lost on restart; the code persists it

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: adjusted
- **Evidence**:
  - [how-it-works.md:167](../../architecture/how-it-works.md): "the conversation and the posts live in memory and are lost on every restart"; :171 lists "Conversation history (InMemoryHistory)" as in memory only.
  - [factory.py:55-58](../../../backend/app/conversation/factory.py): `DbHistory` and `DbNotes` whenever `DATABASE_URL` is set ("ADR 0030: with the database, the conversation and the notes survive a deploy").
  - [backend/README.md:101](../../../backend/README.md): correctly says history is in Postgres, but labels the link "ADR 0028" while it points to 0030.
- **Problem**: The only accurate as-built doc, merged on 2026-10-19 in PR #62, is wrong about what survives a deploy, which is exactly what the on-call person needs to know when a pilot Owner says "se olvidó de lo que hablamos". Two docs now contradict each other.
- **Recommendation**: Fix how-it-works.md's "What survives a restart" table: conversation steps, the Conversation summary and Owner notes are in Postgres when `DATABASE_URL` is set; Posts, chat photos, served JPEGs and the dedupe store are in memory. Fix the ADR link label in backend/README.md.
- **Impact**: Correct incident triage and Owner messaging after deploys.
- **Verifier note**: Confirmed exactly; [ADR 0030](../../decisions/0030-orchestrator-memory-and-context.md) (line 12) agrees with the code. It is a two-line doc fix, so severity drops to low.
- **Related**: [ARCH-15](backend-architecture.md)

### DOC-18: Trend notes depend on a local file path, and there is no "how to add a niche or category" guide

- **Severity**: medium · **Effort**: S · **Confidence**: medium · **Verified**: confirmed
- **Evidence**:
  - [config.py:46-48](../../../backend/app/config.py): `niche_report_path`, a report saved by the CLI, is the trend notes "until the weekly job saves them in niche_reports (T19)".
  - [factory.py:59](../../../backend/app/conversation/factory.py): `trend_notes = load_trend_notes(settings.niche_report_path)`.
  - `NICHE_REPORT_PATH` is absent from [backend/README.md](../../../backend/README.md)'s production table (lines 72-81).
  - [niches.py:46](../../../backend/app/agents/data/niches.py): one niche, `curated-wood-furniture-uy`.
  - [categories.ts](../../../frontend/lib/categories.ts): per-category examples, audiences and brand words.
  - [ADR 0025](../../decisions/0025-weekly-niche-report.md) plans a weekly run, but [tasks.md:261](../../implementation/tasks.md) says T58, the weekly job, is not built, and `niche_reports` is in no migration.
- **Problem**: Unless someone set `NICHE_REPORT_PATH` by hand on Railway, which is undocumented and needs a file in the container, production Posts get no trend notes, and the ADR 0025 feature exists only on a developer laptop. Onboarding a pilot Owner outside furniture (a restaurant, a clothing shop) needs coordinated edits to `niches.py`, `categories.ts`, a research doc and a manual CLI run, and none of it is written down.
- **Recommendation**: Record in backend/README.md that production has no trend notes today (`out/` is excluded from the image). Before relying on trend notes, add the `niche_reports` migration and read the latest report per Business niche from the database (T58), instead of one global file. Write `docs/operations/add-a-niche.md` covering the `niches.py` entry, the `categories.ts` entry, the research doc and the `niche_cli` run.
- **Impact**: Makes the Niche Report actually affect pilot Posts, and makes adding the next vertical a 1-hour task instead of guesswork.
- **Verifier note**: Confirmed, and understated: [backend/.dockerignore](../../../backend/.dockerignore) excludes `out/`, so the documented `NICHE_REPORT_PATH=out/niche-report.json` can never exist in the production image. There is also a cross-vertical problem: `factory.py:59` builds a single Post drafter with one `trend_notes` value for every Business, so a set report would give furniture trends to a restaurant.

### DOC-19: No release notes or deploy traceability

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - `git tag` and `gh release list` return nothing, and there is no `CHANGELOG` file (audit observation, 2026-10-19).
  - [backend/README.md:48](../../../backend/README.md) and [frontend/README.md:36](../../../frontend/README.md): every push to `main` deploys production on Railway and Vercel.
  - [backend/README.md:95-99](../../../backend/README.md): on rollback, migrations are not undone.
- **Problem**: When a pilot Owner reports that something changed or broke, there is no quick way to map "Tuesday afternoon" to a deploy and its PRs. Owners also never hear about new features (for example scheduling, once built), which is a missed retention moment.
- **Recommendation**: Adopt release-please (or a weekly `docs/releases/YYYY-MM-DD.md` generated from the Conventional Commits) and tag production deploys. Add a short Spanish "novedades" message pattern for features Owners can use, sent inside the 24-hour window or later as an approved template.
- **Impact**: Faster incident correlation and a lightweight Owner-engagement channel.
- **Verifier note**: Confirmed; low severity is appropriate.

### DOC-20: Glossary drift: built concepts are missing, and unbuilt or legacy ones remain

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [glossary.md:15](../../glossary.md): a Business "whose day-to-day operations the assistant helps with", the framing from before [ADR 0013](../../decisions/0013-focus-marketing.md).
  - [glossary.md:94,98-101](../../glossary.md): a Post is "the Variation the Owner picked"; no code file uses "variation".
  - Terms used in code and ADRs but missing from the glossary: Designed slide, Template family and Scene ([ADR 0029](../../decisions/0029-designed-slides-ai-scene-code-layout.md); `TemplateFamily` in [schemas.py](../../../backend/app/carousel/schemas.py)), Revision ([store.py:18](../../../backend/app/posts/store.py), "replaced"), Magic link, Tier or Plan ([ADR 0031](../../decisions/0031-pricing-free-basic-pro.md)), Trend notes, Post Drafter.
  - [store.py:35](../../../backend/app/posts/store.py): Posts are keyed by `sender`, a phone number, not by Business.
  - [glossary.md](../../glossary.md): all 22 terms are still `Status: draft`.
- **Problem**: [AGENTS.md:115](../../../AGENTS.md) asks everyone to use glossary terms, but the glossary misses the vocabulary of the built Post pipeline and keeps a term (Variation) for a feature that isn't built. The code keys Posts by phone number rather than Business, which will matter once a Business has more than one number or a staff member.
- **Recommendation**: Run a domain-modeling pass. Remove Variation or mark it "not built". Fix Business. Add Designed slide, Template family, Scene, Revision, Magic link, Plan or Tier, and Trend notes. Settle the stable terms (Owner, Business, Post, Approval) as accepted. Open an issue to key Posts by `business_id` when T17 moves them to the database.
- **Impact**: Shared language for pilot issues and prompts, and less ambiguity for agents.
- **Verifier note**: Confirmed; the docstring at `store.py:64` also says Posts are kept per sender until T19.

### DOC-21: Small broken or incorrect references the docs check doesn't catch

- **Severity**: low · **Effort**: S · **Confidence**: high · **Verified**: confirmed
- **Evidence**:
  - [.claude/skills/README.md:33](../../../.claude/skills/README.md): use-railway links `../../docs/decisions/0012-backend-host-railway.md`, which doesn't exist; Railway is [ADR 0017](../../decisions/0017-backend-host-railway.md).
  - [check_docs_index.py:9-10](../../../scripts/check_docs_index.py): skips all of `.claude/skills/`, including the team-owned README, and doesn't check anchors.
  - [frontend/README.md:37](../../../frontend/README.md): `vercel link --project build101`, while line 32 says the project is `neitorai`.
  - [architecture/README.md:8-12](../../architecture/README.md), [product/README.md:7-10](../../product/README.md) and [implementation/README.md:7-9](../../implementation/README.md): dates say 2026-10-17 for files last changed on 2026-10-18 or 2026-10-19.
  - [AGENTS.md:17](../../../AGENTS.md): the frontend has a "dashboard, WhatsApp simulator", neither built.
  - [.claude/rules/python.md](../../../.claude/rules/python.md) project table: build backend "TBD", while [pyproject.toml:20-21](../../../backend/pyproject.toml) uses hatchling.
- **Problem**: Each one is small, but each sends a reader or an agent to a wrong file or command. The manual Vercel link command may link the wrong project during an incident.
- **Recommendation**: Fix all of these in one sweep PR. Let `check_docs_index.py` include `.claude/skills/README.md` (skipping only vendored skill folders) and validate `#anchors` against headings. Drop the per-file Date column in the indexes, or derive it from git.
- **Impact**: Fewer dead ends for humans and agents, and catches future drift automatically.
- **Verifier note**: Confirmed in full: 0012 is the catalog ADR. The reviewer added that the README also describes the frontend as having a dashboard and simulator; on re-check, the root [README.md:21](../../../README.md) correctly marks both as planned, and the other place with the stale description is the bug-hunt prompt ([nightly-bug-hunt.md:12](../../../.claude/routines/nightly-bug-hunt.md)).
