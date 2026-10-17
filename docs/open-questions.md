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

## Second design pass (ADR 0016)

From [ADR 0016](decisions/0016-demo-scope-one-post.md) and the [mockups](design/mockups/README.md).

- [ ] **Instagram feed import (F2.8, Could): can we read the Owner's existing media?** Zernio's `GET /v1/accounts/{accountId}/posts` lists the 25 most recent posts with a `picture` URL, but its docs don't say whether Instagram is supported or whether `picture` is full size; the Instagram Graph API (`GET /{ig-user-id}/media`) needs our own Meta app with read permissions, which [ADR 0008](decisions/0008-publishing-via-zernio.md) avoided. Test the Zernio endpoint on the demo account before the hackathon ([integrations.md](architecture/integrations.md#reading-the-owners-existing-instagram-media-could)). Until it works, the wizard must not promise the import.
- [x] **Stories:** the mockups show one (Chat-6), but stories are **Won't** for the MVP (F4.7). They would need a 1080×1920 render and story publishing through Zernio; revisit after Reels.
- [ ] **Approving by writing:** which phrases count as an explicit approval ("subilo", "publicalo", "dale") and which only as praise ("me encanta"). Start with the list in [agents.md](architecture/agents.md#conversation-rules) and tune it with the owner during rehearsal ([ADR 0007](decisions/0007-approve-every-post.md)).

## Catalog, content and Reels (Could)

From [ADR 0012](decisions/0012-catalog-content-dashboard-reels.md), moved to Could by [ADR 0016](decisions/0016-demo-scope-one-post.md); facts in [research/media-uploads.md](research/media-uploads.md).

- [ ] Reel length cap: Zernio documents 3–90 s, Meta 3 s–15 min. Test a 60 s and a 2-minute video through Zernio before the hackathon.
- [ ] WhatsApp video preview: confirm the media size limit for outbound video, and whether the cover + dashboard link fallback is enough.
- [ ] Transcribe video audio (faster-whisper in the backend container) in v1, so the Agency knows what is said in the Owner's videos?
- [ ] Agency-suggested Offers (F8.9): when and how the Agency proposes packs and promos (for example once a week inside the plan), post-MVP.
- [ ] Dashboard access without user accounts: anyone with a forwarded link can edit for 7 days. Acceptable until accounts exist (F7.4)?
- [ ] Supabase Pro (US$25/month): not needed for the Must scope (photos only, Free plan). Decide who pays for it once the Could video work starts, and the storage cost per Business once Owners upload lots of video.

## Product (post-hackathon)

- [ ] Pricing: posts per month per plan? Free trial length?
- [ ] Should owners be able to switch to "auto mode" (approve the plan once, auto-publish)? See [ADR 0007](decisions/0007-approve-every-post.md).
- [ ] Which network after Instagram: Facebook (cheap, same provider) or TikTok (needs video)?
- [ ] Voice notes: owners in the region send many. Make transcription a Must for v1?
- [ ] Measuring results: do we pull Instagram insights to show "this post brought N messages"?
- [ ] How does this evolve back toward the broader "chief of staff" vision (suppliers, orders, follow-ups)? Which second vertical?

## Add yours below
