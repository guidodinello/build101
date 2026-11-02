import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from functools import cache
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request

from app.background import BackgroundWork, get_background_work
from app.config import Settings, get_settings
from app.conversation.events import Notify
from app.conversation.factory import Conversation, build_conversation
from app.copy import messages_es
from app.db.session import get_sessionmaker
from app.media.public import get_public_images, get_public_videos
from app.pilot import PilotGate, PilotList, get_pilot_list
from app.publishing.factory import get_publisher
from app.ratelimit import TURNS_BURST, TURNS_PER_MINUTE, RateLimiter

from .base import ChannelError, ChannelPort
from .factory import build_channel
from .inbound import (
    DbDedupeStore,
    DedupeStore,
    InboundHandler,
    InMemoryDedupeStore,
    RateLimitedHandler,
    mask,
)
from .kapso_webhook import MESSAGE_RECEIVED_EVENT, is_stale, parse_message, verify_signature

logger = logging.getLogger(__name__)


@cache
def get_channel() -> ChannelPort:
    return build_channel(get_settings())


@cache
def get_dedupe_store() -> DedupeStore:
    # With the database the ids survive a deploy (#105); without it a restart forgets them.
    if get_settings().database_url:
        return DbDedupeStore(get_sessionmaker(), get_background_work())
    return InMemoryDedupeStore()


def get_clock() -> float:
    """Seconds since the epoch; a dependency so tests can stand at the fixtures' time."""
    return time.time()


@cache
def get_conversation() -> Conversation:
    settings = get_settings()
    conversation = build_conversation(
        settings, get_public_images(), get_publisher(), get_public_videos()
    )
    # In front of everything the factory builds, the no-database chat handler included: the rate
    # limit (#106) and, before it, the pilot list (#186), so a number off the list never gets the
    # limit's notice either. `notify` is not wrapped: it carries events raised by code, not the
    # Owner's turns.
    limited = RateLimitedHandler(
        conversation.handler,
        RateLimiter(TURNS_BURST, TURNS_PER_MINUTE),
        messages_es.RATE_LIMITED,
        background=get_background_work(),
    )
    gate = PilotGate(limited, get_pilot_list(), messages_es.waitlist(settings.assistant_name))
    return replace(conversation, handler=gate)


def get_inbound_handler() -> InboundHandler:
    return get_conversation().handler


def get_owner_notify() -> Notify:
    """How code outside the chat (jobs, the onboarding API) tells the Owner something."""
    return get_conversation().notify


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Built at boot so a missing GEMINI_API_KEY or PUBLIC_BACKEND_URL stops the app, instead of
    # turning every webhook into a 500. Tests swap the handler through dependency_overrides.
    app.dependency_overrides.get(get_inbound_handler, get_inbound_handler)()
    pilot: PilotList = app.dependency_overrides.get(get_pilot_list, get_pilot_list)()
    await pilot.log_at_boot()
    yield


async def close_clients() -> None:
    """Close the Kapso and Zernio HTTP clients, only if a request ever built them."""
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


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    background: Annotated[BackgroundWork, Depends(get_background_work)],
    settings: Annotated[Settings, Depends(get_settings)],
    dedupe: Annotated[DedupeStore, Depends(get_dedupe_store)],
    handler: Annotated[InboundHandler, Depends(get_inbound_handler)],
    channel: Annotated[ChannelPort, Depends(get_channel)],
    now: Annotated[float, Depends(get_clock)],
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
    except (ChannelError, ValueError, KeyError, TypeError):
        logger.warning("unparseable %s payload", x_webhook_event, exc_info=True)
        return {"status": "ignored"}

    # A validly signed body can be replayed later: anything past the window is acknowledged (a
    # 4xx would make Kapso retry) and dropped.
    if is_stale(message, now):
        logger.warning("stale message %s ignored", message.message_id)
        return {"status": "stale"}

    # Dedupe on the WhatsApp message id; the idempotency key stands in when it is missing.
    if not await dedupe.first_seen(message.message_id):
        logger.info("duplicate delivery of %s ignored", message.message_id)
        return {"status": "duplicate"}

    logger.info(
        "queued inbound %s id=%s from=%s", message.kind, message.message_id, mask(message.sender)
    )
    # Not the request's BackgroundTasks: uvicorn waits for those before the shutdown even starts,
    # while the job poller still claims jobs.
    background.start(
        handler.handle(message, channel),
        f"inbound {message.kind} {message.message_id} from {mask(message.sender)}",
    )
    return {"status": "ok"}
