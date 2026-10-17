from app.config import Settings

from .base import ImageGenPort
from .gemini import GeminiImageGen
from .mock import MockImageGen


def build_image_gen(settings: Settings) -> ImageGenPort:
    match settings.image_gen:
        case "gemini":
            if not settings.gemini_api_key:
                raise ValueError("IMAGE_GEN=gemini needs GEMINI_API_KEY")
            return GeminiImageGen.from_api_key(
                api_key=settings.gemini_api_key,
                model=settings.gemini_image_model,
                thinking_level=settings.gemini_thinking_level,
                max_concurrency=settings.image_gen_max_concurrency,
            )
        case "openai":
            raise NotImplementedError("the OpenAI fallback adapter is task T43")
        case "mock":
            return MockImageGen()
