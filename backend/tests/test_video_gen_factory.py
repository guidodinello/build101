import pytest

from app.config import Settings
from app.llm.ledger import MeteredVideoGen
from app.videogen import factory
from app.videogen.factory import build_video_gen
from app.videogen.gemini import GeminiVideoGen
from app.videogen.mock import MockVideoGen


def test_video_generation_is_off_by_default() -> None:
    settings = Settings(_env_file=None)

    assert settings.video_gen_enabled is False
    assert settings.video_gen == "mock"
    assert build_video_gen(settings) is None


def test_flag_off_builds_nothing_even_with_gemini_and_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("no client may be built while the flag is off")

    monkeypatch.setattr(factory.GeminiVideoGen, "from_api_key", fail)
    settings = Settings(
        _env_file=None, video_gen_enabled=False, video_gen="gemini", gemini_video_api_key="k"
    )

    assert build_video_gen(settings) is None


def test_gemini_never_falls_back_to_the_image_key() -> None:
    settings = Settings(
        _env_file=None, video_gen_enabled=True, video_gen="gemini", gemini_api_key="image-key"
    )

    with pytest.raises(ValueError, match="GEMINI_VIDEO_API_KEY"):
        build_video_gen(settings)


def test_gemini_with_its_own_key_builds_the_adapter() -> None:
    settings = Settings(
        _env_file=None, video_gen_enabled=True, video_gen="gemini", gemini_video_api_key="k"
    )

    video_gen = build_video_gen(settings)

    assert isinstance(video_gen, MeteredVideoGen) and isinstance(video_gen.inner, GeminiVideoGen)


def test_the_mock_is_built_when_enabled() -> None:
    settings = Settings(_env_file=None, video_gen_enabled=True, video_gen="mock")

    video_gen = build_video_gen(settings)

    assert isinstance(video_gen, MeteredVideoGen) and isinstance(video_gen.inner, MockVideoGen)
