import asyncio
import logging
from collections.abc import AsyncIterator

import httpx
import pytest
import uvicorn

from app.log_redaction import (
    RedactAccessLog,
    RedactQueryTokens,
    redact_request_target,
    redact_url,
)

MEDIA_URL = "https://api.kapso.ai/meta/whatsapp/media_download?token=s3cr3t.abc&x=1"


def httpx_record(url: str, status: int = 200) -> logging.LogRecord:
    return logging.LogRecord(
        "httpx",
        logging.INFO,
        __file__,
        1,
        'HTTP Request: %s %s "%s %d %s"',
        ("GET", httpx.URL(url), "HTTP/1.1", status, "OK"),
        None,
    )


def test_redacts_the_media_token_and_keeps_the_rest() -> None:
    record = httpx_record(MEDIA_URL)

    assert RedactQueryTokens().filter(record) is True

    assert record.getMessage() == (
        "HTTP Request: GET "
        "https://api.kapso.ai/meta/whatsapp/media_download?token=REDACTED&x=1"
        ' "HTTP/1.1 200 OK"'
    )


def test_redacts_a_key_param() -> None:
    assert redact_url("https://g.test/v1/models?key=AIza123&alt=sse") == (
        "https://g.test/v1/models?key=REDACTED&alt=sse"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://generativelanguage.googleapis.com/v1beta/models/m:generateContent",
        "https://api.kapso.ai/meta/whatsapp/v24.0/pn-1/messages",
        "https://api.kapso.ai/meta/whatsapp/v24.0/media-1?phone_number_id=pn-1",
    ],
)
def test_other_httpx_lines_are_unchanged(url: str) -> None:
    record = httpx_record(url, status=429)
    before = record.getMessage()

    RedactQueryTokens().filter(record)

    assert record.getMessage() == before


async def test_a_real_httpx_request_logs_no_token(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("httpx")
    redactor = RedactQueryTokens()
    logger.addFilter(redactor)
    try:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200))
        ) as client:
            with caplog.at_level(logging.INFO, logger="httpx"):
                await client.get(MEDIA_URL)
    finally:
        logger.removeFilter(redactor)

    assert "s3cr3t" not in caplog.text
    assert "media_download?token=REDACTED&x=1" in caplog.text
    assert "200 OK" in caplog.text


TOKEN = "Zm9vYmFyYmF6cXV4-SECRET_token123"


def access_record(target: str, status: int = 200) -> logging.LogRecord:
    """The shape uvicorn gives its access logger: client, method, target, HTTP version, status."""
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", "GET", target, "1.1", status),
        None,
    )


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (f"/api/o/{TOKEN}", "/api/o/REDACTED"),
        (f"/api/o/{TOKEN}/assets/1/complete", "/api/o/REDACTED/assets/1/complete"),
        (
            f"/api/o/{TOKEN}/instagram/start?ticket=1.sig",
            "/api/o/REDACTED/instagram/start?ticket=REDACTED",
        ),
        (
            "/oauth/instagram/callback?code=AQD123&state=nonce&error=access_denied",
            "/oauth/instagram/callback?code=REDACTED&state=REDACTED&error=access_denied",
        ),
        ("/health", "/health"),
        ("/webhooks/whatsapp", "/webhooks/whatsapp"),
        ("/media/abc.jpg?w=1", "/media/abc.jpg?w=1"),
    ],
)
def test_request_targets_lose_the_token_code_and_state(target: str, expected: str) -> None:
    assert redact_request_target(target) == expected


def test_the_access_filter_masks_a_formatted_access_line() -> None:
    record = access_record(f"/api/o/{TOKEN}/instagram/connect", status=200)

    assert RedactAccessLog().filter(record) is True

    assert record.getMessage() == (
        '127.0.0.1:5000 - "GET /api/o/REDACTED/instagram/connect HTTP/1.1" 200'
    )


def test_the_access_filter_ignores_records_that_are_not_access_lines() -> None:
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, "plain %s", ("x",), None
    )

    assert RedactAccessLog().filter(record) is True
    assert record.getMessage() == "plain x"


async def test_a_real_uvicorn_server_logs_no_token_code_or_state() -> None:
    """Real requests through uvicorn's own access logger, with its default logging config applied
    (the dictConfig runs when the Config is built): the filter set in main.py survives it."""
    from app.db.session import get_session
    from app.main import app  # importing it installs the filter on `uvicorn.access`

    lines: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(record.getMessage())

    async def no_database() -> AsyncIterator[None]:
        # The callback is refused before it queries anything, so no session is ever used.
        yield None

    uvicorn_loggers = [logging.getLogger(n) for n in ("uvicorn", "uvicorn.error", "uvicorn.access")]
    saved = [(lg, lg.handlers[:], lg.level, lg.propagate) for lg in uvicorn_loggers]
    app.dependency_overrides[get_session] = no_database
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, lifespan="off"))
    logging.getLogger("uvicorn.access").addHandler(Capture())  # after the dictConfig
    serving = asyncio.create_task(server.serve())
    try:
        async with asyncio.timeout(5):
            while not server.started:
                if serving.done():
                    serving.result()  # raises why the server failed to start
                    pytest.fail("the server stopped before it started")
                await asyncio.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
            await client.get(f"/api/o/{TOKEN}/not-a-route")
            await client.get("/oauth/instagram/callback?code=AQD-secret-code&state=secret-state")
            await client.get("/health")
    finally:
        server.should_exit = True
        await serving
        app.dependency_overrides.pop(get_session, None)
        for lg, handlers, level, propagate in saved:  # uvicorn's dictConfig is global state
            lg.handlers[:], lg.level, lg.propagate = handlers, level, propagate

    text = "\n".join(lines)
    assert len(lines) == 3
    for secret in (TOKEN, "AQD-secret-code", "secret-state"):
        assert secret not in text
    assert 'GET /api/o/REDACTED/not-a-route HTTP/1.1" 404' in text
    assert "code=REDACTED&state=REDACTED" in text
    assert 'GET /health HTTP/1.1" 200' in text
