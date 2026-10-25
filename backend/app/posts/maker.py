import asyncio
import logging
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agents.schemas import BrandBrain
from app.background import BackgroundWork
from app.carousel.generator import CarouselGenerator
from app.carousel.schemas import MAX_SLIDES
from app.channels.base import ChannelPort
from app.channels.inbound import mask
from app.conversation.events import Event, Notify, PostFailed, PostFailure, PostSent
from app.conversation.photos import InMemoryPhotos, Photo, local_now
from app.copy import messages_es
from app.imagegen.base import ImageGenError, ImageGenPort
from app.knowledge.base import BusinessKnowledge, Knowledge
from app.media.images import add_logo, to_post_image
from app.media.public import PublicImages
from app.rendering.base import RendererError, RendererPort
from app.rendering.slides import render_slides

from .drafts import PostDrafter, PreviousPost
from .lifecycle import PostLifecycle
from .store import Post, PostImage

logger = logging.getLogger(__name__)

MIN_SLIDES = 2
WHATSAPP_CAPTION_MAX = 1024
# Everything before sending (knowledge, copy, scenes, render, waiting for an image slot) must fit
# in this; past it the Post fails and the Owner can ask again (BUG-13)
POST_DEADLINE_S = 240.0


class CreatePostArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief: str = Field(min_length=1)
    asset_ids: list[str] = Field(default_factory=list, max_length=MAX_SLIDES)
    style: Literal["photos", "design"]
    slide_count: int | None = Field(default=None, ge=MIN_SLIDES, le=MAX_SLIDES)
    with_logo: bool = False
    replaces: str | None = None


class RevisePostArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_id: str = Field(min_length=1)
    change: str = Field(min_length=1)
    part: Literal["caption", "images"]


@dataclass(frozen=True, slots=True)
class RenderedPost:
    images: list[bytes]
    text: str  # caption + hashtags, as the Owner receives it
    headlines: list[str]  # one per slide of a design; empty for photos as they are
    style_prompt: str | None = None  # a design's shared look, kept by its revisions


@dataclass(frozen=True, slots=True)
class Remake:
    """What a remake keeps from the post it replaces."""

    previous: PreviousPost
    images: list[bytes] | None = None  # set when only the caption changes


