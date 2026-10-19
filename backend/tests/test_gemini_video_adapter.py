from io import BytesIO
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from google.genai import errors, types
from PIL import Image

from app.videogen.base import (
    VideoGenBlocked,
    VideoGenNoVideo,
    VideoGenRejected,
    VideoGenTimeout,
    VideoGenUnavailable,
)
from app.videogen.gemini import GeminiVideoGen
from tests.conftest import make_image

LITE = "veo-3.1-lite-generate-preview"
FAST = "veo-3.1-fast-generate-preview"
MP4 = b"\x00\x00\x00\x18ftypmp42 fake clip"


def operation(
    *,
    done: bool = True,
    videos: list[types.Video] | None = None,
    error: dict[str, Any] | None = None,
    filtered: int | None = None,
    reasons: list[str] | None = None,
) -> types.GenerateVideosOperation:
    return types.GenerateVideosOperation(
        name="operations/1",
        done=done,
        error=error,
        response=types.GenerateVideosResponse(
            generated_videos=[types.GeneratedVideo(video=video) for video in videos or []],
            rai_media_filtered_count=filtered,
            rai_media_filtered_reasons=reasons,
        ),
    )


def finished() -> types.GenerateVideosOperation:
    return operation(videos=[types.Video(uri="files/abc", mime_type="video/mp4")])


class FakeVideoClient:
    """The slice of `genai.Client.aio` the adapter uses; records what it was sent."""

    def __init__(
        self,
        submitted: types.GenerateVideosOperation,
        polls: list[types.GenerateVideosOperation] | None = None,
    ) -> None:
        self.submitted = submitted
        self.polls = list(polls or [])
        self.generate_calls: list[dict[str, Any]] = []
        self.poll_count = 0
        self.downloaded: list[types.Video] = []
        self.aio = SimpleNamespace(
            models=SimpleNamespace(generate_videos=self._generate),
            operations=SimpleNamespace(get=self._get),
            files=SimpleNamespace(download=self._download),
        )

    async def _generate(self, **kwargs: Any) -> types.GenerateVideosOperation:
        self.generate_calls.append(kwargs)
        return self.submitted

    async def _get(self, op: types.GenerateVideosOperation) -> types.GenerateVideosOperation:
        self.poll_count += 1
        return self.polls.pop(0)

    async def _download(self, *, file: types.Video) -> bytes:
        self.downloaded.append(file)
        return MP4


def adapter(client: FakeVideoClient, model: str = LITE, timeout_s: float = 5) -> GeminiVideoGen:
    return GeminiVideoGen(
        client,  # type: ignore[arg-type]
        model,
        max_concurrency=1,
        poll_interval_s=0.001,
        timeout_s=timeout_s,
    )


async def test_polls_until_done_then_downloads_the_clip() -> None:
    client = FakeVideoClient(operation(done=False), [operation(done=False), finished()])

    video = await adapter(client).generate("a clip", [make_image((1080, 1350))])

    assert client.poll_count == 2
    assert video.data == MP4
    assert video.mime == "video/mp4"
    assert video.provider == "gemini"
    assert video.model == LITE
    assert video.duration_seconds == 8
    assert client.downloaded[0].uri == "files/abc"


async def test_lite_sends_the_first_reference_as_the_first_frame() -> None:
    client = FakeVideoClient(finished())

    await adapter(client, LITE).generate(
        "a clip", [make_image((1080, 1350)), make_image((800, 800))], duration_seconds=6
    )

    call = client.generate_calls[0]
    config: types.GenerateVideosConfig = call["config"]
    source: types.GenerateVideosSource = call["source"]
    assert call["model"] == LITE
    assert source.prompt == "a clip"
    assert source.image is not None
    assert config.reference_images is None
    assert config.duration_seconds == 6
    assert config.aspect_ratio == "9:16"
    assert config.person_generation == "allow_adult"


async def test_the_first_frame_is_cropped_to_the_clips_ratio() -> None:
    client = FakeVideoClient(finished())

    await adapter(client).generate("a clip", [make_image((1080, 1350))], aspect_ratio="9:16")

    image = client.generate_calls[0]["source"].image
    with Image.open(BytesIO(image.image_bytes)) as frame:
        assert abs(frame.width / frame.height - 9 / 16) < 0.01
    assert image.mime_type == "image/jpeg"


async def test_fast_sends_up_to_three_asset_references_and_forces_eight_seconds() -> None:
    client = FakeVideoClient(finished())
    images = [make_image((800, 800), color=color) for color in ("red", "green", "blue", "black")]

    video = await adapter(client, FAST).generate("a clip", images, duration_seconds=4)

    call = client.generate_calls[0]
    config: types.GenerateVideosConfig = call["config"]
    assert call["source"].image is None
    assert config.reference_images is not None
    assert len(config.reference_images) == 3
    assert {ref.reference_type for ref in config.reference_images} == {
        types.VideoGenerationReferenceType.ASSET
    }
    assert config.duration_seconds == 8
    assert video.duration_seconds == 8


