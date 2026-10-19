import logging
from typing import Any

import pytest

from app.conversation.chat import ChatHandler
from tests.fakes import FakeChannel, ScriptedModel, call_reply, text_reply
from tests.test_chat_handler import build, message

ARGUMENT = "SENTINEL-ARGUMENT mesa de roble a 4500"
RESULT = "SENTINEL-RESULT https://instagram.test/p/abc"
REPLY = "SENTINEL-REPLY quedó hermosa la mesa"
SENTINELS = (ARGUMENT, RESULT, REPLY)


async def run_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    async def tool_result(self: ChatHandler, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"saved": RESULT}

    monkeypatch.setattr(ChatHandler, "_tool_result", tool_result)
    model = ScriptedModel(replies=[call_reply("remember", note=ARGUMENT), text_reply(REPLY)])
    await build(model)[0].handle(message("text"), FakeChannel())


async def test_info_logs_of_a_turn_have_no_owner_content(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    await run_turn(monkeypatch)

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "tool remember" in logged  # the turn did log
    assert not [sentinel for sentinel in SENTINELS if sentinel in logged]


async def test_debug_logs_still_show_the_content(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="app.conversation.chat")

    await run_turn(monkeypatch)

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert all(sentinel in logged for sentinel in SENTINELS)
