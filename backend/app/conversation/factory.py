import logging

from app.channels.inbound import EchoHandler, InboundHandler
from app.config import Settings
from app.db.session import get_sessionmaker
from app.imagegen.factory import build_image_gen
from app.knowledge.base import Knowledge
from app.knowledge.db import DbKnowledge
from app.knowledge.local import LocalKnowledge, load_trend_notes
from app.llm.client import GeminiChat
from app.media.public import PublicImages
from app.posts.drafts import PostDrafter
from app.posts.maker import PostMaker
from app.posts.publish import PostPublisher
from app.posts.store import InMemoryPosts
from app.publishing.base import PublisherPort
from app.publishing.mock import MOCK_ACCOUNT_ID
from app.rendering.factory import build_renderer
from app.storage import get_storage

from .button_router import ButtonRouter
from .chat import ChatHandler
from .history import DbHistory, History, InMemoryHistory
from .library import BrandLibrary
from .notes import DbNotes, InMemoryNotes, OwnerNotes
from .onboarding import OnboardingGate
from .photo_keeper import PhotoKeeper
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
            photos, store = InMemoryPhotos(), InMemoryPosts()
            account_id = settings.zernio_account_id or (
                MOCK_ACCOUNT_ID if settings.publisher == "mock" else None
            )
            if account_id is None:
                logger.warning(
                    "PUBLISHER=zernio without ZERNIO_ACCOUNT_ID: posts can't be published"
                )
            sessions = get_sessionmaker() if settings.database_url else None
            # ADR 0030: with the database, the conversation and the notes survive a deploy.
            history: History = DbHistory(sessions) if sessions else InMemoryHistory()
            notes: OwnerNotes = DbNotes(sessions) if sessions else InMemoryNotes()
            # With the database, each Business reads its niche's latest report (ADR 0025); the
            # file is only the fallback without it, where every sender shares it.
            knowledge: Knowledge = (
                DbKnowledge(sessions)
                if sessions
                else LocalKnowledge(notes, history, load_trend_notes(settings.niche_report_path))
            )
            posts = PostMaker(
                PostDrafter(model),
                build_image_gen(settings),
                build_renderer(settings),
                photos,
                images,
                store,
                settings.public_backend_url,
                settings.max_posts_per_day,
                knowledge=knowledge,
            )
            publishing = PostPublisher(
                publisher, store, images, settings.public_backend_url, account_id
            )
            buttons = ButtonRouter(store, posts, publishing, sessions)
            storage = (
                get_storage()
                if sessions and settings.supabase_url and settings.supabase_service_role_key
                else None
            )
            library = BrandLibrary(sessions, storage) if sessions and storage else None
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
                notes=notes,
                knowledge=knowledge,
                keeper=PhotoKeeper(model, sessions, storage),
            )
            posts.on_event(chat.notify)
            publishing.on_event(chat.notify)
            if sessions is None:
                return chat
            return OnboardingGate(chat, sessions, settings.frontend_url, settings.assistant_name)
        case "echo":
            return EchoHandler()
