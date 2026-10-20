import logging
from dataclasses import dataclass

from app.background import get_background_work
from app.channels.inbound import EchoHandler, InboundHandler
from app.config import Settings
from app.db.session import get_sessionmaker
from app.imagegen.factory import build_image_gen
from app.knowledge.base import Knowledge
from app.knowledge.db import DbKnowledge
from app.knowledge.local import LocalKnowledge, load_trend_notes
from app.llm.client import GeminiChat
from app.media.public import PublicImages, PublicVideos
from app.posts.drafts import PostDrafter
from app.posts.lifecycle import PostLifecycle
from app.posts.maker import PostMaker
from app.posts.publish import PostPublisher
from app.posts.store import InMemoryPosts
from app.posts.video_maker import VideoMaker
from app.publishing.base import PublisherPort
from app.publishing.mock import MOCK_ACCOUNT_ID
from app.rendering.factory import build_renderer
from app.storage import get_storage
from app.videogen.factory import build_video_gen

from .button_router import ButtonRouter
from .chat import ChatHandler
from .events import Notify
from .history import DbHistory, History, InMemoryHistory
from .library import BrandLibrary
from .notes import DbNotes, InMemoryNotes, OwnerNotes
from .onboarding import OnboardingGate
from .outbound import FixedReplies
from .photo_keeper import PhotoKeeper
from .photos import InMemoryPhotos

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Conversation:
    """What answers the Owner: `handler` for their messages, `notify` for the events code raises
    (jobs, the onboarding API). Both share one history, so one lock per sender."""

    handler: InboundHandler
    notify: Notify


def build_conversation(
    settings: Settings,
    images: PublicImages,
    publisher: PublisherPort,
    videos: PublicVideos | None = None,
) -> Conversation:
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
            background = get_background_work()
            photos, store = InMemoryPhotos(), InMemoryPosts()
            lifecycle = PostLifecycle(store)
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
                lifecycle,
                settings.public_backend_url,
                settings.max_posts_per_day,
                knowledge=knowledge,
                background=background,
            )
            public_videos = videos or PublicVideos()
            public_videos.serve_from(store.video)
            publishing = PostPublisher(
                publisher,
                lifecycle,
                images,
                settings.public_backend_url,
                account_id,
                background=background,
                videos=public_videos,
            )
            # None while VIDEO_GEN_ENABLED is off: no maker, so no tool and no Veo call (ADR 0033)
            video_gen = build_video_gen(settings)
            video_maker = (
                VideoMaker(
                    video_gen,
                    lifecycle,
                    public_videos,
                    settings.public_backend_url,
                    settings.max_videos_per_day,
                    background=background,
                )
                if video_gen
                else None
            )
            buttons = ButtonRouter(lifecycle, posts, publishing, sessions, video_maker)
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
                lifecycle,
                buttons,
                library,
                settings.assistant_name,
                max_photo_mb=settings.max_photo_mb,
                notes=notes,
                knowledge=knowledge,
                videos=video_maker,
                keeper=PhotoKeeper(model, sessions, storage),
                background=background,
            )
            if sessions is None:
                return Conversation(chat, chat.notify)
            gate = OnboardingGate(chat, sessions, settings.frontend_url, settings.assistant_name)
            return Conversation(gate, chat.notify)
        case "echo":
            # No chat handler: events still reach the Owner, as their fixed text.
            history = DbHistory(get_sessionmaker()) if settings.database_url else InMemoryHistory()
            return Conversation(EchoHandler(), FixedReplies(history))
