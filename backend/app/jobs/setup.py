import logging
from collections.abc import Callable

from app.background import get_background_work
from app.channels.base import ChannelPort
from app.config import Settings
from app.conversation.events import Notify
from app.db.session import get_sessionmaker
from app.instagram.factory import build_instagram
from app.llm.client import GeminiChat
from app.storage import get_storage

from .asset import analyze_asset
from .brand import generate_brand, queue_stranded_brands, resume_revision
from .instagram import import_instagram_job
from .niche import CHECK_EVERY, enqueue_due_niche_reports, niche_report_job
from .runner import JobFunction, JobRunner, PeriodicCheck, Undo
from .uploads import SWEEP_EVERY, upload_sweep

logger = logging.getLogger(__name__)

JOBS: dict[str, JobFunction] = {
    "analyze_asset": analyze_asset,
    "generate_brand": generate_brand,
}
# A photo whose analysis fails is still usable, so only the brand bothers the Owner.
NOTIFY_ON_FAILURE = frozenset({"generate_brand"})
# Safe to run again from the start. The Instagram import isn't: it claims the Owner's token when
# it starts, so an interrupted one needs a reconnect. A failed niche report is queued again by
# its own check.
REQUEUE_IF_INTERRUPTED = frozenset({"analyze_asset", "generate_brand"})
UNDO: dict[str, Undo] = {"generate_brand": resume_revision}


def build_job_runner(
    settings: Settings, channel: ChannelPort, owner_notify: Callable[[], Notify]
) -> JobRunner | None:
    """The runner, or None (logged) when the database, Storage or Gemini isn't configured.

    `owner_notify` is resolved only once the runner will exist: it builds the conversation.
    """
    missing = [
        name
        for name, value in (
            ("DATABASE_URL", settings.database_url),
            ("SUPABASE_URL", settings.supabase_url),
            ("SUPABASE_SERVICE_ROLE_KEY", settings.supabase_service_role_key),
            ("GEMINI_API_KEY", settings.gemini_api_key),
        )
        if not value
    ]
    if missing:
        logger.warning("job runner is off: %s not set", ", ".join(missing))
        return None
    model = GeminiChat.from_api_key(settings.gemini_api_key or "", settings.gemini_chat_model)
    jobs = {
        **JOBS,
        "import_instagram": import_instagram_job(
            build_instagram(settings),
            settings.instagram_import_max_posts,
            settings.instagram_import_max_images,
        ),
        # Silent and per niche: no Owner to notify when it fails (ADR 0025).
        "generate_niche_report": niche_report_job(model),
    }
    storage = get_storage()
    return JobRunner(
        get_sessionmaker(),
        jobs,
        storage,
        channel,
        model,
        owner_notify(),
        NOTIFY_ON_FAILURE,
        REQUEUE_IF_INTERRUPTED,
        UNDO,
        checks=(
            PeriodicCheck("stranded brands", None, queue_stranded_brands),
            PeriodicCheck("niche reports", CHECK_EVERY, enqueue_due_niche_reports),
            PeriodicCheck(
                "upload sweep", SWEEP_EVERY, upload_sweep(storage, get_background_work())
            ),
        ),
        background=get_background_work(),
    )
