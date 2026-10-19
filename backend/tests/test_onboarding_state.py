import logging

import pytest

from app.db.models import Business
from app.onboarding.state import (
    BEFORE_THE_FORM,
    REVISABLE,
    InvalidOnboardingTransition,
    OnboardingState,
    ask_for_brand_correction,
    awaiting,
    brand_brain_written,
    confirm_brand,
    form_submitted,
    name_received,
    resume_after_failed_revision,
    skip_to_web_form,
    start_brand_revision,
    state_of,
    welcome,
)

S = OnboardingState


def business(state: OnboardingState, conversation_state: dict[str, str] | None = None) -> Business:
    return Business(
        owner_phone="59899000000",
        onboarding_state=state,
        conversation_state=conversation_state or {},
    )


def others(allowed: set[OnboardingState]) -> list[OnboardingState]:
    return [state for state in OnboardingState if state not in allowed]


def test_a_business_not_saved_yet_is_new() -> None:
    fresh = Business(owner_phone="59899000000")

    assert state_of(fresh) == S.NEW
    assert awaiting(fresh) is None


def test_the_first_message_welcomes_then_the_name_leads_to_the_form() -> None:
    owner = business(S.NEW)

    welcome(owner)
    assert state_of(owner) == S.AWAITING_NAME
    name_received(owner)

    assert state_of(owner) == S.AWAITING_WEB_FORM


@pytest.mark.parametrize("state", others({S.NEW}))
def test_welcome_only_from_new(state: OnboardingState) -> None:
    with pytest.raises(InvalidOnboardingTransition):
        welcome(business(state))


@pytest.mark.parametrize("state", others({S.AWAITING_NAME}))
def test_the_name_is_only_taken_while_awaiting_it(state: OnboardingState) -> None:
    with pytest.raises(InvalidOnboardingTransition):
        name_received(business(state))


@pytest.mark.parametrize("state", list(OnboardingState))
def test_the_dev_shortcut_only_moves_businesses_before_the_name_is_known(
    state: OnboardingState,
) -> None:
    owner = business(state)

    skip_to_web_form(owner)

    expected = S.AWAITING_WEB_FORM if state in {S.NEW, S.AWAITING_NAME} else state
    assert state_of(owner) == expected


@pytest.mark.parametrize("state", sorted(BEFORE_THE_FORM))
def test_submitting_the_form_starts_the_brand(state: OnboardingState) -> None:
    owner = business(state)

    form_submitted(owner)

    assert state_of(owner) == S.GENERATING_BRAND


@pytest.mark.parametrize("state", others(set(BEFORE_THE_FORM)))
def test_submitting_the_form_late_warns_and_still_starts_the_brand(
    state: OnboardingState, caplog: pytest.LogCaptureFixture
) -> None:
    owner = business(state)

    with caplog.at_level(logging.WARNING):
        form_submitted(owner)

    assert state_of(owner) == S.GENERATING_BRAND
    assert f"unexpected onboarding state {state.value}" in caplog.text


@pytest.mark.parametrize("state", [S.GENERATING_BRAND, S.AWAITING_BRAND_CONFIRMATION, S.ACTIVE])
def test_a_written_brand_asks_for_confirmation_and_clears_the_conversation(
    state: OnboardingState, caplog: pytest.LogCaptureFixture
) -> None:
    owner = business(state, {"awaiting": "brand_correction"})

    with caplog.at_level(logging.WARNING):
        brand_brain_written(owner)

    assert (state_of(owner), owner.conversation_state) == (S.AWAITING_BRAND_CONFIRMATION, {})
    assert caplog.text == ""


@pytest.mark.parametrize("state", sorted(BEFORE_THE_FORM))
def test_a_brand_written_before_the_form_warns_and_still_asks_for_confirmation(
    state: OnboardingState, caplog: pytest.LogCaptureFixture
) -> None:
    owner = business(state)

    with caplog.at_level(logging.WARNING):
        brand_brain_written(owner)

    assert state_of(owner) == S.AWAITING_BRAND_CONFIRMATION
    assert f"unexpected onboarding state {state.value}" in caplog.text


def test_confirming_the_brand_activates_the_business() -> None:
    owner = business(S.AWAITING_BRAND_CONFIRMATION, {"awaiting": "brand_correction"})

    confirm_brand(owner)

    assert (state_of(owner), owner.conversation_state) == (S.ACTIVE, {})


@pytest.mark.parametrize("state", others({S.AWAITING_BRAND_CONFIRMATION}))
def test_only_a_pending_summary_can_be_confirmed_or_corrected(state: OnboardingState) -> None:
    with pytest.raises(InvalidOnboardingTransition):
        confirm_brand(business(state))
    with pytest.raises(InvalidOnboardingTransition):
        ask_for_brand_correction(business(state))


def test_asking_for_a_correction_keeps_the_state_and_marks_what_is_awaited() -> None:
    owner = business(S.AWAITING_BRAND_CONFIRMATION)

    ask_for_brand_correction(owner)

    assert state_of(owner) == S.AWAITING_BRAND_CONFIRMATION
    assert awaiting(owner) == "brand_correction"


@pytest.mark.parametrize("state", REVISABLE)
def test_a_revision_remembers_where_to_come_back_to(state: OnboardingState) -> None:
    owner = business(state, {"awaiting": "brand_correction"})

    start_brand_revision(owner)

    assert state_of(owner) == S.GENERATING_BRAND
    assert owner.conversation_state == {"resume_state": state.value}
    assert awaiting(owner) is None


@pytest.mark.parametrize("state", others(set(REVISABLE)))
def test_a_revision_needs_a_first_brand_and_not_one_in_progress(state: OnboardingState) -> None:
    with pytest.raises(InvalidOnboardingTransition):
        start_brand_revision(business(state))


@pytest.mark.parametrize("state", REVISABLE)
def test_a_failed_revision_puts_the_business_back(state: OnboardingState) -> None:
    owner = business(state)
    start_brand_revision(owner)

    assert resume_after_failed_revision(owner) is True

    assert (state_of(owner), owner.conversation_state) == (state, {})


def test_a_failed_first_brand_has_nowhere_to_go_back_to() -> None:
    owner = business(S.GENERATING_BRAND)

    assert resume_after_failed_revision(owner) is False
    assert state_of(owner) == S.GENERATING_BRAND


def test_a_revision_that_already_finished_is_not_undone() -> None:
    owner = business(S.AWAITING_BRAND_CONFIRMATION, {"resume_state": "active"})

    assert resume_after_failed_revision(owner) is False
    assert state_of(owner) == S.AWAITING_BRAND_CONFIRMATION


def test_the_states_keep_the_values_stored_in_the_database() -> None:
    assert [state.value for state in OnboardingState] == [
        "new",
        "awaiting_name",
        "awaiting_web_form",
        "generating_brand",
        "awaiting_brand_confirmation",
        "active",
    ]
