import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.agents.schemas import BrandBrain
from app.carousel.generator import CarouselGenerator
from app.carousel.schemas import MAX_SLIDES
from app.channels.base import ChannelPort
from app.channels.inbound import mask
from app.conversation.events import Event, Notify, PostFailed, PostSent
from app.conversation.photos import InMemoryPhotos, Photo, local_now
from app.copy import messages_es
from app.imagegen.base import ImageGenPort
from app.media.images import add_logo, to_post_image
from app.media.public import PublicImages
from app.rendering.base import RendererPort
from app.rendering.slides import render_slides

from .drafts import PostDrafter, PreviousPost
from .store import APPROVABLE, InMemoryPosts, Post, PostImage

logger = logging.getLogger(__name__)

MIN_SLIDES = 2
WHATSAPP_CAPTION_MAX = 1024


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
    ("cambiale el título"). T19 moves the guards onto `posts` and the generation onto the job
    runner (T16, T17).
    """

    def __init__(
        self,
        drafter: PostDrafter,
        image_gen: ImageGenPort,
        renderer: RendererPort,
        photos: InMemoryPhotos,
        images: PublicImages,
        posts: InMemoryPosts,
        public_base_url: str,
        max_posts_per_day: int,
        brand_of: Callable[[str], Awaitable[BrandBrain | None]] | None = None,
        now: Callable[[], datetime] = local_now,
        notes_of: Callable[[str], Awaitable[list[str]]] | None = None,
        trends_of: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> None:
        self._drafter = drafter
        self._image_gen = image_gen
        self._renderer = renderer
        self._photos = photos
        self._images = images
        self._posts = posts
        self._public_base_url = public_base_url.rstrip("/")
        self._max_posts_per_day = max_posts_per_day
        self._brand_of = brand_of
        self._notes_of = notes_of
        self._trends_of = trends_of
        self._now = now
        self._generating: set[str] = set()
        self._designs_today: dict[str, tuple[date, int]] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._notify: Notify | None = None

    def on_event(self, callback: Notify) -> None:
        """Register who tells the Owner about a post (wired where the chat handler is built)."""
        self._notify = callback

    def create_post(
        self, sender: str, arguments: dict[str, Any], channel: ChannelPort
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
        return self._start(sender, args, photos, channel, remake)

    def revise_post(
        self, sender: str, arguments: dict[str, Any], channel: ChannelPort
    ) -> dict[str, Any]:
        """Remake a sent post with one change, keeping the rest; a caption change keeps the
        images, so it generates nothing."""
        try:
            args = RevisePostArgs.model_validate(arguments)
        except ValidationError as exc:
            return {"error": "invalid_arguments", "detail": str(exc)}
        old = self._posts.get(sender, args.post_id)
        if old is None:
            return {"error": "unknown_post"}
        if old.status not in APPROVABLE:
            return {"error": "post_not_pending", "status": old.status}
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
        return self._start(sender, create, old.source_photos, channel, remake)

    def remake(self, post: Post, channel: ChannelPort) -> dict[str, Any]:
        """Another post from the same request as `post` ([Sí, otro] after [Descartar])."""
        args = CreatePostArgs(
            brief=post.brief,
            asset_ids=[photo.id for photo in post.source_photos],
            style=post.style,
            slide_count=post.slide_count,
            with_logo=post.with_logo,
        )
        return self._start(post.sender, args, post.source_photos, channel)

    def _start(
        self,
        sender: str,
        args: CreatePostArgs,
        photos: list[Photo],
        channel: ChannelPort,
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
        task = asyncio.create_task(
            self._generate(sender, post_id, args, photos, logo, channel, remake)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return {"post_id": post_id, "status": "generating"}

    async def join(self) -> None:
        """Wait for the running generations (tests, shutdown)."""
        await asyncio.gather(*self._tasks)

    async def _generate(
        self,
        sender: str,
        post_id: str,
        args: CreatePostArgs,
        photos: list[Photo],
        logo: bytes | None,
        channel: ChannelPort,
        remake: Remake | None = None,
    ) -> None:
        started = time.monotonic()
        event: Event
        try:
            brand = await self._brand(sender, post_id)
            notes = await self._notes(sender, post_id)
            trends = await self._trends(sender, post_id)
            post = await self._render(args, photos, brand, logo, notes, remake, trends)
            paths = await self._send(sender, post.images, post.text, channel)
            self._keep(sender, post_id, args, photos, paths, post)
            event = PostSent(
                post_id,
                len(post.images),
                args.style,
                tuple(photo.id for photo in photos),
                tuple(post.headlines),
                post.text,
            )
            logger.info(
                "post %s (%s, %d images) sent to %s in %.1fs",
                post_id,
                args.style,
                len(post.images),
                mask(sender),
                time.monotonic() - started,
            )
        except Exception:
            # The task's boundary: nobody awaits it, so log and tell the Owner.
            logger.exception("post %s failed for %s", post_id, mask(sender))
            event = PostFailed(post_id, args.style, tuple(photo.id for photo in photos), args.brief)
        finally:
            self._generating.discard(sender)
        # After the guard is released, and outside the try: a failing notify must not report a
        # failed post that the Owner already has.
        await self._announce(sender, post_id, event, channel)

    async def _brand(self, sender: str, post_id: str) -> BrandBrain | None:
        """The sender's Brand Brain; without it when the database fails, rather than no post."""
        if self._brand_of is None:
            return None
        try:
            return await self._brand_of(sender)
        except SQLAlchemyError:
            logger.warning(
                "post %s for %s goes without the Brand Brain", post_id, mask(sender), exc_info=True
            )
            return None

    async def _notes(self, sender: str, post_id: str) -> list[str]:
        """The Owner's notes; without them when the database fails, rather than no post."""
        if self._notes_of is None:
            return []
        try:
            return await self._notes_of(sender)
        except SQLAlchemyError:
            logger.warning(
                "post %s for %s goes without the notes", post_id, mask(sender), exc_info=True
            )
            return []

    async def _trends(self, sender: str, post_id: str) -> str | None:
        """The niche's trend notes; without them when the database fails, rather than no post."""
        if self._trends_of is None:
            return None
        try:
            return await self._trends_of(sender)
        except SQLAlchemyError:
            logger.warning(
                "post %s for %s goes without the trend notes", post_id, mask(sender), exc_info=True
            )
            return None

    async def _announce(
        self, sender: str, post_id: str, event: Event, channel: ChannelPort
    ) -> None:
        if self._notify is None:
            raise RuntimeError("PostMaker.on_event was never called: nobody can tell the Owner")
        try:
            await self._notify(sender, event, channel)
        except Exception:
            logger.exception("event for post %s failed for %s", post_id, mask(sender))

    async def _render(
        self,
        args: CreatePostArgs,
        photos: list[Photo],
        brand: BrandBrain | None,
        logo: bytes | None,
        notes: list[str] | None = None,
        remake: Remake | None = None,
        trend_notes: str | None = None,
    ) -> RenderedPost:
        """The post's images in order (one per photo, unless a design asks for a slide count).

        Photos as they are get the logo stamped in a corner (ADR 0027); a design's slides are
        rendered from templates over text-free scenes, logo included (ADR 0029).
        """
        references = [photo.data for photo in photos]
        previous = remake.previous if remake else None
        if remake is not None and remake.images is not None:
            copy = await self._drafter.recaption(references, remake.previous, brand, notes)
            return RenderedPost(
                remake.images,
                post_text(copy.caption, copy.hashtags),
                headlines=remake.previous.headlines,
                style_prompt=remake.previous.style_prompt,
            )
        if args.style == "photos":
            copy = await self._drafter.copy(
                args.brief, references, brand, notes, previous, trend_notes
            )
            images = [await asyncio.to_thread(to_post_image, data) for data in references]
            return RenderedPost(
                await with_logo(images, logo), post_text(copy.caption, copy.hashtags), headlines=[]
            )

        count = args.slide_count or len(photos)
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
        scenes = await CarouselGenerator(self._image_gen).generate(
            copy,
            brief,
            references,
            slide_references={n: [data] for n, data in enumerate(references, start=1)}
            if one_per_photo
            else None,
        )
        return RenderedPost(
            await render_slides(self._renderer, copy, brief, scenes, brand, logo),
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
        old = self._posts.get(sender, args.replaces)
        if old is None or old.status not in APPROVABLE:
            logger.info(
                "post %s replaces %s, which is not pending: ignored", post_id, args.replaces
            )
            return
        old.status = "replaced"

    async def _send(
        self, sender: str, images: list[bytes], caption: str, channel: ChannelPort
    ) -> list[str]:
        """Numbered images with the post text on the first, so nothing arrives out of order.

        Returns the public path of each image, in order.
        """
        count = len(images)
        numbers = [
            messages_es.carousel_slide(n, count) if count > 1 else "" for n in range(1, count + 1)
        ]
        first = f"{numbers[0]}\n\n{caption}".strip()
        text_fits = len(first) <= WHATSAPP_CAPTION_MAX
        captions = [first if text_fits else numbers[0], *numbers[1:]]
        paths: list[str] = []
        for image, image_caption in zip(images, captions, strict=True):
            paths.append(self._images.add(image))
            await channel.send_image(
                sender, self._public_base_url + paths[-1], caption=image_caption or None
            )
        if not text_fits:
            logger.warning("post text is %d chars, over the image caption limit", len(caption))
            await channel.send_text(sender, caption)
        return paths


def previous_post(post: Post, change: str | None) -> PreviousPost:
    return PreviousPost(post.brief, post.caption, post.headlines, post.style_prompt, change)


async def with_logo(images: list[bytes], logo: bytes | None) -> list[bytes]:
    if logo is None:
        return images
    return [await asyncio.to_thread(add_logo, image, logo) for image in images]


def post_text(caption: str, hashtags: list[str]) -> str:
    return f"{caption}\n\n{' '.join(hashtags)}" if hashtags else caption
