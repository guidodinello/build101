import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.channels.router import get_channel, get_inbound_handler
from app.config import (
    Settings,
    adapters_in_use,
    check_production,
    get_settings,
    production_problems,
)
from app.main import app

SECRETS = {
    "database_url": "postgresql+asyncpg://postgres:db-password@db.example.com:5432/postgres",
    "supabase_service_role_key": "supabase-service-role-secret",
    "gemini_api_key": "gemini-secret",
    "gemini_video_api_key": "gemini-video-secret",
    "kapso_api_key": "kapso-secret",
    "kapso_webhook_secret": "kapso-webhook-secret",
    "renderer_secret": "renderer-secret",
    "zernio_api_key": "zernio-secret",
    "instagram_app_secret": "instagram-app-secret",
    "dev_token": "dev-token-secret",
}


def production(**changes: Any) -> dict[str, Any]:
    """A complete production config, as Settings kwargs; `None` drops a setting (unset)."""
    config: dict[str, Any] = {
        "env": "prod",
        **SECRETS,
        "supabase_url": "https://ref.supabase.co",
        "frontend_url": "https://neitorai.vercel.app",
        "frontend_origins": "https://neitorai.vercel.app",
        "whatsapp_bot_number": "56920403095",
        "image_gen": "gemini",
        "renderer": "takumi",
        "renderer_url": "https://neitorai.vercel.app",
        "inbound_handler": "chat",
        "public_backend_url": "https://backend.up.railway.app",
        "whatsapp_channel": "kapso",
        "kapso_phone_number_id": "1234567890",
        "publisher": "zernio",
        "zernio_account_id": "account-1",
        "instagram": "meta",
        "instagram_app_id": "app-1",
    }
    config.update(changes)
    return {name: value for name, value in config.items() if value is not None}


def set_production_env(monkeypatch: pytest.MonkeyPatch, **changes: Any) -> None:
    """A complete production config in the environment, the way Railway passes it."""
    for name, value in production(**changes).items():
        monkeypatch.setenv(name.upper(), value)
    get_settings.cache_clear()


def problems(**changes: Any) -> set[str]:
    """The settings a complete config with `changes` is refused for; the error names each."""
    settings = Settings(**production(**changes))
    found = production_problems(settings)
    with pytest.raises(ValueError) as error:
        check_production(settings)
    assert all(name in str(error.value) for name in found)
    return set(found)


@pytest.mark.parametrize("publisher", [None, "mock"], ids=["unset", "mock"])
def test_prod_refuses_to_start_on_the_mock_publisher(publisher: str | None) -> None:
    assert problems(publisher=publisher) == {"PUBLISHER"}


@pytest.mark.parametrize(
    ("setting", "fallback", "name"),
    [
        ("image_gen", "mock", "IMAGE_GEN"),
        ("renderer", "mock", "RENDERER"),
        ("instagram", "mock", "INSTAGRAM"),
        ("inbound_handler", "echo", "INBOUND_HANDLER"),
        ("whatsapp_channel", "simulator", "WHATSAPP_CHANNEL"),
    ],
)
def test_prod_refuses_to_start_on_every_demo_fallback(
    setting: str, fallback: str, name: str
) -> None:
    assert problems(**{setting: fallback}) == {name}


@pytest.mark.parametrize("setting", ["image_gen", "renderer", "instagram"])
def test_an_unset_adapter_is_the_mock_and_refused(setting: str) -> None:
    assert problems(**{setting: None}) == {setting.upper()}


def test_the_mock_video_generator_is_refused_only_while_reels_are_on() -> None:
    check_production(Settings(**production(video_gen_enabled=False, video_gen="mock")))

    assert problems(video_gen_enabled=True, video_gen="mock") == {"VIDEO_GEN"}


@pytest.mark.parametrize(
    "setting",
    [
        "database_url",
        "supabase_url",
        "supabase_service_role_key",
        "gemini_api_key",
        "kapso_api_key",
        "kapso_webhook_secret",
        "kapso_phone_number_id",
        "public_backend_url",
        "renderer_url",
        "renderer_secret",
        "zernio_api_key",
        "zernio_account_id",
        "instagram_app_id",
        "instagram_app_secret",
        "whatsapp_bot_number",
    ],
)
def test_prod_refuses_to_start_without_a_setting_it_needs(setting: str) -> None:
    assert problems(**{setting: None}) == {setting.upper()}


def test_instagram_off_starts_without_the_meta_app() -> None:
    settings = Settings(
        **production(instagram="off", instagram_app_id=None, instagram_app_secret=None)
    )

    check_production(settings)
    assert adapters_in_use(settings)["INSTAGRAM"] == "off"


@pytest.mark.parametrize("instagram", ["mock", None], ids=["mock", "unset"])
def test_the_meta_app_is_needed_only_with_instagram_meta(instagram: str | None) -> None:
    assert problems(instagram=instagram, instagram_app_id=None, instagram_app_secret=None) == {
        "INSTAGRAM"
    }


@pytest.mark.parametrize("blank", ["", " ", "\t"], ids=["empty", "space", "tab"])
def test_a_blank_setting_counts_as_unset(blank: str) -> None:
    assert problems(kapso_webhook_secret=blank) == {"KAPSO_WEBHOOK_SECRET"}


