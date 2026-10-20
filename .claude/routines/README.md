# Routines

Scheduled cloud agents (Claude Code routines) that work on this repo unattended. Each one runs in Anthropic's cloud on a cron schedule, clones `guidodinello/build101`, and opens **draft** PRs (or issues) for a human to review. They never merge, approve or push to `main`.

The live routines are configured on claude.ai under the account that created them; this folder is their backup and source of truth. Each file holds the settings in its frontmatter and the prompt, verbatim, as its body.

| Routine | Runs | Opens | Label |
|---|---|---|---|
| [nightly-issue-fixer.md](nightly-issue-fixer.md) | Daily 01:00 Montevideo (`0 4 * * *` UTC) | Up to 2 draft PRs, each implementing one open issue end to end (`Closes #N`); issues labeled `nightly-fix` go first, then trusted-author `security`, `bug`, `nightly-bug` and `enhancement` issues that are code-only and decided | `nightly-fix` |
| [nightly-product-research.md](nightly-product-research.md) | Daily 03:00 Montevideo (`0 6 * * *` UTC) | Up to 2 draft PRs implementing ideas from competitor research, or 1 issue with the ranked ideas | `nightly-idea` |
| [nightly-bug-hunt.md](nightly-bug-hunt.md) | Daily 05:00 Montevideo (`0 8 * * *` UTC) | Up to 3 draft PRs fixing provable bugs, and up to 3 issues for bugs it could not fix safely | `nightly-bug` |

A `nightly-*` PR closed without merging tells the next runs that the team rejected that idea or fix, so they don't propose it again. To queue an issue for the issue fixer, add the `nightly-fix` label; to keep it away from an issue, assign the issue to someone.

## Changing or restoring a routine

- **Change**: edit the file here in a PR, then apply the same change to the live routine (`/schedule` in Claude Code, or [claude.ai/code/routines](https://claude.ai/code/routines)), so the two never drift.
- **Restore or move to another account**: run `/schedule` in Claude Code and ask it to create a routine from the file. The account needs GitHub connected (`/web-setup`) with push access to the repo.
- **Pause or delete**: only from [claude.ai/code/routines](https://claude.ai/code/routines).
