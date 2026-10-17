# AGENTS.md

How the build101 team works. This file is the single source of truth for the workflow, for humans and for any AI tool (Claude Code, Codex, Cursor, Copilot) or none. The goal: everything we learn and decide ends up in [`docs/`](docs/README.md), so the next person (or agent) starts from shared knowledge instead of a chat log.

## Where things live

| Path | What lives there |
|---|---|
| [`docs/`](docs/README.md) | Shared knowledge base: idea, competitors, open questions, research, decisions. Start here |
| [`docs/research/`](docs/research/README.md) | Investigations, spikes, competitor/market/tech research, policy reading |
| [`docs/decisions/`](docs/decisions/README.md) | ADRs (`NNNN-short-title.md`) + template + index |
| [`docs/glossary.md`](docs/glossary.md) | Shared domain language (Owner, Business, Channel, ...) |
| [`docs/open-questions.md`](docs/open-questions.md) | Risks and unknowns still to resolve |
| [`backend/`](backend/README.md) | Agent, integrations, APIs (Python + FastAPI, uv project root) |
| [`frontend/`](frontend/README.md) | Owner-facing UI / demo surface (stack TBD) |
| [`.claude/skills/`](.claude/skills/README.md) | Agent skills that automate the steps below; plain Markdown, readable by anyone |
| [`.claude/rules/`](.claude/rules/README.md) | Path-scoped coding rules (Python, database, Docker, CI) |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | CI: markdownlint, docs index check, actionlint; one aggregate `CI` check |
| [`scripts/`](scripts/) | Repo tooling (e.g. `check_docs_index.py`) |
| GitHub issues / PRs | Work items (issues) and changes under review (PRs) |

## The workflow loop

| # | Step | Output (where it lands) | Skill (Claude Code) |
|---|---|---|---|
| 1 | Capture | GitHub issue, `idea` label | — |
| 2 | Research | `docs/research/` + README indexes, summary in top-level docs | `docs-index` |
| 3 | Decide | ADR in `docs/decisions/`, terms in `docs/glossary.md` | `grill-with-docs`, `domain-modeling` |
| 4 | Plan | GitHub issues with acceptance criteria | `ticket-refinement` |
| 5 | Build | Branch + commits in `backend/` / `frontend/` | `configure-dependency` (+ rules); frontend: `impeccable`, `shadcn`, `vercel-react-best-practices`, `next-dev-loop` |
| 6 | Review | PR with review comments resolved | `code-review`, `address-pr-comments`; frontend: `web-design-guidelines` |
| 7 | Close the loop | `docs/` updated in the same PR | `docs-index`, `domain-modeling` |

Not every change walks all seven steps: a typo fix goes straight to 5. Anything that changes what we build or why passes through 3.

### 1. Capture

- **When**: you have an idea, a question, or want to challenge an assumption.
- **Steps**: open a GitHub issue with the **Idea / question** template ([`idea.md`](.github/ISSUE_TEMPLATE/idea.md), applies the `idea` label). Link related docs.
- **Done when**: the issue states the idea or question, why it matters, and the related docs.
- **Without a skill**: just open the issue in the GitHub UI or with `gh issue create --template idea.md`.

### 2. Research

- **When**: an issue or question needs evidence before it can be decided.
- **Steps**:
  1. Check the indexes first ([`docs/research/README.md`](docs/research/README.md)); extend an existing doc rather than starting a new one.
  2. Write to `docs/research/short-topic.md`, or a `docs/research/short-topic/` folder with its own `README.md` once a topic grows past one doc.
  3. Cite a source inline next to every claim; add the date read for anything that changes (pricing, terms, product pages).
  4. Update the `README.md` index of every folder you touched.
  5. Add a one-line summary + link in the relevant top-level doc ([`competitors.md`](docs/competitors.md), [`idea.md`](docs/idea.md)).
  6. New unknowns go to [`open-questions.md`](docs/open-questions.md).
