import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from app.channels.base import ChannelError, ChannelPort, InboundMessage
from app.channels.inbound import InMemoryDedupeStore
from app.channels.router import (
    MAX_BODY_BYTES,
    get_channel,
    get_dedupe_store,
    get_inbound_handler,
)
from app.config import Settings, get_settings
from app.main import app
from tests.conftest import FIXTURES, sign

SECRET = "test-secret"
EVENT = "whatsapp.message.received"


@dataclass
class RecordingHandler:
    handled: list[InboundMessage] = field(default_factory=list)

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        self.handled.append(message)


@pytest.fixture
def handler() -> RecordingHandler:
    return RecordingHandler()


@pytest.fixture
def client(handler: RecordingHandler) -> Iterator[TestClient]:
    app.dependency_overrides[get_settings] = lambda: Settings(kapso_webhook_secret=SECRET)
    # One fresh store per test: all fixtures share the same message id.
    store = InMemoryDedupeStore()
    app.dependency_overrides[get_dedupe_store] = lambda: store
    app.dependency_overrides[get_inbound_handler] = lambda: handler
    app.dependency_overrides[get_channel] = lambda: object()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def raw_fixture(name: str) -> bytes:
    body = json.loads((FIXTURES / f"kapso_message_{name}.json").read_text())["body"]
    return json.dumps(body).encode()


def post(
    client: TestClient,
    raw: bytes,
    *,
    signature: str | None = None,
    event: str = EVENT,
    key: str = "key-1",
):
    headers = {"x-webhook-event": event, "x-idempotency-key": key}
    if signature is not None:
        headers["x-webhook-signature"] = signature
    return client.post("/webhooks/whatsapp", content=raw, headers=headers)


def test_valid_signature_is_accepted_and_handled(
    client: TestClient, handler: RecordingHandler
) -> None:
    raw = raw_fixture("text")

    response = post(client, raw, signature=sign(raw, SECRET))

    assert response.status_code == 200
    assert [m.text for m in handler.handled] == ["hola bot"]


def test_invalid_signature_is_rejected(client: TestClient, handler: RecordingHandler) -> None:
    raw = raw_fixture("text")

    response = post(client, raw, signature=sign(raw, "wrong-secret"))

    assert response.status_code == 401
    assert handler.handled == []


def test_missing_signature_is_rejected(client: TestClient, handler: RecordingHandler) -> None:
    response = post(client, raw_fixture("text"))

    assert response.status_code == 401
    assert handler.handled == []


def test_duplicate_delivery_is_handled_once(client: TestClient, handler: RecordingHandler) -> None:
    raw = raw_fixture("text")
    signature = sign(raw, SECRET)

    first = post(client, raw, signature=signature)
    second = post(client, raw, signature=signature)

    assert first.json() == {"status": "ok"}
    assert second.json() == {"status": "duplicate"}
    assert len(handler.handled) == 1


def test_other_events_are_acknowledged_and_ignored(
    client: TestClient, handler: RecordingHandler
) -> None:
    raw = b'{"status": "delivered"}'

    response = post(client, raw, signature=sign(raw, SECRET), event="whatsapp.message.delivered")

    assert response.status_code == 200
    assert handler.handled == []


def test_unparseable_message_is_acknowledged_not_retried(
    client: TestClient, handler: RecordingHandler
) -> None:
    raw = b'{"unexpected": true}'

    response = post(client, raw, signature=sign(raw, SECRET))

    assert response.status_code == 200
    assert handler.handled == []


def test_no_configured_secret_rejects_everything() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(kapso_webhook_secret=None)
    app.dependency_overrides[get_channel] = lambda: object()
    try:
        with TestClient(app) as test_client:
            raw = raw_fixture("text")
            assert post(test_client, raw, signature=sign(raw, "")).status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_health_boots_without_any_kapso_config() -> None:
    get_channel.cache_clear()
    with TestClient(app) as test_client:
        assert test_client.get("/health").status_code == 200


def test_oversized_declared_body_is_rejected_before_the_signature_check(
    client: TestClient, handler: RecordingHandler
) -> None:
    raw = b"x" * (MAX_BODY_BYTES + 1)

    response = post(client, raw, signature=sign(raw, SECRET))

    assert response.status_code == 413
    assert handler.handled == []


def test_oversized_body_without_content_length_is_rejected_while_reading(
    client: TestClient, handler: RecordingHandler
) -> None:
    def chunks() -> Iterator[bytes]:
        for _ in range(5):
            yield b"x" * (MAX_BODY_BYTES // 4)

    response = client.post(
        "/webhooks/whatsapp",
        content=chunks(),  # an iterator is sent chunked, with no Content-Length
        headers={"x-webhook-event": EVENT, "x-webhook-signature": "irrelevant"},
    )

    assert response.status_code == 413
    assert handler.handled == []


def test_a_body_at_the_cap_is_still_read(client: TestClient) -> None:
    raw = b"x" * MAX_BODY_BYTES

    assert post(client, raw, signature=sign(raw, "wrong")).status_code == 401


def test_a_failing_handler_is_logged_with_the_message_id_and_no_payload(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    class FailingHandler:
        async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
            raise ChannelError("kapso 500: boom")

    app.dependency_overrides[get_inbound_handler] = FailingHandler
    raw = raw_fixture("text")

    with caplog.at_level(logging.ERROR, logger="app.channels.router"):
        response = post(client, raw, signature=sign(raw, SECRET))

    assert response.status_code == 200
    failure = next(r for r in caplog.records if r.levelno == logging.ERROR)
    assert failure.getMessage() == (
        "inbound handling failed: text id=wamid.FAKE0000000000000000000001"
    )
    assert "hola bot" not in caplog.text
