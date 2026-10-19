"""What ties the Instagram connect to the browser that started it (RFC 6749 §10.12).

The wizard's magic-link token is a bearer secret, so it never goes in the OAuth `state`: that
travels to instagram.com and into access logs. Two signed values carry it instead:

- A **ticket** in the `auth_url` the wizard navigates to (`/api/o/{token}/instagram/start`).
  It lives 2 minutes, so a forwarded start URL dies fast.
- A **binding cookie**, set by that start hop on the backend's own origin (HttpOnly, SameSite=Lax,
  so it also works when the wizard and the backend are on different sites). It holds the token and
  a random nonce. The nonce is the only thing in `state`; the callback needs the cookie, whose
  nonce must equal `state`. It takes the token from the cookie, since only its hash is stored.

Each signature is domain-separated (`start.` / `bind.`) so one value can't stand in for the other.
"""

import hashlib
import hmac
import secrets
import time

TICKET_TTL_S = 2 * 60
BINDING_TTL_S = 15 * 60
SIGNATURE_CHARS = 32


class InvalidState(Exception):
    pass


def sign_ticket(token: str, secret: str, now: float | None = None) -> str:
    expires = int(_now(now) + TICKET_TTL_S)
    return f"{expires}.{_signature(f'start.{token}.{expires}', secret)}"


def verify_ticket(token: str, ticket: str, secret: str, now: float | None = None) -> None:
    """InvalidState when the ticket is forged, for another token, malformed or expired."""
    expires, _, signature = ticket.partition(".")
    if not expires.isdigit():
        raise InvalidState("malformed ticket")
    if not _same(signature, _signature(f"start.{token}.{expires}", secret)):
        raise InvalidState("bad ticket signature")
    if int(expires) < _now(now):
        raise InvalidState("expired ticket")


def new_binding(token: str, secret: str, now: float | None = None) -> tuple[str, str]:
    """A fresh `(nonce, cookie value)`: the nonce goes in `state`, the value in the cookie."""
    nonce = secrets.token_urlsafe(32)
    expires = int(_now(now) + BINDING_TTL_S)
    payload = f"{token}.{nonce}.{expires}"
    return nonce, f"{payload}.{_signature(f'bind.{payload}', secret)}"


def verify_binding(cookie: str, state: str, secret: str, now: float | None = None) -> str:
    """The magic-link token in the cookie; InvalidState unless it is ours, fresh and for `state`."""
    payload, _, signature = cookie.rpartition(".")
    token, _, rest = payload.partition(".")
    nonce, _, expires = rest.partition(".")
    if not (token and nonce and expires.isdigit()):
        raise InvalidState("malformed binding")
    if not _same(signature, _signature(f"bind.{payload}", secret)):
        raise InvalidState("bad binding signature")
    if int(expires) < _now(now):
        raise InvalidState("expired binding")
    if not _same(nonce, state):
        raise InvalidState("state does not match the browser that started the connect")
    return token


def _same(a: str, b: str) -> bool:
    """Constant-time; bytes because compare_digest raises on a non-ASCII str."""
    return hmac.compare_digest(a.encode(), b.encode())


def _now(now: float | None) -> float:
    return now if now is not None else time.time()


def _signature(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:SIGNATURE_CHARS]
