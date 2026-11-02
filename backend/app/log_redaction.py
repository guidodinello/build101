import logging
import re
from typing import override
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

REDACTED = "REDACTED"
# Kapso's media download URL embeds a signed `token`; `key` covers an API key in a query string;
# the Instagram Graph API takes the Owner's `access_token` and our `client_secret` in the query.
SENSITIVE_QUERY_PARAMS = frozenset({"token", "key", "access_token", "client_secret"})
# What reaches our own access log: the OAuth callback's `code` and `state`, and the start hop's
# `ticket`. The onboarding magic-link token is a path segment: /api/o/{token}/...
ACCESS_LOG_SENSITIVE_PARAMS = SENSITIVE_QUERY_PARAMS | {"code", "state", "ticket"}
ONBOARDING_TOKEN_SEGMENT = re.compile(r"(/o/)[^/?#]+")


def redact_query(query: str, sensitive: frozenset[str] = SENSITIVE_QUERY_PARAMS) -> str:
    pairs = [
        (name, REDACTED if name in sensitive else value)
        for name, value in parse_qsl(query, keep_blank_values=True)
    ]
    return urlencode(pairs)


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.query:
        return url
    return urlunsplit(parts._replace(query=redact_query(parts.query)))


def redact_request_target(target: str) -> str:
    """A request target (path and query) with the onboarding token and OAuth secrets masked."""
    path, separator, query = target.partition("?")
    path = ONBOARDING_TOKEN_SEGMENT.sub(rf"\1{REDACTED}", path)
    if not query:
        return path + separator
    return f"{path}?{redact_query(query, ACCESS_LOG_SENSITIVE_PARAMS)}"


class RedactQueryTokens(logging.Filter):
    """Redacts secret query params from URLs in log args, keeping method, host, path, status.

    httpx logs `HTTP Request: %s %s "%s %d %s"` with the URL as an arg, so the message text
    only exists once the record is formatted: rewrite the args instead.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_redact_arg(arg) for arg in record.args)
        return True


def _redact_arg(arg: object) -> object:
    if isinstance(arg, httpx.URL):
        return redact_url(str(arg))
    if isinstance(arg, str) and arg.startswith(("http://", "https://")):
        return redact_url(arg)
    return arg


class RedactAccessLog(logging.Filter):
    """Masks tokens in uvicorn's access lines, which log `%s - "%s %s HTTP/%s" %d` with the
    request target (path and query) as the third arg."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], redact_request_target(args[2]), *args[3:])
        return True
