"""The Business's onboarding state: its states, what each means, and the moves between them.

This module is the only writer of `Business.onboarding_state` and of the `awaiting` and
`resume_state` keys of `Business.conversation_state`. Everyone else asks it to move the Business
forward; the column stays a plain string, the enum gives the values a name and a meaning.

Transitions mutate the Business in place. The caller owns the session, the row lock and the
commit. Most transitions raise `InvalidOnboardingTransition` from a state that doesn't allow
them; their callers select the Business with an SQL guard on the state (or check it first), so
the raise cannot happen in a normal flow. `form_submitted` and `brand_brain_written` instead log
a warning and do the same write: they have always been unconditional.
"""

import logging
from collections.abc import Collection
from enum import StrEnum

from app.db.models import Business

logger = logging.getLogger(__name__)

AWAITING_BRAND_CORRECTION = "brand_correction"
_AWAITING = "awaiting"
_RESUME_STATE = "resume_state"


class OnboardingState(StrEnum):
    NEW = "new"
    """First message not answered yet. The gate sends the welcome (Flow 1)."""
    AWAITING_NAME = "awaiting_name"
    """Welcomed; the Owner's next message is the business name."""
    AWAITING_WEB_FORM = "awaiting_web_form"
    """Has the magic link; the gate only sends reminders until the form is submitted."""
    GENERATING_BRAND = "generating_brand"
    """The Brand Strategist is writing (or revising) the Brand Brain; the old summary's buttons
    are stale."""
    AWAITING_BRAND_CONFIRMATION = "awaiting_brand_confirmation"
    """The Owner saw `brand_summary` and must tap Sí, es mi marca or Corregir algo."""
    ACTIVE = "active"
    """Onboarding is complete: messages go to the orchestrator, jobs run for this Business."""


BEFORE_THE_FORM = frozenset(
    {OnboardingState.NEW, OnboardingState.AWAITING_NAME, OnboardingState.AWAITING_WEB_FORM}
)
# Where the Owner can ask for a different brand: after the first summary, even once active.
REVISABLE = (OnboardingState.AWAITING_BRAND_CONFIRMATION, OnboardingState.ACTIVE)


class InvalidOnboardingTransition(ValueError):
    def __init__(self, action: str, state: OnboardingState) -> None:
        super().__init__(f"{action} is not allowed from {state.value}")


def state_of(business: Business) -> OnboardingState:
    # A Business that isn't flushed yet has no server default.
    return OnboardingState(business.onboarding_state or OnboardingState.NEW)


def awaiting(business: Business) -> str | None:
    """What the Owner's next free-text message is an answer to, e.g. the brand correction."""
    return _conversation(business).get(_AWAITING)


def _conversation(business: Business) -> dict[str, str]:
    return business.conversation_state or {}


def _require(business: Business, action: str, allowed: Collection[OnboardingState]) -> None:
    state = state_of(business)
    if state not in allowed:
        raise InvalidOnboardingTransition(action, state)


def _expect(business: Business, action: str, allowed: Collection[OnboardingState]) -> None:
    state = state_of(business)
    if state not in allowed:
        logger.warning("%s from the unexpected onboarding state %s", action, state.value)


def welcome(business: Business) -> None:
    _require(business, "welcome", {OnboardingState.NEW})
    business.onboarding_state = OnboardingState.AWAITING_NAME


def name_received(business: Business) -> None:
    _require(business, "name_received", {OnboardingState.AWAITING_NAME})
    business.onboarding_state = OnboardingState.AWAITING_WEB_FORM


def skip_to_web_form(business: Business) -> None:
    """Dev shortcut past the WhatsApp onboarding. Idempotent: a no-op once the form is reached."""
    if state_of(business) in {OnboardingState.NEW, OnboardingState.AWAITING_NAME}:
        business.onboarding_state = OnboardingState.AWAITING_WEB_FORM


def form_submitted(business: Business) -> None:
    _expect(business, "form_submitted", BEFORE_THE_FORM)
    business.onboarding_state = OnboardingState.GENERATING_BRAND


def brand_brain_written(business: Business) -> None:
    """A Brand Brain version was saved; its summary goes out, or waits for the 24 h window."""
    _expect(
        business,
        "brand_brain_written",
        {
            OnboardingState.GENERATING_BRAND,
            OnboardingState.AWAITING_BRAND_CONFIRMATION,
            OnboardingState.ACTIVE,
        },
    )
    business.onboarding_state = OnboardingState.AWAITING_BRAND_CONFIRMATION
    business.conversation_state = {}


def confirm_brand(business: Business) -> None:
    _require(business, "confirm_brand", {OnboardingState.AWAITING_BRAND_CONFIRMATION})
    business.onboarding_state = OnboardingState.ACTIVE
    business.conversation_state = {}


def ask_for_brand_correction(business: Business) -> None:
    """The orchestrator reads the Owner's next message as the brand correction."""
    _require(business, "ask_for_brand_correction", {OnboardingState.AWAITING_BRAND_CONFIRMATION})
    business.conversation_state = {_AWAITING: AWAITING_BRAND_CORRECTION}


def start_brand_revision(business: Business) -> None:
    """Back to generating, remembering where a failed revision puts the Business back."""
    _require(business, "start_brand_revision", REVISABLE)
    business.conversation_state = {_RESUME_STATE: state_of(business).value}
    business.onboarding_state = OnboardingState.GENERATING_BRAND


def resume_after_failed_revision(business: Business) -> bool:
    """True when the Business went back to where it was before the revision (ADR 0030)."""
    previous = _conversation(business).get(_RESUME_STATE)
    if state_of(business) != OnboardingState.GENERATING_BRAND or not previous:
        return False
    business.onboarding_state = OnboardingState(previous)
    business.conversation_state = {}
    return True
