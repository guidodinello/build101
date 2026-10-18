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
| [instagram-content-trends.md](instagram-content-trends.md) | What works on Instagram in 2026: ranking signals, originality rule, Reels vs carousels vs images benchmarks, hashtags/CTAs, October 2026 trend templates, implications for the agents | 2026-10-17 |
| [carousel-references.md](carousel-references.md) | 8 reference carousels analysed: slide types (cover, point, closing), copy and design patterns, four template families, implications for generating furniture carousels | 2026-10-17 |
| [niche-trend-sources.md](niche-trend-sources.md) | Data sources for a weekly niche analysis feeding post generation: Gemini URL context + Google Search (chosen), Claude web search and fetch, Instagram Business Discovery and Hashtag Search, scrapers (rejected), Ad Library, Google Trends | 2026-10-18 |
| [furniture-decor-uruguay.md](furniture-decor-uruguay.md) | Curated wood furniture and home stores in Uruguay: reference websites (La Ibérica, KATEI), peers, how they differ from price-led chains, commercial calendar and search themes for the Niche Report (ADR 0025) | 2026-10-18 |
| [post-design/](post-design/README.md) | Why post and carousel designs look generic and what fixes it: AI makes text-free visuals, code templates (Takumi on Vercel) add type, figures, logo and connected carousels; design trends and template families, image models, renderers, hosted template APIs | 2026-10-18 |
| [orchestrator-intelligence.md](orchestrator-intelligence.md) | Why the WhatsApp assistant forgets and misreads the Owner: no brand context in the orchestrator, a 40-step in-memory history, keyword approval refusing "sí"/"dale", revisions that rebuild posts; prioritized fixes (P0 to P2) | 2026-10-18 |
