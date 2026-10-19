import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.agents.niche_analyst import NicheReport, trend_notes
from app.channels.inbound import EchoHandler, InboundHandler
from app.config import Settings
from app.db.session import get_sessionmaker
from app.imagegen.factory import build_image_gen
from app.llm.client import GeminiChat
from app.media.public import PublicImages, PublicVideos
from app.posts.drafts import PostDrafter
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
from .context import BusinessContexts
from .history import DbHistory, History, InMemoryHistory
from .library import BrandBrains, BrandLibrary, NicheTrends
from .notes import DbNotes, InMemoryNotes, OwnerNotes
from .onboarding import OnboardingGate
from .photo_keeper import PhotoKeeper
from .photos import InMemoryPhotos

logger = logging.getLogger(__name__)


def build_inbound_handler(
    settings: Settings,
    images: PublicImages,
    publisher: PublisherPort,
    videos: PublicVideos | None = None,
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
            trend_notes = None if sessions else load_trend_notes(settings.niche_report_path)
            posts = PostMaker(
                PostDrafter(model),
                build_image_gen(settings),
                build_renderer(settings),
                photos,
                images,
                store,
                settings.public_backend_url,
                settings.max_posts_per_day,
                brand_of=BrandBrains(sessions).latest if sessions else None,
                notes_of=note_texts(notes),
                trends_of=NicheTrends(sessions).latest if sessions else fixed(trend_notes),
            )
            public_videos = videos or PublicVideos()
            publishing = PostPublisher(
                publisher,
                store,
                images,
                settings.public_backend_url,
                account_id,
                videos=public_videos,
            )
            # None while VIDEO_GEN_ENABLED is off: no maker, so no tool and no Veo call (ADR 0033)
            video_gen = build_video_gen(settings)
            video_maker = (
                VideoMaker(
                    video_gen,
                    store,
                    public_videos,
                    settings.public_backend_url,
                    settings.max_videos_per_day,
                )
                if video_gen
                else None
            )
            buttons = ButtonRouter(store, posts, publishing, sessions, video_maker)
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
                videos=video_maker,
                contexts=BusinessContexts(sessions) if sessions else None,
                keeper=PhotoKeeper(model, sessions, storage),
                trend_notes=trend_notes,
            )
            posts.on_event(chat.notify)
            publishing.on_event(chat.notify)
            if video_maker:
                video_maker.on_event(chat.notify)
            if sessions is None:
                return chat
            return OnboardingGate(chat, sessions, settings.frontend_url, settings.assistant_name)
        case "echo":
            return EchoHandler()


def note_texts(notes: OwnerNotes) -> Callable[[str], Awaitable[list[str]]]:
    async def texts(sender: str) -> list[str]:
        return [note.text for note in await notes.list(sender)]

    return texts


def fixed(trend_notes: str | None) -> Callable[[str], Awaitable[str | None]] | None:
    """The same trend notes for every sender (no database), or None without them."""
    if trend_notes is None:
        return None

    async def same(sender: str) -> str | None:
        return trend_notes

    return same


def load_trend_notes(path: Path | None) -> str | None:
    """The saved Niche Report's insights as trend notes; a missing file is a config error."""
    if path is None:
        return None
    report = NicheReport.model_validate_json(path.read_text())
    logger.info("trend notes from the Niche Report of the week of %s", report.week_start)
    return trend_notes(report)
