"""Connecting the Owner's Instagram from the wizard, to read it for the Brand Brain (ADR 0028).

The browser goes from the wizard to Instagram's consent screen and comes back to the backend's
callback, which keeps the token, queues the import and sends the Owner back to the wizard.
"""

import html
import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Business, SocialAccount
from app.instagram.access import connect_allowed
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
from app.pilot import PilotList
from app.ratelimit import limit_onboarding_token

from .errors import ApiError, error_response
from .onboarding import (
    OpenOnboardingDep,
    PilotDep,
    SessionDep,
    SettingsDep,
    check_pilot,
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
INSTAGRAM_UNAVAILABLE = "Por ahora no podemos conectar tu Instagram. Seguí con el formulario."
# The start hop and the callback are top-level navigations: a connect that can't be matched to
# the browser that started it (expired, or back in another browser) gets a page, not JSON.
EXPIRED_PAGE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Se venció la conexión con Instagram</title>
<style>
body {{ margin: 0; font-family: system-ui, sans-serif; background: #f7f5f0; color: #1d1d1b; }}
main {{ max-width: 28rem; margin: 0 auto; padding: 3rem 1.25rem; }}
h1 {{ font-size: 1.5rem; line-height: 1.25; }}
p {{ font-size: 1.0625rem; line-height: 1.5; }}
a {{ display: block; margin-top: 2rem; padding: 1rem; border-radius: 999px; background: #1f7a4d;
  color: #fff; font-size: 1.125rem; font-weight: 700; text-align: center; text-decoration: none; }}
</style>
</head>
<body>
<main>
<h1>Se venció la conexión con Instagram</h1>
<p>Pasó mucho tiempo, o Instagram te devolvió a otro navegador. Volvé a WhatsApp y abrí de nuevo
el link del formulario para probar otra vez.</p>
<p>Si preferís, seguí sin Instagram: subís 3 fotos y listo.</p>
<a href="{whatsapp_url}">Volver a WhatsApp</a>
</main>
</body>
</html>
"""

InstagramDep = Annotated[InstagramPort, Depends(get_instagram)]


async def require_instagram(settings: SettingsDep) -> None:
    """With INSTAGRAM=off there is no connect: nothing reaches Meta and no mock data is made."""
    if settings.instagram == "off":
        raise ApiError(404, "instagram_unavailable", INSTAGRAM_UNAVAILABLE)


# First in every route: it runs before `InstagramDep`, which has no adapter to build when off
router = APIRouter(dependencies=[Depends(require_instagram)])


def check_connect_allowed(settings: Settings, business: Business) -> None:
    """Until App Review, our Meta app reads only the accounts the team made testers (#199)."""
    if not connect_allowed(settings, business.owner_phone):
        raise ApiError(403, "instagram_not_allowed", INSTAGRAM_UNAVAILABLE)


def expired_page(settings: Settings) -> HTMLResponse:
    return HTMLResponse(
        EXPIRED_PAGE.format(whatsapp_url=html.escape(settings.whatsapp_url)), status_code=400
    )


class ConnectResponse(BaseModel):
    auth_url: str


@router.post("/api/o/{token}/instagram/connect", dependencies=[Depends(limit_onboarding_token)])
async def connect_instagram(
    token: str,
    onboarding: OpenOnboardingDep,
    request: Request,
    settings: SettingsDep,
) -> ConnectResponse:
    """The wizard navigates to `auth_url`; the start hop sets the cookie that binds the callback."""
    check_connect_allowed(settings, onboarding.business)
    ticket = sign_ticket(token, _state_secret(settings))
    start = f"{_backend_url(request, settings)}/api/o/{token}/instagram/start?ticket={ticket}"
    return ConnectResponse(auth_url=start)


@router.get("/api/o/{token}/instagram/start", dependencies=[Depends(limit_onboarding_token)])
async def start_instagram(
    token: str,
    ticket: str,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    instagram: InstagramDep,
    pilot: PilotDep,
) -> Response:
    """Top-level hop: set the binding cookie on our own origin, then go to the consent screen."""
    secret = _state_secret(settings)
    try:
        verify_ticket(token, ticket, secret)
    except InvalidState as exc:
        logger.warning("instagram start with a bad ticket: %s", exc)
        return expired_page(settings)
    onboarding = await get_open_onboarding(await get_onboarding(token, session), session, pilot)
    check_connect_allowed(settings, onboarding.business)
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
    pilot: PilotDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    binding: Annotated[str | None, Cookie(alias=BINDING_COOKIE)] = None,
) -> Response:
    """Every outcome, errors included, clears the cookie: it holds the token for 15 minutes."""
    response: Response
    try:
        token = verify_binding(binding or "", state or "", _state_secret(settings))
        response = await _finish_connect(
            token, code, error, request, session, settings, instagram, pilot
        )
    except InvalidState as exc:
        logger.warning("instagram callback with a bad state: %s", exc)
        response = expired_page(settings)
    except ApiError as exc:
        response = error_response(exc)
    except Exception:
        logger.exception("instagram callback failed")
        response = PlainTextResponse("Internal Server Error", status_code=500)
    response.delete_cookie(BINDING_COOKIE, path=BINDING_COOKIE_PATH)
    return response


async def _finish_connect(
    token: str,
    code: str | None,
    error: str | None,
    request: Request,
    session: AsyncSession,
    settings: Settings,
    instagram: InstagramPort,
    pilot: PilotList,
) -> RedirectResponse:
    onboarding = await get_onboarding(token, session)
    business = onboarding.business
    await check_pilot(pilot, business)
    wizard = onboarding_url(settings.frontend_url, token)
    if not connect_allowed(settings, business.owner_phone):
        # Taken off the list since the start hop: the wizard now resumes past the Instagram step.
        logger.info("instagram callback for %s, which may no longer connect", business.id)
        return RedirectResponse(wizard, status_code=303)
    # Locked before the check, as in get_open_onboarding: a submit in flight finishes first.
    await session.refresh(business, with_for_update=True)
    if await is_submitted(session, business.id):
        # Same rule as the connect endpoint: a submitted form takes no more answers, and the
        # Brand Brain it started would never see this import (ADR 0032).
        logger.info("instagram callback for %s after the onboarding was completed", business.id)
        return RedirectResponse(wizard, status_code=303)
    back = f"{wizard}?step=instagram&connected="

    if error:
        logger.info("instagram connect for %s not authorized: %s", business.id, error)
        return RedirectResponse(back + "0&reason=denied", status_code=303)
    if not code:
        logger.warning("instagram callback for %s without a code", business.id)
        return RedirectResponse(back + "0&reason=unreadable", status_code=303)
    try:
        ig_token = await instagram.exchange_code(code, _redirect_uri(request, settings))
        profile = await instagram.profile(ig_token.access_token)
    except InstagramError:
        # Most likely a personal account, or a tester invite not accepted yet (ADR 0028).
        logger.exception("instagram connect for %s failed", business.id)
        return RedirectResponse(back + "0&reason=unreadable", status_code=303)

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
