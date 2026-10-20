"""Dev-only endpoints, behind ENABLE_DEV_ENDPOINTS and X-Dev-Token (api.md § Dev / simulator)."""

import hmac
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.models import Business
from app.db.session import get_session
from app.onboarding.links import add_onboarding_link, onboarding_url
from app.onboarding.state import skip_to_web_form

BusinessName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


def require_dev_token(
    settings: Annotated[Settings, Depends(get_settings)],
    x_dev_token: Annotated[str | None, Header()] = None,
) -> None:
    # Never in production, whatever the flag says.
    if settings.env == "prod" or not settings.enable_dev_endpoints:
        raise HTTPException(status_code=404)
    # Bytes: compare_digest raises TypeError on a non-ASCII str, which would be a 500.
    if not settings.dev_token or not hmac.compare_digest(
        (x_dev_token or "").encode(), settings.dev_token.encode()
    ):
        raise HTTPException(status_code=401)


# Not in the OpenAPI schema: it would list these routes even where they are off.
router = APIRouter(
    prefix="/dev", dependencies=[Depends(require_dev_token)], include_in_schema=False
)


class OnboardingLinkRequest(BaseModel):
    phone: Annotated[str, StringConstraints(pattern=r"^\+?[\d\s-]{8,20}$")]
    business_name: BusinessName | None = None


class OnboardingLinkResponse(BaseModel):
    business_id: str
    token: str
    url: str


@router.post("/onboarding-link")
async def create_onboarding_link(
    body: OnboardingLinkRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OnboardingLinkResponse:
    """Shortcut past the WhatsApp onboarding, for tests and the simulator: a Business, a link."""
    phone = re.sub(r"\D", "", body.phone)
    business = await session.scalar(select(Business).where(Business.owner_phone == phone))
    if business is None:
        business = Business(owner_phone=phone)
        session.add(business)
        await session.flush()
    if body.business_name:
        business.name = body.business_name
    skip_to_web_form(business)
    token = add_onboarding_link(session, business)
    await session.commit()
    return OnboardingLinkResponse(
        business_id=str(business.id), token=token, url=onboarding_url(settings.frontend_url, token)
    )
