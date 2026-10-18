# 0031: Launch pricing is Free, Basic US$29 and Pro US$49

- Date: 2026-10-18
- Status: proposed

## Context

The [roadmap](../roadmap.md#pricing) carried a draft of Basic ~US$8, Pro ~US$20 and Plus TBD, and the landing page showed it as "draft". The team set the launch prices, and wants owners to try the product before paying.

## Decision

Two paid plans, billed monthly, plus a small free tier:

| Tier | USD/month | Includes |
|---|---|---|
| Free | 0 | Up to 3 posts or carousels a month from the owner's photos, approved on WhatsApp and published to Instagram; no card |
| Basic | 29 | Posts and carousels from photos, publish now or scheduled, weekly content plan, every post approved on WhatsApp |
| Pro | 49 | Everything in Basic, plus replies to comments and DMs, sale alerts and a weekly results summary as they ship |

Plus is dropped from launch; reels, more posts and multiple accounts are left for a later tier.

## Consequences

- The landing page shows Free, Basic and Pro, without the "draft" label. Pro stays a waitlist ("Join the Pro list") until its features ship.
- The free tier costs us LLM, image and WhatsApp spend per owner with no revenue, so its post cap must be enforced in the backend once billing exists ([roadmap Phase 2](../roadmap.md#phase-2-many-businesses-23-months)).
- Post limits for Basic and Pro are still open ([open-questions.md](../open-questions.md#product-post-hackathon)).
