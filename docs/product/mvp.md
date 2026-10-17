# MVP definition

Context: built in a **24-hour hackathon** by **2 people**, as a demo that must later grow into a real product without a rewrite. That means: real integrations where the demo needs them, simple infrastructure, and clean seams (interfaces) where we cut corners.

## Demo goal

In ~4 minutes on stage, show a real furniture business owner doing a **short onboarding** (WhatsApp + the web form) and then, from WhatsApp, **sending photos and asking for a post in their own words**. The bot asks at most one question, AI-generated variations of the image arrive ([ADR 0018](../decisions/0018-ai-image-generation-service.md)), the owner picks one and approves it by tapping or writing "subilo", and it is **really published** on Instagram with the link sent back. The Owner can also ask for a carousel in the same chat ([ADR 0022](../decisions/0022-carousels-in-mvp.md)). Every Must below is on stage; everything else waits ([ADR 0016](../decisions/0016-demo-scope-one-post.md)).

## Success criteria (demo day)

1. A new phone number messages the WhatsApp bot and completes onboarding (WhatsApp + short web form) in under 5 minutes.
2. The system produces a Brand Brain that the owner recognizes as "their brand" (summary shown in WhatsApp).
3. After the owner confirms the brand, the bot opens the chat ("¿En qué te puedo ayudar hoy?") instead of pushing a plan.
4. The owner sends photos and a request in their own words ("me llegó esta mesa ratona nueva, armame algo para subir") and, after at most one question, gets generated image variations that still show the real product, picks one, and gets it with its caption and **Aprobar / Cambiar / Descartar** buttons.
5. Approving by button or by writing ("subilo") **really publishes** the post on the business's Instagram, and the bot replies with the permalink.
6. Asking for a carousel ("armame un carrusel con estas fotos") returns 3 to 5 numbered slides whose text comes from the copy, then the preview; "cambiá la 3" redoes only that slide, and approving publishes the carousel ([ADR 0022](../decisions/0022-carousels-in-mvp.md)).
7. If WhatsApp, the image service or the publisher fails on stage, the same flow runs from the **web chat simulator**, the **fallback image provider** (or the mock) and the **mock publisher** (see fallbacks).

The weekly plan, revisions, scheduling, the dashboard and Reels are no longer demo criteria; they are Should or Could below.

## Feature list and priority

Priority uses MoSCoW for the 24h build: **Must** = the demo fails without it; **Should** = build if Must is done by hour 16; **Could** = only if everything else is solid; **Won't** = explicitly out of scope.

### F1 — WhatsApp conversation (orchestrator)

