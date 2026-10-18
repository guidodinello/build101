import pytest

from app.instagram.oauth_state import STATE_TTL_S, InvalidState, sign_state, verify_state

SECRET = "app-secret"
NOW = 1_800_000_000.0


def test_a_signed_state_gives_back_its_token() -> None:
    state = sign_state("tok_en-123", SECRET, now=NOW)

    assert verify_state(state, SECRET, now=NOW + STATE_TTL_S) == "tok_en-123"


@pytest.mark.parametrize(
    "state",
    [
        "",
        "only-a-token",
        "token.not-a-number.sig",
        f"other-token.{int(NOW) + 60}.{sign_state('token', SECRET, now=NOW).rsplit('.', 1)[1]}",
    ],
)
def test_a_malformed_or_forged_state_is_rejected(state: str) -> None:
    with pytest.raises(InvalidState):
        verify_state(state, SECRET, now=NOW)


def test_a_state_signed_with_another_secret_is_rejected() -> None:
    with pytest.raises(InvalidState):
        verify_state(sign_state("token", "other", now=NOW), SECRET, now=NOW)


def test_an_expired_state_is_rejected() -> None:
    state = sign_state("token", SECRET, now=NOW)

    with pytest.raises(InvalidState, match="expired"):
        verify_state(state, SECRET, now=NOW + STATE_TTL_S + 1)
