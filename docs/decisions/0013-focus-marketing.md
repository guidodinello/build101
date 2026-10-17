# 0013: Focus the MVP on marketing and social media

- Date: 2026-10-17
- Status: proposed

## Context

The first draft was an owner-facing operations assistant (follow-ups, suppliers, staff). Talking to real owners (for example, a small business owner who sells bags), the pain that repeats is social media: the owner already does it, but it doubles their workload.

## Decision

The product is an AI community manager (the Agency in the [glossary](../glossary.md)): content from the owner's photos, Instagram publishing, replies to comments and DMs, sales, weekly plan and metrics. Operations are out of scope for now.

The hackathon MVP builds only the first slice, content from the owner's photos and Instagram publishing ([ADR 0016](0016-demo-scope-one-post.md)). Replies to comments and DMs, sales and metrics follow in the [roadmap](../roadmap.md) (Phase 1).

## Consequences

- Once comments and DMs are in, the product becomes partly customer-facing, a crowded space; our difference is that the owner runs everything from WhatsApp and does nothing else. Until then it only talks to the owner ([idea.md](../idea.md#not-this-for-now)).
- Instagram is the first and main network.
- Reading comments and answering DMs needs our own Meta app ([ADR 0015](0015-instagram-login.md)); publishing in the MVP goes through Zernio ([ADR 0008](0008-publishing-via-zernio.md)).
