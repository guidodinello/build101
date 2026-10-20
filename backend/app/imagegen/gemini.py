import asyncio
import logging
from typing import Self

from google import genai
from google.genai import errors, types

from app.media.images import image_mime

from .base import GeneratedImage, ImageGenBlocked, ImageGenNoImage, ImageGenUnavailable

logger = logging.getLogger(__name__)

PROVIDER = "gemini"
ASPECT_RATIO = "4:5"
REQUEST_TIMEOUT_MS = 120_000

# google-genai does not retry unless retry_options is set; with it set, it retries
# 408, 429 and 5xx with exponential backoff.
RETRY_OPTIONS = types.HttpRetryOptions(attempts=4, initial_delay=2.0, max_delay=30.0)

BLOCKING_REASONS = frozenset(
    {
        types.FinishReason.IMAGE_SAFETY,
        types.FinishReason.IMAGE_PROHIBITED_CONTENT,
        types.FinishReason.IMAGE_RECITATION,
        types.FinishReason.SAFETY,
        types.FinishReason.PROHIBITED_CONTENT,
        types.FinishReason.BLOCKLIST,
        types.FinishReason.SPII,
        types.FinishReason.RECITATION,
    }
)


class GeminiImageGen:
    def __init__(
        self,
        client: genai.Client,
        model: str,
        thinking_level: str,
        image_size: str,
        max_concurrency: int,
    ) -> None:
        self._client = client
        self._model = model
        self._image_size = image_size
        self._thinking_level = types.ThinkingLevel(thinking_level.upper())
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @classmethod
    def from_api_key(
        cls, api_key: str, model: str, thinking_level: str, image_size: str, max_concurrency: int
    ) -> Self:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS, retry_options=RETRY_OPTIONS),
        )
        return cls(client, model, thinking_level, image_size, max_concurrency)

    async def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        style_image: bytes | None = None,
        *,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
    ) -> GeneratedImage:
        parts = build_contents(prompt, reference_images, style_image)
        contents: list[types.ContentUnion] = [*parts]  # list is invariant: widen to the SDK type
        config = types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio or ASPECT_RATIO, image_size=image_size or self._image_size
            ),
            thinking_config=types.ThinkingConfig(thinking_level=self._thinking_level),
        )
        async with self._semaphore:
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model, contents=contents, config=config
                )
            except errors.APIError as exc:
                raise ImageGenUnavailable(f"gemini {exc.code} {exc.status}: {exc.message}") from exc
        return parse_response(response, self._model)


def build_contents(
    prompt: str, reference_images: list[bytes], style_image: bytes | None
) -> list[types.Part]:
    parts = [types.Part.from_text(text=prompt)]
    for number, image in enumerate(reference_images, start=1):
        parts.append(types.Part.from_text(text=f"Product reference {number}:"))
        parts.append(types.Part.from_bytes(data=image, mime_type=image_mime(image)))
    if style_image is not None:
        # gemini-nano-banana-2.1 has no style-reference slot; the prompt says what this image is for
        parts.append(types.Part.from_text(text="Another slide of this carousel:"))
        parts.append(types.Part.from_bytes(data=style_image, mime_type=image_mime(style_image)))
    return parts


def parse_response(response: types.GenerateContentResponse, model: str) -> GeneratedImage:
    if not response.candidates:
        feedback = response.prompt_feedback
        if feedback is not None and feedback.block_reason is not None:
            raise ImageGenBlocked(feedback.block_reason.value)
        raise ImageGenNoImage("gemini returned no candidates")

    candidate = response.candidates[0]
    finish_reason = candidate.finish_reason
    parts = candidate.content.parts if candidate.content and candidate.content.parts else []
    for part in parts:
        if part.thought:
            continue
        if part.inline_data is not None and part.inline_data.data:
            return GeneratedImage(
                data=part.inline_data.data,
                mime=part.inline_data.mime_type or "image/png",
                provider=PROVIDER,
                model=model,
                usage=usage_counts(response.usage_metadata),
                finish_reason=finish_reason.value if finish_reason else None,
            )

    text = " ".join(part.text for part in parts if part.text and not part.thought)
    if finish_reason is not None and finish_reason in BLOCKING_REASONS:
        raise ImageGenBlocked(finish_reason.value)
    logger.warning("gemini returned no image (finish_reason=%s): %.300s", finish_reason, text)
    raise ImageGenNoImage(f"gemini returned no image (finish_reason={finish_reason})")


def usage_counts(usage: types.GenerateContentResponseUsageMetadata | None) -> dict[str, int]:
    if usage is None:
        return {}
    counts = {
        "prompt_tokens": usage.prompt_token_count,
        "output_tokens": usage.candidates_token_count,
        "thoughts_tokens": usage.thoughts_token_count,
        "cached_tokens": usage.cached_content_token_count,
        "total_tokens": usage.total_token_count,
    }
    for prefix, details in (
        ("prompt", usage.prompt_tokens_details),
        ("output", usage.candidates_tokens_details),
    ):
        for detail in details or []:
            if detail.modality is not None:
                counts[f"{prefix}_{detail.modality.value.lower()}_tokens"] = detail.token_count
    return {key: value for key, value in counts.items() if value is not None}
