import logging

from app.channels.base import ChannelPort
from app.config import Settings
from app.db.session import get_sessionmaker
from app.instagram.factory import build_instagram
from app.llm.client import GeminiChat
from app.storage import get_storage

from .asset import analyze_asset
from .brand import generate_brand
from .instagram import clear_stale_token, import_instagram_job
from .niche import CHECK_EVERY, enqueue_due_niche_reports, niche_report_job
from .runner import JobFunction, JobRunner, PeriodicCheck

logger = logging.getLogger(__name__)

JOBS: dict[str, JobFunction] = {
    "analyze_asset": analyze_asset,
    "generate_brand": generate_brand,
}
# A photo whose analysis fails is still usable, so only the brand bothers the Owner.
NOTIFY_ON_FAILURE = frozenset({"generate_brand"})


def build_job_runner(settings: Settings, channel: ChannelPort) -> JobRunner | None:
    """The runner, or None (logged) when the database, Storage or Gemini isn't configured."""
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
    return JobRunner(
        get_sessionmaker(),
        jobs,
        get_storage(),
        channel,
        model,
        NOTIFY_ON_FAILURE,
        checks=(PeriodicCheck("niche reports", CHECK_EVERY, enqueue_due_niche_reports),),
        on_stale={"import_instagram": clear_stale_token},
    )
