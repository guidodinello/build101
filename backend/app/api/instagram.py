"""Connecting the Owner's Instagram from the wizard, to read it for the Brand Brain (ADR 0028).

The browser goes from the wizard to Instagram's consent screen and comes back to the backend's
callback, which keeps the token, queues the import and sends the Owner back to the wizard.
"""

import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.config import Settings
from app.db.models import SocialAccount
from app.instagram.base import InstagramError, InstagramPort
from app.instagram.factory import get_instagram
from app.instagram.oauth_state import InvalidState, sign_state, verify_state
from app.jobs.queue import enqueue
from app.onboarding.links import onboarding_url

from .errors import ApiError
from .onboarding import OpenOnboardingDep, SessionDep, SettingsDep, get_onboarding

logger = logging.getLogger(__name__)

CALLBACK_PATH = "/oauth/instagram/callback"
# Signs the OAuth state when there is no app secret, i.e. INSTAGRAM=mock
DEV_STATE_SECRET = secrets.token_hex(32)
CONNECT_EXPIRED = "Se venció la conexión con Instagram. Volvé al formulario y probá de nuevo."

InstagramDep = Annotated[InstagramPort, Depends(get_instagram)]

router = APIRouter()


class ConnectResponse(BaseModel):
    auth_url: str


@router.post("/api/o/{token}/instagram/connect")
async def connect_instagram(
    token: str,
    _: OpenOnboardingDep,
    request: Request,
    settings: SettingsDep,
    instagram: InstagramDep,
) -> ConnectResponse:
    state = sign_state(token, _state_secret(settings))
    return ConnectResponse(
        auth_url=instagram.authorize_url(_redirect_uri(request, settings), state)
    )


@router.get(CALLBACK_PATH)
async def instagram_callback(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    instagram: InstagramDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    try:
        token = verify_state(state or "", _state_secret(settings))
    except InvalidState as exc:
        logger.warning("instagram callback with a bad state: %s", exc)
        raise ApiError(400, "invalid_state", CONNECT_EXPIRED) from None
    onboarding = await get_onboarding(token, session)
    business = onboarding.business
    wizard = onboarding_url(settings.frontend_url, token)
    if onboarding.link.completed_at is not None:
        # Same rule as the connect endpoint: a submitted form takes no more answers, and the
        # Brand Brain it started would never see this import (ADR 0032).
        logger.info("instagram callback for %s after the onboarding was completed", business.id)
        return RedirectResponse(wizard, status_code=303)
    back = f"{wizard}?step=instagram&connected="

    if error or not code:
        logger.info("instagram connect for %s not authorized: %s", business.id, error)
        return RedirectResponse(back + "0", status_code=303)
    try:
        ig_token = await instagram.exchange_code(code, _redirect_uri(request, settings))
        profile = await instagram.profile(ig_token.access_token)
    except InstagramError:
        logger.exception("instagram connect for %s failed", business.id)
        return RedirectResponse(back + "0", status_code=303)

    account = await session.scalar(
        select(SocialAccount).where(
            SocialAccount.business_id == business.id,
            SocialAccount.platform == "instagram",
            SocialAccount.provider == settings.instagram,
        )
    )
    if account is None:
        account = SocialAccount(
            business_id=business.id, platform="instagram", provider=settings.instagram
        )
        session.add(account)
    account.provider_account_id = ig_token.user_id or profile.user_id
    account.handle = profile.username
    account.access_token = ig_token.access_token
    account.token_expires_at = ig_token.expires_at
    account.status = "connected"
    business.instagram_handle = business.instagram_handle or profile.username
    enqueue(session, "import_instagram", business.id, {})
    await session.commit()
    return RedirectResponse(back + "1", status_code=303)


def _state_secret(settings: Settings) -> str:
    return settings.instagram_app_secret or DEV_STATE_SECRET


def _redirect_uri(request: Request, settings: Settings) -> str:
    """Meta matches it exactly against the app's list, so a deploy uses PUBLIC_BACKEND_URL."""
    if settings.public_backend_url:
        return settings.public_backend_url.rstrip("/") + CALLBACK_PATH
    return str(request.url_for("instagram_callback"))
