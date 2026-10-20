import pytest

from app.instagram.oauth_state import (
    BINDING_TTL_S,
    TICKET_TTL_S,
    InvalidState,
    new_binding,
    sign_ticket,
    verify_binding,
    verify_ticket,
)

SECRET = "app-secret"
NOW = 1_800_000_000.0
TOKEN = "tok_en-123"


def test_a_signed_ticket_verifies_for_its_token() -> None:
    ticket = sign_ticket(TOKEN, SECRET, now=NOW)

    verify_ticket(TOKEN, ticket, SECRET, now=NOW + TICKET_TTL_S)


@pytest.mark.parametrize("ticket", ["", "no-dot", "not-a-number.sig", f"{int(NOW) + 60}.forged"])
def test_a_malformed_or_forged_ticket_is_rejected(ticket: str) -> None:
    with pytest.raises(InvalidState):
        verify_ticket(TOKEN, ticket, SECRET, now=NOW)


def test_a_ticket_is_only_good_for_its_own_token_and_secret() -> None:
    ticket = sign_ticket(TOKEN, SECRET, now=NOW)

    with pytest.raises(InvalidState):
        verify_ticket("other-token", ticket, SECRET, now=NOW)
    with pytest.raises(InvalidState):
        verify_ticket(TOKEN, ticket, "other-secret", now=NOW)


def test_an_expired_ticket_is_rejected() -> None:
    ticket = sign_ticket(TOKEN, SECRET, now=NOW)

    with pytest.raises(InvalidState, match="expired"):
        verify_ticket(TOKEN, ticket, SECRET, now=NOW + TICKET_TTL_S + 1)


def test_a_binding_gives_back_its_token_for_the_matching_state() -> None:
    nonce, cookie = new_binding(TOKEN, SECRET, now=NOW)

    assert verify_binding(cookie, nonce, SECRET, now=NOW + BINDING_TTL_S) == TOKEN


def test_the_state_nonce_carries_no_token() -> None:
    nonce, _ = new_binding(TOKEN, SECRET, now=NOW)

    assert TOKEN not in nonce
    assert "." not in nonce


def test_each_binding_has_its_own_nonce() -> None:
    assert new_binding(TOKEN, SECRET, now=NOW)[0] != new_binding(TOKEN, SECRET, now=NOW)[0]


def test_a_state_from_another_browsers_binding_is_rejected() -> None:
    _, victim_cookie = new_binding(TOKEN, SECRET, now=NOW)
    attacker_nonce, _ = new_binding(TOKEN, SECRET, now=NOW)

    with pytest.raises(InvalidState, match="does not match"):
        verify_binding(victim_cookie, attacker_nonce, SECRET, now=NOW)


@pytest.mark.parametrize("cookie", ["", "only-a-token", "a.b.not-a-number.sig", "a.b.c"])
def test_a_malformed_binding_is_rejected(cookie: str) -> None:
    with pytest.raises(InvalidState):
        verify_binding(cookie, "state", SECRET, now=NOW)


def test_a_tampered_binding_is_rejected() -> None:
    nonce, cookie = new_binding(TOKEN, SECRET, now=NOW)
    _, _, rest = cookie.partition(".")

    with pytest.raises(InvalidState, match="signature"):
        verify_binding(f"other-token.{rest}", nonce, SECRET, now=NOW)


def test_a_binding_signed_with_another_secret_is_rejected() -> None:
    nonce, cookie = new_binding(TOKEN, "other", now=NOW)

    with pytest.raises(InvalidState, match="signature"):
        verify_binding(cookie, nonce, SECRET, now=NOW)


def test_an_expired_binding_is_rejected() -> None:
    nonce, cookie = new_binding(TOKEN, SECRET, now=NOW)

    with pytest.raises(InvalidState, match="expired"):
        verify_binding(cookie, nonce, SECRET, now=NOW + BINDING_TTL_S + 1)


def test_a_ticket_cannot_stand_in_for_a_binding() -> None:
    ticket = sign_ticket(TOKEN, SECRET, now=NOW)

    with pytest.raises(InvalidState):
        verify_binding(f"{TOKEN}.nonce.{ticket}", "nonce", SECRET, now=NOW)


def test_a_non_ascii_state_is_rejected_not_crashed() -> None:
    _, cookie = new_binding(TOKEN, SECRET, now=NOW)

    with pytest.raises(InvalidState):
        verify_binding(cookie, "ñandú", SECRET, now=NOW)
