import logging

from app.channels.base import ChannelPort
from app.config import Settings
from app.db.session import get_sessionmaker
from app.llm.client import GeminiChat
from app.storage import get_storage

from .asset import analyze_asset
from .brand import generate_brand
from .runner import JobFunction, JobRunner

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
    return JobRunner(get_sessionmaker(), JOBS, get_storage(), channel, model, NOTIFY_ON_FAILURE)
