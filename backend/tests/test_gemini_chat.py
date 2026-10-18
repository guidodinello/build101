from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from google.genai._gaos.lib.compat_errors import APITimeoutError
from pydantic import BaseModel

from app.llm.client import FunctionCall, GeminiChat, LLMError, text_content, user_step


class TimingOutInteractions:
    async def create(self, **_: object) -> None:
        raise APITimeoutError(request=httpx.Request("POST", "https://example.test"))


class TimingOutClient:
    interactions = TimingOutInteractions()


@dataclass
class FakeStep:
    data: dict[str, Any]

    @property
    def type(self) -> str:
        return self.data["type"]

    def model_dump(self, **_: object) -> dict[str, Any]:
        return self.data


@dataclass
class FakeInteraction:
    status: str
    output_text: str | None = None
    steps: list[FakeStep] = field(default_factory=list)
    usage: None = None
    errors: None = None


@dataclass
class FixedInteractions:
    interaction: FakeInteraction
    requests: list[dict[str, Any]] = field(default_factory=list)

    async def create(self, **kwargs: Any) -> FakeInteraction:
        self.requests.append(kwargs)
        return self.interaction


@dataclass
class FixedClient:
    interactions: FixedInteractions


def chat_with(interaction: FakeInteraction) -> tuple[GeminiChat, FixedInteractions]:
    interactions = FixedInteractions(interaction)
    return GeminiChat(FixedClient(interactions), "gemini-3.8-flash"), interactions  # type: ignore[arg-type]


class Title(BaseModel):
    title: str


async def test_an_interactions_timeout_becomes_llm_error() -> None:
    model = GeminiChat(TimingOutClient(), "gemini-3.8-flash")  # type: ignore[arg-type]

    with pytest.raises(LLMError, match="orchestrator"):
        await model.reply("orchestrator", "system", [user_step("hola")], thinking_level="low")


async def test_a_function_call_needs_no_text() -> None:
    call = {"type": "function_call", "id": "call_1", "name": "create_post", "arguments": {"a": 1}}
    model, interactions = chat_with(
        FakeInteraction(
            status="requires_action",
            steps=[FakeStep({"type": "thought", "signature": "s"}), FakeStep(call)],
        )
    )
    tools = [{"type": "function", "name": "create_post"}]

    reply = await model.reply("orchestrator", "system", [], "low", tools=tools)

    assert reply.text == ""
    assert reply.function_calls == [FunctionCall("call_1", "create_post", {"a": 1})]
    assert [step["type"] for step in reply.steps] == ["thought", "function_call"]
    assert interactions.requests[0]["tools"] == tools


async def test_no_text_and_no_call_is_an_error() -> None:
    model, interactions = chat_with(FakeInteraction(status="completed", output_text=""))

    with pytest.raises(LLMError):
        await model.reply("orchestrator", "system", [], "low")
    assert "tools" not in interactions.requests[0]


async def test_structured_output_is_validated_against_the_schema() -> None:
    model, interactions = chat_with(
        FakeInteraction(status="completed", output_text='{"title": "Mesa"}')
    )

    title = await model.structured("drafter", "system", [text_content("hola")], Title, "medium")

    assert title == Title(title="Mesa")
    response_format = interactions.requests[0]["response_format"]
    assert response_format["schema"]["required"] == ["title"]


async def test_structured_output_that_does_not_match_is_an_error() -> None:
    model, _ = chat_with(FakeInteraction(status="completed", output_text='{"name": "Mesa"}'))

    with pytest.raises(LLMError, match="Title"):
        await model.structured("drafter", "system", [text_content("hola")], Title, "medium")
