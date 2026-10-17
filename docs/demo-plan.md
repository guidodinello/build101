# Hackathon demo plan (superseded)

> Superseded by [product/demo-script.md](product/demo-script.md) and [ADR 0016](decisions/0016-demo-scope-one-post.md): the demo is now a short onboarding plus one post, published through Zernio ([ADR 0008](decisions/0008-publishing-via-zernio.md)). The comment, DM and sales loop below moved to the [roadmap](roadmap.md) (Phase 1). Kept for history.

Goal: show **one real loop end to end**, live, with the pilot owner's Instagram. Everything else is shown as a roadmap, not faked as working.

## The demo story (≈3 minutes)

1. **Owner sends work.** On WhatsApp: 3 photos of a restored dresser + a voice note: "I finished this oak dresser, I'm selling it for 12,000 pesos."
2. **AI proposes a post.** The bot transcribes the audio and replies with a carousel preview, a caption in the owner's voice, hashtags, and a suggested time. Buttons: **Publish** / **Change something**.
3. **Owner approves.** Tap **Publish**, and the post appears on the owner's Instagram.
4. **A customer shows up.** From another account, comment "price?" on the post. The bot replies to the comment and opens a DM. The customer says "I want it."
5. **Sale + notification.** The sales agent confirms the details and the owner gets a WhatsApp message: "🎉 Sale: oak dresser, 12,000 UYU, buyer @…"
6. **Weekly plan.** Ask the bot "what do we post this week?" It returns a plan that includes the next special date.

## Must work live vs. can be shown

| Piece | Tomorrow |
|---|---|
| WhatsApp in/out (text, photos, voice) | **Live** |
| Voice transcription | **Live** |
| Caption + hashtags in brand voice | **Live** |
| Carousel publish to Instagram | **Live** |
| Comment reply + DM sales flow | **Live** (stretch: may fall back to a recorded clip) |
| Owner sale notification | **Live** |
| Weekly plan with special dates | **Live** (just an LLM call + a dates file) |
| Graphic design (before/after layout) | Stretch |
| Reels | Roadmap slide |
| Metrics | Roadmap slide, or Instagram Insights numbers if time allows |
| Multi-business onboarding, billing | Roadmap slide |

## Architecture (demo)

```text
Owner (WhatsApp) ──► WhatsApp Cloud API ──webhook──► Backend
                                                     │
                                       Orchestrator (LLM, tool calling)
                                       ├─ transcribe(audio)
                                       ├─ write_post(photos, notes, brand_voice)
                                       ├─ weekly_plan(dates, history)
                                       └─ publish_carousel(...) ──► Instagram API
Customer (Instagram) ──comments/DMs webhook──► Sales agent ──► reply + notify owner on WhatsApp
```

- **Agents** are prompts + tools on one LLM, not separate services. That's enough for the demo, and the architecture slide can still show them as a team.
- **Photos** need a public URL for Instagram to fetch: upload them to object storage (S3 / R2 / Supabase Storage) first.
- **Brand voice**: pull the owner's last ~20 captions once and put them in the system prompt.
- **State**: a single small database (SQLite / Supabase), with one table each for posts, conversations and businesses.

## Meta setup checklist (do first; this is the slowest part)

- [ ] Meta developer account + app (type: Business)
- [ ] WhatsApp: add the product, use the **test number**, register the demo phone as a recipient (max 5), set the webhook
- [ ] Instagram: the owner's account must be **Business or Creator**; add it as **Instagram Tester** on the app; use *Instagram API with Instagram Login*
- [ ] Permissions (dev mode, no App Review needed for our own account): `instagram_business_basic`, `instagram_business_content_publishing`, `instagram_business_manage_comments`, `instagram_business_manage_messages`
- [ ] Public HTTPS URL for webhooks (deploy, or a tunnel such as ngrok / cloudflared)

## Fallbacks

- Record a full video of the working flow the night before. If Wi-Fi or Meta fails on stage, play it.
- If the Instagram webhooks for comments/DMs don't work in time, demo steps 1–3 and 5 live and show step 4 on video.
