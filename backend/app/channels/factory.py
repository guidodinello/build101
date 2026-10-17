from app.config import Settings

from .base import ChannelPort
from .kapso import KapsoChannel


def build_channel(settings: Settings) -> ChannelPort:
    match settings.whatsapp_channel:
        case "kapso":
            if not settings.kapso_api_key or not settings.kapso_phone_number_id:
                raise ValueError(
                    "WHATSAPP_CHANNEL=kapso needs KAPSO_API_KEY and KAPSO_PHONE_NUMBER_ID"
                )
            return KapsoChannel.from_settings(
                api_key=settings.kapso_api_key,
                phone_number_id=settings.kapso_phone_number_id,
                base_url=settings.kapso_base_url,
            )
        case "simulator":
            raise NotImplementedError("the simulator channel is task T21")
