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
from app.channels.base import ChannelError, ChannelPort
from app.channels.inbound import mask
from app.conversation.history import InMemoryHistory
from app.conversation.photos import InMemoryPhotos, Photo, local_now
from app.copy import messages_es
from app.imagegen.base import ImageGenPort
from app.llm.client import user_step
from app.media.images import to_post_image
from app.media.public import PublicImages

from .drafts import PostDrafter
from .store import InMemoryPosts, Post, PostImage

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

    The result goes into the sender's history as a note, so the model knows what was sent
    ("cambiale el título"). T19 moves the guards onto `posts` and the generation onto the job
    runner (T16, T17).
    """

    def __init__(
        self,
        drafter: PostDrafter,
        image_gen: ImageGenPort,
        photos: InMemoryPhotos,
        history: InMemoryHistory,
        images: PublicImages,
        posts: InMemoryPosts,
        public_base_url: str,
        max_posts_per_day: int,
        now: Callable[[], datetime] = local_now,
    ) -> None:
        self._drafter = drafter
        self._image_gen = image_gen
        self._photos = photos
        self._history = history
        self._images = images
        self._posts = posts
        self._public_base_url = public_base_url.rstrip("/")
        self._max_posts_per_day = max_posts_per_day
        self._now = now
        self._generating: set[str] = set()
        self._designs_today: dict[str, tuple[date, int]] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def create_post(
        self, sender: str, arguments: dict[str, Any], channel: ChannelPort
    ) -> dict[str, Any]:
        """Check the guards and start the generation; the result goes back to the model."""
        try:
            args = CreatePostArgs.model_validate(arguments)
        except ValidationError as exc:
            return {"error": "invalid_arguments", "detail": str(exc)}
        if sender in self._generating:
            return {"error": "generation_in_progress"}
        # Only a design generates images, which is what the daily limit caps.
        today = self._now().date()
        day, started = self._designs_today.get(sender, (today, 0))
        designs_today = started if day == today else 0
        if args.style == "design" and designs_today >= self._max_posts_per_day:
            return {"error": "daily_limit"}
        photos, unknown = self._photos.find(sender, args.asset_ids)
        if unknown:
            return {"error": "unknown_asset", "asset_ids": unknown}
        if not photos:
            return {"error": "no_photos"}

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
        try:
            post = await self._render(args, photos)
            paths = await self._send(sender, post.images, post.text, channel)
            self._keep(sender, post_id, args, paths, post)
            self._history.extend(sender, [user_step(sent_note(post_id, args, photos, post))])
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
            self._history.extend(sender, [user_step(failed_note(post_id))])
            try:
                await channel.send_text(sender, messages_es.JOB_FAILED)
            except ChannelError:
                logger.warning("could not tell %s that post %s failed", mask(sender), post_id)
        finally:
            self._generating.discard(sender)

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
        self, sender: str, post_id: str, args: CreatePostArgs, paths: list[str], post: RenderedPost
    ) -> None:
        """Store the sent post for approval, and retire the one it remakes."""
        images = [PostImage(path, data) for path, data in zip(paths, post.images, strict=True)]
        self._posts.add(Post(post_id, sender, images, post.text))
        if args.replaces is None:
            return
        old = self._posts.get(sender, args.replaces)
        if old is None or old.status != "pending_approval":
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


def sent_note(post_id: str, args: CreatePostArgs, photos: list[Photo], post: RenderedPost) -> str:
    style = "photos as they are" if args.style == "photos" else "design"
    photo_ids = " ".join(photo.id for photo in photos)
    lines = [
        f"[post {post_id} sent to the Owner] {len(post.images)} image(s), {style}, "
        f"from photos {photo_ids}."
    ]
    if post.headlines:
        headlines = "; ".join(f'{n} "{text}"' for n, text in enumerate(post.headlines, start=1))
        lines.append(f"Slide headlines: {headlines}")
    lines.append(f'Text: "{post.text}"')
    return "\n".join(lines)


def failed_note(post_id: str) -> str:
    return (
        f"[post {post_id} failed] The Owner was told something went wrong and asked whether "
        "to try again."
    )
