"""One orchestrator turn (ADR 0023, ADR 0026): context → model loop → tools → remember → offer.

An Owner turn answers the Owner's words (text, a voice note, photos with captions); an event turn
answers what code reports (`notify`, ADR 0026). They share one pipeline (`_run`) and differ in the
`_Turn` they hand it and in what they do with the answer.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.background import BackgroundWork
from app.channels.base import ChannelError, ChannelPort
from app.channels.inbound import mark_read, mask
from app.copy import messages_es
from app.knowledge.base import Knowledge
from app.llm.client import (
    ChatModel,
    LLMError,
    Step,
    ThinkingLevel,
    function_result_step,
    image_content,
    text_content,
    user_step,
)
from app.posts.lifecycle import PostLifecycle
from app.prompts import escape, load_prompt
from app.storage import StorageError

from .approval import Approval
from .context import render
from .events import (
    Event,
    PhotosReceived,
    PostApproved,
    PostSent,
    Published,
    VideoSent,
    fallback,
    verbatim,
)
from .history import Compactor, History
from .library import BrandLibrary
from .outbound import send
from .photos import InMemoryPhotos, Photo
from .toolbox import Toolbox

logger = logging.getLogger(__name__)

AGENT = "orchestrator"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "orchestrator.md"
VIDEO_PROMPT_PATH = Path(__file__).parent / "prompts" / "video.md"
MAX_STEPS = 5
# WhatsApp hides the typing indicator after about 25 s, and as soon as we send a message.
KEEP_ALIVE_S = 20.0
# The Owner's turns resolve references and decide on paid generations; events are one-liners.
OWNER_THINKING: ThinkingLevel = "medium"
EVENT_THINKING: ThinkingLevel = "low"
LOGGED_REPLY_CHARS = 300
WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


@cache
def system_prompt(assistant_name: str, with_video: bool = False) -> str:
    """The instructions; the video section only with `create_video` registered, so the model
    never reads about a tool it can't call."""
    prompt = load_prompt(SYSTEM_PROMPT_PATH).format(assistant_name=assistant_name)
    return f"{prompt}\n\n{load_prompt(VIDEO_PROMPT_PATH)}" if with_video else prompt


@dataclass(frozen=True, slots=True)
class _Turn:
    """What differs between an Owner turn and an event turn."""

    stored: Step  # what enters the history: the Owner's words or the event's note
    text: str  # what the model reads, with the context block when it looks at photos
    approval: Approval  # what the Owner explicitly approved; empty for an event
    with_photos: bool  # refresh the library, attach the unseen photos, keep the Owner posted
    owner_request: bool  # whether the tools that act on the Owner's words are allowed
    thinking: ThinkingLevel
    message_id: str


