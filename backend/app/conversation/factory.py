import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.background import BackgroundWork, get_background_work
from app.channels.inbound import EchoHandler, InboundHandler
from app.config import Settings
from app.db.session import get_sessionmaker
from app.imagegen.base import ImageGenPort
from app.imagegen.factory import build_image_gen
from app.knowledge.base import Knowledge
from app.knowledge.db import DbKnowledge
from app.knowledge.local import LocalKnowledge, load_trend_notes
from app.llm.client import ChatModel, GeminiChat, StructuredModel
from app.llm.factory import build_structured
from app.media.public import PublicImages, PublicVideos
from app.posts.critic import DesignCritic
from app.posts.drafts import PostDrafter
from app.posts.lifecycle import PostLifecycle
from app.posts.maker import PostMaker
from app.posts.publish import PostPublisher, Sleep
from app.posts.shared_account import SharedAccountGuard
from app.posts.store import InMemoryPosts
from app.posts.video_maker import VideoMaker
from app.publishing.base import PublisherPort
from app.publishing.mock import MOCK_ACCOUNT_ID
from app.rendering.base import RendererPort
from app.rendering.factory import build_renderer
from app.storage import get_storage
from app.videogen.base import VideoGenPort
from app.videogen.factory import build_video_gen

from .brand import BrandFlow
from .button_router import ButtonRouter
from .chat import ChatHandler
from .events import Notify
from .history import Compactor, DbHistory, History, InMemoryHistory
from .library import BrandLibrary
from .notes import DbNotes, InMemoryNotes, OwnerNotes
from .onboarding import OnboardingGate
from .outbound import FixedReplies
from .photo_batches import PHOTO_DEBOUNCE_S, PhotoBatches
from .photo_keeper import PhotoKeeper
from .photos import InMemoryPhotos, local_now
from .toolbox import Toolbox
from .turns import KEEP_ALIVE_S, Turns

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Conversation:
    """What answers the Owner: `handler` for their messages, `notify` for the events code raises
    (jobs, the onboarding API). Both share one history, so one lock per sender."""

    handler: InboundHandler
    notify: Notify


@dataclass(frozen=True, slots=True)
class ChatParts:
    """What `build_chat` needs: the ports and numbers the chat is built from. Production fills
    them from `Settings`; a test fills only what it looks at."""

    model: ChatModel
    image_gen: ImageGenPort
    renderer: RendererPort
    publisher: PublisherPort
    images: PublicImages
    videos: PublicVideos
    background: BackgroundWork
    public_backend_url: str
    account_id: str | None
    assistant_name: str
    max_photo_mb: int
    max_posts_per_day: int
    max_videos_per_day: int
    history: History = field(default_factory=InMemoryHistory)
    notes: OwnerNotes = field(default_factory=InMemoryNotes)
    # None: the Business knowledge of the history and notes alone, no Brand Brain or Catalog.
    knowledge: Knowledge | None = None
    library: BrandLibrary | None = None
    keeper: PhotoKeeper | None = None
    compactor: Compactor | None = None
    sessions: async_sessionmaker[AsyncSession] | None = None
    # None while VIDEO_GEN_ENABLED is off: no maker, so no tool and no Veo call (ADR 0033).
    video_gen: VideoGenPort | None = None
    photo_debounce_s: float = PHOTO_DEBOUNCE_S
    keep_alive_s: float = KEEP_ALIVE_S
    publish_sleep: Sleep | None = None
    # None: every Owner's Approval publishes to `account_id` (ADR 0024).
    shared_account: SharedAccountGuard | None = None
    # ADR 0035: the Art Director's model (None: `model`) and the review of rendered designs
    designer: StructuredModel | None = None
    critic: DesignCritic | None = None
    now: Callable[[], datetime] = local_now


@dataclass(frozen=True, slots=True)
class Chat:
    """The built conversation graph: `handler` and `notify` are what the app uses; the rest is
    what tests and the wiring around the chat (the onboarding gate) read."""

    handler: ChatHandler
    notify: Notify
    background: BackgroundWork
    history: History
    photos: InMemoryPhotos
    lifecycle: PostLifecycle
    posts: PostMaker
    publishing: PostPublisher
    video_maker: VideoMaker | None
    buttons: ButtonRouter


