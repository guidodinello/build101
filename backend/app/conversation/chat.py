import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.channels.base import ChannelError, ChannelPort, InboundMedia, InboundMessage
from app.channels.inbound import mask
from app.copy import messages_es
from app.knowledge.base import Knowledge
from app.knowledge.local import LocalKnowledge
from app.llm.client import (
    ChatModel,
    FunctionCall,
    LLMError,
    Step,
    ThinkingLevel,
    function_result_step,
    image_content,
    text_content,
    user_step,
)
from app.media.images import prepare_reference
from app.posts.lifecycle import PostLifecycle
from app.posts.maker import PostMaker
from app.posts.publish import PostPublisher
from app.posts.store import Post
from app.posts.video_maker import VideoMaker
from app.prompts import load_prompt
from app.storage import StorageError

from .approval import CAPTION_START_CHARS, Approval
from .button_router import ButtonRouter
from .context import render
from .events import (
    AudioUnclear,
    Event,
    PhotosReceived,
    PhotoTooBig,
    PhotoUnreadable,
    PostApproved,
    PostSent,
    Published,
    StaleButton,
    UnsupportedMedia,
    VideoSent,
    fallback,
    verbatim,
)
from .history import Compactor, History
from .library import BrandLibrary
from .notes import InMemoryNotes, OwnerNotes
from .outbound import send
from .photo_keeper import PhotoKeeper
from .photos import InMemoryPhotos, Photo, local_now
from .tools import CREATE_VIDEO, TOOLS

logger = logging.getLogger(__name__)

AGENT = "orchestrator"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "orchestrator.md"
VIDEO_PROMPT_PATH = Path(__file__).parent / "prompts" / "video.md"
MAX_STEPS = 5
BYTES_PER_MB = 1024 * 1024
# WhatsApp delivers an album as one message per photo, 1–4 s apart (seen on 2026-10-17).
PHOTO_DEBOUNCE_S = 5.0
# WhatsApp hides the typing indicator after about 25 s, and as soon as we send a message.
KEEP_ALIVE_S = 20.0
# The Owner's turns resolve references and decide on paid generations; events are one-liners.
OWNER_THINKING: ThinkingLevel = "medium"
EVENT_THINKING: ThinkingLevel = "low"
LOGGED_REPLY_CHARS = 300
WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
# Tools that act on the Owner's words: an event turn has none.
OWNER_TOOLS = frozenset(
    {"create_post", "create_video", "revise_post", "remember", "forget", "update_brand"}
)


@cache
def system_prompt(assistant_name: str, with_video: bool = False) -> str:
    """The instructions; the video section only with `create_video` registered, so the model
    never reads about a tool it can't call."""
    prompt = load_prompt(SYSTEM_PROMPT_PATH).format(assistant_name=assistant_name)
    return f"{prompt}\n\n{load_prompt(VIDEO_PROMPT_PATH)}" if with_video else prompt


@dataclass(slots=True)
class _PhotoBatch:
    photos: list[Photo] = field(default_factory=list)
    last_message_id: str = ""
    timer: asyncio.Task[None] | None = None


