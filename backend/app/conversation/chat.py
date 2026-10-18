import asyncio
import logging
from collections.abc import Coroutine
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from app.channels.base import ChannelError, ChannelPort, InboundMedia, InboundMessage
from app.channels.inbound import mask
from app.copy import messages_es
from app.llm.client import (
    ChatModel,
    FunctionCall,
    LLMError,
    Step,
    function_result_step,
    image_content,
    text_content,
    user_step,
)
from app.media.images import prepare_reference
from app.posts.maker import PostMaker
from app.posts.publish import PostPublisher
from app.posts.store import InMemoryPosts
from app.prompts import load_prompt

from .approval import Approval, decide
from .events import (
    AudioUnclear,
    Event,
    PhotosReceived,
    PhotoTooBig,
    PhotoUnreadable,
    PostSent,
    Published,
    StaleButton,
    UnsupportedMedia,
    fallback,
)
from .history import InMemoryHistory
from .photos import InMemoryPhotos, Photo
from .tools import TOOLS

logger = logging.getLogger(__name__)

AGENT = "orchestrator"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "orchestrator.md"
MAX_STEPS = 5
BYTES_PER_MB = 1024 * 1024
# WhatsApp delivers an album as one message per photo, 1–4 s apart (seen on 2026-10-17).
PHOTO_DEBOUNCE_S = 5.0
# WhatsApp hides the typing indicator after about 25 s, and as soon as we send a message.
KEEP_ALIVE_S = 20.0


@cache
def system_prompt(assistant_name: str) -> str:
    return load_prompt(SYSTEM_PROMPT_PATH).format(assistant_name=assistant_name)


@dataclass(slots=True)
class _PhotoBatch:
    photos: list[Photo] = field(default_factory=list)
    last_message_id: str = ""
    timer: asyncio.Task[None] | None = None


