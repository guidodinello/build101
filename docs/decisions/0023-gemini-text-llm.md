# 0023: Gemini as the text LLM

- Date: 2026-10-17
- Status: proposed

## Context

[ADR 0010](0010-anthropic-sdk-own-orchestration.md) chose Claude through the Anthropic SDK for the orchestrator and the specialists. Since then Gemini came in for image generation ([ADR 0019](0019-image-provider-gemini.md)) and as the voice-note transcription fallback ([ADR 0021](0021-voice-notes-kapso-transcript-gemini-fallback.md)), so the backend already depends on `google-genai` and `GEMINI_API_KEY`. Running text on Gemini too leaves one provider, one key and one bill. Facts on the SDK, the Interactions API, models and prices: [research/gemini-api.md](../research/gemini-api.md).

## Decision

- Text calls (orchestrator, specialists; the carousel Text Checker until [ADR 0028](0028-designed-slides-ai-scene-code-layout.md) removed it) use the **Gemini API** through `google-genai`'s async client and the **Interactions API**, model **`gemini-3.8-flash`** (`GEMINI_CHAT_MODEL`), with per-agent **thinking level** (`low` / `medium` / `high`) instead of per-agent models.
- ADR 0010's orchestration choice stands: our own small loop, no LangGraph. History is ours: `store=False`, and the model's steps are stored and resent unchanged, thought steps included.
- All text calls go through `backend/app/llm/client.py` (`ChatModel` port, `GeminiChat` adapter).
- First slice: `ChatHandler` replaces the echo handler behind Kapso's webhook ([ADR 0020](0020-whatsapp-via-kapso.md)); it answers text and voice-note transcripts. `INBOUND_HANDLER=echo` keeps the old echo for channel tests.

## Consequences

- The same key serves images, transcription and text. Use it from a project with **billing linked**: free-tier content is used by Google to improve its products ([ADR 0019](0019-image-provider-gemini.md) already requires billing for the Owner's photos).
- No server-side refusal fallback: the client treats a non-`completed` status, empty text or an SDK error as `LLMError`, and the Owner gets a fixed message.
- Gemini reads audio and video natively, so the Frame Extractor and the separate transcription step could later collapse into the agents' own calls; this ADR doesn't change them.
- Prompts and structured-output schemas in [agents.md](../architecture/agents.md) were written for Claude; each agent is checked on Gemini when it is built.
- Supersedes [ADR 0010](0010-anthropic-sdk-own-orchestration.md) in the provider and SDK only.
