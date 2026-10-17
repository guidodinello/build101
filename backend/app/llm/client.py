import logging
import time
from dataclasses import dataclass
from typing import Any, Literal, Protocol, Self, runtime_checkable

import httpx
from google import genai
from google.genai import errors

# The Interactions API raises its own error family (timeouts, connection and HTTP status
# errors), not `errors.APIError`, and google-genai 2.31 exports it only from this module.
from google.genai._gaos.lib.compat_errors import GeminiNextGenAPIClientError

logger = logging.getLogger(__name__)

ThinkingLevel = Literal["low", "medium", "high"]
Step = dict[str, Any]  # an Interactions API step, as sent and as stored in the history

REQUEST_TIMEOUT_S = 30.0


class LLMError(Exception):
    """The model gave no usable answer: API error, non-completed status or empty text."""


@dataclass(frozen=True, slots=True)
class Reply:
    text: str
    steps: list[Step]  # the model's steps, thought steps included, to append to the history


@runtime_checkable
class ChatModel(Protocol):
    async def reply(
        self, agent: str, system: str, history: list[Step], thinking_level: ThinkingLevel
    ) -> Reply: ...


def user_step(text: str) -> Step:
    return {"type": "user_input", "content": [{"type": "text", "text": text}]}


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
        self, agent: str, system: str, history: list[Step], thinking_level: ThinkingLevel
    ) -> Reply:
        started = time.monotonic()
        try:
            interaction = await self._client.interactions.create(
                model=self._model,
                system_instruction=system,
                input=history,
                generation_config={"thinking_level": thinking_level},
                store=False,
                timeout=REQUEST_TIMEOUT_S,
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
        if interaction.status != "completed" or not interaction.output_text:
            raise LLMError(f"{agent}: status={interaction.status} errors={interaction.errors}")

        steps = [
            step.model_dump(mode="json", exclude_none=True)
            for step in interaction.steps or []
            if step.type != "user_input"
        ]
        return Reply(text=interaction.output_text, steps=steps)
