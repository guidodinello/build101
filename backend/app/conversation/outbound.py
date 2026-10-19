"""The one way a typed event reaches the Owner on WhatsApp (ADR 0026).

Whoever writes the text (the orchestrator, or `events.fallback` for a verbatim event), the event's
buttons, the WhatsApp body limit and the text/buttons split live here and nowhere else.
"""

import logging

from app.channels.base import Button, ChannelError, ChannelPort
from app.channels.inbound import mask
from app.copy import messages_es
from app.llm.client import user_step

from .events import (
    BrandSummaryReady,
    Event,
    JobFailed,
    PostApproved,
    PostDiscarded,
    PostSent,
    PublishFailed,
    VideoSent,
    fallback,
    verbatim,
)
from .history import History

logger = logging.getLogger(__name__)

WHATSAPP_BODY_MAX = 1024
# What the buttons message says when the text before it already went out alone.
POINTS_UP = "👆"
BRAND_QUESTION = "¿Es así?"


def buttons(event: Event) -> list[Button]:
    """The buttons that go under the message about `event` (T18)."""
    match event:
        case PostSent(post_id=post_id) | VideoSent(post_id=post_id):
            return [
                Button(id=f"post_approve:{post_id}", title=messages_es.BUTTON_APPROVE),
                Button(id=f"post_change:{post_id}", title=messages_es.BUTTON_CHANGE),
                Button(id=f"post_discard:{post_id}", title=messages_es.BUTTON_DISCARD),
            ]
        case PostApproved(post_id=post_id):
            return [Button(id=f"post_publish:{post_id}", title=messages_es.BUTTON_PUBLISH_NOW)]
        case PostDiscarded(post_id=post_id):
            return [
                Button(id=f"post_replace:{post_id}", title=messages_es.BUTTON_ANOTHER),
                Button(id="noop", title=messages_es.BUTTON_NO_THANKS),
            ]
        case PublishFailed(post_id=post_id):
            return [Button(id=f"post_retry:{post_id}", title=messages_es.BUTTON_RETRY)]
        case BrandSummaryReady():
            return [
                Button(id="brand_ok", title=messages_es.BUTTON_BRAND_OK),
                Button(id="brand_fix", title=messages_es.BUTTON_BRAND_FIX),
            ]
        case JobFailed(job_id=job_id):
            return [Button(id=f"retry:{job_id}", title=messages_es.BUTTON_RETRY)]
        case _:
            return []


def header_video_url(event: Event) -> str | None:
    """The video that goes as the header of the buttons message about `event`."""
    return event.video_url if isinstance(event, VideoSent) else None


async def send(channel: ChannelPort, to: str, text: str, event: Event) -> None:
    """`text` with `event`'s buttons under it (and its video as their header), or alone when the
    event has none. A body over the WhatsApp limit goes first as plain text."""
    attached = buttons(event)
    if not attached:
        await channel.send_text(to, text)
        return
    if len(text) > WHATSAPP_BODY_MAX:
        text = await _send_overflow(channel, to, text, event)
    await channel.send_buttons(to, text, attached, header_video_url=header_video_url(event))


async def _send_overflow(channel: ChannelPort, to: str, text: str, event: Event) -> str:
    """Send the part of `text` that doesn't fit a buttons body; return the body that goes with
    the buttons."""
    if isinstance(event, BrandSummaryReady):
        # A summary over the limit even after the Strategist's retry: the text first, then the
        # question under the buttons.
        await channel.send_text(to, text.removesuffix(BRAND_QUESTION).rstrip())
        return BRAND_QUESTION
    await channel.send_text(to, text)
    return POINTS_UP


class FixedReplies:
    """`Notify` without a model: the event's fixed text, for when no chat handler exists
    (`INBOUND_HANDLER=echo`) and for tests.

    Same contract as `ChatHandler.notify`: the note goes in the sender's history under its lock,
    and a failure is logged, except that a verbatim event's `ChannelError` reaches the caller.
    """

    def __init__(self, history: History) -> None:
        self._history = history

    async def __call__(self, sender: str, event: Event, channel: ChannelPort) -> None:
        try:
            async with self._history.lock(sender):
                text = fallback(event)
                if text is not None:
                    await send(channel, sender, text, event)
                # After the send: a message that never reached the Owner leaves no note.
                await self._history.extend(sender, [user_step(event.note())])
        except ChannelError:
            if verbatim(event):
                raise
            logger.exception("%s event failed for %s", type(event).__name__, mask(sender))
        except Exception:
            logger.exception("%s event failed for %s", type(event).__name__, mask(sender))