class PostMaker:
    """`create_post` before the database: guards per sender, then a background generation.

    The result is an event (`PostSent` / `PostFailed`) for the orchestrator, which writes the
    message and keeps the note in the history, so the model knows what was sent
    ("cambiale el título"). The generation runs on `BackgroundWork`, and the guards stay in memory
    like the Posts they protect: both move to the database together (T19).
    """

    def __init__(
        self,
        drafter: PostDrafter,
        image_gen: ImageGenPort,
        renderer: RendererPort,
        photos: InMemoryPhotos,
        images: PublicImages,
        posts: PostLifecycle,
        public_base_url: str,
        max_posts_per_day: int,
        knowledge: Knowledge | None = None,
        now: Callable[[], datetime] = local_now,
        *,
        background: BackgroundWork,
        deadline_s: float = POST_DEADLINE_S,
    ) -> None:
        self._drafter = drafter
        self._image_gen = image_gen
        self._renderer = renderer
        self._photos = photos
        self._images = images
        self._posts = posts
        self._public_base_url = public_base_url.rstrip("/")
        self._max_posts_per_day = max_posts_per_day
        self._knowledge = knowledge
        self._now = now
        self._generating: set[str] = set()
        self._designs_today: dict[str, tuple[date, int]] = {}
        self._background = background
        self._deadline_s = deadline_s

    def create_post(
        self, sender: str, arguments: dict[str, Any], channel: ChannelPort, notify: Notify
    ) -> dict[str, Any]:
        """Check the guards and start the generation; the result goes back to the model."""
        try:
            args = CreatePostArgs.model_validate(arguments)
        except ValidationError as exc:
            return {"error": "invalid_arguments", "detail": str(exc)}
        photos, unknown = self._photos.find(sender, args.asset_ids)
        if unknown:
            return {"error": "unknown_asset", "asset_ids": unknown}
        if not photos:
            return {"error": "no_photos"}
        old = self._posts.get(sender, args.replaces) if args.replaces else None
        remake = Remake(previous_post(old, change=None)) if old else None
        return self._start(sender, args, photos, channel, notify, remake)

    def revise_post(
        self, sender: str, arguments: dict[str, Any], channel: ChannelPort, notify: Notify
    ) -> dict[str, Any]:
        """Remake a sent post with one change, keeping the rest; a caption change keeps the
        images, so it generates nothing."""
        try:
            args = RevisePostArgs.model_validate(arguments)
        except ValidationError as exc:
            return {"error": "invalid_arguments", "detail": str(exc)}
        old = self._posts.approvable_post(sender, args.post_id)
        if isinstance(old, dict):
            return old
        if old.video is not None:
            # A caption-only remake would drop the clip; another take is a new `create_video`.
            return {"error": "video_post"}
        if args.part == "images" and old.style == "photos":
            return {"error": "photos_as_they_are"}
        create = CreatePostArgs(
            brief=f"{old.brief}\nCambio: {args.change}",
            asset_ids=[photo.id for photo in old.source_photos],
            style=old.style,
            slide_count=old.slide_count,
            with_logo=old.with_logo,
            replaces=old.id,
        )
        kept = [image.data for image in old.images] if args.part == "caption" else None
        remake = Remake(previous_post(old, change=args.change), kept)
        return self._start(sender, create, old.source_photos, channel, notify, remake)

    def remake(self, post: Post, channel: ChannelPort, notify: Notify) -> dict[str, Any]:
        """Another post from the same request as `post` ([Sí, otro] after [Descartar])."""
        args = CreatePostArgs(
            brief=post.brief,
            asset_ids=[photo.id for photo in post.source_photos],
            style=post.style,
            slide_count=post.slide_count,
            with_logo=post.with_logo,
        )
        return self._start(post.sender, args, post.source_photos, channel, notify)

    def _start(
        self,
        sender: str,
        args: CreatePostArgs,
        photos: list[Photo],
        channel: ChannelPort,
        notify: Notify,
        remake: Remake | None = None,
    ) -> dict[str, Any]:
        if sender in self._generating:
            return {"error": "generation_in_progress"}
        keeps_images = remake is not None and remake.images is not None
        # Kept images already carry the logo.
        logo = self._photos.logo(sender) if args.with_logo and not keeps_images else None
        if args.with_logo and not keeps_images and logo is None:
            return {"error": "no_logo"}
        # Only a design generates images, which is what the daily limit caps.
        generates = args.style == "design" and not keeps_images
        today = self._now().date()
        day, started = self._designs_today.get(sender, (today, 0))
        designs_today = started if day == today else 0
        if generates and designs_today >= self._max_posts_per_day:
            return {"error": "daily_limit"}

        self._generating.add(sender)
        if generates:
            self._designs_today[sender] = (today, designs_today + 1)
        for photo in photos:
            photo.used = True
        post_id = uuid.uuid4().hex[:8]
        counted_on = today if generates else None
        self._background.start(
            self._generate(
                sender, post_id, args, photos, logo, channel, notify, remake, counted_on
            ),
            f"post {post_id} for {mask(sender)}",
        )
        return {"post_id": post_id, "status": "generating"}

    async def _generate(
        self,
        sender: str,
        post_id: str,
        args: CreatePostArgs,
        photos: list[Photo],
        logo: bytes | None,
        channel: ChannelPort,
        notify: Notify,
        remake: Remake | None = None,
        counted_on: date | None = None,
    ) -> None:
        """`counted_on`: the day this Post took one of the sender's daily designs, if it did."""
        started = time.monotonic()
        steps: dict[str, float] = {}
        delivered: list[str] = []
        event: Event
        try:
            deadline = asyncio.timeout(self._deadline_s)
            try:
                async with deadline:
                    with timed(steps, "knowledge"):
                        known = await self._known(sender)
                    post = await self._render(
                        args,
                        photos,
                        known.brand,
                        logo,
                        [note.text for note in known.notes],
                        remake,
                        known.trend_notes,
                        steps,
                    )
            except TimeoutError as exc:
                if deadline.expired():
                    raise PostDeadline(f"over {self._deadline_s:.0f}s") from exc
                raise
            # Sending is never cut off halfway: once the images are ready, they all go out.
            with timed(steps, "send"):
                await self._send(sender, post.images, post.text, channel, delivered)
            self._keep(sender, post_id, args, photos, delivered, post)
            event = PostSent(
                post_id,
                len(post.images),
                args.style,
                tuple(photo.id for photo in photos),
                tuple(post.headlines),
                post.text,
            )
            logger.info(
                "post %s (%s, %d images) sent to %s in %.1fs (%s)",
                post_id,
                args.style,
                len(post.images),
                mask(sender),
                time.monotonic() - started,
                step_times(steps),
            )
        except Exception as exc:
            # The task's boundary: nobody awaits it, so log and tell the Owner.
            reason = failure_reason(exc)
            log = logger.warning if isinstance(exc, PostDeadline) else logger.exception
            log(
                "post %s failed for %s after %.1fs: %s (%s)",
                post_id,
                mask(sender),
                time.monotonic() - started,
                reason,
                step_times(steps),
            )
            if counted_on is not None and not delivered:
                self._give_back_design(sender, counted_on)
            event = PostFailed(
                post_id, args.style, tuple(photo.id for photo in photos), args.brief, reason
            )
        finally:
            self._generating.discard(sender)
        # After the guard is released, and outside the try: a failing notify must not report a
        # failed post that the Owner already has.
        await notify(sender, event, channel)

    def _give_back_design(self, sender: str, day: date) -> None:
        """A design that never reached the Owner doesn't use up one of their daily designs."""
        counted_day, count = self._designs_today.get(sender, (day, 0))
        if counted_day == day and count > 0:
            self._designs_today[sender] = (day, count - 1)

    async def _known(self, sender: str) -> BusinessKnowledge:
        """What the Agency knows about the sender's Business; a post makes do with nothing."""
        if self._knowledge is None:
            return BusinessKnowledge()
        return await self._knowledge.of(sender)

    async def _render(
        self,
        args: CreatePostArgs,
        photos: list[Photo],
        brand: BrandBrain | None,
        logo: bytes | None,
        notes: list[str] | None = None,
        remake: Remake | None = None,
        trend_notes: str | None = None,
        steps: dict[str, float] | None = None,
    ) -> RenderedPost:
        """The post's images in order (one per photo, unless a design asks for a slide count).

        Photos as they are get the logo stamped in a corner (ADR 0027); a design's slides are
        rendered from templates over text-free scenes, logo included (ADR 0029).
        """
        steps = {} if steps is None else steps
        references = [photo.data for photo in photos]
        previous = remake.previous if remake else None
        if remake is not None and remake.images is not None:
            with timed(steps, "copy"):
                copy = await self._drafter.recaption(references, remake.previous, brand, notes)
            return RenderedPost(
                remake.images,
                post_text(copy.caption, copy.hashtags),
                headlines=remake.previous.headlines,
                style_prompt=remake.previous.style_prompt,
            )
        if args.style == "photos":
            with timed(steps, "copy"):
                copy = await self._drafter.copy(
                    args.brief, references, brand, notes, previous, trend_notes
                )
            images = [await asyncio.to_thread(to_post_image, data) for data in references]
            return RenderedPost(
                await with_logo(images, logo), post_text(copy.caption, copy.hashtags), headlines=[]
            )

        count = args.slide_count or len(photos)
        with timed(steps, "copy"):
            copy, brief = await self._drafter.design(
                args.brief,
                references,
                [photo.id for photo in photos],
                count,
                brand,
                notes,
                previous,
                trend_notes,
            )
        style_prompt = brief.style_prompt
        one_per_photo = len(photos) == count
        with timed(steps, "scenes"):
            scenes = await CarouselGenerator(self._image_gen).generate(
                copy,
                brief,
                references,
                slide_references={n: [data] for n, data in enumerate(references, start=1)}
                if one_per_photo
                else None,
            )
        with timed(steps, "render"):
            images = await render_slides(self._renderer, copy, brief, scenes, brand, logo)
        return RenderedPost(
            images,
            post_text(copy.caption, copy.hashtags),
            headlines=[slide.headline for slide in copy.slides],
            style_prompt=style_prompt,
        )

    def _keep(
        self,
        sender: str,
        post_id: str,
        args: CreatePostArgs,
        photos: list[Photo],
        paths: list[str],
        post: RenderedPost,
    ) -> None:
        """Store the sent post for approval, and retire the one it remakes."""
        images = [PostImage(path, data) for path, data in zip(paths, post.images, strict=True)]
        self._posts.add(
            Post(
                post_id,
                sender,
                images,
                post.text,
                brief=args.brief,
                style=args.style,
                slide_count=args.slide_count,
                with_logo=args.with_logo,
                source_photos=photos,
                headlines=post.headlines,
                style_prompt=post.style_prompt,
            )
        )
        if args.replaces is None:
            return
        if not self._posts.retire(sender, args.replaces):
            logger.info(
                "post %s replaces %s, which is not pending: ignored", post_id, args.replaces
            )

    async def _send(
        self,
        sender: str,
        images: list[bytes],
        caption: str,
        channel: ChannelPort,
        delivered: list[str],
    ) -> None:
        """Numbered images with the post text on the first, so nothing arrives out of order.

        Appends the public path of each image to `delivered` once WhatsApp took it, so a send
        that fails halfway still shows what reached the Owner.
        """
        count = len(images)
        numbers = [
            messages_es.carousel_slide(n, count) if count > 1 else "" for n in range(1, count + 1)
        ]
        first = f"{numbers[0]}\n\n{caption}".strip()
        text_fits = len(first) <= WHATSAPP_CAPTION_MAX
        captions = [first if text_fits else numbers[0], *numbers[1:]]
        for image, image_caption in zip(images, captions, strict=True):
            path = self._images.add(image)
            await channel.send_image(
                sender, self._public_base_url + path, caption=image_caption or None
            )
            delivered.append(path)
        if not text_fits:
            logger.warning("post text is %d chars, over the image caption limit", len(caption))
            await channel.send_text(sender, caption)