def test_the_video_key_is_needed_only_while_reels_are_on() -> None:
    check_production(Settings(**production(gemini_video_api_key=None)))

    assert problems(video_gen_enabled=True, video_gen="gemini", gemini_video_api_key=None) == {
        "GEMINI_VIDEO_API_KEY"
    }


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("frontend_url", None),
        ("frontend_url", "http://localhost:3000"),
        ("frontend_origins", None),
        ("frontend_origins", " , "),
        ("frontend_origins", "https://neitorai.vercel.app,http://localhost:3000"),
        ("frontend_origins", "http://127.0.0.1:3000"),
        ("frontend_url", "http://127.0.1.1:3000"),
        ("frontend_url", "http://[0:0:0:0:0:0:0:1]:3000"),
        ("frontend_url", "http://localhost.:3000"),
        ("frontend_url", "http://app.localhost:3000"),
        ("frontend_url", "http://127.1:3000"),
        ("renderer_url", "http://2130706433"),
        ("public_backend_url", "http://0x7f.0.0.1"),
        ("frontend_origins", "http://10.1"),
        ("frontend_origins", "http://192.168.1.5:3000"),
        ("public_backend_url", "http://localhost:8000"),
        ("renderer_url", "http://localhost:3000"),
        ("renderer_url", "neitorai.vercel.app"),
    ],
)
def test_prod_refuses_a_frontend_or_public_url_that_is_not_public(
    setting: str, value: str | None
) -> None:
    assert problems(**{setting: value}) == {setting.upper()}


def test_one_error_names_every_wrong_setting() -> None:
    names = problems(
        publisher="mock",
        inbound_handler="echo",
        database_url=None,
        kapso_webhook_secret=None,
        frontend_origins="http://localhost:3000",
    )

    assert names == {
        "PUBLISHER",
        "INBOUND_HANDLER",
        "DATABASE_URL",
        "KAPSO_WEBHOOK_SECRET",
        "FRONTEND_ORIGINS",
    }


def test_prod_with_nothing_set_names_every_setting_production_needs() -> None:
    with pytest.raises(ValueError) as error:
        check_production(Settings(env="prod"))

    message = str(error.value)
    for name in (
        "IMAGE_GEN",
        "RENDERER",
        "PUBLISHER",
        "INSTAGRAM",
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "GEMINI_API_KEY",
        "KAPSO_API_KEY",
        "KAPSO_WEBHOOK_SECRET",
        "KAPSO_PHONE_NUMBER_ID",
        "PUBLIC_BACKEND_URL",
        "FRONTEND_URL",
        "FRONTEND_ORIGINS",
        "RENDERER_URL",
        "RENDERER_SECRET",
        "ZERNIO_API_KEY",
        "ZERNIO_ACCOUNT_ID",
        "WHATSAPP_BOT_NUMBER",
    ):
        assert name in message


def test_the_error_never_contains_a_value() -> None:
    config = production(publisher="mock", frontend_url="http://localhost:3000/private-path")

    with pytest.raises(ValueError) as error:
        check_production(Settings(**config))

    message = str(error.value)
    for value in [*SECRETS.values(), config["frontend_url"], config["zernio_account_id"]]:
        assert value not in message


def test_locally_mocks_and_missing_keys_are_fine() -> None:
    check_production(Settings())
    check_production(Settings(env="local", publisher="mock", inbound_handler="echo"))


def test_the_app_refuses_to_start_in_prod_with_the_mock_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENV", "prod")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="PUBLISHER"), TestClient(app):
        pass


def test_a_complete_production_config_starts_and_logs_the_adapters_by_name_only(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    set_production_env(monkeypatch)
    monkeypatch.setattr("app.main.build_job_runner", lambda *_: None)
    get_channel.cache_clear()
    app.dependency_overrides[get_inbound_handler] = lambda: None
    try:
        with caplog.at_level(logging.INFO), TestClient(app) as client:
            assert client.get("/health").json() == {"status": "ok"}
    finally:
        app.dependency_overrides.clear()
        get_channel.cache_clear()

    lines = [record.getMessage() for record in caplog.records if record.name == "app.main"]
    assert (
        "adapters in use: IMAGE_GEN=gemini RENDERER=takumi PUBLISHER=zernio INSTAGRAM=meta "
        "VIDEO_GEN=off INBOUND_HANDLER=chat WHATSAPP_CHANNEL=kapso"
    ) in lines
    for value in SECRETS.values():
        assert value not in caplog.text


def test_the_app_starts_locally_on_mocks_and_logs_the_adapters_by_name_only(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    for name in ("zernio_api_key", "renderer_secret", "instagram_app_secret", "dev_token"):
        monkeypatch.setenv(name.upper(), SECRETS[name])
    get_settings.cache_clear()
    app.dependency_overrides[get_inbound_handler] = lambda: None
    try:
        with caplog.at_level(logging.INFO, logger="app.main"), TestClient(app) as client:
            assert client.get("/health").json() == {"status": "ok"}
    finally:
        app.dependency_overrides.clear()

    lines = [record.getMessage() for record in caplog.records if record.name == "app.main"]
    assert (
        "adapters in use: IMAGE_GEN=mock RENDERER=mock PUBLISHER=mock INSTAGRAM=mock "
        "VIDEO_GEN=off INBOUND_HANDLER=chat WHATSAPP_CHANNEL=kapso"
    ) in lines
    for value in SECRETS.values():
        assert value not in caplog.text


def test_the_adapters_are_named_never_their_keys() -> None:
    adapters = adapters_in_use(Settings(**production(video_gen_enabled=True, video_gen="gemini")))

    assert adapters == {
        "IMAGE_GEN": "gemini",
        "RENDERER": "takumi",
        "PUBLISHER": "zernio",
        "INSTAGRAM": "meta",
        "VIDEO_GEN": "gemini",
        "INBOUND_HANDLER": "chat",
        "WHATSAPP_CHANNEL": "kapso",
    }
