# The idea

## One-liner

An **AI marketing agency in your WhatsApp**: a small business owner answers a few questions about their business, and a team of specialized AI agents plans, creates and publishes their social media content. Every post goes out only after the owner approves it in the chat.

## Where this comes from

The original idea was an owner-facing AI "chief of staff" that runs day-to-day operations from the chat app the owner already uses. Marketing is the **first vertical** of that vision. It is a job owners know they should do, rarely have time for, and can't afford to hire an agency for. The output (posts) is visible and easy to judge, which makes it a strong demo. The same architecture (an orchestrator in WhatsApp + specialist agents + approval before acting) extends later to other jobs: suppliers, follow-ups, orders.

## Problem

Small business owners in Latin America know social media sells, but:

- They don't have time to plan, write and design posts every week.
- An agency or community manager costs more than they can justify.
- DIY tools (Canva, Meta Business Suite, ChatGPT) still assume they will sit at a computer, learn the tool, and do the work themselves.
- The result: inconsistent posting, off-brand content, or an abandoned Instagram.

## Target user

**Primary persona: Laura, 52, owns a small furniture business in Montevideo.**

- Sells custom and ready-made furniture; has a workshop, 2–4 employees, and an Instagram account with a few thousand followers that she updates "when she can".
- Lives in WhatsApp: talks to clients, suppliers and staff there all day. Sends voice notes. Doesn't use dashboards.
- Has good product photos on her phone, a logo, and a clear sense of her style, but can't articulate a "content strategy".
- Wants: more inquiries via Instagram/WhatsApp, a professional-looking feed, zero extra work.
- Fears: posting something that looks fake or "not like us", losing control of her account.

The demo uses a real furniture business owned by a teammate (see [product/demo-script.md](product/demo-script.md)).

## Value proposition

> "Tenés una agencia de marketing en tu WhatsApp. Vos aprobás, ella hace el resto."

1. **Zero learning curve.** Everything happens in a WhatsApp conversation, in Rioplatense Spanish. The only web step is a 5-minute onboarding form opened from a link in the chat.
2. **It knows your brand.** Onboarding builds a *Brand Brain* (tone, colors, products, audience, content pillars) that every agent uses, so content sounds and looks like the business.
3. **A team, not a tool.** A strategist, a copywriter, an art director and a publisher work for the owner, coordinated by one account manager (the orchestrator).
4. **You stay in control.** Nothing is published without an explicit "Aprobar" tap.

## Scope of this product (MVP)

The MVP covers three marketing jobs for Instagram (Facebook optional):

1. **Strategy & calendar** — a weekly content plan built from the Brand Brain.
2. **Content creation** — caption + branded image for each planned post, plus one-off posts on request ("hacé un post de la promo del finde").
3. **Publishing** — publish now or schedule, after approval.

Full scope, cut lines and success criteria: [product/mvp.md](product/mvp.md).

## Not this (for now)

- Answering the business's own customers (comment and DM replies, sales). It's the next step after the MVP ([ADR 0013](decisions/0013-focus-marketing.md), [roadmap](roadmap.md) Phase 1), not part of the hackathon build.
- Paid ads management (Meta Ads / Google Ads).
- Email marketing, SEO, websites.
- Analytics and reporting beyond "published / scheduled" status (a weekly Instagram Insights summary is in the [roadmap](roadmap.md), Phase 1).