class Turns:
    """Runs the orchestrator's turns. The caller of an Owner or event turn holds the sender's
    history lock; `notify` takes it.

    The model sees the Business, its Brand Brain, the Owner's notes and the conversation summary
    in its system prompt (ADR 0030).
    """

    def __init__(
        self,
        model: ChatModel,
        history: History,
        photos: InMemoryPhotos,
        lifecycle: PostLifecycle,
        toolbox: Toolbox,
        knowledge: Knowledge,
        library: BrandLibrary | None,
        compactor: Compactor,
        assistant_name: str,
        now: Callable[[], datetime],
        keep_alive_s: float = KEEP_ALIVE_S,
        *,
        background: BackgroundWork,
    ) -> None:
        self._model = model
        self._history = history
        self._photos = photos
        self._lifecycle = lifecycle
        self._toolbox = toolbox
        self._knowledge = knowledge
        self._library = library
        self._compactor = compactor
        self._system = system_prompt(assistant_name, with_video=toolbox.with_video)
        self._now = now
        self._keep_alive_s = keep_alive_s
        self._background = background

    async def owner_turn(
        self,
        sender: str,
        message_id: str,
        text: str,
        channel: ChannelPort,
        words: str,
        attached: bool,
    ) -> str:
        """The reply to send. `text` is what the model reads; `words`, the Owner's own text,
        decides approval. A failed turn is `REPLY_FAILED` and leaves no trace in the history."""
        approval = self._lifecycle.approval_for(
            sender, words, attached=attached, recent_photos=self._photos.recent(sender)
        )
        turn = _Turn(user_step(text), text, approval, True, True, OWNER_THINKING, message_id)
        past = await self._history.get(sender)
        answer = await self._run(sender, past, turn, channel)
        if answer is None:
            return messages_es.REPLY_FAILED
        reply, steps = answer
        # Only a completed turn enters the history, so a failure leaves no dangling user step.
        await self._remember(sender, past, [turn.stored, *steps], reply, offered=None)
        return reply

    def note_sent(self, sender: str, message_id: str) -> None:
        self._lifecycle.note_sent(sender, message_id)

    async def reaction(
        self, sender: str, emoji: str | None, target_message_id: str | None, channel: ChannelPort
    ) -> None:
        """Apply a yes reaction only to the exact message that most recently asked to publish."""
        approval = self._lifecycle.reaction_approval(
            sender, emoji, target_message_id, self._photos.recent(sender)
        )
        if approval.post_id:
            self._toolbox.approve_reaction(sender, approval.post_id, approval, channel, self.notify)

    async def notify(self, sender: str, event: Event, channel: ChannelPort) -> None:
        """The model's own message about `event` (ADR 0026), under the sender's history lock.

        Runs after any Owner turn in progress, never interleaved with it. Failures are logged:
        nobody awaits the producers that call this. The exception is a verbatim event: whatever
        fails (the history, the send), its caller (a job, the onboarding API) must know the Owner
        may not have it.
        """
        try:
            async with self._history.lock(sender):
                await self.event_turn(sender, event, channel)
        except Exception:
            if verbatim(event):
                raise
            # The task's boundary, like the photo batches.
            logger.exception("%s event failed for %s", type(event).__name__, mask(sender))

    async def event_turn(
        self, sender: str, event: Event, channel: ChannelPort, message_id: str = ""
    ) -> None:
        """Answer `event` with one model turn; the caller holds the sender's lock.

        No Owner words, so the `Approval` is empty (nothing can be published, ADR 0007) and,
        except for photos with no text, the tools that act on the Owner's words are refused.
        Photos with no text are the exception: the Owner may have asked for a post before
        sending them, so they get the photo context and the keep-alive like an Owner turn.
        """
        note = event.note()
        step = user_step(note)
        past = await self._history.get(sender)
        if verbatim(event):
            # Its text is fixed (the Owner reads it as written), so no model turn. The note goes
            # in after the send: a message that never reached the Owner leaves no note.
            text = fallback(event)
            if text is not None:
                await send(channel, sender, text, event)
            await self._history_extend(sender, past, [step])
            return
        if isinstance(event, PostSent | VideoSent):
            post = self._lifecycle.get(sender, event.post_id)
            if post is None or not self._lifecycle.awaiting_approval(post):
                # Already approved or replaced while this waited for the lock: nothing to ask.
                await self._history_extend(sender, past, [step])
                return
        with_photos = isinstance(event, PhotosReceived)
        turn = _Turn(
            step,
            note,
            Approval(),
            with_photos,
            with_photos,
            OWNER_THINKING if with_photos else EVENT_THINKING,
            message_id,
        )
        answer = await self._run(sender, past, turn, channel)
        if answer is None:
            await self._send_fallback(sender, past, event, step, channel)
            return
        text, steps = answer
        if isinstance(event, Published) and event.permalink and event.permalink not in text:
            # The link is data, not copy: it reaches the Owner exactly, whatever the model wrote.
            text = f"{text}\n{event.permalink}"
        await self._remember(sender, past, [step, *steps], text, offered_post(event))
        sent_id = await send(channel, sender, text, event)
        self.note_sent(sender, sent_id)

    async def _run(
        self, sender: str, past: list[Step], turn: _Turn, channel: ChannelPort
    ) -> tuple[str, list[Step]] | None:
        """The model's reply text and the steps of the turn, or None when it couldn't answer.

        Marks the photos it showed the model as seen, only for a completed turn.
        """
        recent: list[Photo] = []
        if turn.with_photos:
            await self._refresh_library(sender)
            recent = self._photos.recent(sender)
        unseen = [photo for photo in recent if not photo.seen]
        current = turn.stored
        keep_alive: asyncio.Task[None] | None = None
        if turn.with_photos:
            current = step_with_photos(
                turn.text,
                recent,
                unseen,
                self._photos.library(sender),
                self._photos.logo(sender),
                now=self._now(),
            )
            keep_alive = self._background.start(
                self._keep_owner_posted(sender, turn.message_id, bool(unseen), channel),
                f"keep-alive for {mask(sender)}",
            )
        try:
            text, steps = await self._converse(sender, past, current, turn, channel)
        except LLMError:
            logger.warning("%s failed for %s", AGENT, mask(sender), exc_info=True)
            return None
        finally:
            if keep_alive:
                keep_alive.cancel()
        if not text:
            logger.warning("%s still calling tools after %d steps", AGENT, MAX_STEPS)
            return None
        for photo in unseen:
            photo.seen = True
        return text, steps

    async def _send_fallback(
        self, sender: str, past: list[Step], event: Event, step: Step, channel: ChannelPort
    ) -> None:
        """The LLM couldn't answer: the fixed text for this event, or nothing."""
        text = fallback(event)
        logger.warning("no %s reply for %s, fallback: %s", AGENT, mask(sender), bool(text))
        if text is None:
            # The note still goes in, so a later "subilo" or a change knows the post id.
            await self._history_extend(sender, past, [step])
            return
        told = user_step(f'{event.note()}\nThe Owner was told: "{text}"')
        await self._history_extend(sender, past, [told])
        self._lifecycle.note_reply(sender, text, offered_post(event))
        sent_id = await send(channel, sender, text, event)
        self.note_sent(sender, sent_id)

    async def _converse(
        self, sender: str, past: list[Step], current: Step, turn: _Turn, channel: ChannelPort
    ) -> tuple[str, list[Step]]:
        """Run the model and tool steps on `current`: the reply text ("" if it kept calling tools
        until MAX_STEPS) and the steps of the turn. Raises LLMError."""
        system = await self._system_for(sender)
        steps: list[Step] = []
        for _ in range(MAX_STEPS):
            reply = await self._model.reply(
                AGENT,
                system,
                [*past, current, *steps],
                thinking_level=turn.thinking,
                tools=self._toolbox.declarations,
            )
            steps.extend(reply.steps)
            if not reply.function_calls:
                return reply.text, steps
            for call in reply.function_calls:
                result = await self._toolbox.run(
                    call, sender, channel, self.notify, turn.approval, turn.owner_request
                )
                steps.append(function_result_step(call, result))
        return "", steps

    async def _system_for(self, sender: str) -> str:
        """The instructions, then what the model knows about this Business (ADR 0030)."""
        known = render(await self._knowledge.of(sender))
        return f"{self._system}\n\n{known}" if known else self._system

    async def _remember(
        self, sender: str, past: list[Step], steps: list[Step], text: str, offered: str | None
    ) -> None:
        """A completed turn: its steps into the history, its reply into the post lifecycle."""
        await self._history_extend(sender, past, steps)
        self._lifecycle.note_reply(sender, text, offered)
        log_reply(sender, text)

    async def _history_extend(self, sender: str, past: list[Step], steps: list[Step]) -> None:
        await self._history.extend(sender, steps)
        if self._compactor.needed(past, steps):
            self._background.start(
                self._compact(sender), f"compacting the history of {mask(sender)}"
            )

    async def _compact(self, sender: str) -> None:
        # A failure is logged by the background boundary; the next turn tries again.
        async with self._history.lock(sender):
            await self._compactor.compact(sender)

    async def _refresh_library(self, sender: str) -> None:
        if self._library is None:
            return
        try:
            photos = await self._library.photos(sender)
            logo = await self._library.logo(sender)
        except (SQLAlchemyError, StorageError):
            # Answer with the photos and logo already loaded rather than not at all.
            logger.warning("loading the brand photos failed for %s", mask(sender), exc_info=True)
            return
        self._photos.set_library(sender, photos)
        self._photos.set_logo(sender, logo)

    async def _keep_owner_posted(
        self, sender: str, message_id: str, looking_at_photos: bool, channel: ChannelPort
    ) -> None:
        """A slow turn gets one "ya te digo" message, then the typing indicator again."""
        await asyncio.sleep(self._keep_alive_s)
        holding = messages_es.LOOKING_AT_PHOTOS if looking_at_photos else messages_es.STILL_WORKING
        logger.info("%s is slow for %s, sending a holding message", AGENT, mask(sender))
        try:
            await channel.send_text(sender, holding)
        except ChannelError:
            logger.warning("holding message failed for %s", mask(sender), exc_info=True)
        while True:
            await mark_read(message_id, channel)
            await asyncio.sleep(self._keep_alive_s)