def build_chat(parts: ChatParts) -> Chat:
    """The one place the chat graph is wired, in production and in tests.

    Nothing here is late-bound: the makers get `notify` with each call (ADR 0026), so building
    the graph in any order can't leave a maker unable to tell the Owner.
    """
    photos, store = InMemoryPhotos(), InMemoryPosts()
    lifecycle = PostLifecycle(store)
    knowledge = parts.knowledge or LocalKnowledge(parts.notes, parts.history)
    background = parts.background
    posts = PostMaker(
        PostDrafter(parts.model, parts.designer),
        parts.image_gen,
        parts.renderer,
        photos,
        parts.images,
        lifecycle,
        parts.public_backend_url,
        parts.max_posts_per_day,
        knowledge=knowledge,
        now=parts.now,
        critic=parts.critic,
        background=background,
    )
    public_videos = parts.videos
    public_videos.serve_from(store.video)
    publishing = PostPublisher(
        parts.publisher,
        lifecycle,
        parts.images,
        parts.public_backend_url,
        parts.account_id,
        parts.publish_sleep or asyncio.sleep,
        videos=public_videos,
        background=background,
        shared_account=parts.shared_account,
    )
    video_maker = (
        VideoMaker(
            parts.video_gen,
            lifecycle,
            public_videos,
            parts.public_backend_url,
            parts.max_videos_per_day,
            parts.now,
            background=background,
        )
        if parts.video_gen
        else None
    )
    brand = BrandFlow(parts.sessions) if parts.sessions else None
    buttons = ButtonRouter(lifecycle, posts, publishing, parts.sessions, brand, video_maker)
    toolbox = Toolbox(posts, publishing, lifecycle, parts.notes, brand, video_maker)
    turns = Turns(
        parts.model,
        parts.history,
        photos,
        lifecycle,
        toolbox,
        knowledge,
        parts.library,
        parts.compactor or Compactor(parts.history, parts.model),
        parts.assistant_name,
        parts.now,
        parts.keep_alive_s,
        background=background,
    )
    batches = PhotoBatches(
        photos,
        parts.keeper,
        parts.max_photo_mb,
        turns.notify,
        parts.photo_debounce_s,
        background=background,
    )
    handler = ChatHandler(turns, batches, buttons, parts.history)
    return Chat(
        handler,
        turns.notify,
        background,
        parts.history,
        photos,
        lifecycle,
        posts,
        publishing,
        video_maker,
        buttons,
    )


def design_critic(settings: Settings, chat: ChatModel) -> DesignCritic | None:
    """Only designs drawn by the real renderer are worth a review: the mock draws no text."""
    if not settings.design_critic or settings.renderer != "takumi":
        return None
    return DesignCritic(build_structured(settings, settings.design_critic_model, chat))


def build_conversation(
    settings: Settings,
    images: PublicImages,
    publisher: PublisherPort,
    videos: PublicVideos,
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
            account_id = settings.zernio_account_id or (
                MOCK_ACCOUNT_ID if settings.publisher == "mock" else None
            )
            if account_id is None:
                logger.warning(
                    "PUBLISHER=zernio without ZERNIO_ACCOUNT_ID: posts can't be published"
                )
            shared_account = SharedAccountGuard(
                settings.zernio_owner_phone, open_when_unset=settings.env != "prod"
            )
            if settings.env == "prod" and not settings.zernio_owner_phone:
                logger.warning(
                    "ENV=prod without ZERNIO_OWNER_PHONE: nobody can publish to the shared "
                    "Instagram account (ADR 0024)"
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
            storage = (
                get_storage()
                if sessions and settings.supabase_url and settings.supabase_service_role_key
                else None
            )
            chat = build_chat(
                ChatParts(
                    model=model,
                    image_gen=build_image_gen(settings),
                    renderer=build_renderer(settings),
                    publisher=publisher,
                    images=images,
                    background=get_background_work(),
                    public_backend_url=settings.public_backend_url,
                    account_id=account_id,
                    assistant_name=settings.assistant_name,
                    max_photo_mb=settings.max_photo_mb,
                    max_posts_per_day=settings.max_posts_per_day,
                    max_videos_per_day=settings.max_videos_per_day,
                    history=history,
                    notes=notes,
                    knowledge=knowledge,
                    library=BrandLibrary(sessions, storage) if sessions and storage else None,
                    keeper=PhotoKeeper(model, sessions, storage),
                    sessions=sessions,
                    video_gen=build_video_gen(settings),
                    videos=videos,
                    shared_account=shared_account,
                    designer=build_structured(settings, settings.art_director_model, model),
                    critic=design_critic(settings, model),
                )
            )
            if sessions is None:
                return Conversation(chat.handler, chat.notify)
            gate = OnboardingGate(
                chat.handler, chat.notify, sessions, settings.frontend_url, settings.assistant_name
            )
            return Conversation(gate, chat.notify)
        case "echo":
            # No chat handler: events still reach the Owner, as their fixed text.
            history = DbHistory(get_sessionmaker()) if settings.database_url else InMemoryHistory()
            return Conversation(EchoHandler(), FixedReplies(history))
