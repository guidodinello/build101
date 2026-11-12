"""Which Businesses may connect their Instagram (#199).

Until Meta's App Review passes, our Meta app reads only accounts added as Instagram testers
(ADR 0028), so with INSTAGRAM=meta the team lists the Owners it has set up as testers in
INSTAGRAM_CONNECT_SENDERS, or `*` once App Review opens the connect to everyone.
"""

from app.channels.inbound import phone_digits
from app.config import Settings
from app.pilot import configured_numbers

EVERYONE = "*"


def connect_allowed(settings: Settings, owner_phone: str) -> bool:
    if settings.instagram == "off":
        return False
    if settings.instagram == "mock" or settings.instagram_connect_senders.strip() == EVERYONE:
        return True
    return phone_digits(owner_phone) in configured_numbers(settings.instagram_connect_senders)
