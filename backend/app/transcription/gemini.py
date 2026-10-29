import logging
import struct
import time
from pathlib import Path
from typing import Self, cast

from google.genai import interactions
from pydantic import BaseModel

from app.llm.client import GeminiChat, LLMError, StructuredModel, audio_content, text_content
from app.prompts import load_prompt, tagged

from .base import TranscriptionError, Vocabulary

logger = logging.getLogger(__name__)

AGENT = "transcribe"
SYSTEM_PROMPT = load_prompt(Path(__file__).parent / "prompts" / "transcribe.md")
# Gemini bills audio at 32 tokens per second (docs/research/voice-notes.md). The prices are
# gemini-3.8-flash's through 2026-12-31 (docs/research/audit-2026-10/unit-economics.md): an
# estimate for the log, the real tokens are on the client's `llm agent=transcribe` line.
AUDIO_TOKENS_PER_S = 32
INPUT_USD_PER_TOKEN = 0.75 / 1_000_000
OUTPUT_USD_PER_TOKEN = 3.75 / 1_000_000
CHARS_PER_TOKEN = 4
# Opus granule positions always count 48 kHz samples (RFC 7845 § 4).
OPUS_GRANULE_RATE = 48_000
OGG_PAGE = b"OggS"
GRANULE_OFFSET = 6


class _Transcript(BaseModel):
    text: str


class GeminiTranscriber:
    """One structured Gemini call with the audio inline (ADR 0021)."""

    def __init__(self, model: StructuredModel, model_name: str) -> None:
        self._model = model
        self._model_name = model_name

    @classmethod
    def from_api_key(cls, api_key: str, model: str) -> Self:
        return cls(GeminiChat.from_api_key(api_key, model), model)

    async def transcribe(self, audio: bytes, mime_type: str, vocabulary: Vocabulary) -> str:
        vocabulary_block = tagged(
            "vocabulary",
            {"business_name": vocabulary.business_name, "products": list(vocabulary.products)},
        )
        # WhatsApp says "audio/ogg; codecs=opus"; Gemini takes the bare type.
        mime = cast(interactions.AudioContentMimeType, mime_type.split(";")[0].strip())
        started = time.monotonic()
        try:
            transcript = await self._model.structured(
                AGENT,
                SYSTEM_PROMPT,
                [text_content(vocabulary_block), audio_content(audio, mime)],
                _Transcript,
                "low",
            )
        except LLMError as exc:
            raise TranscriptionError(str(exc)) from exc
        seconds = opus_seconds(audio)
        logger.info(
            "transcribe model=%s bytes=%d audio_s=%s latency_ms=%d chars=%d est_usd=%s",
            self._model_name,
            len(audio),
            f"{seconds:.1f}" if seconds is not None else None,
            (time.monotonic() - started) * 1000,
            len(transcript.text),
            f"{estimated_usd(seconds, transcript.text):.5f}" if seconds is not None else None,
        )
        return transcript.text.strip()


def opus_seconds(audio: bytes) -> float | None:
    """The length of an Ogg Opus file, from the granule position of its last page; None when
    it isn't one."""
    last_page = audio.rfind(OGG_PAGE)
    end = last_page + GRANULE_OFFSET + 8
    if last_page < 0 or end > len(audio):
        return None
    (granule,) = struct.unpack_from("<q", audio, last_page + GRANULE_OFFSET)
    return granule / OPUS_GRANULE_RATE if granule >= 0 else None


def estimated_usd(seconds: float, text: str) -> float:
    audio_tokens = seconds * AUDIO_TOKENS_PER_S
    text_tokens = len(text) / CHARS_PER_TOKEN
    return audio_tokens * INPUT_USD_PER_TOKEN + text_tokens * OUTPUT_USD_PER_TOKEN
