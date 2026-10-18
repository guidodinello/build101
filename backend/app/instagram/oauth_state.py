"""The OAuth `state` of the Instagram connect: the wizard's magic-link token, signed, expiring.

The callback needs the token to find the Business and to send the Owner back to `/o/{token}`,
and only its hash is stored. The signature stops a forged state; the expiry keeps a connect
link someone forwards from working for long.
"""

import hashlib
import hmac
import time

STATE_TTL_S = 15 * 60
SIGNATURE_CHARS = 32


class InvalidState(Exception):
    pass


def sign_state(token: str, secret: str, now: float | None = None) -> str:
    expires = int((now if now is not None else time.time()) + STATE_TTL_S)
    payload = f"{token}.{expires}"
    return f"{payload}.{_signature(payload, secret)}"


def verify_state(state: str, secret: str, now: float | None = None) -> str:
    """The magic-link token in `state`; InvalidState when forged, malformed or expired."""
    token, _, rest = state.partition(".")
    expires, _, signature = rest.partition(".")
    if not token or not expires.isdigit():
        raise InvalidState("malformed state")
    if not hmac.compare_digest(signature, _signature(f"{token}.{expires}", secret)):
        raise InvalidState("bad signature")
    if int(expires) < (now if now is not None else time.time()):
        raise InvalidState("expired")
    return token


def _signature(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:SIGNATURE_CHARS]