def log_reply(sender: str, text: str) -> None:
    logger.info("%s replied to %s (%d chars)", AGENT, mask(sender), len(text))
    logger.debug("%s reply: %s", AGENT, text[:LOGGED_REPLY_CHARS])


def offered_post(event: Event) -> str | None:
    """The post an event's message may ask to publish."""
    match event:
        case PostSent(post_id=post_id) | VideoSent(post_id=post_id) | PostApproved(post_id=post_id):
            return post_id
        case _:
            return None


def request(photos: list[Photo], text: str) -> str:
    """The Owner's words, tagged with the photos they came with: "[fotos f1 f2] armame algo"."""
    if not photos:
        return text
    label = "foto" if len(photos) == 1 else "fotos"
    return f"[{label} {' '.join(photo.id for photo in photos)}] {text}"


def step_with_photos(
    text: str,
    recent: list[Photo],
    unseen: list[Photo],
    library: list[Photo] | None = None,
    logo: bytes | None = None,
    now: datetime | None = None,
) -> Step:
    """The context (and the photos the model hasn't seen) ride on this turn's user step only,
    so the system prompt and the stored history stay byte-identical across turns."""
    return user_step(
        text,
        text_content(context_block(recent, unseen, library, has_logo=logo is not None, now=now)),
        *(image_content(photo.data, "image/jpeg") for photo in unseen),
    )


