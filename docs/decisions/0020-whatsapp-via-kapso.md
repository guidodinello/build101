# 0020: WhatsApp through Kapso

- Date: 2026-10-17
- Status: proposed

## Context

This record supersedes [ADR 0014](0014-whatsapp-cloud-api.md) and revises the provider choice in [ADR 0002](0002-whatsapp-cloud-api-channel.md) ("Meta WhatsApp Cloud API directly, no BSP"). ADR 0002's other choices stand: the Owner talks to the Agency on WhatsApp from the MVP, all channel code sits behind `ChannelPort`, and the web simulator implements the same port.

We are at the hackathon and there is no channel code yet. Going to Meta directly needs about an hour of setup (a Meta app with the WhatsApp product, a System User with a permanent token, the webhook), and its free test number can only message up to 5 verified recipients.

[Kapso](https://kapso.com) is a platform for the official WhatsApp API, built on top of Meta's Cloud API. Facts read 2026-10-17:

- Pricing ([kapso.com/pricing](https://kapso.com/pricing)): Free plan $0/month with 2,000 messages/month, 1 connected number plus a free pre-verified US number, and $2 in credits; Pro $25/month. Meta's own fees are passed through "at cost, with no markup".
- A REST API ([API introduction](https://docs.kapso.ai/api/introduction.md)); the official SDK is TypeScript only, there is no Python SDK.
- Webhooks ([overview](https://docs.kapso.ai/docs/platform/webhooks/overview.md)) with signatures ([security](https://docs.kapso.ai/docs/platform/webhooks/security.md)) and documented retries and ordering ([advanced](https://docs.kapso.ai/docs/platform/webhooks/advanced.md)).
- Sending reply buttons ([buttons](https://docs.kapso.ai/docs/whatsapp/send-messages/buttons.md)) and images ([image](https://docs.kapso.ai/docs/whatsapp/send-messages/image.md)).
- A sandbox for testing that only messages the registered recipient and sends no templates ([sandbox](https://docs.kapso.ai/docs/how-to/whatsapp/use-sandbox-for-testing.md)).

Not verified yet (a teammate is testing Kapso now; see [open questions](../open-questions.md)): whether the free US number is dedicated to us and delivers webhooks to our backend, the recipient limit, whether webhook payloads match Meta's format, the exact auth header and the names of the values we must configure, and how inbound media (photos, voice notes) is downloaded.

## Decision

- Connect the Owner's WhatsApp through **Kapso**, calling its **REST API** from the Python backend with `httpx`, behind the existing `ChannelPort`. A Kapso adapter replaces the planned direct Meta adapter; nothing outside the adapter knows about Kapso.
- The **web simulator** stays the stage fallback and the dev channel.
- **Meta Cloud API directly** is plan B: if Kapso fails the first-hour test, we build the Meta adapter documented in [integrations.md](../architecture/integrations.md#plan-b-meta-cloud-api-direct) behind the same port.
- Kept from ADR 0014: the bot is task-specific (it runs the Business's marketing), not an open-ended assistant, and off-topic requests get a polite redirect. Voice notes are transcribed by us if F1.7 (*Could*) is built, since WhatsApp doesn't transcribe them; how Kapso hands us the audio file is not known yet.
- The same inbound rules as before: verify the webhook signature, return `200` fast, dedupe by the WhatsApp message id.

## Consequences

- One more intermediary between the Owner and us, with its own outages, limits and terms; `ChannelPort` keeps the switch to Meta direct cheap.
- Meta's policy risk is unchanged: Meta still decides whether an AI marketing assistant counts as an allowed task-specific use, so re-check its WhatsApp Business terms before launching beyond the pilot.
- Meta's fees are separate from Kapso's plan (Kapso passes them through at cost). Messages outside the 24-hour window still need approved templates, which cost money; the sandbox sends none.
- The free plan's 2,000 messages/month covers the demo and a small pilot; Pro is $25/month.
- Webhook payload parsing and media download stay unbuilt until the first-hour test confirms Kapso's formats.