async def test_text_only_call_sends_no_image_in_either_mode() -> None:
    client = FakeVideoClient(finished())

    await adapter(client).generate("a clip", [])

    call = client.generate_calls[0]
    assert call["source"].image is None
    assert call["config"].reference_images is None
    # Text-to-video accepts only `allow_all` (the default), never `allow_adult`
    assert call["config"].person_generation is None


async def test_the_submit_call_never_retries() -> None:
    client = FakeVideoClient(finished())

    await adapter(client).generate("a clip", [make_image((800, 800))])

    config: types.GenerateVideosConfig = client.generate_calls[0]["config"]
    assert config.http_options is not None
    assert config.http_options.retry_options is not None
    assert config.http_options.retry_options.attempts == 1


@pytest.mark.parametrize(
    ("kwargs"), [{"aspect_ratio": "1:1"}, {"duration_seconds": 5}], ids=["ratio", "duration"]
)
async def test_a_bad_ratio_or_duration_is_refused_before_any_call(kwargs: dict[str, Any]) -> None:
    client = FakeVideoClient(finished())

    with pytest.raises(ValueError):
        await adapter(client).generate("a clip", [], **kwargs)

    assert client.generate_calls == []


async def test_an_operation_error_is_unavailable() -> None:
    client = FakeVideoClient(operation(error={"message": "boom"}))

    with pytest.raises(VideoGenUnavailable, match="boom"):
        await adapter(client).generate("a clip", [])


async def test_rai_filtering_is_blocked_with_its_reason() -> None:
    client = FakeVideoClient(operation(filtered=1, reasons=["child safety"]))

    with pytest.raises(VideoGenBlocked) as raised:
        await adapter(client).generate("a clip", [])

    assert raised.value.reason == "child safety"


async def test_no_video_and_no_filter_reason_is_no_video() -> None:
    client = FakeVideoClient(operation())

    with pytest.raises(VideoGenNoVideo):
        await adapter(client).generate("a clip", [])


async def test_a_clip_that_never_finishes_times_out() -> None:
    client = FakeVideoClient(operation(done=False), [operation(done=False)] * 10_000)

    with pytest.raises(VideoGenTimeout):
        await adapter(client, timeout_s=0.05).generate("a clip", [])


async def test_an_api_error_is_unavailable() -> None:
    client = FakeVideoClient(finished())

    async def refuse(**kwargs: Any) -> None:
        raise errors.APIError(503, {"error": {"message": "overloaded", "status": "UNAVAILABLE"}})

    client.aio.models.generate_videos = refuse

    with pytest.raises(VideoGenUnavailable, match="overloaded"):
        await adapter(client).generate("a clip", [])


def failing_submit(client: FakeVideoClient, exc: Exception) -> None:
    async def refuse(**kwargs: Any) -> None:
        raise exc

    client.aio.models.generate_videos = refuse


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ReadTimeout("slow"),
        httpx.ConnectError("down"),
        errors.ServerError(500, {"error": {"message": "oops", "status": "INTERNAL"}}),
        errors.ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}}),
    ],
    ids=["read-timeout", "connect-error", "5xx", "429"],
)
async def test_network_server_and_rate_limit_errors_are_unavailable(exc: Exception) -> None:
    client = FakeVideoClient(finished())
    failing_submit(client, exc)

    with pytest.raises(VideoGenUnavailable) as raised:
        await adapter(client).generate("a clip", [])

    assert not isinstance(raised.value, VideoGenRejected)


async def test_a_refused_request_is_rejected_not_unavailable() -> None:
    client = FakeVideoClient(finished())
    failing_submit(
        client, errors.ClientError(400, {"error": {"message": "bad image", "status": "INVALID"}})
    )

    with pytest.raises(VideoGenRejected, match="bad image") as raised:
        await adapter(client).generate("a clip", [])

    assert not isinstance(raised.value, VideoGenUnavailable)


async def test_image_modes_send_allow_adult() -> None:
    lite, fast = FakeVideoClient(finished()), FakeVideoClient(finished())

    await adapter(lite, LITE).generate("a clip", [make_image((800, 800))])
    await adapter(fast, FAST).generate("a clip", [make_image((800, 800))])

    assert lite.generate_calls[0]["config"].person_generation == "allow_adult"
    assert fast.generate_calls[0]["config"].person_generation == "allow_adult"
