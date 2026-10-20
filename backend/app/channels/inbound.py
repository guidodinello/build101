import asyncio
import logging
from collections import OrderedDict
from typing import Protocol, runtime_checkable

from .base import ChannelError, ChannelPort, InboundMessage

logger = logging.getLogger(__name__)

DEDUPE_MAX_KEYS = 10_000


@runtime_checkable
class DedupeStore(Protocol):
    async def first_seen(self, key: str) -> bool:
        """Atomically record `key`; True if it was not seen before.

        T02 can back this with `INSERT ... ON CONFLICT DO NOTHING` on `messages.external_id`.
        """
        ...


@runtime_checkable
class InboundHandler(Protocol):
    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None: ...


class InMemoryDedupeStore:
    """Remembers the last `max_keys` keys; enough for provider retries, replaced by T02."""

    def __init__(self, max_keys: int = DEDUPE_MAX_KEYS) -> None:
        self._max_keys = max_keys
        self._keys: OrderedDict[str, None] = OrderedDict()
        self._lock = asyncio.Lock()

    async def first_seen(self, key: str) -> bool:
        async with self._lock:
            if key in self._keys:
                return False
            self._keys[key] = None
            if len(self._keys) > self._max_keys:
                self._keys.popitem(last=False)
            return True


async def mark_read(message_id: str, channel: ChannelPort) -> None:
    """Show the Owner their message was read, with the typing indicator; a failure only logs."""
    try:
        await channel.mark_read(message_id, typing=True)
    except ChannelError:
        logger.warning("mark_read failed for %s", message_id, exc_info=True)


class EchoHandler:
    """Placeholder until the conversation router (T23): echoes and describes what arrived."""

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        logger.info(
            "inbound %s id=%s from=%s", message.kind, message.message_id, mask(message.sender)
        )
        await mark_read(message.message_id, channel)
        await channel.send_text(message.sender, describe(message))


def describe(message: InboundMessage) -> str:
    match message.kind:
        case "text":
            return f"Recibí: {message.text}"
        case "button" if message.button:
            return f'Tocaste "{message.button.title}" ({message.button.id})'
        case "image":
            caption = f" ({message.text})" if message.text else ""
            return f"Recibí una foto{caption}"
        case "audio" if message.audio and message.audio.provider_transcript:
            return f'Recibí un audio: "{message.audio.provider_transcript}"'
        case "audio":
            return "Recibí un audio sin transcripción"
        case _:
            return "Recibí un mensaje que todavía no sé leer"


def mask(phone: str) -> str:
    return f"***{phone[-4:]}"
