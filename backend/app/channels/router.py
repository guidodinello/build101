import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import cache
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request

from app.config import Settings, get_settings

from .base import ChannelPort
from .factory import build_channel
from .inbound import DedupeStore, EchoHandler, InboundHandler, InMemoryDedupeStore, mask
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
    return EchoHandler()


@asynccontextmanager
async def lifespan(_: Any) -> AsyncIterator[None]:
    yield
    # Close the HTTP clients only if a request ever built the channel.
    if get_channel.cache_info().currsize:
        aclose = getattr(get_channel(), "aclose", None)
        if aclose:
            await aclose()


router = APIRouter(lifespan=lifespan)


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
    raw_body = await request.body()
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
    background_tasks.add_task(handler.handle, message, channel)
    return {"status": "ok"}
