import json
from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from app.channels.base import ChannelPort, InboundMessage
from app.channels.inbound import InMemoryDedupeStore
from app.channels.router import get_channel, get_dedupe_store, get_inbound_handler
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
