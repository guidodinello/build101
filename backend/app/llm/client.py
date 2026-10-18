import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Self, runtime_checkable

import httpx
from google import genai
from google.genai import errors

# The Interactions API raises its own error family (timeouts, connection and HTTP status
# errors), not `errors.APIError`, and google-genai 2.31 exports it only from this module.
from google.genai._gaos.lib.compat_errors import GeminiNextGenAPIClientError
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

ThinkingLevel = Literal["low", "medium", "high"]
Step = dict[str, Any]  # an Interactions API step, as sent and as stored in the history
Content = dict[str, Any]  # a content block of a user_input step (text or image)
Tool = dict[str, Any]  # a function declaration: {"type": "function", "name", "description", ...}

# Free-tier gemini-3.8-flash took 5–26 s per chat turn on 2026-10-17, and some turns over 30 s.
REQUEST_TIMEOUT_S = 60.0
STRUCTURED_TIMEOUT_S = 90.0

# A turn that asks for function calls ends in `requires_action` with no text (checked live).
ANSWERED_STATUSES = frozenset({"completed", "requires_action"})


class LLMError(Exception):
    """The model gave no usable answer: API error, non-completed status or empty text."""


@dataclass(frozen=True, slots=True)
class FunctionCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Reply:
    text: str  # empty when the model only asks for function calls
    steps: list[Step]  # the model's steps, thought steps included, to append to the history
    function_calls: list[FunctionCall] = field(default_factory=list)


@runtime_checkable
class ChatModel(Protocol):
    async def reply(
        self,
        agent: str,
        system: str,
        history: list[Step],
        thinking_level: ThinkingLevel,
        tools: list[Tool] | None = None,
    ) -> Reply: ...

    async def structured[T: BaseModel](
        self,
        agent: str,
        system: str,
        content: list[Content],
        schema: type[T],
        thinking_level: ThinkingLevel,
    ) -> T: ...


def text_content(text: str) -> Content:
    return {"type": "text", "text": text}


def image_content(data: bytes, mime_type: str) -> Content:
    return {"type": "image", "data": base64.b64encode(data).decode(), "mime_type": mime_type}


def user_step(text: str, *extra: Content) -> Step:
    return {"type": "user_input", "content": [text_content(text), *extra]}


def function_result_step(call: FunctionCall, result: dict[str, Any]) -> Step:
    return {
        "type": "function_result",
        "call_id": call.id,
        "name": call.name,
        "result": json.dumps(result, ensure_ascii=False),
    }


class GeminiChat:
    """Text turns on Gemini's Interactions API, stateless: we keep and resend the history.

    Thought steps carry the signatures Gemini needs on later turns, so callers store
    `Reply.steps` unchanged (docs/research/gemini-api.md).
    """

    def __init__(self, client: genai.client.AsyncClient, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    def from_api_key(cls, api_key: str, model: str) -> Self:
        return cls(genai.Client(api_key=api_key).aio, model)

    async def reply(
        self,
        agent: str,
        system: str,
        history: list[Step],
        thinking_level: ThinkingLevel,
        tools: list[Tool] | None = None,
    ) -> Reply:
        options: dict[str, Any] = {"tools": tools} if tools else {}
        interaction = await self._create(
            agent, system, history, thinking_level, REQUEST_TIMEOUT_S, **options
        )
        steps = [
            step.model_dump(mode="json", exclude_none=True)
            for step in interaction.steps or []
            if step.type != "user_input"
        ]
        calls = [
            FunctionCall(step["id"], step["name"], step.get("arguments") or {})
            for step in steps
            if step["type"] == "function_call"
        ]
        text = interaction.output_text or ""
        if interaction.status not in ANSWERED_STATUSES or not (text or calls):
            raise LLMError(f"{agent}: status={interaction.status} errors={interaction.errors}")
        return Reply(text=text, steps=steps, function_calls=calls)

    async def structured[T: BaseModel](
        self,
        agent: str,
        system: str,
        content: list[Content],
        schema: type[T],
        thinking_level: ThinkingLevel,
    ) -> T:
        response_format = {
            "type": "text",
            "mime_type": "application/json",
            "schema": schema.model_json_schema(),
        }
        interaction = await self._create(
            agent,
            system,
            [{"type": "user_input", "content": content}],
            thinking_level,
            STRUCTURED_TIMEOUT_S,
            response_format=response_format,
        )
        if interaction.status != "completed" or not interaction.output_text:
            raise LLMError(f"{agent}: status={interaction.status} errors={interaction.errors}")
        try:
            return schema.model_validate_json(interaction.output_text)
        except ValidationError as exc:
            raise LLMError(f"{agent}: output doesn't match {schema.__name__}: {exc}") from exc

    async def _create(
        self,
        agent: str,
        system: str,
        steps: list[Step],
        thinking_level: ThinkingLevel,
        timeout_s: float,
        **options: Any,
    ) -> Any:
        started = time.monotonic()
        try:
            interaction = await self._client.interactions.create(
                model=self._model,
                system_instruction=system,
                input=steps,
                generation_config={"thinking_level": thinking_level},
                store=False,
                timeout=timeout_s,
                **options,
            )
        except (GeminiNextGenAPIClientError, errors.APIError, httpx.HTTPError) as exc:
            raise LLMError(f"{agent}: {exc}") from exc

        usage = interaction.usage
        logger.info(
            "llm agent=%s model=%s status=%s in=%s out=%s thought=%s latency_ms=%d",
            agent,
            self._model,
            interaction.status,
            usage.total_input_tokens if usage else None,
            usage.total_output_tokens if usage else None,
            usage.total_thought_tokens if usage else None,
            (time.monotonic() - started) * 1000,
        )
        return interaction
