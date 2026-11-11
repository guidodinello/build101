import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Self, TypedDict, Unpack, cast, runtime_checkable

import httpx
from google import genai
from google.genai import errors, interactions, types

# The Interactions API raises its own error family (timeouts, connection and HTTP status
# errors), not `errors.APIError`, and google-genai 2.31 exports it only from this module.
from google.genai._gaos.lib.compat_errors import GeminiNextGenAPIClientError
from google.genai._gaos.types.basemodel import UnrecognizedStr
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

ThinkingLevel = Literal["low", "medium", "high"]
# The SDK's request TypedDicts, discriminated by `type`. They are plain dicts at runtime, so the
# steps stored as JSONB in the history replay as they are.
Step = interactions.StepParam  # an Interactions API step, as sent and as stored in the history
Content = interactions.ContentParam  # a content block of a user_input step (text or image)
Tool = interactions.ToolParam  # a function declaration, or a built-in tool

# Free-tier gemini-3.8-flash took 5–26 s per chat turn on 2026-10-17, and some turns over 30 s.
REQUEST_TIMEOUT_S = 60.0
STRUCTURED_TIMEOUT_S = 90.0
# Niche Analyst runs with url_context + google_search took 33–100 s on 2026-10-18.
GROUNDED_TIMEOUT_S = 180.0

# The SDK sleeps for a 429's Retry-After as-is, ignoring its own backoff cap
# (google/genai/_gaos/utils/retries.py); a daily-quota 429 asked for 19 h on 2026-10-18.
# So 429 is not retried, and each call also gets a wall-clock deadline (`_create`).
RETRY_STATUS_CODES = [408, 409, 500, 502, 503, 504]  # the SDK default minus 429
HTTP_OPTIONS = types.HttpOptions(
    retry_options=types.HttpRetryOptions(http_status_codes=RETRY_STATUS_CODES)
)

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


@dataclass(frozen=True, slots=True)
class WebSource:
    url: str
    title: str | None = None


@dataclass(frozen=True, slots=True)
class Grounded[T: BaseModel]:
    output: T
    sources: list[WebSource]  # what the tools actually read or cited, from the response steps


@runtime_checkable
class StructuredModel(Protocol):
    """One call that answers in a schema: what the specialists need, on any provider."""

    async def structured[T: BaseModel](
        self,
        agent: str,
        system: str,
        content: list[Content],
        schema: type[T],
        thinking_level: ThinkingLevel,
    ) -> T: ...


@runtime_checkable
class ChatModel(StructuredModel, Protocol):
    async def reply(
        self,
        agent: str,
        system: str,
        history: list[Step],
        thinking_level: ThinkingLevel,
        tools: list[Tool] | None = None,
    ) -> Reply: ...


class GroundedModel(Protocol):
    async def grounded[T: BaseModel](
        self,
        agent: str,
        system: str,
        content: list[Content],
        schema: type[T],
        thinking_level: ThinkingLevel,
        tools: list[Tool],
    ) -> Grounded[T]: ...


def text_content(text: str) -> Content:
    return {"type": "text", "text": text}


def image_content(data: bytes, mime_type: interactions.ImageContentMimeType) -> Content:
    return {"type": "image", "data": base64.b64encode(data).decode(), "mime_type": mime_type}


def audio_content(data: bytes, mime_type: interactions.AudioContentMimeType) -> Content:
    return {"type": "audio", "data": base64.b64encode(data).decode(), "mime_type": mime_type}


def user_step(text: str, *extra: Content) -> Step:
    return {"type": "user_input", "content": [text_content(text), *extra]}


def function_result_step(call: FunctionCall, result: dict[str, Any]) -> Step:
    return {
        "type": "function_result",
        "call_id": call.id,
        "name": call.name,
        "result": json.dumps(result, ensure_ascii=False),
    }


class _Options(TypedDict, total=False):
    tools: list[Tool]
    response_format: interactions.CreateModelInteractionResponseFormatParam


