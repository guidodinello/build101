import json

import pytest

from app.channels.base import ChannelError
from app.channels.kapso_webhook import parse_message, verify_signature
from tests.conftest import FIXTURES, sign

SECRET = "test-secret"


def body(name: str) -> dict:
    return json.loads((FIXTURES / f"kapso_message_{name}.json").read_text())["body"]


def test_text_message() -> None:
    message = parse_message(body("text"))

    assert message.kind == "text"
    assert message.text == "hola bot"
    assert message.message_id == "wamid.FAKE0000000000000000000001"
    assert message.sender == "59899000001"
    assert message.phone_number_id == "fake-phone_number_id"
    assert message.timestamp == 1792270000


def test_button_reply_keeps_our_button_id() -> None:
    message = parse_message(body("interactive"))

    assert message.kind == "button"
    assert message.button is not None
    assert message.button.id == "post_approve:00000000-0000-0000-0000-000000000001"
    assert message.button.title == "Publicar"
    assert message.text is None


def test_image_carries_caption_from_kapso_and_media_url() -> None:
    message = parse_message(body("image"))

    assert message.kind == "image"
    assert message.text == "foto de prueba"
    assert message.media is not None
    assert message.media.url == "https://example.test/media/fake"
    assert message.media.mime_type == "image/jpeg"
    assert message.media.byte_size == 168882


def test_image_prefers_metas_own_caption_field() -> None:
    payload = body("image")
    payload["message"]["image"]["caption"] = "meta caption"

    assert parse_message(payload).text == "meta caption"


def test_audio_carries_provider_transcript() -> None:
    message = parse_message(body("audio"))

    assert message.kind == "audio"
    assert message.text is None
    assert message.audio is not None
    assert message.audio.provider_transcript == "Quiero un post para la promo del sábado"
    assert message.audio.mime_type == "audio/ogg; codecs=opus"
    assert message.audio.byte_size == 5153
    assert message.audio.media_id == "wamid.FAKE0000000000000000000001"


def test_audio_without_transcript_has_none() -> None:
    payload = body("audio")
    payload["message"]["kapso"]["transcript"] = {"text": "  "}

    assert parse_message(payload).audio.provider_transcript is None


def test_unknown_type_is_other() -> None:
    payload = body("text")
    payload["message"]["type"] = "sticker"

    assert parse_message(payload).kind == "other"


def test_missing_message_id_falls_back_to_the_idempotency_key() -> None:
    payload = body("text")
    del payload["message"]["id"]

    assert parse_message(payload, fallback_id="key-1").message_id == "key-1"
    with pytest.raises(ChannelError):
        parse_message(payload)


def test_verify_signature() -> None:
    raw = b'{"a": 1}'

    assert verify_signature(raw, sign(raw, SECRET), SECRET)
    assert not verify_signature(raw, sign(raw, "other"), SECRET)
    assert not verify_signature(raw + b" ", sign(raw, SECRET), SECRET)
    assert not verify_signature(raw, None, SECRET)
    assert not verify_signature(raw, sign(raw, ""), "")


def test_an_album_header_is_its_own_kind() -> None:
    payload = body("text")
    payload["message"] = {
        "id": "wamid.ALBUM",
        "from": "59899000001",
        "type": "unsupported",
        "unsupported": {"type": "album", "raw_type": "album"},
    }

    assert parse_message(payload).kind == "album"


def test_a_payload_without_what_its_kind_needs_raises_the_channel_error() -> None:
    no_phone_number = body("text")
    del no_phone_number["phone_number_id"]
    no_text_block = body("text")
    del no_text_block["message"]["text"]
    no_sender = body("text")
    del no_sender["message"]["from"]

    for payload in (no_phone_number, no_text_block, no_sender, {"unexpected": True}):
        with pytest.raises(ChannelError):
            parse_message(payload)


def test_null_optional_blocks_are_treated_as_absent() -> None:
    payload = body("image")
    payload["message"]["kapso"] = None
    payload["message"]["timestamp"] = "not a number"

    message = parse_message(payload)

    assert message.kind == "image"
    assert message.media is not None
    assert message.media.url is None
    assert message.timestamp is None