def context_block(
    recent: list[Photo],
    attached: list[Photo],
    library: list[Photo] | None = None,
    *,
    has_logo: bool = False,
    now: datetime | None = None,
) -> str:
    lines = [describe_photo(photo) for photo in recent] or ["none"]
    if attached:
        lines.append(f"Attached below, in this order: {', '.join(photo.id for photo in attached)}")
    block = f"<now>{local_time(now)}</now>\n" if now else ""
    block += "<recent_photos>\n" + "\n".join(lines) + "\n</recent_photos>"
    # A photo sent in the chat is also a Brand asset: list it once, as recent.
    listed = {photo.asset_id for photo in recent if photo.asset_id}
    kept = [photo for photo in library or [] if photo.asset_id not in listed]
    if kept:
        described = "\n".join(f"- {photo.id}: {escape(photo.caption or '')}" for photo in kept)
        block += f"\n<brand_photos>\n{described}\n</brand_photos>"
    if has_logo:
        block += "\n<brand_logo>uploaded</brand_logo>"
    return block


def local_time(now: datetime) -> str:
    return f"{WEEKDAYS[now.weekday()]} {now:%d/%m/%Y %H:%M}"


def describe_photo(photo: Photo) -> str:
    line = f"- {photo.id} sent {photo.received_at:%H:%M}"
    if photo.caption:
        line += f', caption "{escape(photo.caption)}"'
    if photo.description:
        line += f": {escape(photo.description)}"
    return line
