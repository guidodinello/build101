# 0033: AI-generated Reels from a product image with Veo, behind a flag

- Date: 2026-10-19
- Status: proposed
- Amends: [0012](0012-catalog-content-dashboard-reels.md)

## Context

[ADR 0012](0012-catalog-content-dashboard-reels.md) says a Reel is one of the Owner's own videos, published unedited. Owners without a usable video get no Reels. Video models can now animate a product photo into a short clip, and Gemini Veo 3.1 runs on the Gemini API we already use for images ([ADR 0019](0019-image-provider-gemini.md)). Facts, read 2026-10-19: [Veo docs](https://ai.google.dev/gemini-api/docs/veo) (models, modes, limits) and [pricing](https://ai.google.dev/gemini-api/docs/pricing) (Lite US$0.05/s at 720p, Fast US$0.10/s, Standard US$0.40/s, no free tier, blocked videos not billed).

Veo has two ways to use a photo:

- **First frame** (image-to-video): supported by every Veo 3.1 model, including Lite. One image.
- **Reference images** (`asset`, up to 3): supported by Fast and Standard only; the docs list Lite as not supporting them. They force 8 s clips.

Alternatives considered: keep Reels to the Owner's own videos only (nothing for Owners without footage); default to Fast to use real references (twice the cost per second, for a result we cannot yet show is better); a different video provider (a second key and vendor for no gain while Veo is on our API).

## Decision

- A **Reel can also be generated** from a Post's product image with Veo 3.1. It goes through the **same Approval** as any Post ([ADR 0007](0007-approve-every-post.md)): nothing publishes a clip the Owner has not approved. Publishing as an Instagram Reel goes through Zernio ([ADR 0008](0008-publishing-via-zernio.md)).
- Video generation sits behind a **`VideoGenPort`** (Gemini Veo and a mock), like images. The mock returns a small bundled MP4, so the whole flow runs without billed calls.
- It is behind a **feature flag**, `VIDEO_GEN_ENABLED`, default `false`. While it is off, no adapter is built, so no Veo call can happen and the Owner never sees a video option.
- It has its **own key**, `GEMINI_VIDEO_API_KEY`. The adapter never falls back to `GEMINI_API_KEY`, so video spend can be cut or capped on its own. The same value may be set in both on purpose.
- **Default model `veo-3.1-lite-generate-preview`**, with the product image as the **first frame**. Fast and Standard use `ASSET` references instead. Lite is the cheapest option and the only trade-off is that extra photos are ignored.
- The first frame is **center-cropped to 9:16 in code** before it is sent, so Veo never decides how to crop. This is a default and can be tuned (padding instead of cropping, a different crop point) after the first live call.
- The **submit call never retries**: a retry after a timeout could start, and bill, a second clip. Polling and downloading retry.
- Clips are served from the backend at `/media/{token}.mp4`, in memory like the images, until Supabase Storage (T17).

## Consequences

- Reels become possible for every Owner with one product photo, at about US$0.40 for an 8 s Lite clip. Cost is per second and there is no free tier, which is why the flag defaults to off and the key is separate.
- A Post gains a video later (T67); this decision only adds the capability. [Glossary](../glossary.md#reel) now includes generated clips.
- Generation takes 11 s to 6 min at peak, so it runs as a job and the Owner is told it is coming, not awaited in the chat turn.
- Unconfirmed until one live call when the flag is first turned on: Veo with reference images at 9:16 (a Cloud sample says yes, a forum answer says 16:9 only), how the crop looks, and whether Zernio or Meta need `Range` requests to fetch the MP4 (the route has none).
- Clips live in memory (20 at most) and are lost on restart, like the images; Veo itself keeps a video only 2 days, so it is downloaded at once.
- Still open: moderation of generated clips beyond Veo's own filters, which surface as a blocked result.
