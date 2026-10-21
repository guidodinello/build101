# Glossary

> Draft. Terms are still being refined with [idea.md](idea.md); challenge them in an issue or PR.

The shared language for Neitor AI (repository: build101): an owner-facing AI assistant for small businesses, living in the chat app the Owner already uses. Its first vertical is marketing: an AI marketing agency in WhatsApp. Format: [GLOSSARY-FORMAT.md](../.claude/skills/domain-modeling/GLOSSARY-FORMAT.md).

## Language

**Owner**:
The person who runs a small Business and is the only one who talks to the assistant directly.
_Avoid_: User, customer, admin
_Status_: draft

**Business**:
The small company the Owner runs, whose day-to-day operations the assistant helps with.
_Avoid_: Client, account, store
_Status_: draft

**Channel**:
The chat app through which the Owner talks to the assistant (e.g. WhatsApp, Telegram, a chat PWA).
_Avoid_: Platform, integration, interface
_Status_: draft

**Pilot list**:
The WhatsApp numbers the team let into the closed pilot; only they can onboard, talk to the Agency and publish, and any other number gets one waitlist reply a day and nothing else.
_Avoid_: Allowlist, whitelist, beta list
_Status_: draft

**Voice note**:
An audio message the Owner records in the Channel, which the assistant reads as its transcript.
_Avoid_: Audio, voice message, voice (reserved for the Brand Brain's brand voice)
_Status_: draft

## Marketing agency

**Agency**:
The team of AI agents that does the Business's marketing on the Owner's behalf, presented to the Owner as one account manager.
_Avoid_: Bot, tool, app
_Status_: draft

**Orchestrator**:
The agent the Owner talks to in the Channel; it understands requests and hands work to Specialists.
_Avoid_: Chatbot, assistant (when the distinction from Specialists matters)
_Status_: draft

**Specialist**:
An agent with one marketing job (strategy, copy, art direction, asset analysis), shared by every Business and personalized by its Brand Brain.
_Avoid_: Sub-agent, worker
_Status_: draft

**Brand Brain**:
Everything the Agency knows about one Business's brand (voice, audience, content pillars, products, colors, constraints), versioned as the Owner corrects it.
_Avoid_: Brand profile, brand kit, context
_Status_: draft

**Owner note**:
A fact about the Business or a standing preference the Owner asked the Agency to keep ("no poner precios", "abrimos sábados"); every agent follows it, and it wins over the Brand Brain when they conflict. See [ADR 0030](decisions/0030-orchestrator-memory-and-context.md).
_Avoid_: Memory, preference, setting
_Status_: draft

**Conversation summary**:
What the Orchestrator keeps of the older part of its conversation with the Owner, once those messages leave its view. See [ADR 0030](decisions/0030-orchestrator-memory-and-context.md).
_Avoid_: Memory, recap, context
_Status_: draft

**Niche Report**:
A weekly summary of what is working on social media in the Business's niche (themes, formats, hooks), with sources; it shapes the angle and look of Posts, never their facts. See [ADR 0025](decisions/0025-weekly-niche-report.md).
_Avoid_: Trend report, market research, insights
_Status_: draft

**Brand asset**:
A logo, photo or video the Owner provided, sent through the Channel or the web, that the Agency learns from and can use in Posts.
_Avoid_: Media, upload, content
_Status_: draft

## What the Business sells

**Product**:
Something the Business sells, described by the Owner (name, description, optional price and category) and shown in its Brand assets.
_Avoid_: Item, SKU, listing
_Status_: draft

**Catalog**:
All the Products of one Business; the Brand Brain summarizes only its most important ones.
_Avoid_: Inventory, store, shop
_Status_: draft

**Offer**:
A commercial proposal the Owner has defined with its conditions (price or discount, validity), either a pack of Products sold together or a promo; the Agency may suggest one, but it exists only once the Owner confirms it.
_Avoid_: Deal, discount, campaign
_Status_: draft

**Content plan**:
The set of Posts proposed for one week, which the Owner approves as a whole before the Posts are created.
_Avoid_: Calendar, schedule
_Status_: draft

**Post**:
One piece of content for a social network that goes through creation, Approval and publishing: an image (the Variation the Owner picked) with its caption, a Carousel, or a Reel.
_Avoid_: Publication, piece
_Status_: draft

**Variation**:
One of the candidate images an AI image service generates for an image Post from the Owner's photos; the Owner picks one, and Approval covers only that one.
_Avoid_: Version, render (in owner-facing Spanish, "opción" is fine)
_Status_: draft

**Carousel**:
A Post made of several Slides, in order, that read as one piece; the Owner gets one per request and approves it as a whole.
_Avoid_: Album, gallery, slideshow (in owner-facing Spanish, "carrusel" is fine)
_Status_: draft

**Slide**:
One image of a Carousel, showing the Owner's real product with a short text written by the Agency; the Owner can ask to redo a single Slide.
_Avoid_: Page, card, Variation
_Status_: draft

**Reel**:
A Post made from one of the Owner's videos, published as-is, or from a clip generated from a Post's product image ([ADR 0033](decisions/0033-ai-generated-reels-veo.md)); the caption and cover frame are chosen by the Agency.
_Avoid_: Video post, clip, story
_Status_: draft

**Video request**:
The Owner asking, in their own words, for a Reel made from the product photo of a Post they already got; it makes a new Post beside the original, which stays as it is. Only exists while `VIDEO_GEN_ENABLED` is on, and is capped per day.
_Avoid_: Reel order, animate button
_Status_: draft

**Approval**:
The Owner's explicit yes to a specific Post (a button tap, "subilo", a "sí" to the publish question, or a 👍 / ✅ reaction to that exact question message); nothing is published without it.
_Avoid_: Confirmation, sign-off
_Status_: draft
