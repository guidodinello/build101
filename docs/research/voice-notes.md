# Voice notes from the Owner

How the Agency can understand the WhatsApp voice notes the Owner sends: what Kapso gives us, how to get the audio, and which speech-to-text options fit. Everything here was read on 2026-10-17. Decision: [ADR 0021](../decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md).

## Why it matters

- The target Owner "sends voice notes" ([idea.md](../idea.md)), and owners in the region send many of them ([open-questions.md](../open-questions.md)).
- Claude's Messages API takes no audio content blocks, and Anthropic has no speech-to-text endpoint ([media-uploads.md](media-uploads.md#what-claude-can-read)). So a voice note has to become text before it reaches the orchestrator.

## What Kapso sends for a voice note

From [Kapso message events](https://docs.kapso.ai/docs/platform/webhooks/message-events.md):

- The event is `whatsapp.message.received`, named in the `X-Webhook-Event` header. The body has `message`, `conversation`, `is_new_conversation` and `phone_number_id`.
- An audio message has `type: "audio"` and `audio.id` (the media id).
- `message.kapso` holds:
  - `media_url`;
  - `media_data`: `url`, `filename` (e.g. `voice.ogg`), `content_type` (`audio/ogg`) and `byte_size`;
  - `has_media`;
  - `content`: a text summary that ends with `Transcript: ...`;
  - **`transcript.text`, a transcript of the audio.**
- No field tells a voice note apart from an attached audio file. WhatsApp voice notes are OGG/Opus ([Kapso send audio](https://docs.kapso.ai/docs/whatsapp/send-messages/audio.md)).
- With buffering turned on, `whatsapp.message.received` arrives in a batch envelope (`batch: true`, `data: [...]`). Each item has the same shape as a single event.

Not documented, so verify it in the first-hour test (T03):

- when `transcript` is filled in, and whether it is always in the first webhook;
- which languages it handles (we need Rioplatense Spanish);
- which provider produces it, and whether it needs a paid plan.

Another integrator treats Kapso's transcript as optional and handles the case where it is missing ([fidy-ai#708](https://github.com/B4rz99/fidy-ai/issues/708)).

## Downloading the audio

From [Get media URL](https://docs.kapso.ai/api/meta/whatsapp/media/get-media-url.md):

- `GET https://api.kapso.ai/meta/whatsapp/v24.0/{media_id}?phone_number_id=...` with the header `X-API-Key: <project key>`.
- The response has `mime_type`, `sha256`, `file_size`, Meta's `url` (expires in 5 minutes) and **`download_url`**.
- `download_url` is a Kapso URL with the auth token built in, so it needs no headers. It is valid for about 4 minutes; `download_url_expires_at` gives the exact time ([Download media file](https://docs.kapso.ai/api/meta/whatsapp/media/download-media-file.md)). Fetch the bytes right away.
- Use `download_url` and check the HTTP status. Fetching Meta's `url` without Meta's bearer token returns a 401 body, and one project saved that body as audio and got empty transcripts (search result for `stefanogebara/twin-me` PR #749, read 2026-10-17; the PR page now returns 404).
- On plan B (Meta direct), media ids in webhooks expire after 7 days, and media URLs expire within minutes ([Meta media](https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/media)). Plan B gives no transcript, so we always transcribe ourselves.

This also answers the voice-note half of the media-download question in [open-questions.md](../open-questions.md#whatsapp-through-kapso-first-hour-test), until T03 confirms it.

## Speech-to-text options

| Option | Fit | Cost | Notes |
|---|---|---|---|
| **Kapso's `transcript`** | Already in the webhook; no extra call, no dependency | Not stated (included in the payload) | Language coverage and reliability unknown; missing on plan B |
| **Gemini audio understanding** | `google-genai` and `GEMINI_API_KEY` are already planned for image generation ([ADR 0019](../decisions/0019-image-provider-gemini.md)) | 32 tokens per second of audio, i.e. 1,920 per minute, billed at the model's input rate | Accepts `audio/ogg` and `audio/opus`; inline requests up to 20 MB total, which covers WhatsApp's 16 MB audio cap; transcription is a prompt plus the audio part ([Gemini audio](https://ai.google.dev/gemini-api/docs/audio)) |
| `faster-whisper` in the container | The old plan ([integrations.md](../architecture/integrations.md)) | Free per call | Adds ~500 MB to the image and seconds of CPU per note on a 1 GB Railway instance ([ADR 0017](../decisions/0017-backend-host-railway.md)) |
| OpenAI `gpt-4o-transcribe` | A new dependency for audio alone; OpenAI is planned only as the image fallback | About $0.006 per minute, billed per second (third-party price pages, e.g. [costgoat](https://costgoat.com/pricing/openai-transcription), not OpenAI's own) | Listed upload formats don't include OGG in the sources we found, so it might need a conversion step |

Community WhatsApp bridges usually transcribe on their own (Groq, OpenAI, Deepgram or a local Whisper), and some use the provider transcript first ([openclaw-kapso-whatsapp](https://github.com/Enriquefft/openclaw-kapso-whatsapp), [Kapso Hermes Agent](https://docs.kapso.ai/docs/whatsapp/hermes-agent)).

## Outcome

Use Kapso's transcript when it is there, and fall back to downloading the audio and transcribing it with Gemini. The whole flow is in [ADR 0021](../decisions/0021-voice-notes-kapso-transcript-gemini-fallback.md) and [integrations.md](../architecture/integrations.md#speech-to-text).
