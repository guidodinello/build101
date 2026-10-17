# MVP definition

Context: built in a **24-hour hackathon** by **2 people**, as a demo that must later grow into a real product without a rewrite. That means: real integrations where the demo needs them, simple infrastructure, and clean seams (interfaces) where we cut corners.

## Demo goal

In ~4 minutes on stage, show a real furniture business owner going from **zero to a published, on-brand Instagram post and Reel, driven from WhatsApp**, with the agents doing the work and the owner only answering questions, loading their Catalog and material from a web link, and tapping "Aprobar". Why the Catalog and Reels are in scope: [ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md).

## Success criteria (demo day)

1. A new phone number messages the WhatsApp bot and completes onboarding (WhatsApp + web form) in under 5 minutes.
2. The system produces a Brand Brain that the owner recognizes as "their brand" (summary shown in WhatsApp).
3. The owner receives a weekly plan of 3 posts and approves it.
4. Each post arrives as an image + caption with **Aprobar / Cambiar / Descartar** buttons.
5. A change request in natural language ("más corto y mencioná el envío gratis") produces a revised post.
6. An approved post is **really published** on the business's Instagram, and the bot replies with the link.
7. An ad-hoc request ("hacé un post para la promo del finde") produces a post without going through the weekly plan.
8. From the dashboard link, the owner adds Products to the Catalog and uploads photos and videos, and the agents use them in the next plan.
9. An approved Reel made from the owner's video is **really published** on Instagram.
10. If WhatsApp or the publisher fails on stage, the same flow runs from the **web chat simulator** and the **mock publisher** (see fallbacks).

## Feature list and priority

Priority uses MoSCoW for the 24h build: **Must** = the demo fails without it; **Should** = build if Must is done by hour 16; **Could** = only if everything else is solid; **Won't** = explicitly out of scope.

### F1 — WhatsApp conversation (orchestrator)

| ID | Feature | Priority |
|---|---|---|
| F1.1 | Receive text messages via WhatsApp Cloud API webhook; reply with text | Must |
| F1.2 | Interactive reply buttons (approve / change / discard, plan approval) | Must |
| F1.3 | Send images and videos (Post and Reel previews) with caption | Must |
| F1.4 | Orchestrator (LLM with tools) answers free text and routes to agents in Rioplatense Spanish | Must |
| F1.5 | Receive photos and videos sent in the chat and store them as Brand assets | Should |
| F1.6 | "Typing"/progress messages for long jobs ("Lo estoy armando, dame un minuto ⏳") | Must |
| F1.7 | Voice notes transcribed (Whisper) | Could |
| F1.8 | Proactive messages outside the 24h window (approved templates) | Won't (demo) |

### F2 — Onboarding

| ID | Feature | Priority |
|---|---|---|
| F2.1 | First contact in WhatsApp: welcome, ask business name, send magic link | Must |
| F2.2 | Web onboarding form (mobile-first): business info, Products (unlimited, ≥ 1), questionnaire, logo + photos and videos upload | Must |
| F2.3 | Connect Instagram account through the publishing provider's hosted connect flow | Must |
| F2.4 | Asset Analyst describes photos and extracts logo colors | Must |
| F2.5 | Brand Strategist generates the Brand Brain; summary sent to WhatsApp for confirmation | Must |
| F2.6 | Owner corrects the Brand Brain in chat ("no somos formales, somos re cercanos") | Could |
| F2.7 | Fully conversational onboarding (no web) | Won't |

### F3 — Strategy & calendar

| ID | Feature | Priority |
|---|---|---|
| F3.1 | Content Strategist creates a weekly plan (default 3 posts) from the Brand Brain | Must |
| F3.2 | Plan sent to WhatsApp as a readable list with Aprobar plan / Cambiar buttons | Must |
| F3.3 | Plan changes in natural language | Could |
| F3.4 | Calendar view on the web dashboard | Could |

### F4 — Content creation

| ID | Feature | Priority |
|---|---|---|
| F4.1 | Copywriter writes caption, hashtags, CTA and on-image headline | Must |
| F4.2 | Art Director chooses template + photo + text; renderer produces a branded 1080×1350 JPEG | Must |
| F4.3 | At least 3 templates (product highlight, promo, tip/quote) | Must (2) / Could (3+) |
| F4.4 | Revision loop from natural-language feedback | Must |
| F4.5 | Ad-hoc post requests outside the plan | Must |
| F4.6 | AI-generated images (no key available yet) | Could, behind an interface |
| F4.7 | Carousels, stories, edited video (cuts, overlays, music) | Won't |
| F4.8 | Reels from the owner's own video, unedited, with a Copywriter caption and a cover frame | Must |

