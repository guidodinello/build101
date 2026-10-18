# 0024: The MVP publishes to one demo Instagram account

- Date: 2026-10-17
- Status: proposed

## Context

F2.3 (connect the Owner's Instagram from the wizard) is a *Must* in [mvp.md](../product/mvp.md). It needs the database (T02: Business, magic-link token, `social_accounts`) and the wizard (T24, T25), none of which exist yet. [ADR 0008](0008-publishing-via-zernio.md) notes that Zernio's free tier has 2 connected accounts across the whole team, so the demo cannot connect many Instagram accounts anyway. The demo Instagram account is already connected by hand in Zernio, under one profile. [ADR 0016](0016-demo-scope-one-post.md) cuts the demo to one post, really published; it does not need a connect flow to show that. Details of the calls: [integrations.md § Zernio](../architecture/integrations.md#publishing-provider-zernio).

Alternative: build the per-Business connect endpoints and the wizard step first (rejected: they block on T02/T24/T25 and add no step the demo shows).

## Decision

The MVP publishes to **one demo Instagram account**. Its Zernio profile and account ids come from env (`ZERNIO_PROFILE_ID`, `ZERNIO_ACCOUNT_ID`) instead of `social_accounts`. `ensure_profile` and `connect_url` exist in the Zernio adapter, but nothing exposes them.

The per-Business connect flow (`/api/o/{token}/instagram/connect` + `/callback`, wizard step 6) moves out of the MVP: F2.3 becomes *Won't (MVP)*. F2.8 (importing the Owner's Instagram feed) goes out with it, because it depends on the Owner connecting their own account.

## Consequences

- Every Business in the demo publishes to the same Instagram account; there is no real multi-business onboarding.
- The wizard has no Instagram screen (step 6) and no feed import (6b); the demo script skips them.
- `PublisherPort` already takes the account id, so callers do not change. To reverse this once T02, T24 and T25 exist: build the connect endpoints and the wizard step, and read the ids from `social_accounts` instead of env.
