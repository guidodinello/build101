from app.config import Settings

from .base import TranscriberPort
from .gemini import GeminiTranscriber
from .mock import MockTranscriber


def build_transcriber(settings: Settings) -> TranscriberPort | None:
    """The fallback for voice notes Kapso sent without a transcript; None answers them as
    unclear (ADR 0021)."""
    match settings.transcribe_fallback:
        case "gemini":
            if not settings.gemini_api_key:
                raise ValueError("TRANSCRIBE_FALLBACK=gemini needs GEMINI_API_KEY")
            return GeminiTranscriber.from_api_key(
                settings.gemini_api_key, settings.transcribe_model
            )
        case "mock":
            return MockTranscriber()
        case "none":
            return None
