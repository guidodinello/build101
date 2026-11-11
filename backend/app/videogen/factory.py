from app.config import Settings
from app.llm.ledger import MeteredVideoGen, get_ledger

from .base import VideoGenPort
from .gemini import GeminiVideoGen
from .mock import MockVideoGen


def build_video_gen(settings: Settings) -> VideoGenPort | None:
    """None while VIDEO_GEN_ENABLED is off: no adapter, so no client and no Veo call (ADR 0033)."""
    if not settings.video_gen_enabled:
        return None
    model = settings.gemini_video_model if settings.video_gen == "gemini" else settings.video_gen
    return MeteredVideoGen(_video_gen(settings), model, get_ledger())


def _video_gen(settings: Settings) -> VideoGenPort:
    match settings.video_gen:
        case "gemini":
            # Its own key: never falls back to GEMINI_API_KEY
            if not settings.gemini_video_api_key:
                raise ValueError("VIDEO_GEN=gemini needs GEMINI_VIDEO_API_KEY")
            return GeminiVideoGen.from_api_key(
                api_key=settings.gemini_video_api_key,
                model=settings.gemini_video_model,
                max_concurrency=settings.video_gen_max_concurrency,
                timeout_s=settings.video_gen_timeout_s,
            )
        case "mock":
            return MockVideoGen()
