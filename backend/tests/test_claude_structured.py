from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from app.config import Settings
from app.conversation.factory import design_critic
from app.llm.anthropic import FALLBACK_BETA, ClaudeStructured, claude_content
from app.llm.client import GeminiChat, LLMError, image_content, text_content
from app.llm.factory import build_structured
from app.llm.ledger import MeteredStructured
from app.llm.usage import Usage, collecting
from app.posts.critic import DesignCritic
from tests.fakes import ScriptedModel


class Verdict(BaseModel):
    ok: bool


@dataclass
class FakeMessages:
    """Stands in for `client.beta.messages`: records the call, answers with `stop_reason`."""

    stop_reason: str = "end_turn"
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def parse(self, **request: Any) -> SimpleNamespace:
        self.calls.append(request)
        parsed = Verdict(ok=True) if self.stop_reason == "end_turn" else None
        usage = SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=30,
            cache_creation_input_tokens=4,
            service_tier="standard",
        )
        return SimpleNamespace(
            model="claude-opus-5-5", stop_reason=self.stop_reason, usage=usage, parsed_output=parsed
        )


def claude(model: str, messages: FakeMessages) -> ClaudeStructured:
    client: Any = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    return ClaudeStructured(client, model)


def test_content_blocks_become_messages_api_blocks() -> None:
    image = claude_content(image_content(b"\xff\xd8jpeg", "image/jpeg"))

    assert claude_content(text_content("hola")) == {"type": "text", "text": "hola"}
    assert image["type"] == "image"
    assert image["source"]["type"] == "base64"
    assert image["source"]["media_type"] == "image/jpeg"


async def test_a_structured_call_sends_the_effort_and_server_side_fallbacks() -> None:
    messages = FakeMessages()

    verdict = await claude("claude-opus-5-5", messages).structured(
        "design_critic", "rules", [text_content("slides")], Verdict, "high"
    )

    assert verdict == Verdict(ok=True)
    [call] = messages.calls
    assert call["system"] == "rules"
    assert call["output_format"] is Verdict
    assert call["output_config"] == {"effort": "high"}
    assert call["betas"] == [FALLBACK_BETA]
    assert call["fallbacks"] == "default"


async def test_haiku_has_no_server_side_fallback() -> None:
    messages = FakeMessages()

    await claude("claude-haiku-5-5", messages).structured("a", "s", [], Verdict, "low")

    assert "default" not in str(messages.calls[0]["fallbacks"])


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
async def test_a_refusal_or_a_cut_answer_is_an_llm_error(stop_reason: str) -> None:
    with pytest.raises(LLMError, match=stop_reason):
        await claude("claude-opus-5-5", FakeMessages(stop_reason)).structured(
            "a", "s", [], Verdict, "medium"
        )


class CutMessages(FakeMessages):
    """The SDK parses the output itself: a cut answer raises before stop_reason is read."""

    async def parse(self, **request: Any) -> Verdict:
        return Verdict.model_validate_json('{"ok": tr')


async def test_an_answer_the_sdk_cannot_parse_is_an_llm_error() -> None:
    with pytest.raises(LLMError, match="doesn't match Verdict"):
        await claude("claude-opus-5-5", CutMessages()).structured("a", "s", [], Verdict, "medium")


def test_an_unset_model_is_the_chat_model_and_claude_needs_its_key() -> None:
    chat = ScriptedModel()
    settings = Settings(_env_file=None, gemini_api_key="g")

    assert build_structured(settings, None, chat) is chat
    assert build_structured(settings, "", chat) is chat
    assert build_structured(settings, settings.gemini_chat_model, chat) is chat
    gemini = build_structured(settings, "gemini-4-argon", chat)
    assert isinstance(gemini, MeteredStructured) and isinstance(gemini.inner, GeminiChat)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        build_structured(settings, "claude-opus-5-5", chat)
    with_key = Settings(_env_file=None, anthropic_api_key="a")
    claude = build_structured(with_key, "claude-opus-5-5", chat)
    assert isinstance(claude, MeteredStructured) and isinstance(claude.inner, ClaudeStructured)


def test_the_critic_reviews_only_designs_from_the_real_renderer() -> None:
    chat = ScriptedModel()
    takumi = {"renderer": "takumi", "renderer_url": "https://x", "renderer_secret": "s"}

    assert design_critic(Settings(_env_file=None), chat) is None
    assert isinstance(design_critic(Settings(_env_file=None, **takumi), chat), DesignCritic)
    assert design_critic(Settings(_env_file=None, design_critic=False, **takumi), chat) is None


async def test_a_call_reports_its_usage_with_the_cache_inside_the_input() -> None:
    with collecting() as reported:
        await claude("claude-opus-5-5", FakeMessages()).structured(
            "art_director", "system", [text_content("hola")], Verdict, "high"
        )

    assert reported == [
        Usage(
            input_tokens=44,
            cached_tokens=30,
            output_tokens=5,
            service_tier="standard",
            stop_reason="end_turn",
        )
    ]
