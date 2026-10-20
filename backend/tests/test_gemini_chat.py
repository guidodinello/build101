import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from google import genai
from google.genai._gaos.lib.compat_errors import APITimeoutError
from pydantic import BaseModel

from app.llm import client as client_module
from app.llm.client import (
    HTTP_OPTIONS,
    FunctionCall,
    GeminiChat,
    LLMError,
    WebSource,
    text_content,
    user_step,
)


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
    assert response_format["schema_"]["required"] == ["title"]


async def test_structured_output_that_does_not_match_is_an_error() -> None:
    model, _ = chat_with(FakeInteraction(status="completed", output_text='{"name": "Mesa"}'))

    with pytest.raises(LLMError, match="Title"):
        await model.structured("drafter", "system", [text_content("hola")], Title, "medium")


def quota_exhausted(_: httpx.Request) -> httpx.Response:
    # Shape of the free-tier daily-quota 429 seen on 2026-10-18: Retry-After of ~19 h.
    body = {"error": {"message": "Rate limit exceeded", "code": "too_many_requests"}}
    return httpx.Response(429, headers={"retry-after": "69915"}, json=body)


async def test_a_429_with_a_long_retry_after_fails_fast() -> None:
    transport = httpx.AsyncClient(transport=httpx.MockTransport(quota_exhausted))
    options = HTTP_OPTIONS.model_copy(update={"httpx_async_client": transport})
    client = genai.Client(api_key="test-key", http_options=options).aio
    model = GeminiChat(client, "gemini-3.8-flash")

    with pytest.raises(LLMError, match="orchestrator"):
        await asyncio.wait_for(
            model.reply("orchestrator", "system", [user_step("hola")], thinking_level="low"),
            timeout=5,
        )


class HangingInteractions:
    async def create(self, **_: object) -> None:
        await asyncio.sleep(3600)


class HangingClient:
    interactions = HangingInteractions()


async def test_a_call_that_never_returns_hits_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "REQUEST_TIMEOUT_S", 0.05)
    model = GeminiChat(HangingClient(), "gemini-3.8-flash")  # type: ignore[arg-type]

    with pytest.raises(LLMError, match="no answer within"):
        await model.reply("orchestrator", "system", [user_step("hola")], thinking_level="low")


async def test_a_grounded_call_returns_the_output_and_what_the_tools_read() -> None:
    steps = [
        {"type": "url_context_call", "id": "u1", "arguments": {"urls": ["https://a.uy"]}},
        {
            "type": "url_context_result",
            "call_id": "u1",
            "result": [
                {"url": "https://a.uy", "status": "success"},
                {"url": "https://paywalled.uy", "status": "paywall"},
            ],
        },
        {"type": "google_search_call", "id": "g1", "arguments": {"queries": ["madera"]}},
        {"type": "google_search_result", "call_id": "g1", "result": [{"search_suggestions": "x"}]},
        {
            "type": "model_output",
            "content": [
                {
                    "type": "text",
                    "text": '{"title": "Mesa"}',
                    "annotations": [
                        {"type": "url_citation", "url": "https://a.uy", "title": "A"},
                        {"type": "url_citation", "url": "https://b.uy/nota"},
                    ],
                }
            ],
        },
    ]
    model, interactions = chat_with(
        FakeInteraction(
            status="completed",
            output_text='{"title": "Mesa"}',
            steps=[FakeStep(step) for step in steps],
        )
    )
    tools = [{"type": "url_context"}, {"type": "google_search"}]

    grounded = await model.grounded(
        "niche_analyst", "system", [text_content("hola")], Title, "medium", tools
    )

    assert grounded.output == Title(title="Mesa")
    assert grounded.sources == [WebSource("https://a.uy", "A"), WebSource("https://b.uy/nota")]
    request = interactions.requests[0]
    assert request["tools"] == tools
    assert request["response_format"]["schema_"]["required"] == ["title"]


async def test_a_grounded_call_with_no_output_is_an_error() -> None:
    model, _ = chat_with(FakeInteraction(status="failed"))

    with pytest.raises(LLMError, match="niche_analyst"):
        await model.grounded("niche_analyst", "system", [], Title, "medium", [])