class GeminiChat:
    """Text turns on Gemini's Interactions API, stateless: we keep and resend the history.

    Thought steps carry the signatures Gemini needs on later turns, so callers store
    `Reply.steps` unchanged (docs/research/gemini-api.md).
    """

    def __init__(self, client: genai.client.AsyncClient, model: str) -> None:
        self._client = client
        # The SDK's `Model` is a union of known ids and `UnrecognizedStr`; a union-typed argument
        # keeps pyright off the non-stream `create` overload, a single member selects it.
        self._model = cast(UnrecognizedStr, model)

    @classmethod
    def from_api_key(cls, api_key: str, model: str) -> Self:
        return cls(genai.Client(api_key=api_key, http_options=HTTP_OPTIONS).aio, model)

    async def reply(
        self,
        agent: str,
        system: str,
        history: list[Step],
        thinking_level: ThinkingLevel,
        tools: list[Tool] | None = None,
    ) -> Reply:
        options: _Options = {"tools": tools} if tools else {}
        interaction = await self._create(
            agent, system, history, thinking_level, REQUEST_TIMEOUT_S, **options
        )
        steps = [_as_step(step) for step in interaction.steps or [] if step.type != "user_input"]
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
        interaction = await self._create(
            agent,
            system,
            [{"type": "user_input", "content": content}],
            thinking_level,
            STRUCTURED_TIMEOUT_S,
            response_format=response_format(schema),
        )
        return parse_output(agent, interaction, schema)

    async def grounded[T: BaseModel](
        self,
        agent: str,
        system: str,
        content: list[Content],
        schema: type[T],
        thinking_level: ThinkingLevel,
        tools: list[Tool],
    ) -> Grounded[T]:
        """A structured call with built-in tools (url_context, google_search) the model runs.

        Tools and a `response_format` schema combine in one interaction (checked live on
        2026-10-18, docs/research/niche-trend-sources.md).
        """
        interaction = await self._create(
            agent,
            system,
            [{"type": "user_input", "content": content}],
            thinking_level,
            GROUNDED_TIMEOUT_S,
            tools=tools,
            response_format=response_format(schema),
        )
        output = parse_output(agent, interaction, schema)
        return Grounded(output, web_sources([_as_step(step) for step in interaction.steps or []]))

    async def _create(
        self,
        agent: str,
        system: str,
        steps: list[Step],
        thinking_level: ThinkingLevel,
        timeout_s: float,
        **options: Unpack[_Options],
    ) -> interactions.Interaction:
        started = time.monotonic()
        try:
            # `timeout` bounds each HTTP attempt; `wait_for` bounds the call, retries included.
            interaction = await asyncio.wait_for(
                self._client.interactions.create(
                    model=self._model,
                    system_instruction=system,
                    input=steps,
                    generation_config={"thinking_level": thinking_level},
                    store=False,
                    timeout=timeout_s,
                    **options,
                ),
                timeout=timeout_s,
            )
        except TimeoutError as exc:
            raise LLMError(f"{agent}: no answer within {timeout_s:.0f} s") from exc
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


def response_format(schema: type[BaseModel]) -> interactions.TextResponseFormatParam:
    return {"type": "text", "mime_type": "application/json", "schema_": schema.model_json_schema()}


def _as_step(step: interactions.Step) -> Step:
    """The SDK's response model dumped to its own request shape, to store and replay as is."""
    return cast(Step, step.model_dump(mode="json", exclude_none=True))


def parse_output[T: BaseModel](
    agent: str, interaction: interactions.Interaction, schema: type[T]
) -> T:
    if interaction.status != "completed" or not interaction.output_text:
        raise LLMError(f"{agent}: status={interaction.status} errors={interaction.errors}")
    try:
        return schema.model_validate_json(interaction.output_text)
    except ValidationError as exc:
        raise LLMError(f"{agent}: output doesn't match {schema.__name__}: {exc}") from exc


def web_sources(steps: list[Step]) -> list[WebSource]:
    """The pages a grounded call read (url_context) or cited (url_citation), first seen first."""
    found: dict[str, WebSource] = {}
    for step in steps:
        if step["type"] == "url_context_result":
            for result in step.get("result", []):
                url = result.get("url")
                if url and result.get("status", "success") == "success":
                    found.setdefault(url, WebSource(url))
        elif step["type"] == "model_output":
            for block in step.get("content", []):
                if block["type"] != "text":  # only text blocks carry annotations
                    continue
                for note in block.get("annotations", []):
                    if note["type"] != "url_citation":
                        continue
                    url = note.get("url")
                    if not url:
                        continue
                    known = found.get(url)
                    if known is None or known.title is None:  # a citation adds the title
                        found[url] = WebSource(url, note.get("title"))
    return list(found.values())
