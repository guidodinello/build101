import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import cache
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request

from app.config import Settings, get_settings
from app.conversation.factory import build_inbound_handler
from app.media.public import get_public_images, get_public_videos
from app.publishing.factory import get_publisher

from .base import ChannelPort, InboundMessage
from .factory import build_channel
from .inbound import DedupeStore, InboundHandler, InMemoryDedupeStore, mask
from .kapso_webhook import MESSAGE_RECEIVED_EVENT, parse_message, verify_signature

logger = logging.getLogger(__name__)


@cache
def get_channel() -> ChannelPort:
    return build_channel(get_settings())


@cache
def get_dedupe_store() -> DedupeStore:
    return InMemoryDedupeStore()


@cache
def get_inbound_handler() -> InboundHandler:
    return build_inbound_handler(
        get_settings(), get_public_images(), get_publisher(), get_public_videos()
    )


@asynccontextmanager
async def lifespan(app: Any) -> AsyncIterator[None]:
    # Built at boot so a missing GEMINI_API_KEY or PUBLIC_BACKEND_URL stops the app, instead of
    # turning every webhook into a 500. Tests swap the handler through dependency_overrides.
    app.dependency_overrides.get(get_inbound_handler, get_inbound_handler)()
    yield
    # Close the HTTP clients only if a request ever built them.
    for cached, get in ((get_channel, get_channel), (get_publisher, get_publisher)):
        if cached.cache_info().currsize:
            aclose = getattr(get(), "aclose", None)
            if aclose:
                await aclose()


router = APIRouter(lifespan=lifespan)

# Real Kapso message payloads are a few KiB. The cap applies before the signature check, so an
# unauthenticated caller can't make us buffer an arbitrarily large body.
MAX_BODY_BYTES = 256 * 1024


async def read_capped_body(request: Request) -> bytes:
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")
    # The header can be missing (chunked) or wrong, so the cap is enforced while reading too.
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="payload too large")
    return bytes(body)


async def run_handler(
    handler: InboundHandler, message: InboundMessage, channel: ChannelPort
) -> None:
    # Runs after the 200 went out, so nobody else would see a failure: log it with the ids only.
    try:
        await handler.handle(message, channel)
    except Exception:
        logger.exception("inbound handling failed: %s id=%s", message.kind, message.message_id)


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    dedupe: Annotated[DedupeStore, Depends(get_dedupe_store)],
    handler: Annotated[InboundHandler, Depends(get_inbound_handler)],
    channel: Annotated[ChannelPort, Depends(get_channel)],
    x_webhook_event: Annotated[str | None, Header()] = None,
    x_webhook_signature: Annotated[str | None, Header()] = None,
    x_idempotency_key: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    raw_body = await read_capped_body(request)
    if not verify_signature(raw_body, x_webhook_signature, settings.kapso_webhook_secret or ""):
        raise HTTPException(status_code=401, detail="invalid signature")

    # Other events (statuses, ...) are acknowledged and ignored: a 4xx would make Kapso retry.
    if x_webhook_event != MESSAGE_RECEIVED_EVENT:
        return {"status": "ignored"}

    try:
        message = parse_message(json.loads(raw_body), fallback_id=x_idempotency_key)
    except (ValueError, KeyError, TypeError):
        logger.warning("unparseable %s payload", x_webhook_event, exc_info=True)
        return {"status": "ignored"}

    # Dedupe on the WhatsApp message id; the idempotency key stands in when it is missing.
    if not await dedupe.first_seen(message.message_id):
        logger.info("duplicate delivery of %s ignored", message.message_id)
        return {"status": "duplicate"}

    logger.info(
        "queued inbound %s id=%s from=%s", message.kind, message.message_id, mask(message.sender)
    )
    background_tasks.add_task(run_handler, handler, message, channel)
    return {"status": "ok"}