class ChatHandler:
    """InboundHandler that answers text, voice notes and photos with the LLM.

    Orchestrator v0 (T56, T57): only `create_post` and `approve_post` are registered, and no
    onboarding or button routing yet (T23, T18), so buttons and other kinds are answered as
    events (`notify`, ADR 0026). Photos wait `PHOTO_DEBOUNCE_S` after the last one and are
    answered together, with any text that arrives meanwhile.
    """

    def __init__(
        self,
        model: ChatModel,
        history: InMemoryHistory,
        photos: InMemoryPhotos,
        posts: PostMaker,
        publisher: PostPublisher,
        store: InMemoryPosts,
        assistant_name: str,
        max_photo_mb: int,
        photo_debounce_s: float = PHOTO_DEBOUNCE_S,
        keep_alive_s: float = KEEP_ALIVE_S,
    ) -> None:
        self._model = model
        self._history = history
        self._photos = photos
        self._posts = posts
        self._publisher = publisher
        self._store = store
        self._system = system_prompt(assistant_name)
        self._max_photo_mb = max_photo_mb
        self._photo_debounce_s = photo_debounce_s
        self._keep_alive_s = keep_alive_s
        self._batches: dict[str, _PhotoBatch] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        match message.kind:
            case "album":
                return
            case "image" if message.media:
                await self._photo_arrived(message, message.media, channel)
                return
        photos = self._take_batch(message.sender)
        async with self._history.lock(message.sender):
            await mark_read(message.message_id, channel)
            reply = await self._answer(message, photos, channel)
            if reply is not None:
                await channel.send_text(message.sender, reply)

    async def join(self) -> None:
        """Wait for the pending photo batches (tests, shutdown); cancelled timers are fine."""
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _answer(
        self, message: InboundMessage, photos: list[Photo], channel: ChannelPort
    ) -> str | None:
        """The reply to send, or None when an event turn already answered."""
        match message.kind:
            case "text" if message.text:
                return await self._llm_turn(
                    message.sender,
                    message.message_id,
                    request(photos, message.text),
                    channel,
                    words=message.text,
                    attached=bool(photos),
                )
            case "audio" if message.audio and message.audio.provider_transcript:
                # ADR 0021: a voice note is handled as its transcript. The Gemini fallback
                # transcriber (TranscriberPort) isn't built yet, so no transcript = unclear.
                transcript = f"[audio] {message.audio.provider_transcript}"
                return await self._llm_turn(
                    message.sender,
                    message.message_id,
                    request(photos, transcript),
                    channel,
                    words=message.audio.provider_transcript,
                    attached=bool(photos),
                )
            case "audio":
                event: Event = AudioUnclear()
            case "button":
                event = StaleButton()
            case _:
                event = UnsupportedMedia()
        await self._event_turn(message.sender, event, channel)
        return None

    async def _photo_arrived(
        self, message: InboundMessage, media: InboundMedia, channel: ChannelPort
    ) -> None:
        if (media.byte_size or 0) > self._max_photo_mb * BYTES_PER_MB:
            await self._photo_too_big(message.sender, channel)
            return
        try:
            data, _ = await channel.download_media(media.media_id)
            if len(data) > self._max_photo_mb * BYTES_PER_MB:
                await self._photo_too_big(message.sender, channel)
                return
            reference = await asyncio.to_thread(prepare_reference, data)
        except (ChannelError, OSError):  # OSError: Pillow can't decode it
            logger.warning("could not read photo %s", media.media_id, exc_info=True)
            await self.notify(message.sender, PhotoUnreadable(), channel)
            return
        batch = self._batches.setdefault(message.sender, _PhotoBatch())
        batch.photos.append(self._photos.add(message.sender, reference, message.text))
        batch.last_message_id = message.message_id
        if batch.timer:
            batch.timer.cancel()
        batch.timer = self._start(self._answer_photos_later(message.sender, channel))

    async def _photo_too_big(self, sender: str, channel: ChannelPort) -> None:
        await self.notify(sender, PhotoTooBig(self._max_photo_mb), channel)

    def _take_batch(self, sender: str) -> list[Photo]:
        batch = self._batches.pop(sender, None)
        if batch is None:
            return []
        if batch.timer:
            batch.timer.cancel()
        return batch.photos

    async def _answer_photos_later(self, sender: str, channel: ChannelPort) -> None:
        await asyncio.sleep(self._photo_debounce_s)
        # Popped right after the wait: a photo arriving from here on starts a new batch.
        batch = self._batches.pop(sender)
        try:
            async with self._history.lock(sender):
                await mark_read(batch.last_message_id, channel)
                captions = " ".join(photo.caption for photo in batch.photos if photo.caption)
                if captions:
                    reply = await self._llm_turn(
                        sender,
                        batch.last_message_id,
                        request(batch.photos, captions),
                        channel,
                        words=captions,
                        attached=True,
                    )
                    await channel.send_text(sender, reply)
                else:
                    event = PhotosReceived(tuple(photo.id for photo in batch.photos))
                    await self._event_turn(sender, event, channel, batch.last_message_id)
        except Exception:
            # The task's boundary, like the webhook's run_handler: nobody awaits it.
            logger.exception("answering %d photos failed for %s", len(batch.photos), mask(sender))

    async def _llm_turn(
        self,
        sender: str,
        message_id: str,
        text: str,
        channel: ChannelPort,
        words: str,
        attached: bool,
    ) -> str:
        """`text` is what the model reads; `words`, the Owner's own text, decides approval."""
        approval = self._approval(sender, words, attached)
        user = user_step(text)
        recent = self._photos.recent(sender)
        unseen = [photo for photo in recent if not photo.seen]
        with_context = step_with_photos(text, recent, unseen)
        keep_alive = self._start(self._keep_owner_posted(sender, message_id, bool(unseen), channel))
        try:
            text, turn = await self._converse(sender, with_context, approval, True, channel)
        except LLMError:
            logger.warning("%s failed for %s", AGENT, mask(sender), exc_info=True)
            return messages_es.REPLY_FAILED
        finally:
            keep_alive.cancel()
        if not text:
            logger.warning("%s still calling tools after %d steps", AGENT, MAX_STEPS)
            return messages_es.REPLY_FAILED
        for photo in unseen:
            photo.seen = True
        # Only a completed turn enters the history, so a failure leaves no dangling user step.
        self._history.extend(sender, [user, *turn])
        return text

    async def notify(self, sender: str, event: Event, channel: ChannelPort) -> None:
        """The model's own message about `event` (ADR 0026), under the sender's history lock.

        Runs after any Owner turn in progress, never interleaved with it. Failures are logged:
        nobody awaits the producers that call this.
        """
        try:
            async with self._history.lock(sender):
                await self._event_turn(sender, event, channel)
        except Exception:
            # The task's boundary, like the photo batches.
            logger.exception("%s event failed for %s", type(event).__name__, mask(sender))

    async def _event_turn(
        self, sender: str, event: Event, channel: ChannelPort, message_id: str = ""
    ) -> None:
        """Answer `event` with one model turn; the caller holds the sender's lock.

        No Owner words, so the `Approval` is empty (nothing can be published, ADR 0007) and,
        except for photos with no text, `create_post` is refused: a new post isn't their intent.
        Photos with no text are the exception: the Owner may have asked for a post before
        sending them, so they get the photo context and the keep-alive like an Owner turn.
        """
        note = event.note()
        step = user_step(note)
        if isinstance(event, PostSent):
            post = self._store.get(sender, event.post_id)
            if post is None or post.status != "pending_approval":
                # Already approved or replaced while this waited for the lock: nothing to ask.
                self._history.extend(sender, [step])
                return
        with_photos = isinstance(event, PhotosReceived)
        # Only these turns attach the photos, so only they may mark them seen.
        recent = self._photos.recent(sender) if with_photos else []
        unseen = [photo for photo in recent if not photo.seen]
        current = step_with_photos(note, recent, unseen) if with_photos else step
        keep_alive = (
            self._start(self._keep_owner_posted(sender, message_id, bool(unseen), channel))
            if with_photos
            else None
        )
        text, turn = "", []
        try:
            text, turn = await self._converse(sender, current, Approval(), with_photos, channel)
        except LLMError:
            logger.warning("%s failed for %s", AGENT, mask(sender), exc_info=True)
        finally:
            if keep_alive:
                keep_alive.cancel()
        if not text:
            await self._send_fallback(sender, event, step, channel)
            return
        for photo in unseen:
            photo.seen = True
        if isinstance(event, Published) and event.permalink and event.permalink not in text:
            # The link is data, not copy: it reaches the Owner exactly, whatever the model wrote.
            text = f"{text}\n{event.permalink}"
        self._history.extend(sender, [step, *turn])
        await channel.send_text(sender, text)

    async def _send_fallback(
        self, sender: str, event: Event, step: Step, channel: ChannelPort
    ) -> None:
        """The LLM couldn't answer: the fixed text for this event, or nothing."""
        text = fallback(event)
        logger.warning("no %s reply for %s, fallback: %s", AGENT, mask(sender), bool(text))
        if text is None:
            # The note still goes in, so a later "subilo" or a change knows the post id.
            self._history.extend(sender, [step])
            return
        told = user_step(f'{event.note()}\nThe Owner was told: "{text}"')
        self._history.extend(sender, [told])
        await channel.send_text(sender, text)

    async def _converse(
        self,
        sender: str,
        current: Step,
        approval: Approval,
        owner_request: bool,
        channel: ChannelPort,
    ) -> tuple[str, list[Step]]:
        """Run the model and tool steps on `current`: the reply text ("" if it kept calling tools
        until MAX_STEPS) and the steps of the turn. Raises LLMError."""
        turn: list[Step] = []
        for _ in range(MAX_STEPS):
            reply = await self._model.reply(
                AGENT,
                self._system,
                [*self._history.get(sender), current, *turn],
                thinking_level="low",
                tools=TOOLS,
            )
            turn.extend(reply.steps)
            if not reply.function_calls:
                return reply.text, turn
            turn.extend(
                function_result_step(
                    call, self._run_tool(call, sender, channel, approval, owner_request)
                )
                for call in reply.function_calls
            )
        return "", turn

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

    def _approval(self, sender: str, words: str, attached: bool) -> Approval:
        """What this turn's message allows `approve_post` to publish, computed in code (ADR 0007).

        Photos came with it, or are waiting unused: the Owner is asking for a post, not
        approving one.
        """
        approval, listed = decide(
            words,
            self._store.pending(sender),
            self._store.listed(sender),
            has_photos=attached or bool(self._photos.recent(sender)),
        )
        self._store.set_listed(sender, listed)
        return approval

    def _run_tool(
        self,
        call: FunctionCall,
        sender: str,
        channel: ChannelPort,
        approval: Approval,
        owner_request: bool,
    ) -> dict[str, Any]:
        logger.info("tool %s for %s: %s", call.name, mask(sender), call.arguments)
        match call.name:
            case "create_post" if not owner_request:
                # A note turn has no Owner words: a new post isn't their intent.
                result = {"error": "not_owner_request"}
            case "create_post":
                result = self._posts.create_post(sender, call.arguments, channel)
            case "approve_post":
                result = self._publisher.approve(sender, call.arguments, approval, channel)
            case _:
                result = {"error": "unknown_tool"}
        logger.info("tool %s result: %s", call.name, result)
        return result

    def _start(self, coroutine: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task


async def mark_read(message_id: str, channel: ChannelPort) -> None:
    try:
        await channel.mark_read(message_id, typing=True)
    except ChannelError:
        logger.warning("mark_read failed for %s", message_id, exc_info=True)


def request(photos: list[Photo], text: str) -> str:
    """The Owner's words, tagged with the photos they came with: "[fotos f1 f2] armame algo"."""
    if not photos:
        return text
    label = "foto" if len(photos) == 1 else "fotos"
    return f"[{label} {' '.join(photo.id for photo in photos)}] {text}"


def step_with_photos(text: str, recent: list[Photo], unseen: list[Photo]) -> Step:
    """The context (and the photos the model hasn't seen) ride on this turn's user step only,
    so the system prompt and the stored history stay byte-identical across turns."""
    return user_step(
        text,
        text_content(context_block(recent, unseen)),
        *(image_content(photo.data, "image/jpeg") for photo in unseen),
    )


def context_block(recent: list[Photo], attached: list[Photo]) -> str:
    lines = [describe_photo(photo) for photo in recent] or ["none"]
    if attached:
        lines.append(f"Attached below, in this order: {', '.join(photo.id for photo in attached)}")
    return "<recent_photos>\n" + "\n".join(lines) + "\n</recent_photos>"


def describe_photo(photo: Photo) -> str:
    line = f"- {photo.id} sent {photo.received_at:%H:%M}"
    return f'{line}, caption "{photo.caption}"' if photo.caption else line
