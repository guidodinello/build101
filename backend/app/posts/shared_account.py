"""Who may publish while every Post goes to the one account in ZERNIO_ACCOUNT_ID (ADR 0024).

An interim guard (#186): once Posts publish to each Business's own account (#185), this module
and its one check in `PostPublisher` go away.
"""

from dataclasses import dataclass

from app.channels.inbound import phone_digits


@dataclass(frozen=True, slots=True)
class SharedAccountGuard:
    """Only the Owner whose Instagram the shared account is (ZERNIO_OWNER_PHONE) may publish to it.

    With no Owner named, nobody may in production and everyone may elsewhere, like the pilot list.
    """

    owner_phone: str | None
    open_when_unset: bool

    def allows(self, sender: str) -> bool:
        if not self.owner_phone:
            return self.open_when_unset
        return phone_digits(sender) == phone_digits(self.owner_phone)
