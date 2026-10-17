from app.channels.inbound import EchoHandler, InboundHandler
from app.config import Settings
from app.llm.client import GeminiChat

from .chat import ChatHandler
from .history import InMemoryHistory


def build_inbound_handler(settings: Settings) -> InboundHandler:
    match settings.inbound_handler:
        case "chat":
            if not settings.gemini_api_key:
                raise ValueError("INBOUND_HANDLER=chat needs GEMINI_API_KEY")
            model = GeminiChat.from_api_key(settings.gemini_api_key, settings.gemini_chat_model)
            return ChatHandler(model, InMemoryHistory(), settings.assistant_name)
        case "echo":
            return EchoHandler()