class ChatHandler:
    """InboundHandler that answers text, voice notes and photos with the LLM.

    Photos wait `PHOTO_DEBOUNCE_S` after the last one and are answered together, with any text
    that arrives meanwhile. Buttons and other kinds are answered as events (`notify`, ADR 0026).
    The model sees the Business, its Brand Brain, the Owner's notes and the conversation summary
    in its system prompt (ADR 0030).
    """

    def __init__(
        self,
        model: ChatModel,
        history: History,
        photos: InMemoryPhotos,
        posts: PostMaker,
        publisher: PostPublisher,
        lifecycle: PostLifecycle,
        buttons: ButtonRouter,
        library: BrandLibrary | None,
        assistant_name: str,
        max_photo_mb: int,
        photo_debounce_s: float = PHOTO_DEBOUNCE_S,
        keep_alive_s: float = KEEP_ALIVE_S,
        *,
        notes: OwnerNotes | None = None,
        knowledge: Knowledge | None = None,
        videos: VideoMaker | None = None,
        keeper: PhotoKeeper | None = None,
        compactor: Compactor | None = None,
        now: Callable[[], datetime] = local_now,
    ) -> None:
        self._model = model
        self._history = history
        self._photos = photos
        self._posts = posts
        self._publisher = publisher
        self._lifecycle = lifecycle
        self._buttons = buttons
        self._library = library
        self._videos = videos
        self._tools = [*TOOLS, CREATE_VIDEO] if videos else TOOLS
        self._system = system_prompt(assistant_name, with_video=videos is not None)
        self._max_photo_mb = max_photo_mb
        self._photo_debounce_s = photo_debounce_s
        self._keep_alive_s = keep_alive_s
        self._notes = notes or InMemoryNotes()
        self._keeper = keeper
        self._compactor = compactor or Compactor(history, model)
        self._knowledge = knowledge or LocalKnowledge(self._notes, history)
        self._now = now
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
            try:
                reply = await self._answer(message, photos, channel)
            except SQLAlchemyError:
                logger.warning("database failed for %s", mask(message.sender), exc_info=True)
                reply = messages_es.REPLY_FAILED
            if reply is not None:
                await channel.send_text(message.sender, reply)

    async def join(self) -> None:
        """Wait for the pending photo batches and compactions (tests, shutdown)."""
        while self._tasks:
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
            case "button" if message.button:
                tapped = await self._buttons.handle(message.sender, message.button.id, channel)
                if tapped is None:
                    return None
                event = tapped
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
        photo = self._photos.add(message.sender, reference, message.text)
        if self._keeper:
            self._start(keep_photo(self._keeper, message.sender, photo))
        batch = self._batches.setdefault(message.sender, _PhotoBatch())
        batch.photos.append(photo)
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
        approval = self._lifecycle.approval_for(
            sender, words, attached=attached, recent_photos=self._photos.recent(sender)
        )
        user = user_step(text)
        await self._refresh_library(sender)
        recent = self._photos.recent(sender)
        unseen = [photo for photo in recent if not photo.seen]
        with_context = step_with_photos(
            text,
            recent,
            unseen,
            self._photos.library(sender),
            self._photos.logo(sender),
            now=self._now(),
        )
        past = await self._history.get(sender)
        keep_alive = self._start(self._keep_owner_posted(sender, message_id, bool(unseen), channel))
        try:
            text, turn = await self._converse(
                sender, past, with_context, approval, True, channel, OWNER_THINKING
            )
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
        await self._remember_turn(sender, past, [user, *turn])
        self._lifecycle.note_reply(sender, text)
        log_reply(sender, text)
        return text

    async def notify(self, sender: str, event: Event, channel: ChannelPort) -> None:
        """The model's own message about `event` (ADR 0026), under the sender's history lock.

        Runs after any Owner turn in progress, never interleaved with it. Failures are logged:
        nobody awaits the producers that call this. The exception is a verbatim event's
        `ChannelError`: its caller (a job) must know the Owner never got it.
        """
        try:
            async with self._history.lock(sender):
                await self._event_turn(sender, event, channel)
        except ChannelError:
            if verbatim(event):
                raise
            logger.exception("%s event failed for %s", type(event).__name__, mask(sender))
        except Exception:
            # The task's boundary, like the photo batches.
            logger.exception("%s event failed for %s", type(event).__name__, mask(sender))

    async def _event_turn(
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
            await self._remember_turn(sender, past, [step])
            return
        if isinstance(event, PostSent | VideoSent):
            post = self._lifecycle.get(sender, event.post_id)
            if post is None or not self._lifecycle.awaiting_approval(post):
                # Already approved or replaced while this waited for the lock: nothing to ask.
                await self._remember_turn(sender, past, [step])
                return
        with_photos = isinstance(event, PhotosReceived)
        # Only these turns attach the photos, so only they may mark them seen.
        recent = self._photos.recent(sender) if with_photos else []
        unseen = [photo for photo in recent if not photo.seen]
        if with_photos:
            await self._refresh_library(sender)
            current = step_with_photos(
                note,
                recent,
                unseen,
                self._photos.library(sender),
                self._photos.logo(sender),
                now=self._now(),
            )
        else:
            current = step
        keep_alive = (
            self._start(self._keep_owner_posted(sender, message_id, bool(unseen), channel))
            if with_photos
            else None
        )
        text, turn = "", []
        thinking = OWNER_THINKING if with_photos else EVENT_THINKING
        try:
            text, turn = await self._converse(
                sender, past, current, Approval(), with_photos, channel, thinking
            )
        except LLMError:
            logger.warning("%s failed for %s", AGENT, mask(sender), exc_info=True)
        finally:
            if keep_alive:
                keep_alive.cancel()
        if not text:
            await self._send_fallback(sender, past, event, step, channel)
            return
        for photo in unseen:
            photo.seen = True
        if isinstance(event, Published) and event.permalink and event.permalink not in text:
            # The link is data, not copy: it reaches the Owner exactly, whatever the model wrote.
            text = f"{text}\n{event.permalink}"
        await self._remember_turn(sender, past, [step, *turn])
        self._lifecycle.note_reply(sender, text, offered_post(event))
        log_reply(sender, text)
        await send(channel, sender, text, event)

    async def _send_fallback(
        self, sender: str, past: list[Step], event: Event, step: Step, channel: ChannelPort
    ) -> None:
        """The LLM couldn't answer: the fixed text for this event, or nothing."""
        text = fallback(event)
        logger.warning("no %s reply for %s, fallback: %s", AGENT, mask(sender), bool(text))
        if text is None:
            # The note still goes in, so a later "subilo" or a change knows the post id.
            await self._remember_turn(sender, past, [step])
            return
        told = user_step(f'{event.note()}\nThe Owner was told: "{text}"')
        await self._remember_turn(sender, past, [told])
        self._lifecycle.note_reply(sender, text, offered_post(event))
        await send(channel, sender, text, event)

    async def _converse(
        self,
        sender: str,
        past: list[Step],
        current: Step,
        approval: Approval,
        owner_request: bool,
        channel: ChannelPort,
        thinking: ThinkingLevel,
    ) -> tuple[str, list[Step]]:
        """Run the model and tool steps on `current`: the reply text ("" if it kept calling tools
        until MAX_STEPS) and the steps of the turn. Raises LLMError."""
        system = await self._system_for(sender)
        turn: list[Step] = []
        for _ in range(MAX_STEPS):
            reply = await self._model.reply(
                AGENT, system, [*past, current, *turn], thinking_level=thinking, tools=self._tools
            )
            turn.extend(reply.steps)
            if not reply.function_calls:
                return reply.text, turn
            for call in reply.function_calls:
                result = await self._run_tool(call, sender, channel, approval, owner_request)
                turn.append(function_result_step(call, result))
        return "", turn

    async def _system_for(self, sender: str) -> str:
        """The instructions, then what the model knows about this Business (ADR 0030)."""
        known = render(await self._knowledge.of(sender))
        return f"{self._system}\n\n{known}" if known else self._system

    async def _remember_turn(self, sender: str, past: list[Step], steps: list[Step]) -> None:
        await self._history.extend(sender, steps)
        if self._compactor.needed(past, steps):
            self._start(self._compact(sender))

    async def _compact(self, sender: str) -> None:
        try:
            async with self._history.lock(sender):
                await self._compactor.compact(sender)
        except Exception:
            # The task's boundary: the next turn tries again.
            logger.exception("compacting the history failed for %s", mask(sender))

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

    async def _run_tool(
        self,
        call: FunctionCall,
        sender: str,
        channel: ChannelPort,
        approval: Approval,
        owner_request: bool,
    ) -> dict[str, Any]:
        logger.info("tool %s for %s: %s", call.name, mask(sender), call.arguments)
        try:
            result = await self._tool_result(call, sender, channel, approval, owner_request)
        except SQLAlchemyError:
            logger.warning("tool %s failed for %s", call.name, mask(sender), exc_info=True)
            result = {"error": "action_failed"}
        logger.info("tool %s result: %s", call.name, result)
        return result

    async def _tool_result(
        self,
        call: FunctionCall,
        sender: str,
        channel: ChannelPort,
        approval: Approval,
        owner_request: bool,
    ) -> dict[str, Any]:
        arguments = call.arguments
        if call.name in OWNER_TOOLS and not owner_request:
            # A note turn has no Owner words: acting on them isn't their intent.
            return {"error": "not_owner_request"}
        match call.name:
            case "create_post":
                return self._posts.create_post(sender, arguments, channel)
            case "create_video" if self._videos is not None:
                return self._videos.create_video(sender, arguments, channel)
            case "revise_post":
                return self._posts.revise_post(sender, arguments, channel)
            case "approve_post":
                return self._publisher.approve(sender, arguments, approval, channel)
            case "list_posts":
                return {"posts": [describe_post(post) for post in self._lifecycle.all(sender)]}
            case "remember":
                text = str(arguments.get("note", "")).strip()
                if not text:
                    return {"error": "invalid_arguments"}
                note = await self._notes.add(sender, text)
                return {"saved": note.id} if note else {"error": "action_failed"}
            case "forget":
                forgotten = await self._notes.archive(sender, str(arguments.get("note_id", "")))
                return {"forgotten": True} if forgotten else {"error": "unknown_note"}
            case "update_brand":
                return await self._update_brand(sender, str(arguments.get("change", "")).strip())
            case _:
                return {"error": "unknown_tool"}

    async def _update_brand(self, sender: str, change: str) -> dict[str, Any]:
        brand = self._buttons.brand
        if brand is None:
            return {"error": "not_available"}
        if not change:
            return {"error": "invalid_arguments"}
        if not await brand.revise(sender, change):
            return {"error": "brand_not_ready"}
        return {"status": "revising"}

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


async def keep_photo(keeper: PhotoKeeper, sender: str, photo: Photo) -> None:
    try:
        await keeper.keep(sender, photo)
    except Exception:
        # The task's boundary: the photo is still usable without its description.
        logger.exception("keeping photo %s failed for %s", photo.id, mask(sender))


def log_reply(sender: str, text: str) -> None:
    logger.info("%s replied to %s: %s", AGENT, mask(sender), text[:LOGGED_REPLY_CHARS])


def offered_post(event: Event) -> str | None:
    """The post an event's message may ask to publish."""
    match event:
        case PostSent(post_id=post_id) | VideoSent(post_id=post_id) | PostApproved(post_id=post_id):
            return post_id
        case _:
            return None


def describe_post(post: Post) -> dict[str, Any]:
    return {
        "post_id": post.id,
        "status": post.status,
        "format": post.format,
        "style": post.style,
        "sent_at": f"{post.created_at:%d/%m %H:%M}",
        "caption_start": post.caption[:CAPTION_START_CHARS],
        "permalink": post.permalink,
    }


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
        described = "\n".join(f"- {photo.id}: {photo.caption}" for photo in kept)
        block += f"\n<brand_photos>\n{described}\n</brand_photos>"
    if has_logo:
        block += "\n<brand_logo>uploaded</brand_logo>"
    return block


def local_time(now: datetime) -> str:
    return f"{WEEKDAYS[now.weekday()]} {now:%d/%m/%Y %H:%M}"


def describe_photo(photo: Photo) -> str:
    line = f"- {photo.id} sent {photo.received_at:%H:%M}"
    if photo.caption:
        line += f', caption "{photo.caption}"'
    if photo.description:
        line += f": {photo.description}"
    return line