| ID | Feature | Priority |
|---|---|---|
| F1.1 | Receive text messages via the WhatsApp webhook (Kapso, [ADR 0020](../decisions/0020-whatsapp-via-kapso.md)); reply with text | Must |
| F1.2 | Interactive reply buttons (approve / change / discard, plan approval) | Must |
| F1.3 | Send images (Post variations, carousel slides and previews) with caption; video previews belong to F4.8 | Must |
| F1.4 | Orchestrator (LLM with tools) answers free text and routes to agents in Rioplatense Spanish | Must |
| F1.5 | Receive photos sent in the chat and store them as Brand assets (videos in the chat: Could) | Must |
| F1.6 | "Typing"/progress messages for long jobs ("Lo estoy armando, dame un minuto ⏳") | Must |
| F1.7 | Voice notes transcribed (Kapso's transcript, Gemini as fallback) and handled like text ([ADR 0021](../decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md)) | Must |
| F1.8 | Proactive messages outside the 24h window (approved templates) | Won't (demo) |
| F1.9 | Match the owner's writing style: short replies to short messages, fuller ones to long messages | Should |
| F1.10 | Open chat after onboarding: the bot asks "¿En qué te puedo ayudar hoy?" instead of offering the weekly plan | Must |

### F2 — Onboarding

| ID | Feature | Priority |
|---|---|---|
| F2.1 | First contact in WhatsApp: welcome, ask business name, send magic link | Must |
| F2.2 | Web onboarding form (mobile-first, 6 steps as in the [mockups](../design/mockups/README.md)): business info, up to 5 Products, logo (optional, with a "Todavía no tengo logo ni colores" option) and colors, 3–15 photos (no videos), questionnaire | Must |
| F2.3 | Connect Instagram account through the publishing provider's hosted connect flow | Must |
| F2.4 | Asset Analyst describes photos and extracts logo colors | Must |
| F2.5 | Brand Strategist generates the Brand Brain; summary sent to WhatsApp for confirmation | Must |
| F2.6 | Owner corrects the Brand Brain in chat ("no somos formales, somos re cercanos") | Could |
| F2.7 | Fully conversational onboarding (no web) | Won't |
| F2.8 | Import photos and videos from the owner's Instagram feed after connecting; the owner unticks what not to use (read access not verified) | Could |
| F2.9 | Build colors (and optionally a simple logo) in the chat when the owner has none: the bot proposes 3 palettes from a photo | Could |

### F3 — Strategy & calendar

| ID | Feature | Priority |
|---|---|---|
| F3.1 | Weekly plan on request ("armame el plan de la semana"): Content Strategist plans 3 posts from the Brand Brain | Should |
| F3.2 | Plan sent to WhatsApp as a readable list with Aprobar plan / Cambiar buttons | Should |
| F3.3 | Plan changes in natural language | Could |
| F3.4 | Calendar view on the web dashboard | Could |
| F3.5 | Ideas on request ("no sé qué subir esta semana"): the bot proposes 3 ideas, the owner picks | Should |

### F4 — Content creation

| ID | Feature | Priority |
|---|---|---|
| F4.1 | Copywriter writes caption, hashtags and CTA (no text goes on an image Post; a carousel's slide text comes from the Copywriter, F4.9) | Must |
| F4.2 | Art Director picks reference photos and writes the image prompt; a third-party image service generates several variations, resized to 1080×1350 JPEG ([ADR 0018](../decisions/0018-ai-image-generation-service.md), [ADR 0019](../decisions/0019-image-provider-gemini.md)); the owner picks one | Must |
| F4.3 | ~~At least 3 templates~~: dropped, there are no templates since [ADR 0018](../decisions/0018-ai-image-generation-service.md) | — |
| F4.4 | Revision loop from natural-language feedback | Should |
| F4.5 | Ad-hoc post from text and/or photos sent in the chat; the bot asks **at most one** short question first when it helps (angle, price, what to highlight). The demo's core | Must |
| F4.6 | ~~AI-generated images behind an interface~~: now the main path, see F4.2 | — |
| F4.7 | Stories, edited video (cuts, overlays, music). Carousels moved to F4.9 ([ADR 0022](../decisions/0022-carousels-in-mvp.md)) | Won't |
| F4.8 | Reels from the owner's own video, unedited, with a Copywriter caption and a cover frame ([ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md)) | Could |
| F4.9 | Carousels on request: 3–5 designed slides (or the Owner's number, up to 10) with text from the Copywriter, generated by the image service anchored on the cover, text-checked; one carousel per request, redo of specific slides ("cambiá la 3"), published as one Instagram carousel ([ADR 0022](../decisions/0022-carousels-in-mvp.md)) | Must |

### F5 — Approval & publishing

| ID | Feature | Priority |
|---|---|---|
| F5.1 | Approval enforced in code: nothing publishes unless `post.status = approved` | Must |
| F5.2 | Publish now to Instagram via the unified publishing API; reply with the permalink | Must |
| F5.3 | Schedule for a date/time (provider-side scheduling) | Should |
| F5.4 | Facebook Page cross-post | Could |
| F5.5 | Mock publisher (demo fallback, local dev) | Must |
| F5.6 | Approve and publish by writing ("subilo", "dale, publicalo"); schedule by writing ("subilo mañana a la tarde") | Must (publish) / Should (schedule) |

### F6 — Web app

| ID | Feature | Priority |
|---|---|---|
| F6.1 | Onboarding wizard (see F2.2, F2.3) | Must |
| F6.2 | Web chat simulator that talks to the same orchestrator as WhatsApp | Must (dev + demo fallback) |
| F6.3 | Read-only dashboard: the Brand Brain and posts with status. The editable Catalog, content and Promos tabs are F8 | Should |
| F6.4 | Edit Brand Brain from the web | Won't |

### F7 — Platform

| ID | Feature | Priority |
|---|---|---|
| F7.1 | One business per WhatsApp number (multi-tenant data model) | Must |
| F7.2 | Agent run log (inputs, outputs, latency, tokens) for debugging | Must |
| F7.3 | Plans and usage limits in the data model, not enforced | Should |
| F7.4 | Billing, user accounts, roles | Won't |

### F8 — Catalog & content

The direction from [ADR 0012](../decisions/0012-catalog-content-dashboard-reels.md); all Could for the hackathon ([ADR 0016](../decisions/0016-demo-scope-one-post.md)).

| ID | Feature | Priority |
|---|---|---|
| F8.1 | Products CRUD in the dashboard (name, description, optional price and category; archive instead of delete) | Could |
| F8.2 | Photo and video upload library in the dashboard: multi-upload with progress, straight to storage | Could |
| F8.3 | Asset Analyst analyzes videos from keyframes extracted with ffmpeg (no transcription) | Could |
| F8.4 | Best video frames saved as derived photo Brand assets, usable in image Posts | Could |
| F8.5 | Brand asset ↔ Product links: the Asset Analyst suggests, the owner corrects | Could |
| F8.6 | Offers (pack or promo) defined by the owner in the dashboard | Could |
| F8.7 | Add Products and Offers from the chat ("agregá la silla Oslo a $4500") | Could |
| F8.8 | Extract Products from a price-list photo or PDF, for the owner to confirm | Could |
| F8.9 | The Agency suggests Offers (packs, promos) | Won't (post-MVP) |

Limits when F8 is built: photos up to 10 MB (JPEG, PNG, WebP, HEIC); videos MP4 or MOV up to 300 MB and 15 min. A video is **reel-suitable** when it lasts 3–90 s (Zernio's Reel cap) and is roughly vertical. Storage is Supabase Pro; uploads go from the browser straight to storage with signed upload URLs ([research](../research/media-uploads.md)).

Dashboard access: a `dashboard` magic link, editable, valid 7 days; the owner gets a new one by writing "link" or "¿dónde veo todo?". Removing material only archives it: published and scheduled Posts are unaffected, draft Posts that use it are flagged for review.

## Explicitly out of scope

Paid ads, email, SEO, analytics and comment/DM replies (both in the [roadmap](../roadmap.md), Phase 1), multiple users per business, team roles, billing, languages other than Spanish, TikTok/LinkedIn publishing, Instagram stories, video editing, audio transcription of videos.

## Demo fallbacks

| Risk on stage | Fallback |
|---|---|
| WhatsApp webhook/number fails | Run the same flow from `/dev/chat` (web simulator). Same orchestrator, same buttons. |
| Publishing provider fails or IG token expires | Switch `PUBLISHER=mock`; show the generated post + "would publish" log. Keep a **pre-published post** on the IG account as proof. |
| Image service fails, blocks or is slow | Switch `IMAGE_GEN=openai` (fallback provider, [ADR 0019](../decisions/0019-image-provider-gemini.md)), only if T43 is built and the OpenAI org is verified; otherwise `IMAGE_GEN=mock` (the Owner's photo, resized). Keep variations generated during rehearsal as proof. |
| Brand generation is slow on stage | Keep a pre-generated Brand Brain for the demo business; if generation passes ~60 s, load it with the dev seed and continue from the brand summary. |
| LLM latency spikes during the post | Narrate the wait with the progress message; the pre-published post on the IG account is the proof if it doesn't arrive. |
| Conference Wi-Fi | Mobile hotspot; the backend is deployed, not local. |

## Definition of done for the hackathon

- All **Must** features work end-to-end on the deployed environment (Vercel + backend host + Supabase) with the demo business.
- The demo script ([demo-script.md](demo-script.md)) has been rehearsed twice end to end, including one fallback switch.
- `README.md` explains how to run it locally in under 10 minutes.