- **Done when**: the doc is reachable from `docs/README.md` by following indexes, and every claim has a source. CI checks the indexes and links; run it locally with `uv run --no-project python scripts/check_docs_index.py`.
- **Public repo**: no personal data about interviewees or real users. Describe them generically (e.g. "owner of a small furniture business").
- **With Claude Code**: use `docs-index`. **Without it**: follow [its conventions](.claude/skills/docs-index/SKILL.md) by hand.

### 3. Decide

- **When**: research or discussion has settled something, or a choice blocks building.
- **Steps**:
  1. Challenge the proposal against existing docs, ADRs and glossary terms.
  2. Record an ADR in `docs/decisions/` using the template in [`docs/decisions/README.md`](docs/decisions/README.md): next `NNNN`, add a row to the index, link the research from Context.
  3. Add or refine terms in [`docs/glossary.md`](docs/glossary.md).
  4. Tick resolved items in [`open-questions.md`](docs/open-questions.md) (and in `idea.md` "To refine"), linking the ADR.
- **Does it deserve an ADR?** Yes if all three hold: **hard to reverse**, **surprising without context**, and **the result of a real trade-off**. Typical: channel, LLM provider, database, hosting, architectural shape, scope boundaries. Details: [ADR-FORMAT.md](.claude/skills/domain-modeling/ADR-FORMAT.md).
- **Done when**: the ADR is in the index with status `proposed` (open in a PR) or `accepted` (agreed by the team).
- **With Claude Code**: `grill-with-docs` (user-invoked interview that writes ADRs and glossary terms as answers settle) or `domain-modeling` (terminology and ADRs). **Without it**: discuss in the issue or PR, then write the ADR by hand from the template.

### 4. Plan

- **When**: a decision is ready to turn into work.
- **Steps**: break it into GitHub issues, each with context, deliverables, acceptance criteria and open questions, linked to the ADR or research behind it. Use glossary terms. Unrecorded decisions go under Open questions, not assumed.
- **Done when**: each issue is small enough for one PR and has testable acceptance criteria.
- **With Claude Code**: use `ticket-refinement` (drafts first, creates or updates the issue only after you approve). **Without it**: write the issue by hand with the same sections.

### 5. Build

- **When**: an issue is ready.
- **Steps**:
  1. One branch per issue: `<type>/<issue#>-short-slug` (e.g. `feat/12-telegram-webhook`, `docs/7-whatsapp-policy`). `<type>` matches the commit type.
  2. [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `chore:`, ...). Keep PRs small.
  3. New dependency or integration: read the official docs first, pin the version, and record an ADR if it is a stack choice or carries lock-in.
  4. Follow the matching rule file in [`.claude/rules/`](.claude/rules/README.md) (Python, database, Docker, CI). Claude Code loads them automatically; everyone else reads the one matching the files they touch.
  5. Backend commands run from `backend/` (per [python.md](.claude/rules/python.md)): `uv run ruff check .` clean and `uv run pytest tests/ -v` green before committing; never call `python3` directly, use `uv run python`.
- **Done when**: acceptance criteria met, lint clean, tests green, and the `CI` check is green on the PR.
- **With Claude Code**: `configure-dependency` for new dependencies (writes the ADR when it implies a stack choice). Frontend work: `impeccable` for design (`/impeccable init` once to write `PRODUCT.md`, then `shape` before building and `polish` before the PR), `shadcn` for components, `vercel-react-best-practices` while writing React, `next-dev-loop` to verify each change in the running app, and `web-design-guidelines` as a UI/accessibility check before opening the PR. **Without it**: same steps by hand.

### 6. Review

- **When**: the branch is ready for others.
- **Steps**:
  1. Open a PR using the [template](.github/pull_request_template.md). Link the issue (`Closes #N`) and the relevant ADR or research.
  2. Reviewer reviews against this file, accepted ADRs and the rules; author answers every thread (fix, decline with reason, or clarify).
  3. Enforced on `main` by a GitHub ruleset: the **`CI` check must pass**, so every change lands through a PR (direct pushes to `main` are rejected). Approvals are not required: authors may merge their own PRs once `CI` is green. Team convention: **squash merge**.