### F5 — Approval & publishing

| ID | Feature | Priority |
|---|---|---|
| F5.1 | Approval enforced in code: nothing publishes unless `post.status = approved` | Must |
| F5.2 | Publish now to Instagram via the unified publishing API; reply with the permalink | Must |
| F5.3 | Schedule for a date/time (provider-side scheduling) | Should |
| F5.4 | Facebook Page cross-post | Could |
| F5.5 | Mock publisher (demo fallback, local dev) | Must |

### F6 — Web app

| ID | Feature | Priority |
|---|---|---|
| F6.1 | Onboarding wizard (see F2.2, F2.3) | Must |
| F6.2 | Web chat simulator that talks to the same orchestrator as WhatsApp | Must (dev + demo fallback) |
| F6.3 | Editable dashboard: Catalog, Brand assets, Offers, plus the Brand Brain and posts with status (read-only) | Must |
| F6.4 | Edit Brand Brain from the web | Won't |

### F7 — Platform

| ID | Feature | Priority |
|---|---|---|
| F7.1 | One business per WhatsApp number (multi-tenant data model) | Must |
| F7.2 | Agent run log (inputs, outputs, latency, tokens) for debugging | Must |
| F7.3 | Plans and usage limits in the data model, not enforced | Should |
| F7.4 | Billing, user accounts, roles | Won't |

### F8 — Catalog & content

| ID | Feature | Priority |
|---|---|---|
| F8.1 | Products CRUD in the dashboard (name, description, optional price and category; archive instead of delete) | Must |
| F8.2 | Photo and video upload library in the dashboard: multi-upload with progress, straight to storage | Must |
| F8.3 | Asset Analyst analyzes videos from keyframes extracted with ffmpeg (no transcription) | Must |
| F8.4 | Best video frames saved as derived photo Brand assets, usable in image Posts | Should |
| F8.5 | Brand asset ↔ Product links: the Asset Analyst suggests, the owner corrects | Should |
| F8.6 | Offers (pack or promo) defined by the owner in the dashboard | Should |
| F8.7 | Add Products and Offers from the chat ("agregá la silla Oslo a $4500") | Should |
| F8.8 | Extract Products from a price-list photo or PDF, for the owner to confirm | Could |
| F8.9 | The Agency suggests Offers (packs, promos) | Won't (post-MVP) |

Limits: photos up to 10 MB (JPEG, PNG, WebP, HEIC); videos MP4 or MOV up to 300 MB and 15 min. A video is **reel-suitable** when it lasts 3–90 s (Zernio's Reel cap) and is roughly vertical. Storage is Supabase Pro; uploads go from the browser straight to storage with signed upload URLs ([research](../research/media-uploads.md)).

Dashboard access: a `dashboard` magic link, editable, valid 7 days; the owner gets a new one by writing "link" or "¿dónde veo todo?". Removing material only archives it: published and scheduled Posts are unaffected, draft Posts that use it are flagged for review.

## Explicitly out of scope

Paid ads, email, SEO, analytics, comment/DM replies, multiple users per business, team roles, billing, languages other than Spanish, TikTok/LinkedIn publishing, video editing, audio transcription of videos.

## Demo fallbacks

| Risk on stage | Fallback |
|---|---|
| WhatsApp webhook/number fails | Run the same flow from `/dev/chat` (web simulator). Same orchestrator, same buttons. |
| Publishing provider fails or IG token expires | Switch `PUBLISHER=mock`; show the rendered post + "would publish" log. Keep a **pre-published post** on the IG account as proof. |
| Reel publish is slow or fails (video processing on Instagram's side) | Same `PUBLISHER=mock` switch; keep a **pre-published Reel** on the IG account as proof and show the cover + caption from the dashboard preview. |
| Uploading a large video on conference Wi-Fi | The demo video is already in the seeded business's library; live upload only shows a photo. |
| LLM latency spikes | Pre-generate the Brand Brain and weekly plan for the demo business the night before; show live generation only for the ad-hoc post. |
| Conference Wi-Fi | Mobile hotspot; the backend is deployed, not local. |

## Definition of done for the hackathon

- All **Must** features work end-to-end on the deployed environment (Vercel + backend host + Supabase) with the demo business.
- The demo script ([demo-script.md](demo-script.md)) has been rehearsed twice end to end, including one fallback switch.
- `README.md` explains how to run it locally in under 10 minutes.
