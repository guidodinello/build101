# Research

Investigations, spikes, competitor deep dives, market and user research, tech/vendor evaluations, and policy reading. The evidence behind [idea.md](../idea.md), [competitors.md](../competitors.md), [open-questions.md](../open-questions.md) and the [decisions](../decisions/README.md).

Cite a source next to every claim, with the date read for anything that changes (pricing, terms). When research settles something, record an ADR in [decisions/](../decisions/README.md) and link back here.

| File | What it covers | Date |
|---|---|---|
| [competitive-landscape.md](competitive-landscape.md) | Evidence behind competitors.md: Meta Business Agent, Sintra/Marblism/Lindy, Sidekick, LatAm WhatsApp agents, Poke vs Pokee, WhatsApp policy | 2026-10-17 |
| [social-publishing-apis.md](social-publishing-apis.md) | Unified APIs to publish to Instagram for the Owner (Zernio, Upload-Post, Ayrshare, ...) | 2026-10-17 |
| [image-generation-providers.md](image-generation-providers.md) | AI image generation APIs for themed post images from the Owner's photos (Gemini Nano Banana, OpenAI GPT Image, FLUX, fal/Replicate), plus the Gemini `generateContent` call verified from docs and SDK source; supports ADR 0018, 0019 and 0022 | 2026-10-17 |
| [media-uploads.md](media-uploads.md) | Storing large photos and videos (Supabase, Vercel limits), what Claude can read (no video/audio), publishing Reels and carousels (Zernio, Instagram) | 2026-10-17 |
| [voice-notes.md](voice-notes.md) | Understanding the Owner's WhatsApp voice notes: Kapso's transcript and media download, speech-to-text options (Gemini, faster-whisper, OpenAI); supports ADR 0021 | 2026-10-17 |
| [gemini-api.md](gemini-api.md) | Gemini API as the text LLM: `google-genai` SDK, Interactions API, structured output, thinking levels, native video, models and prices, free-tier data use | 2026-10-17 |
