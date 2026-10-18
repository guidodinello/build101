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

BusinessName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
STATES_BEFORE_THE_FORM = frozenset({"new", "awaiting_name"})


def require_dev_token(
    settings: Annotated[Settings, Depends(get_settings)],
    x_dev_token: Annotated[str | None, Header()] = None,
) -> None:
    if not settings.enable_dev_endpoints:
        raise HTTPException(status_code=404)
    if not settings.dev_token or not hmac.compare_digest(x_dev_token or "", settings.dev_token):
        raise HTTPException(status_code=401)


router = APIRouter(prefix="/dev", dependencies=[Depends(require_dev_token)])


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
    """Stand-in for the WhatsApp onboarding (T23): the Business for a phone, and a new link."""
    phone = re.sub(r"\D", "", body.phone)
    business = await session.scalar(select(Business).where(Business.owner_phone == phone))
    if business is None:
        business = Business(owner_phone=phone)
        session.add(business)
        await session.flush()
    if body.business_name:
        business.name = body.business_name
    if business.onboarding_state in STATES_BEFORE_THE_FORM:
        business.onboarding_state = "awaiting_web_form"
    token = add_onboarding_link(session, business)
    await session.commit()
    return OnboardingLinkResponse(
        business_id=str(business.id), token=token, url=onboarding_url(settings.frontend_url, token)
    )
