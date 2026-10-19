from app.videogen.base import VideoGenPort
from app.videogen.mock import MockVideoGen


async def test_the_mock_returns_the_bundled_mp4() -> None:
    mock = MockVideoGen(delay_s=0)

    video = await mock.generate("a clip", [b"image"], aspect_ratio="9:16", duration_seconds=6)

    assert isinstance(mock, VideoGenPort)
    assert video.data[4:8] == b"ftyp"
    assert video.mime == "video/mp4"
    assert video.provider == "mock"
    assert video.duration_seconds == 6
