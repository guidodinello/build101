import asyncio
import logging
from collections.abc import Coroutine
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.channels.base import Button, ChannelError, ChannelPort, InboundMedia, InboundMessage
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
from app.storage import StorageError

from .approval import Approval, decide
from .button_router import ButtonRouter
from .history import InMemoryHistory
from .library import BrandLibrary
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
    onboarding yet (T23). Buttons go to the `ButtonRouter` (T18); while the Owner corrects their
    brand summary, their next message is the correction. Photos wait `PHOTO_DEBOUNCE_S` after the
    last one and are answered together, with any text that arrives meanwhile.
    """

    def __init__(
        self,
        model: ChatModel,
        history: InMemoryHistory,
        photos: InMemoryPhotos,
        posts: PostMaker,
        publisher: PostPublisher,
        store: InMemoryPosts,
        buttons: ButtonRouter,
        library: BrandLibrary | None,
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
        self._buttons = buttons
        self._library = library
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
            if reply:
                await channel.send_text(message.sender, reply)

    async def join(self) -> None:
        """Wait for the pending photo batches (tests, shutdown); cancelled timers are fine."""
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _answer(
        self, message: InboundMessage, photos: list[Photo], channel: ChannelPort
    ) -> str | None:
        words = message.text if message.kind == "text" else None
        if message.kind == "audio" and message.audio:
            words = message.audio.provider_transcript
        if words and await self._took_brand_correction(message.sender, words):
            return messages_es.REVISING
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
                return messages_es.AUDIO_UNCLEAR
            case "button" if message.button:
                return await self._buttons.handle(message.sender, message.button.id, channel)
            case _:
                return messages_es.UNSUPPORTED_MEDIA

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
            await self._reply_now(message.sender, messages_es.PHOTO_UNREADABLE, channel)
            return
        batch = self._batches.setdefault(message.sender, _PhotoBatch())
        batch.photos.append(self._photos.add(message.sender, reference, message.text))
        batch.last_message_id = message.message_id
        if batch.timer:
            batch.timer.cancel()
        batch.timer = self._start(self._answer_photos_later(message.sender, channel))

    async def _photo_too_big(self, sender: str, channel: ChannelPort) -> None:
        await self._reply_now(sender, messages_es.photo_too_big(self._max_photo_mb), channel)

    async def _reply_now(self, sender: str, text: str, channel: ChannelPort) -> None:
        async with self._history.lock(sender):
            await channel.send_text(sender, text)

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
                    await offer_photo_post(sender, batch.photos, channel)
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
        await self._refresh_library(sender)
        recent = self._photos.recent(sender)
        unseen = [photo for photo in recent if not photo.seen]
        # The context (and the photos the model hasn't seen) ride on this turn's user step
        # only, so the system prompt and the stored history stay byte-identical across turns.
        with_context = user_step(
            text,
            text_content(context_block(recent, unseen, self._photos.library(sender))),
            *(image_content(photo.data, "image/jpeg") for photo in unseen),
        )
        turn: list[Step] = []
        keep_alive = self._start(self._keep_owner_posted(sender, message_id, bool(unseen), channel))
        try:
            for _ in range(MAX_STEPS):
                reply = await self._model.reply(
                    AGENT,
                    self._system,
                    [*self._history.get(sender), with_context, *turn],
                    thinking_level="low",
                    tools=TOOLS,
                )
                turn.extend(reply.steps)
                if not reply.function_calls:
                    break
                turn.extend(
                    function_result_step(call, self._run_tool(call, sender, channel, approval))
                    for call in reply.function_calls
                )
        except LLMError:
            logger.warning("%s failed for %s", AGENT, mask(sender), exc_info=True)
            return messages_es.REPLY_FAILED
        finally:
            keep_alive.cancel()
        if not reply.text:
            logger.warning("%s still calling tools after %d steps", AGENT, MAX_STEPS)
            return messages_es.REPLY_FAILED
        for photo in unseen:
            photo.seen = True
        # Only a completed turn enters the history, so a failure leaves no dangling user step.
        self._history.extend(sender, [user, *turn])
        return reply.text

    async def _refresh_library(self, sender: str) -> None:
        if self._library is None:
            return
        try:
            self._photos.set_library(sender, await self._library.photos(sender))
        except (SQLAlchemyError, StorageError):
            # Answer with the photos already loaded rather than not at all.
            logger.warning("loading the wizard photos failed for %s", mask(sender), exc_info=True)

    async def _took_brand_correction(self, sender: str, words: str) -> bool:
        brand = self._buttons.brand
        if brand is None:
            return False
        try:
            return await brand.take_correction(sender, words)
        except SQLAlchemyError:
            # The database is down: answer as a normal turn rather than not at all.
            logger.warning("brand correction check failed for %s", mask(sender), exc_info=True)
            return False

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
        self, call: FunctionCall, sender: str, channel: ChannelPort, approval: Approval
    ) -> dict[str, Any]:
        logger.info("tool %s for %s: %s", call.name, mask(sender), call.arguments)
        match call.name:
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


async def offer_photo_post(sender: str, photos: list[Photo], channel: ChannelPort) -> None:
    """`photo_saved` with [Sí, armalo] [No, guardala], for photos sent without a word."""
    many = len(photos) > 1
    buttons = [
        Button(
            id="photo_post:" + ",".join(photo.id for photo in photos),
            title=messages_es.BUTTON_MAKE_POST,
        ),
        Button(
            id="noop",
            title=messages_es.BUTTON_KEEP_PHOTOS if many else messages_es.BUTTON_KEEP_PHOTO,
        ),
    ]
    text = messages_es.PHOTOS_KEPT if many else messages_es.PHOTO_KEPT
    await channel.send_buttons(sender, text, buttons)


def request(photos: list[Photo], text: str) -> str:
    """The Owner's words, tagged with the photos they came with: "[fotos f1 f2] armame algo"."""
    if not photos:
        return text
    label = "foto" if len(photos) == 1 else "fotos"
    return f"[{label} {' '.join(photo.id for photo in photos)}] {text}"


def context_block(
    recent: list[Photo], attached: list[Photo], library: list[Photo] | None = None
) -> str:
    lines = [describe_photo(photo) for photo in recent] or ["none"]
    if attached:
        lines.append(f"Attached below, in this order: {', '.join(photo.id for photo in attached)}")
    block = "<recent_photos>\n" + "\n".join(lines) + "\n</recent_photos>"
    if library:
        listed = "\n".join(f"- {photo.id}: {photo.caption}" for photo in library)
        block += f"\n<brand_photos>\n{listed}\n</brand_photos>"
    return block


def describe_photo(photo: Photo) -> str:
    line = f"- {photo.id} sent {photo.received_at:%H:%M}"
    return f'{line}, caption "{photo.caption}"' if photo.caption else line
