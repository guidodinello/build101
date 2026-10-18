import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.carousel.generator import CarouselGenerator
from app.carousel.schemas import MAX_SLIDES
from app.channels.base import ChannelPort
from app.channels.inbound import mask
from app.conversation.events import Event, Notify, PostFailed, PostSent
from app.conversation.photos import InMemoryPhotos, Photo, local_now
from app.copy import messages_es
from app.imagegen.base import ImageGenPort
from app.media.images import to_post_image
from app.media.public import PublicImages

from .drafts import PostDrafter
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
    replaces: str | None = None


@dataclass(frozen=True, slots=True)
class RenderedPost:
    images: list[bytes]
    text: str  # caption + hashtags, as the Owner receives it
    headlines: list[str]  # one per slide of a design; empty for photos as they are


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
        photos: InMemoryPhotos,
        images: PublicImages,
        posts: InMemoryPosts,
        public_base_url: str,
        max_posts_per_day: int,
        now: Callable[[], datetime] = local_now,
    ) -> None:
        self._drafter = drafter
        self._image_gen = image_gen
        self._photos = photos
        self._images = images
        self._posts = posts
        self._public_base_url = public_base_url.rstrip("/")
        self._max_posts_per_day = max_posts_per_day
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
        return self._start(sender, args, photos, channel)

    def remake(self, post: Post, channel: ChannelPort) -> dict[str, Any]:
        """Another post from the same request as `post` ([Sí, otro] after [Descartar])."""
        args = CreatePostArgs(
            brief=post.brief,
            asset_ids=[photo.id for photo in post.source_photos],
            style=post.style,
            slide_count=post.slide_count,
        )
        return self._start(post.sender, args, post.source_photos, channel)

    def _start(
        self, sender: str, args: CreatePostArgs, photos: list[Photo], channel: ChannelPort
    ) -> dict[str, Any]:
        if sender in self._generating:
            return {"error": "generation_in_progress"}
        # Only a design generates images, which is what the daily limit caps.
        today = self._now().date()
        day, started = self._designs_today.get(sender, (today, 0))
        designs_today = started if day == today else 0
        if args.style == "design" and designs_today >= self._max_posts_per_day:
            return {"error": "daily_limit"}

        self._generating.add(sender)
        if args.style == "design":
            self._designs_today[sender] = (today, designs_today + 1)
        for photo in photos:
            photo.used = True
        post_id = uuid.uuid4().hex[:8]
        task = asyncio.create_task(self._generate(sender, post_id, args, photos, channel))
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
        channel: ChannelPort,
    ) -> None:
        started = time.monotonic()
        event: Event
        try:
            post = await self._render(args, photos)
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

    async def _announce(
        self, sender: str, post_id: str, event: Event, channel: ChannelPort
    ) -> None:
        if self._notify is None:
            raise RuntimeError("PostMaker.on_event was never called: nobody can tell the Owner")
        try:
            await self._notify(sender, event, channel)
        except Exception:
            logger.exception("event for post %s failed for %s", post_id, mask(sender))

    async def _render(self, args: CreatePostArgs, photos: list[Photo]) -> RenderedPost:
        """The post's images in order (one per photo, unless a design asks for a slide count)."""
        references = [photo.data for photo in photos]
        if args.style == "photos":
            copy = await self._drafter.copy(args.brief, references)
            images = [await asyncio.to_thread(to_post_image, data) for data in references]
            return RenderedPost(images, post_text(copy.caption, copy.hashtags), headlines=[])

        count = args.slide_count or len(photos)
        copy, brief = await self._drafter.design(
            args.brief, references, [photo.id for photo in photos], count
        )
        one_per_photo = len(photos) == count
        slides = await CarouselGenerator(self._image_gen).generate(
            copy,
            brief,
            references,
            slide_references={n: [data] for n, data in enumerate(references, start=1)}
            if one_per_photo
            else None,
        )
        return RenderedPost(
            [slide.image for slide in slides],
            post_text(copy.caption, copy.hashtags),
            headlines=[slide.headline for slide in copy.slides],
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
                source_photos=photos,
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


def post_text(caption: str, hashtags: list[str]) -> str:
    return f"{caption}\n\n{' '.join(hashtags)}" if hashtags else caption
