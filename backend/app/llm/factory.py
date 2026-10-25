from app.config import Settings

from .anthropic import ClaudeStructured
from .client import ChatModel, GeminiChat, StructuredModel

CLAUDE_PREFIX = "claude-"


def build_structured(settings: Settings, model: str | None, chat: ChatModel) -> StructuredModel:
    """The model behind one agent's structured calls (ADR 0035); unset or empty, the chat model."""
    if not model or model == settings.gemini_chat_model:
        return chat
    if model.startswith(CLAUDE_PREFIX):
        if not settings.anthropic_api_key:
            raise ValueError(f"{model} needs ANTHROPIC_API_KEY")
        return ClaudeStructured.from_api_key(settings.anthropic_api_key, model)
    if not settings.gemini_api_key:
        raise ValueError(f"{model} needs GEMINI_API_KEY")
    return GeminiChat.from_api_key(settings.gemini_api_key, model)