- **Done when**: every thread is answered and resolved, `CI` is green, step 7 done.
- **With Claude Code**: reviewer runs `code-review`; author runs `address-pr-comments`. **Without it**: review and reply in the GitHub UI.

### 7. Close the loop

- **When**: before merging any PR.
- **Steps**: check that `docs/` reflects what was learned: new terms in the glossary, new or superseded ADRs, resolved or new open questions, research indexed.
- **Done when**: a reader of `docs/` alone would know what changed and why. **A PR that changes behaviour or a decision without updating docs is not done.**

## Golden rules

- **`docs/` is the shared memory**, not chat, Slack or a single person's notes. If it matters, it is written there.
- **Cite sources** next to claims; date anything that changes.
- **Every `docs/` folder has a `README.md` index**; new docs are linked from it.
- **Decisions are ADRs**, never buried in PR comments or chat threads.
- **Use glossary terms** in code, docs, issues and PRs; challenge a term in an issue instead of inventing a synonym.
- **Public repo**: no secrets, credentials, tokens or personal data. `.env` is never committed (use `.env.example`).
- **AI output is reviewed by a human** before it lands in `docs/`, code, issues or PRs.

## For AI agents

- Read this file and [`docs/README.md`](docs/README.md) first.
- Navigate `docs/` through the `README.md` indexes before grepping; grep is the fallback.
- Follow the workflow loop above; anything not recorded in `docs/decisions/` is undecided, so do not assume it.
- Never create GitHub issues, PRs or comments without the human's explicit approval of the content.
- Write findings to `docs/` per steps 2–3 instead of only reporting them in chat.
- Skills in [`.claude/skills/`](.claude/skills/README.md) are plain Markdown; agents other than Claude Code can read and follow them as procedures.

## Reasoning discipline

> Adapted from [guidodinello/claude-dotfiles `guidelines/reasoning-discipline.md`](https://github.com/guidodinello/claude-dotfiles/blob/main/.claude/guidelines/reasoning-discipline.md) (MIT, see [THIRD_PARTY_NOTICES](.claude/THIRD_PARTY_NOTICES.md)).

Apply on any non-trivial task, especially before committing to an approach or declaring done.

- **Don't accept the offered options as the whole option space.** When handed a choice ("do A or B"), check what the framing excludes; the best answer is often a third option neither side named.
- **Verify claims against primary sources, not memory.** When a decision turns on how a tool, library or API behaves, read the actual source or official docs and quote it. Don't assert from recollection.
- **Verify empirically before declaring done.** Source-verified is not done: run it once and watch the expected signal. A passing self-test that doesn't check the real thing is not evidence.
- **Separate what's required from what was merely suggested.** Keep only the changes the goal actually needs; revert incidental edits.

## Debugging patterns

> Adapted from [guidodinello/claude-dotfiles `guidelines/debugging-patterns.md`](https://github.com/guidodinello/claude-dotfiles/blob/main/.claude/guidelines/debugging-patterns.md) (MIT, see [THIRD_PARTY_NOTICES](.claude/THIRD_PARTY_NOTICES.md)).

### Fix completeness verification

When fixing a bug that affects multiple consumers of a field or value, verify the fix is exhaustive before declaring done. Work in layers:

1. **Try the type system first.** Temporarily remove the field from the shared type and run the type checker (if the layer has one). If types are tight, every access site errors: exhaustive by definition. If types are loose or there is no checker, move to step 2.
2. **Search for explicit reads.** Search for the field name across the codebase. This catches attribute access, destructuring and string-keyed access. This is the consumer side.
3. **Recognize the blind spot: implicit propagation.** A text search misses cases where the full object is parsed and forwarded without naming the field, e.g. `json.loads(blob)` or `JSON.parse(blob)` returns a field silently if it is in the blob. No explicit access, no search hit.
4. **For the supply side, search structurally.** Instead of searching for the field name, search for the data-serving pattern: find every endpoint that returns the blob to callers. Verify each one either fetches and overlays the authoritative source, or doesn't feed any surface that uses the field.

The fix is complete when all explicit consumers are covered (search) and all implicit supply paths either overlay the authoritative source or are confirmed not to reach an affected surface (structural check).
