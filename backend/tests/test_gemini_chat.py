import httpx
import pytest
from google.genai._gaos.lib.compat_errors import APITimeoutError

from app.llm.client import GeminiChat, LLMError, user_step


class TimingOutInteractions:
    async def create(self, **_: object) -> None:
        raise APITimeoutError(request=httpx.Request("POST", "https://example.test"))


class TimingOutClient:
    interactions = TimingOutInteractions()


async def test_an_interactions_timeout_becomes_llm_error() -> None:
    model = GeminiChat(TimingOutClient(), "gemini-3.8-flash")  # type: ignore[arg-type]

    with pytest.raises(LLMError, match="orchestrator"):
        await model.reply("orchestrator", "system", [user_step("hola")], thinking_level="low")
