# 0015: Connect Instagram through Instagram Login

- Date: 2026-10-17
- Status: proposed

## Context

The bot must publish, read comments and answer DMs on the owner's account, securely. [ADR 0008](0008-publishing-via-zernio.md) publishes through Zernio, which runs its own Instagram Login connect flow, so the MVP never needs our own Meta app. Zernio's publishing covers the MVP; reading comments, answering DMs and reading Insights are not part of it.

## Decision

Use Meta's Instagram API with Instagram Login (OAuth) in our own Meta app for what Zernio doesn't cover: comments, DMs and Insights ([roadmap](../roadmap.md) Phase 1). The owner authorizes our app; we store a revocable token, never a password. Requires a Business or Creator account. Publishing stays on Zernio for the MVP; this app is also the fallback publisher behind the `PublisherPort` if Zernio fails.

## Consequences

- Demo/pilot: dev mode with the account added as a tester, no App Review.
- Serving other businesses requires App Review for Advanced Access (estimated at weeks, not days).
- Two Instagram connections per business (Zernio and ours) until we decide whether to move publishing to our app; the owner should see this as one step.
