import logging

from app.channels.inbound import EchoHandler, InboundHandler
from app.config import Settings
from app.db.session import get_sessionmaker
from app.imagegen.factory import build_image_gen
from app.llm.client import GeminiChat
from app.media.public import PublicImages
from app.posts.drafts import PostDrafter
from app.posts.maker import PostMaker
from app.posts.publish import PostPublisher
from app.posts.store import InMemoryPosts
from app.publishing.base import PublisherPort
from app.publishing.mock import MOCK_ACCOUNT_ID
from app.storage import get_storage

from .button_router import ButtonRouter
from .chat import ChatHandler
from .history import InMemoryHistory
from .library import BrandBrains, BrandLibrary
from .onboarding import OnboardingGate
from .photos import InMemoryPhotos

logger = logging.getLogger(__name__)


def build_inbound_handler(
    settings: Settings, images: PublicImages, publisher: PublisherPort
) -> InboundHandler:
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
            photos, history, store = InMemoryPhotos(), InMemoryHistory(), InMemoryPosts()
            account_id = settings.zernio_account_id or (
                MOCK_ACCOUNT_ID if settings.publisher == "mock" else None
            )
            if account_id is None:
                logger.warning(
                    "PUBLISHER=zernio without ZERNIO_ACCOUNT_ID: posts can't be published"
                )
            sessions = get_sessionmaker() if settings.database_url else None
            posts = PostMaker(
                PostDrafter(model),
                build_image_gen(settings),
                photos,
                images,
                store,
                settings.public_backend_url,
                settings.max_posts_per_day,
                brand_of=BrandBrains(sessions).latest if sessions else None,
            )
            publishing = PostPublisher(
                publisher, store, images, settings.public_backend_url, account_id
            )
            buttons = ButtonRouter(store, posts, publishing, sessions)
            library = (
                BrandLibrary(sessions, get_storage())
                if sessions and settings.supabase_url and settings.supabase_service_role_key
                else None
            )
            chat = ChatHandler(
                model,
                history,
                photos,
                posts,
                publishing,
                store,
                buttons,
                library,
                settings.assistant_name,
                max_photo_mb=settings.max_photo_mb,
            )
            posts.on_event(chat.notify)
            publishing.on_event(chat.notify)
            if sessions is None:
                return chat
            return OnboardingGate(chat, sessions, settings.frontend_url, settings.assistant_name)
        case "echo":
            return EchoHandler()
