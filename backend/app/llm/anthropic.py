import asyncio
import logging
import time
from typing import Any, Self

import anthropic
from anthropic.types.beta import BetaMessageParam
from pydantic import BaseModel

from .client import STRUCTURED_TIMEOUT_S, Content, LLMError, ThinkingLevel

logger = logging.getLogger(__name__)

MAX_TOKENS = 16_000
# Server-side refusal fallbacks ("default" routes by refusal category); Haiku has none
FALLBACK_BETA = "server-side-fallback-2026-07-01"
NO_FALLBACK_PREFIX = "claude-haiku"


def claude_content(block: Content) -> dict[str, Any]:
    """A Gemini-shaped content block (app/llm/client.py) as a Messages API block."""
    if block["type"] == "image":
        source = {"type": "base64", "media_type": block.get("mime_type"), "data": block.get("data")}
        return {"type": "image", "source": source}
    if block["type"] == "text":
        return {"type": "text", "text": block["text"]}
    raise ValueError(f"unsupported content block for Claude: {block['type']}")


class ClaudeStructured:
    """StructuredModel on the Claude API (ADR 0035): Art Director and Design Critic calls.

    Only `structured`: the orchestrator's history is stored in Gemini's step format, so the chat
    stays on Gemini (ADR 0023).
    """

    def __init__(self, client: anthropic.AsyncAnthropic, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    def from_api_key(cls, api_key: str, model: str) -> Self:
        return cls(anthropic.AsyncAnthropic(api_key=api_key, timeout=STRUCTURED_TIMEOUT_S), model)

    async def structured[T: BaseModel](
        self,
        agent: str,
        system: str,
        content: list[Content],
        schema: type[T],
        thinking_level: ThinkingLevel,
    ) -> T:
        blocks: list[Any] = [claude_content(block) for block in content]
        messages: list[BetaMessageParam] = [{"role": "user", "content": blocks}]
        fallback = not self._model.startswith(NO_FALLBACK_PREFIX)
        started = time.monotonic()
        try:
            response = await asyncio.wait_for(
                self._client.beta.messages.parse(
                    model=self._model,
                    max_tokens=MAX_TOKENS,
                    system=system,
                    messages=messages,
                    output_format=schema,
                    output_config={"effort": thinking_level},
                    betas=[FALLBACK_BETA] if fallback else anthropic.omit,
                    fallbacks="default" if fallback else anthropic.omit,
                ),
                timeout=STRUCTURED_TIMEOUT_S * 2,
            )
        except TimeoutError as exc:
            raise LLMError(f"{agent}: no answer within {STRUCTURED_TIMEOUT_S * 2:.0f} s") from exc
        except anthropic.APIError as exc:
            raise LLMError(f"{agent}: {exc}") from exc
        usage = response.usage
        logger.info(
            "llm agent=%s model=%s stop=%s in=%s out=%s cache_read=%s latency_ms=%d",
            agent,
            response.model,
            response.stop_reason,
            usage.input_tokens,
            usage.output_tokens,
            usage.cache_read_input_tokens,
            (time.monotonic() - started) * 1000,
        )
        if response.stop_reason in {"refusal", "max_tokens"} or response.parsed_output is None:
            raise LLMError(f"{agent}: stop_reason={response.stop_reason}, no parsed output")
        return response.parsed_output