class PostDeadline(Exception):
    """The Post didn't get its images ready within `POST_DEADLINE_S`."""


def failure_reason(exc: Exception) -> PostFailure:
    match exc:
        case PostDeadline():
            return "deadline"
        case ImageGenError():
            return "image_service"
        case RendererError():
            return "renderer"
        case _:
            return "failed"


@contextmanager
def timed(steps: dict[str, float], step: str) -> Iterator[None]:
    """Adds the step's seconds to `steps`, also when it fails or is cancelled."""
    started = time.monotonic()
    try:
        yield
    finally:
        steps[step] = steps.get(step, 0.0) + time.monotonic() - started


def step_times(steps: dict[str, float]) -> str:
    return ", ".join(f"{step} {seconds:.1f}s" for step, seconds in steps.items()) or "no steps"


def previous_post(post: Post, change: str | None) -> PreviousPost:
    return PreviousPost(post.brief, post.caption, post.headlines, post.style_prompt, change)


async def with_logo(images: list[bytes], logo: bytes | None) -> list[bytes]:
    if logo is None:
        return images
    return [await asyncio.to_thread(add_logo, image, logo) for image in images]


def post_text(caption: str, hashtags: list[str]) -> str:
    return f"{caption}\n\n{' '.join(hashtags)}" if hashtags else caption
