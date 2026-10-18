# Roadmap

## Phase 0: Hackathon demo (now)

One live loop, scoped by [ADR 0016](decisions/0016-demo-scope-one-post.md): a short onboarding (WhatsApp + the web form), then the owner sends a photo and asks for a post (or a carousel, [ADR 0022](decisions/0022-carousels-in-mvp.md)) on WhatsApp, approves the branded preview by tapping or writing "subilo", and it is published on Instagram. The owner can also talk in voice notes, which the bot reads as their transcript ([ADR 0021](decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md)). Script: [product/demo-script.md](product/demo-script.md); scope and priorities: [product/mvp.md](product/mvp.md). The earlier plan is kept in [demo-plan.md](demo-plan.md) (superseded).

## Phase 1: Pilot with one owner (2–4 weeks)

- Run it on the pilot owner's real account every day; log every correction the owner makes
- Finish the MVP's *Should* items: weekly plan on request and every Monday with Uruguayan commercial dates, ideas on request, revisions, scheduling by writing, matching the owner's style, read-only dashboard ([ADR 0016](decisions/0016-demo-scope-one-post.md))
- Replies to comments and DMs, sales flow and a WhatsApp alert to the owner on each sale, through our own Meta app with Instagram Login ([ADR 0013](decisions/0013-focus-marketing.md), [ADR 0015](decisions/0015-instagram-login.md))
- Brand voice learns from corrections, not only from past posts
- Catalog, content uploads and Offers in the dashboard; Reels v1 from the owner's own videos ([ADR 0012](decisions/0012-catalog-content-dashboard-reels.md))
- From the second design pass ([design/mockups/](design/mockups/README.md)), beyond the MVP:
  - Import the owner's Instagram feed after connecting, so the Agency starts with real material: built as an automatic import through our own Meta app ([ADR 0028](decisions/0028-read-instagram-with-our-meta-app.md)); the Wizard 6b review grid and video import remain
  - Build colors, and optionally a simple logo, in the chat when the owner has none (WA-Sin-marca; F2.9)
  - Instagram stories from a request ("el sábado abrimos el taller de 10 a 14, hacé una historia"): a vertical 1080×1920 generated image ([ADR 0018](decisions/0018-ai-image-generation-service.md)); publishing support through Zernio to verify (Chat 6; F4.7, Won't in the MVP)
- Designer agent: before/after layouts from real photos, through the same image service ([ADR 0018](decisions/0018-ai-image-generation-service.md)), never altering the product. Carousels with text slides are already in the MVP ([ADR 0022](decisions/0022-carousels-in-mvp.md))
- Reels v2: before/after video built from the photos (with royalty-free audio; Instagram's music library isn't available through the API)
- Basic metrics: weekly WhatsApp summary from Instagram Insights
- **Success metric**: hours per week the owner spends on social media, before vs. after; plus DMs answered and sales closed by the bot

## Phase 2: Many businesses (2–3 months)

- Self-serve onboarding stays in WhatsApp + the web form; connecting Instagram uses the official Instagram Login (OAuth). We never handle passwords
- Meta **App Review** for Advanced Access (needed once accounts outside our team connect) + Business Verification + a production WhatsApp number
- Decide whether publishing moves from Zernio to our own Meta app ([ADR 0008](decisions/0008-publishing-via-zernio.md), [ADR 0015](decisions/0015-instagram-login.md))
- Approval levels per business: approve everything / approve only posts / fully autonomous
- Payment links in the sales flow (e.g. Mercado Pago in Uruguay)
- Billing + tiers

## Phase 3: Grow

- Facebook, TikTok, Marketplace
- Paid ads suggestions based on what performs
- Back-office operations (the original "chief of staff" idea)

## Pricing (draft)

| Tier | ~USD/month | Includes |
|---|---|---|
| Basic | 8 | Content from photos + scheduled publishing + weekly plan |
| Pro | 20 | + replies to comments and DMs, sales + owner notifications, metrics |
| Plus | TBD | + reels, more posts, multiple accounts |

To validate: WhatsApp and LLM costs per active business must fit well under the Basic price.
