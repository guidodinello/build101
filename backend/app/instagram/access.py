from app.config import Settings
from app.db.models import Business


def instagram_allowed(settings: Settings, business: Business) -> bool:
    """Allow mock connections everywhere; restrict Meta to configured Business IDs."""
    if settings.instagram == "mock":
        return True

    allowed_ids = {
        item.strip() for item in settings.instagram_pilot_businesses.split(",") if item.strip()
    }
    return "*" in allowed_ids or str(business.id) in allowed_ids
