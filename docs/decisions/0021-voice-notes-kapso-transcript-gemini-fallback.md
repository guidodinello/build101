# 0021: Voice notes via Kapso's transcript, with Gemini as fallback

- Date: 2026-10-17
- Status: proposed

## Context

Owners in the region talk to each other in voice notes ([idea.md](../idea.md), [open-questions.md](../open-questions.md)). Until now, voice notes were F1.7, *Could*: they would be transcribed with `faster-whisper` inside the backend container, and until then the bot would answer them with `unsupported_media` ([ADR 0014](0014-whatsapp-cloud-api.md), [ADR 0020](0020-whatsapp-via-kapso.md)).

Claude takes no audio, so a voice note has to become text first. What we found ([research/voice-notes.md](../research/voice-notes.md)):

- Kapso's `whatsapp.message.received` webhook already carries `message.kapso.transcript.text` for audio messages. When it is filled in, which languages it covers, and which plan it needs are not documented.
- Kapso gives the audio bytes through a short-lived `download_url` from `GET /meta/whatsapp/v24.0/{media_id}`.
- Gemini, which we already use for images ([ADR 0019](0019-image-provider-gemini.md)), accepts OGG/Opus audio and transcribes it from a prompt.
- `faster-whisper` would add about 500 MB to the image and seconds of CPU per note on our single Railway instance ([ADR 0017](0017-backend-host-railway.md)).

## Decision

- Voice notes are **Must** (F1.7). This revises that one item of the MVP priorities set with [ADR 0016](0016-demo-scope-one-post.md). The demo path itself does not change.
- A voice note is handled as its **transcript**, which is used exactly like a text message. The text is resolved in this order:
  1. Kapso's `transcript.text`, if it is not empty.
  2. Otherwise, download the audio through `ChannelPort.download_media` and transcribe it with **Gemini** behind a `TranscriberPort` (`TRANSCRIBE_FALLBACK=gemini|none|mock`). The prompt asks for a verbatim transcription in Rioplatense Spanish, with no summarizing.
  3. If there is still no text, send `audio_unclear` and don't run the orchestrator.
- **Inbound only:** the bot keeps replying in text. No speech synthesis, and no audio recording in the web simulator.
- `faster-whisper` is dropped for voice notes. It remains an option only for transcribing the audio of videos, which is post-MVP.

## Consequences

- No new vendor and no heavier image: Gemini reuses `GEMINI_API_KEY`, and Kapso's transcript costs nothing extra when it is present.
- The Owner's voice reaches Kapso's transcription service and possibly Gemini. As with photos, only call Gemini from a project with billing linked, because unpaid use trains on inputs ([ADR 0019](0019-image-provider-gemini.md)).
- Transcripts can mishear product names and prices. The orchestrator knows a turn was a voice note and asks before using an ambiguous number it heard.
- If T03 shows that Kapso's transcript is missing, late or poor in Spanish, Gemini becomes the primary path. That is a config change, not a design change. Plan B (Meta direct) has no provider transcript and always uses Gemini.
- Each Gemini transcription is logged to `agent_runs` (`agent = 'transcribe'`) so its cost can be measured.
