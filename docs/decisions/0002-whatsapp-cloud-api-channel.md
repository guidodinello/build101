# 0002: WhatsApp as the channel from day one

- Date: 2026-10-17
- Status: proposed
- Extended by: [0014](0014-whatsapp-cloud-api.md) (policy stance, voice notes; superseded by [0020](0020-whatsapp-via-kapso.md))
- Provider revised by: [0020](0020-whatsapp-via-kapso.md) (Kapso on top of the Cloud API instead of Meta directly)

## Context

The target owner lives in WhatsApp and doesn't use dashboards. Options were a web/PWA chat first, WhatsApp first, or both. Meta restricts general-purpose AI assistants on the WhatsApp Business API since Jan 15, 2026, and production numbers need business verification.

## Decision

The owner talks to the orchestrator on WhatsApp from the MVP, through the **Meta WhatsApp Cloud API directly** (no BSP), using the free test number (setup in [architecture/integrations.md](../architecture/integrations.md#plan-b-meta-cloud-api-direct)) for the demo. All channel code sits behind a `ChannelPort`; a **web simulator** implements the same port for development and as the stage fallback.

## Consequences

- Best possible demo of "zero learning curve".
- Pre-hackathon setup needed: Meta app, permanent System User token, verified recipient numbers (max 5 on the test number).
- Policy risk for a public launch stays open (see [open-questions.md](../open-questions.md)); our use case is task-specific, which fits the allowed use.
- Proactive messages outside the 24h window need approved templates (post-MVP). Until then, notifications for posts scheduled beyond the window may not be delivered (see [integrations.md](../architecture/integrations.md#receiving)).
