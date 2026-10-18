import logging
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

REDACTED = "REDACTED"
# Kapso's media download URL embeds a signed `token`; `key` covers an API key in a query string;
# the Instagram Graph API takes the Owner's `access_token` and our `client_secret` in the query.
SENSITIVE_QUERY_PARAMS = frozenset({"token", "key", "access_token", "client_secret"})


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.query:
        return url
    query = [
        (name, REDACTED if name in SENSITIVE_QUERY_PARAMS else value)
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit(parts._replace(query=urlencode(query)))


class RedactQueryTokens(logging.Filter):
    """Redacts secret query params from URLs in log args, keeping method, host, path, status.

    httpx logs `HTTP Request: %s %s "%s %d %s"` with the URL as an arg, so the message text
    only exists once the record is formatted: rewrite the args instead.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_redact_arg(arg) for arg in record.args)
        return True


def _redact_arg(arg: Any) -> Any:
    if isinstance(arg, httpx.URL):
        return redact_url(str(arg))
    if isinstance(arg, str) and arg.startswith(("http://", "https://")):
        return redact_url(arg)
    return arg
