from app.channels.inbound import EchoHandler, InboundHandler
from app.config import Settings
from app.imagegen.factory import build_image_gen
from app.llm.client import GeminiChat
from app.media.public import PublicImages
from app.posts.drafts import PostDrafter
from app.posts.maker import PostMaker

from .chat import ChatHandler
from .history import InMemoryHistory
from .photos import InMemoryPhotos


def build_inbound_handler(settings: Settings, images: PublicImages) -> InboundHandler:
    match settings.inbound_handler:
        case "chat":
            if not settings.gemini_api_key:
                raise ValueError("INBOUND_HANDLER=chat needs GEMINI_API_KEY")
            if not settings.public_backend_url:
                raise ValueError(
                    "INBOUND_HANDLER=chat needs PUBLIC_BACKEND_URL: WhatsApp fetches the "
                    "post images from it"
                )
            model = GeminiChat.from_api_key(settings.gemini_api_key, settings.gemini_chat_model)
            photos, history = InMemoryPhotos(), InMemoryHistory()
            posts = PostMaker(
                PostDrafter(model),
                build_image_gen(settings),
                photos,
                history,
                images,
                settings.public_backend_url,
                settings.max_posts_per_day,
            )
            return ChatHandler(
                model,
                history,
                photos,
                posts,
                settings.assistant_name,
                max_photo_mb=settings.max_photo_mb,
            )
        case "echo":
            return EchoHandler()
