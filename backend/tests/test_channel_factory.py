import pytest

from app.channels.factory import build_channel
from app.channels.kapso import KapsoChannel
from app.config import Settings


def test_kapso_needs_api_key_and_phone_number_id(monkeypatch: pytest.MonkeyPatch) -> None:
    # A local .env or shell that sets the phone number id would make the settings complete
    monkeypatch.delenv("KAPSO_PHONE_NUMBER_ID", raising=False)
    with pytest.raises(ValueError, match="KAPSO_API_KEY"):
        build_channel(Settings(_env_file=None, whatsapp_channel="kapso", kapso_api_key="key"))


def test_kapso_channel_is_built_from_settings() -> None:
    settings = Settings(whatsapp_channel="kapso", kapso_api_key="key", kapso_phone_number_id="1")

    assert isinstance(build_channel(settings), KapsoChannel)


def test_simulator_is_not_built_yet() -> None:
    with pytest.raises(NotImplementedError, match="T21"):
        build_channel(Settings(whatsapp_channel="simulator"))
