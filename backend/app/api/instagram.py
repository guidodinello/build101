"""Connecting the Owner's Instagram from the wizard, to read it for the Brand Brain (ADR 0028).

The browser goes from the wizard to Instagram's consent screen and comes back to the backend's
callback, which keeps the token, queues the import and sends the Owner back to the wizard.
"""

import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import SocialAccount
from app.instagram.base import InstagramError, InstagramPort
from app.instagram.factory import get_instagram
from app.instagram.oauth_state import (
    BINDING_TTL_S,
    InvalidState,
    new_binding,
    sign_ticket,
    verify_binding,
    verify_ticket,
)
from app.jobs.queue import enqueue
from app.onboarding.links import onboarding_url

from .errors import ApiError, error_response
from .onboarding import (
    OpenOnboardingDep,
    SessionDep,
    SettingsDep,
    get_onboarding,
    get_open_onboarding,
    is_submitted,
)

logger = logging.getLogger(__name__)

CALLBACK_PATH = "/oauth/instagram/callback"
BINDING_COOKIE = "ig_oauth"
# The cookie goes only to the callback, never to the rest of the API
BINDING_COOKIE_PATH = CALLBACK_PATH.rsplit("/", 1)[0]
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
) -> ConnectResponse:
    """The wizard navigates to `auth_url`; the start hop sets the cookie that binds the callback."""
    ticket = sign_ticket(token, _state_secret(settings))
    start = f"{_backend_url(request, settings)}/api/o/{token}/instagram/start?ticket={ticket}"
    return ConnectResponse(auth_url=start)


@router.get("/api/o/{token}/instagram/start")
async def start_instagram(
    token: str,
    ticket: str,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    instagram: InstagramDep,
) -> RedirectResponse:
    """Top-level hop: set the binding cookie on our own origin, then go to the consent screen."""
    secret = _state_secret(settings)
    try:
        verify_ticket(token, ticket, secret)
    except InvalidState as exc:
        logger.warning("instagram start with a bad ticket: %s", exc)
        raise ApiError(400, "invalid_state", CONNECT_EXPIRED) from None
    await get_open_onboarding(await get_onboarding(token, session), session)
    nonce, cookie = new_binding(token, secret)
    response = RedirectResponse(
        instagram.authorize_url(_redirect_uri(request, settings), nonce), status_code=303
    )
    response.set_cookie(
        BINDING_COOKIE,
        cookie,
        max_age=BINDING_TTL_S,
        path=BINDING_COOKIE_PATH,
        httponly=True,
        secure=_backend_url(request, settings).startswith("https://"),
        samesite="lax",
    )
    return response


@router.get(CALLBACK_PATH)
async def instagram_callback(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    instagram: InstagramDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    binding: Annotated[str | None, Cookie(alias=BINDING_COOKIE)] = None,
) -> Response:
    """Every outcome, errors included, clears the cookie: it holds the token for 15 minutes."""
    try:
        token = _bound_token(binding, state, settings)
        response: Response = await _finish_connect(
            token, code, error, request, session, settings, instagram
        )
    except ApiError as exc:
        response = error_response(exc)
    except Exception:
        logger.exception("instagram callback failed")
        response = PlainTextResponse("Internal Server Error", status_code=500)
    response.delete_cookie(BINDING_COOKIE, path=BINDING_COOKIE_PATH)
    return response


def _bound_token(binding: str | None, state: str | None, settings: Settings) -> str:
    try:
        return verify_binding(binding or "", state or "", _state_secret(settings))
    except InvalidState as exc:
        logger.warning("instagram callback with a bad state: %s", exc)
        raise ApiError(400, "invalid_state", CONNECT_EXPIRED) from None


async def _finish_connect(
    token: str,
    code: str | None,
    error: str | None,
    request: Request,
    session: AsyncSession,
    settings: Settings,
    instagram: InstagramPort,
) -> RedirectResponse:
    onboarding = await get_onboarding(token, session)
    business = onboarding.business
    wizard = onboarding_url(settings.frontend_url, token)
    # Locked before the check, as in get_open_onboarding: a submit in flight finishes first.
    await session.refresh(business, with_for_update=True)
    if await is_submitted(session, business.id):
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


def _backend_url(request: Request, settings: Settings) -> str:
    """Where the browser reaches us; a deploy sits behind a proxy, so it sets PUBLIC_BACKEND_URL."""
    if settings.public_backend_url:
        return settings.public_backend_url.rstrip("/")
    return str(request.base_url).rstrip("/")


def _redirect_uri(request: Request, settings: Settings) -> str:
    """Meta matches it exactly against the app's list, so a deploy uses PUBLIC_BACKEND_URL."""
    return _backend_url(request, settings) + CALLBACK_PATH
