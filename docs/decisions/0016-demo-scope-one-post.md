# 0016: Demo scope is one post, from request to published

- Date: 2026-10-17
- Status: proposed

## Context

[ADR 0012](0012-catalog-content-dashboard-reels.md) made the editable dashboard and Reels *Must*, on top of the weekly plan, revisions and scheduling. That is too much for 24 hours with 2 people. The second design pass ([design/mockups/](../design/mockups/README.md)) also moved the product toward a free-form chat: after onboarding the bot asks "¿En qué te puedo ayudar hoy?" instead of pushing a weekly plan; the Owner sends photos and asks for a post in their own words; approving and scheduling happen by writing ("subilo mañana a la tarde"); the bot matches the Owner's writing style. The wizard went back to a short form (up to 5 products, 3 to 15 photos), and added optional Instagram feed import and a chat path for Owners with no logo or colors.

Alternatives: keep ADR 0012's Musts and add the new design on top (rejected: no time); demo only the post with a pre-onboarded business (rejected: the onboarding is part of the story the team wants to show).

## Decision

The demo shows a **short onboarding** (WhatsApp + the web form) and then **one post**: the Owner sends a photo and asks for a post, the bot asks at most one question, the preview arrives, the Owner approves it by tapping or writing, and it is **really published** on Instagram. Only what that demo needs is *Must*. The weekly plan, revisions, scheduling, ideas on request, style matching and the read-only dashboard move to *Should*; the editable dashboard (Catalog and content uploads), Reels and video, Instagram feed import and building the brand in the chat move to *Could*; stories stay *Won't*.

ADR 0012's model (Products, Offers, videos, Reels) stays the product direction; only its priorities change.

## Consequences

- A smaller, more reliable demo; every Must is on stage.
- The wizard returns to the design's limits (up to 5 products, 3 to 15 photos, no videos), so more material comes from photos sent in the chat.
- Instagram feed import needs read access to the Owner's media, through Zernio or the Instagram API; not verified yet.
- After the hackathon, the order of work is Should first (plan, revisions, scheduling, dashboard), then ADR 0012's Catalog and Reels.
