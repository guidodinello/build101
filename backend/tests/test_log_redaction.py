import logging

import httpx
import pytest

from app.log_redaction import RedactQueryTokens, redact_url

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
