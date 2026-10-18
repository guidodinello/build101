import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Business, MagicLink

ONBOARDING_LINK_TTL = timedelta(days=7)
TOKEN_BYTES = 32


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def add_onboarding_link(session: AsyncSession, business: Business) -> str:
    """Add a magic link for the web wizard to the session and return its raw token.

    Only the hash is stored; the raw token lives in the URL the Owner gets.
    """
    token = secrets.token_urlsafe(TOKEN_BYTES)
    session.add(
        MagicLink(
            business_id=business.id,
            token_hash=hash_token(token),
            purpose="onboarding",
            expires_at=datetime.now(UTC) + ONBOARDING_LINK_TTL,
        )
    )
    return token


def onboarding_url(frontend_url: str, token: str) -> str:
    return f"{frontend_url.rstrip('/')}/o/{token}"
