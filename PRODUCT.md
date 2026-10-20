# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Small business owners in Latin America (first market: Uruguay) who know social media sells but have no time, skill or budget to run it. Primary persona: the owner of a small furniture business in Montevideo, 50s, 2–4 employees, an Instagram account updated "when she can". Lives in WhatsApp all day (clients, suppliers, staff), sends voice notes, does not use dashboards. Has good product photos on the phone, a logo and a clear sense of style, but no "content strategy". Wants more inquiries and a professional feed with zero extra work; fears posts that look fake or "not like us" and losing control of the account.

Secondary audience for the landing page: hackathon judges and early investors evaluating the product. The landing copy is in Rioplatense Spanish like the rest of the product: the owner is who it's for, and the product speaking the owner's language is part of the pitch.

## Product Purpose

Neitor AI is an AI marketing agency that lives in the owner's WhatsApp. The owner answers a few questions about the business; a team of specialized AI agents (strategist, copywriter, art director, publisher), coordinated by one account manager, plans, creates and publishes their Instagram content. Nothing is published without the owner's explicit "Approve". Success: the owner posts consistently, on-brand, with minutes per week instead of hours.

## Positioning

Every competitor makes the owner operate software (Sintra, Predis, Canva, Meta Business Suite) or talks to the business's customers (WhatsApp sales bots). Neitor AI is a team that works for the owner inside the chat they already live in, in their own language, with approval before anything goes out. Pitch line: "Other tools give you a team you have to manage. We give you one person who manages the team for you."

## Operating Context

- The whole relationship happens in a WhatsApp conversation: text, photos, voice notes, reply buttons ("Approve", "Change").
- The only web step is a ~5-minute onboarding form opened from a link in the chat (business, products, logo and colors, photos, tone).
- Onboarding builds a Brand Brain (voice, audience, content pillars, products, colors) every agent uses.
- Typical loop: the owner sends a product photo and asks for a post → gets a branded preview with caption → taps Approve or asks for a change → it publishes to Instagram now or on schedule.

## Capabilities and Constraints

- MVP: image posts and carousels from the owner's real photos (AI-generated branded images, product never altered), captions in the brand voice, publish now or schedule on Instagram, voice notes understood, weekly content plan on request.
- Roadmap, not shipped: replies to comments and DMs, sales flow, weekly Insights summary, Reels from the owner's videos, Facebook/TikTok.
- Not in scope: paid ads, email marketing, SEO, websites.
- Launch pricing ([ADR 0031](docs/decisions/0031-pricing-free-basic-pro.md)): Free (up to 3 posts or carousels a month, no card), Basic US$29/month (content from photos, scheduled publishing, weekly plan), Pro US$49/month (+ comment and DM replies, sales notifications, metrics; waitlist until those ship). Billed monthly.
- Primary CTA: start the conversation on WhatsApp (`https://wa.me/56920403095`, the shared Kapso sandbox number, which only answers phones with an active sandbox session).

## Brand Commitments

- Name: **Neitor AI** (user-confirmed 2026-10-18).
- Owner-facing voice, landing page included, is Rioplatense Spanish (vos), warm and plain.
- No jargon toward owners: "your brand", not "Brand Brain", in owner-facing copy.

## Evidence on Hand

- Demo business: a real solid-wood furniture business owned by a teammate (see docs/product/demo-script.md).
- UI mockups of the WhatsApp flows, wizard and dashboard: docs/design/mockups/.
- No customers, testimonials, metrics, press or logos yet. Never fabricate them; any illustrative chat, post or business shown on the landing is synthetic and labeled or obviously a demo.

## Product Principles

1. The chat is the product: if it can't happen in WhatsApp, it should take minutes on the web, not a session.
2. The owner stays in control: nothing goes out without Approve.
3. It must look and sound like the business, never like generic AI.
4. One face, a whole team behind it: the owner never coordinates agents.

## Accessibility & Inclusion

Owners are often 45+ and phone-first: large type, high contrast, big tap targets, plain language.
