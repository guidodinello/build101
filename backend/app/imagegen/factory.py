from app.config import Settings
from app.llm.ledger import MeteredImageGen, get_ledger

from .base import ImageGenPort
from .gemini import GeminiImageGen
from .mock import MockImageGen


def build_image_gen(settings: Settings) -> ImageGenPort:
    """The image port, metered: every call leaves an agent run (#205)."""
    model = settings.gemini_image_model if settings.image_gen == "gemini" else settings.image_gen
    return MeteredImageGen(
        _image_gen(settings),
        model,
        settings.gemini_thinking_level,
        settings.gemini_image_size,
        get_ledger(),
    )


def _image_gen(settings: Settings) -> ImageGenPort:
    match settings.image_gen:
        case "gemini":
            if not settings.gemini_api_key:
                raise ValueError("IMAGE_GEN=gemini needs GEMINI_API_KEY")
            return GeminiImageGen.from_api_key(
                api_key=settings.gemini_api_key,
                model=settings.gemini_image_model,
                thinking_level=settings.gemini_thinking_level,
                image_size=settings.gemini_image_size,
                max_concurrency=settings.image_gen_max_concurrency,
            )
        case "openai":
            raise NotImplementedError("the OpenAI fallback adapter is task T43")
        case "mock":
            return MockImageGen()
