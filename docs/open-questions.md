# Open questions & risks

## To decide before the hackathon

- [ ] **Product name and assistant name.** Needed for the welcome message, the wizard header and the pitch (`ASSISTANT_NAME`).
- [ ] **Hackathon rules:** is pre-written code allowed? If not, only accounts, materials and these docs are prepared in advance (see [implementation/plan.md](implementation/plan.md#before-the-hackathon-checklist)).
- [ ] **Backend host:** confirm Tenki runs a Docker image with Chromium (≥ 1 GB RAM) and exposes HTTPS; otherwise Railway/Render.
- [ ] **Demo materials** from the furniture business (logo, photos, products, questionnaire answers, promo, permission to publish).

## Channel / platform risk

Meta restricted general-purpose AI chatbots on the WhatsApp Business API starting Jan 15, 2026.

- [x] Demo: use the Cloud API test number ([ADR 0002](decisions/0002-whatsapp-cloud-api-channel.md)).
- [ ] Before a public launch: read the current WhatsApp Business policy and confirm a task-specific marketing assistant for the owner's own business is allowed. Our position: it's not a general-purpose assistant; it only does marketing for the business.
- [ ] Production needs Meta business verification, an own phone number, and approved templates for proactive messages (e.g. "tu plan de la semana está listo").

## Publishing

- [ ] Confirm the exact query params Zernio appends to the connect redirect (log them in the pre-hackathon test).
- [ ] Zernio pricing beyond 2 accounts (per-account) vs. building our own Meta app with app review: decide when we have >10 businesses.

## Catalog, content and Reels

From [ADR 0012](decisions/0012-catalog-content-dashboard-reels.md); facts in [research/media-uploads.md](research/media-uploads.md).

- [ ] Reel length cap: Zernio documents 3–90 s, Meta 3 s–15 min. Test a 60 s and a 2-minute video through Zernio before the hackathon.
- [ ] WhatsApp video preview: confirm the media size limit for outbound video, and whether the cover + dashboard link fallback is enough.
- [ ] Transcribe video audio (faster-whisper in the backend container) in v1, so the Agency knows what is said in the Owner's videos?
- [ ] Agency-suggested Offers (F8.9): when and how the Agency proposes packs and promos (for example once a week inside the plan), post-MVP.
- [ ] Dashboard access without user accounts: anyone with a forwarded link can edit for 7 days. Acceptable until accounts exist (F7.4)?
- [ ] Supabase Pro (US$25/month) from day one: who pays for it during the hackathon, and storage cost per Business once Owners upload lots of video.

## Product (post-hackathon)

- [ ] Pricing: posts per month per plan? Free trial length?
- [ ] Should owners be able to switch to "auto mode" (approve the plan once, auto-publish)? See [ADR 0007](decisions/0007-approve-every-post.md).
- [ ] Which network after Instagram: Facebook (cheap, same provider) or TikTok (needs video)?
- [ ] Voice notes: owners in the region send many. Make transcription a Must for v1?
- [ ] Measuring results: do we pull Instagram insights to show "this post brought N messages"?
- [ ] How does this evolve back toward the broader "chief of staff" vision (suppliers, orders, follow-ups)? Which second vertical?

## Add yours below
