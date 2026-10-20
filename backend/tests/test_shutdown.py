"""The shutdown on a deploy (#180): work in flight finishes, then the Kapso and Zernio clients
close. The job runner's part is in test_jobs.py, the webhook's in test_whatsapp_router.py."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import pytest

from app.channels.base import ChannelError
from app.channels.router import get_channel, get_inbound_handler
from app.main import app
from app.publishing.base import PublisherError, PublishResult
from app.publishing.factory import get_publisher
from tests.fakes import PERMALINK, FakeChannel, FakePublisher, ScriptedModel, text_reply
from tests.test_chat_handler import (
    CREATE,
    FOLLOW_UP,
    POST_ID,
    REPLY_TEXT,
    SENDER,
    build,
    message,
    start_gated_post,
)
from tests.test_post_publisher import LIVE, STARTED, Rig, approve

# Well past what the work below takes: none of it is cut short.
DEADLINE_S = 5.0


async def test_a_post_being_generated_at_shutdown_is_still_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = ScriptedModel(replies=[CREATE, text_reply("Dale ⏳"), text_reply(FOLLOW_UP)])
    chat, background, channel, gate = await start_gated_post(model, monkeypatch)

    asyncio.get_running_loop().call_later(0.05, gate.set)
    await background.drain(DEADLINE_S)

    assert len(channel.images) == 1
    assert channel.sent[-1] == (SENDER, FOLLOW_UP)
    post = chat.lifecycle.get(SENDER, POST_ID)
    assert post is not None and post.status == "pending_approval"


async def test_an_album_waiting_to_be_answered_at_shutdown_still_gets_its_reply() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    chat, background = build(model)
    await chat.handler.handle(message("text", kind="album", text=None), channel)
    await chat.handler.handle(message("image", text="armame un post con estos muebles"), channel)
    await chat.handler.handle(message("image", text=None), channel)
    assert channel.sent == []

    await background.drain(DEADLINE_S)

    assert channel.sent == [(SENDER, REPLY_TEXT)]
    assert "Attached below, in this order: f1, f2" in model.calls[0][-1]["content"][1]["text"]


async def test_a_post_still_generating_at_the_deadline_is_cancelled_and_logged_by_its_id(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    model = ScriptedModel(replies=[CREATE, text_reply("Dale ⏳")])
    _, background, channel, _ = await start_gated_post(model, monkeypatch)

    with caplog.at_level(logging.WARNING, logger="app.background"):
        await asyncio.wait_for(background.drain(timeout_s=0.1), timeout=2)

    assert f"post {POST_ID} for ***0001" in caplog.text
    assert channel.images == []


@dataclass
class ClosingChannel(FakeChannel):
    """The Kapso client: nothing goes out once it is closed."""

    closed: bool = False

    async def aclose(self) -> None:
        self.closed = True

    async def send_text(self, to: str, text: str) -> str:
        if self.closed:
            raise ChannelError("client closed")
        return await super().send_text(to, text)


@dataclass
class ClosingPublisher(FakePublisher):
    """The Zernio client: a request still in flight when it closes fails."""

    closed: bool = False

    async def aclose(self) -> None:
        self.closed = True

    async def publish(self, *args: Any, **kwargs: Any) -> PublishResult:
        result = await super().publish(*args, **kwargs)
        if self.closed:
            raise PublisherError("client closed")
        return result


async def test_kapso_and_zernio_close_after_a_publish_that_ends_during_the_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = asyncio.Event()
    rig = Rig(ScriptedModel(replies=[approve("p1"), STARTED, LIVE]), ClosingPublisher(gate=gate))
    channel = rig.channel = ClosingChannel()
    post = rig.add_post("p1")
    publisher = rig.publisher
    assert isinstance(publisher, ClosingPublisher)
    # The app as deployed, with the clients a first request would have built.
    monkeypatch.setattr("app.main.get_background_work", lambda: rig.background)
    monkeypatch.setattr("app.channels.router.build_channel", lambda settings: channel)
    monkeypatch.setattr("app.publishing.factory.build_publisher", lambda settings: publisher)
    app.dependency_overrides[get_inbound_handler] = lambda: rig.chat.handler
    get_channel.cache_clear()
    get_publisher.cache_clear()
    get_channel()
    get_publisher()
    try:
        async with app.router.lifespan_context(app):
            await rig.say("subilo")
            asyncio.get_running_loop().call_later(0.05, gate.set)
    finally:
        app.dependency_overrides.clear()
        get_channel.cache_clear()
        get_publisher.cache_clear()

    assert (post.status, post.permalink) == ("published", PERMALINK)
    assert rig.said == [STARTED.text, f"{LIVE.text}\n{PERMALINK}"]
    assert channel.closed and publisher.closed
