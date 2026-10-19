import asyncio
import logging
from io import BytesIO
from typing import Self

from google import genai
from google.genai import errors, types
from PIL import Image, ImageOps

from .base import (
    GeneratedVideo,
    VideoGenBlocked,
    VideoGenNoVideo,
    VideoGenTimeout,
    VideoGenUnavailable,
)

logger = logging.getLogger(__name__)

PROVIDER = "gemini"
REQUEST_TIMEOUT_MS = 120_000
POLL_INTERVAL_S = 10.0
ASPECT_RATIOS = frozenset({"9:16", "16:9"})
DURATIONS = frozenset({4, 6, 8})
MAX_REFERENCES = 3
REFERENCE_DURATION_S = 8
FIRST_FRAME_HEIGHT = 1280
# https://ai.google.dev/gemini-api/docs/veo: Lite has no reference images (image-to-video from one
# first frame only); Fast and Standard take up to 3 `asset` references, which force 8 s clips.
LITE_MARKER = "lite"

# Polling and downloading are safe to repeat; the submit call is not (see `generate`).
RETRY_OPTIONS = types.HttpRetryOptions(attempts=4, initial_delay=2.0, max_delay=30.0)
NO_RETRY_OPTIONS = types.HttpRetryOptions(attempts=1)


class GeminiVideoGen:
    def __init__(
        self,
        client: genai.Client,
        model: str,
        max_concurrency: int,
        poll_interval_s: float = POLL_INTERVAL_S,
        timeout_s: float = 600,
    ) -> None:
        self._client = client
        self._model = model
        self._poll_interval_s = poll_interval_s
        self._timeout_s = timeout_s
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @classmethod
    def from_api_key(
        cls,
        api_key: str,
        model: str,
        max_concurrency: int,
        poll_interval_s: float = POLL_INTERVAL_S,
        timeout_s: float = 600,
    ) -> Self:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS, retry_options=RETRY_OPTIONS),
        )
        return cls(client, model, max_concurrency, poll_interval_s, timeout_s)

    @property
    def uses_references(self) -> bool:
        return LITE_MARKER not in self._model

    async def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        *,
        aspect_ratio: str = "9:16",
        duration_seconds: int = 8,
    ) -> GeneratedVideo:
        if aspect_ratio not in ASPECT_RATIOS:
            raise ValueError(f"aspect_ratio must be one of {sorted(ASPECT_RATIOS)}")
        if duration_seconds not in DURATIONS:
            raise ValueError(f"duration_seconds must be one of {sorted(DURATIONS)}")

        source, config = self._build_request(
            prompt, reference_images, aspect_ratio, duration_seconds
        )
        duration = config.duration_seconds or duration_seconds
        async with self._semaphore:
            try:
                async with asyncio.timeout(self._timeout_s):
                    # A retried submit after a timeout could start, and bill, a second clip, so it
                    # never retries; polling and the download keep the client's retries.
                    operation = await self._client.aio.models.generate_videos(
                        model=self._model, source=source, config=config
                    )
                    while not operation.done:
                        await asyncio.sleep(self._poll_interval_s)
                        operation = await self._client.aio.operations.get(operation)
                    video = _pick_video(operation)
                    data = await self._client.aio.files.download(file=video)
            except TimeoutError as exc:
                raise VideoGenTimeout(f"veo did not finish in {self._timeout_s}s") from exc
            except errors.APIError as exc:
                raise VideoGenUnavailable(f"gemini {exc.code} {exc.status}: {exc.message}") from exc
        return GeneratedVideo(
            data=data,
            mime=video.mime_type or "video/mp4",
            provider=PROVIDER,
            model=self._model,
            duration_seconds=duration,
        )

    def _build_request(
        self,
        prompt: str,
        reference_images: list[bytes],
        aspect_ratio: str,
        duration_seconds: int,
    ) -> tuple[types.GenerateVideosSource, types.GenerateVideosConfig]:
        config = types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
            number_of_videos=1,
            # Required by Veo 3.1 for image-to-video and reference images
            person_generation="allow_adult",
            http_options=types.HttpOptions(retry_options=NO_RETRY_OPTIONS),
        )
        source = types.GenerateVideosSource(prompt=prompt)
        if not reference_images:
            return source, config
        if self.uses_references:
            if len(reference_images) > MAX_REFERENCES:
                logger.warning("veo takes %d references, dropping the rest", MAX_REFERENCES)
            config.reference_images = [
                types.VideoGenerationReferenceImage(
                    image=_frame(image, aspect_ratio),
                    reference_type=types.VideoGenerationReferenceType.ASSET,
                )
                for image in reference_images[:MAX_REFERENCES]
            ]
            config.duration_seconds = REFERENCE_DURATION_S
        else:
            if len(reference_images) > 1:
                logger.warning("%s takes one first frame, dropping the rest", self._model)
            source.image = _frame(reference_images[0], aspect_ratio)
        return source, config


def _frame(data: bytes, aspect_ratio: str) -> types.Image:
    """The image center-cropped to the clip's ratio, so Veo never decides how to crop."""
    width, height = (int(part) for part in aspect_ratio.split(":"))
    size = (round(FIRST_FRAME_HEIGHT * width / height), FIRST_FRAME_HEIGHT)
    with Image.open(BytesIO(data)) as opened:
        fitted = ImageOps.fit(ImageOps.exif_transpose(opened).convert("RGB"), size)
    buffer = BytesIO()
    fitted.save(buffer, format="JPEG")
    return types.Image(image_bytes=buffer.getvalue(), mime_type="image/jpeg")


def _pick_video(operation: types.GenerateVideosOperation) -> types.Video:
    if operation.error:
        raise VideoGenUnavailable(f"veo operation failed: {operation.error}")
    response = operation.response
    for generated in (response.generated_videos if response else None) or []:
        if generated.video is not None:
            return generated.video
    if response is not None and response.rai_media_filtered_count:
        reasons = response.rai_media_filtered_reasons or []
        raise VideoGenBlocked(reasons[0] if reasons else "filtered")
    raise VideoGenNoVideo("veo returned no video")
