# 0014: WhatsApp via the official Cloud API

- Date: 2026-10-17
- Status: proposed

## Context

WhatsApp is non-negotiable as the owner's interface. [ADR 0002](0002-whatsapp-cloud-api-channel.md) already puts the owner on WhatsApp from day one through the Cloud API (test number for the demo); this record adds the policy stance and voice notes. Since Jan 15, 2026 Meta bars general-purpose AI chatbots (where the AI itself is the product) from the WhatsApp Business API, while task-specific business bots stay allowed.

## Decision

Use the official WhatsApp Cloud API and pay its fees. The bot is task-specific (it runs the business's social media); it is not an open-ended assistant. Voice notes are downloaded via the API and transcribed by us, since the API doesn't transcribe them (F1.7, *Could* in the MVP: [product/mvp.md](../product/mvp.md)).

## Consequences

- Keep the bot scoped: off-topic requests get a polite redirect.
- Re-check Meta's WhatsApp Business Solution terms before launching beyond the pilot; Meta decides what counts as a primary use case.
- Messages outside the 24-hour window (e.g. sale alerts) need approved templates, which cost money.
