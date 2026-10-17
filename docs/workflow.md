# Development workflow with Claude Code

How we take a task from "ready" to merged on `main`. It is the hands-on version of steps 5–7 of the workflow loop in [AGENTS.md](../AGENTS.md#the-workflow-loop); follow both. Everyone on the team uses this loop so PRs look the same and get reviewed the same way.

## The loop

| # | Step | You do | Done when |
|---|---|---|---|
| 1 | Pick the task | Take a task from [implementation/tasks.md](implementation/tasks.md) (or an issue) and create its branch from the latest `main` | Branch exists, named per [AGENTS.md § Build](../AGENTS.md#5-build) |
| 2 | Plan | Start Claude Code in plan mode with `opusplan` (below), point it at the task and the docs it links | Claude presents a plan with an **Open questions** section |
| 3 | Review the plan | Read the whole plan. Answer every open question; send corrections with "Tell Claude what to change" until the plan matches the task, the ADRs and the contracts in [architecture/api.md](architecture/api.md) | You would sign the plan as written |
| 4 | Implement | Approve with **"Yes, and use auto mode"**. Claude implements, runs lint and tests, and commits | Lint clean, tests green, docs updated (step 7 of AGENTS.md) |
| 5 | Open the PR | Push and open the PR with the [template](../.github/pull_request_template.md) | `CI` runs on the PR |
| 6 | Wait for review | `CI` must go green. Code PRs get a Tenki review automatically (a few minutes) | Tenki posted its review (code PRs) |
| 7 | Address the review | Run the `address-pr-comments` skill: it fixes valid findings, declines the rest with evidence, pushes, and replies to every thread | Every thread has a reply; `CI` green again |
| 8 | Merge | Squash-merge and delete the branch | The change is on `main` |

## Starting Claude Code

```bash
claude --model opusplan --permission-mode plan
```

- `opusplan` uses Opus while planning and Sonnet while executing: the expensive model where judgment matters, the cheap one for the edits.
- Plan mode means Claude investigates and proposes, but writes nothing until you approve.
- A good first prompt names the task and asks for open questions, e.g. "Implement T20 from docs/implementation/tasks.md. Read the docs it links, then write a plan with an explicit Open questions section."

## Reviewing the plan (step 3)

The plan review is where most mistakes are caught; approving a plan you did not read is how drift starts.

- Check it against the task's acceptance criteria, the relevant ADRs and the interfaces in [architecture/api.md](architecture/api.md).
- Answer the open questions yourself when the docs already decide them. Product, security or legal forks go to the team (issue or ADR), not into a plan answer.
- Long answers: write them to a file in the worktree (not committed) and tell Claude to read it, instead of pasting into the prompt.

## Review comments (step 7)

- Treat Tenki's findings as claims to verify, not orders. Fix what is real; decline what is not with a concrete reason (code, docs or ADR).
- Every thread gets a reply before merging, even the declined ones.
- Docs-only PRs get no automatic Tenki review (to save credits). Comment `@tenki-reviewer` on the PR to ask for one, or to re-review after pushes.

## Merging (step 8)

- The `main` ruleset requires only the `CI` check. It does **not** block on unresolved review threads or require approvals, so "every thread answered" is a team rule you check yourself before merging.
- Squash merge, with the PR title as the commit title (Conventional Commits).

## Rules that always apply

- Never `--no-verify`. If a hook fails for an unrelated reason, fix it in a separate commit or ask.
- No secrets, tokens or personal data in code, fixtures, logs or PRs: the repo is public. Test fixtures use synthetic values.
- AI output is reviewed by a human before it lands (AGENTS.md golden rules): you read the plan before approving it and the diff before merging it.
- Stacked PRs (a branch built on another open PR): say so in "Notes for reviewers" and merge the base PR first.
