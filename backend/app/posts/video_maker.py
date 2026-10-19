import logging
import time
import uuid
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.background import BackgroundWork
from app.channels.base import ChannelPort
from app.channels.inbound import mask
from app.conversation.events import Event, Notify, VideoFailed, VideoSent
from app.conversation.photos import Photo, local_now
from app.media.public import PublicVideos
from app.videogen.base import (
    VideoGenBlocked,
    VideoGenNoVideo,
    VideoGenPort,
    VideoGenRejected,
    VideoGenTimeout,
    VideoGenUnavailable,
)

from .lifecycle import PostLifecycle
from .store import Post, PostVideo

logger = logging.getLogger(__name__)

# Lite animates one first frame (ADR 0033), so the first photo of the source Post is the clip.
VIDEO_PROMPT = (
    "Animate this product photo into a short vertical video for an Instagram Reel. Smooth, "
    "subtle camera movement; keep the product exactly as photographed; do not add text, logos, "
    "people or other products."
)


class CreateVideoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_id: str = Field(min_length=1)
    direction: str = ""


class VideoMaker:
    """`create_video`: guards per sender in code, then a background generation (ADR 0033).

    A video is a new Post next to the one it animates, which is left as it is: the Owner may
    approve either or both (ADR 0007). Veo bills per second, so `generate` is called once per
    request and never retried; every failure becomes a `VideoFailed` event for the Owner.
    The flag is enforced where this is built: with `VIDEO_GEN_ENABLED` off there is no maker.
    """

    def __init__(
        self,
        video_gen: VideoGenPort,
        posts: PostLifecycle,
        videos: PublicVideos,
        public_base_url: str,
        max_videos_per_day: int,
        now: Callable[[], datetime] = local_now,
        *,
        background: BackgroundWork,
    ) -> None:
        self._video_gen = video_gen
        self._posts = posts
        self._videos = videos
        self._public_base_url = public_base_url.rstrip("/")
        self._max_videos_per_day = max_videos_per_day
        self._now = now
        self._generating: set[str] = set()
        self._videos_today: dict[str, tuple[date, int]] = {}
        self._background = background
        self._notify: Notify | None = None

    def on_event(self, callback: Notify) -> None:
        """Register who tells the Owner about a video (wired where the chat handler is built)."""
        self._notify = callback

    def create_video(
        self, sender: str, arguments: dict[str, Any], channel: ChannelPort
    ) -> dict[str, Any]:
        """Check the guards and start the generation; the result goes back to the model."""
        self._require_wired()
        try:
            args = CreateVideoArgs.model_validate(arguments)
        except ValidationError as exc:
            return {"error": "invalid_arguments", "detail": str(exc)}
        source = self._posts.approvable_post(sender, args.post_id)
        if isinstance(source, dict):
            return source
        if source.video is not None:
            return {"error": "already_video"}
        return self._start(sender, source.source_photos, source.caption, args.direction, channel)

    def remake(self, post: Post, channel: ChannelPort) -> dict[str, Any]:
        """Another video from the same request as `post` ([Sí, otro] after [Descartar])."""
        self._require_wired()
        return self._start(post.sender, post.source_photos, post.caption, post.brief, channel)

    def _start(
        self, sender: str, photos: list[Photo], caption: str, direction: str, channel: ChannelPort
    ) -> dict[str, Any]:
        if not photos:
            return {"error": "no_photos"}
        if sender in self._generating:
            return {"error": "generation_in_progress"}
        today = self._now().date()
        if self._count_today(sender) >= self._max_videos_per_day:
            return {"error": "video_daily_limit"}
        self._generating.add(sender)
        self._videos_today[sender] = (today, self._count_today(sender) + 1)
        post_id = uuid.uuid4().hex[:8]
        self._background.start(
            self._generate(sender, post_id, photos, caption, direction.strip(), channel),
            f"video {post_id} for {mask(sender)}",
        )
        return {"post_id": post_id, "status": "generating"}

    def _require_wired(self) -> None:
        """Refuse before any guard or spend: a clip nobody can announce is billed for nothing."""
        if self._notify is None:
            raise RuntimeError("VideoMaker.on_event was never called: nobody can tell the Owner")

    def _count_today(self, sender: str) -> int:
        day, count = self._videos_today.get(sender, (self._now().date(), 0))
        return count if day == self._now().date() else 0

    def _refund(self, sender: str) -> None:
        day, count = self._videos_today.get(sender, (self._now().date(), 0))
        self._videos_today[sender] = (day, max(count - 1, 0))

    async def _generate(
        self,
        sender: str,
        post_id: str,
        photos: list[Photo],
        caption: str,
        direction: str,
        channel: ChannelPort,
    ) -> None:
        started = time.monotonic()
        prompt = f"{VIDEO_PROMPT} {direction}".strip()
        event: Event
        try:
            video = await self._video_gen.generate(prompt, [photos[0].data])
            path = self._videos.add(video.data)
            self._posts.add(
                Post(
                    post_id,
                    sender,
                    [],
                    caption,
                    brief=direction,
                    source_photos=photos,
                    video=PostVideo(path, video.data),
                )
            )
            event = VideoSent(
                post_id, self._public_base_url + path, video.duration_seconds, caption
            )
            logger.info(
                "video %s (%ds) ready for %s in %.1fs",
                post_id,
                video.duration_seconds,
                mask(sender),
                time.monotonic() - started,
            )
        except Exception as exc:
            # The task's boundary: nobody awaits it, so log and tell the Owner.
            reason = failure_reason(exc)
            if reason == "blocked":
                self._refund(sender)  # the only error Veo doesn't bill
            logger.exception("video %s failed (%s) for %s", post_id, reason, mask(sender))
            event = VideoFailed(post_id, reason, tuple(photo.id for photo in photos))
        finally:
            self._generating.discard(sender)
        # After the guard is released, and outside the try: a failing notify must not report a
        # failed video that the Owner already has.
        await self._announce(sender, post_id, event, channel)

    async def _announce(
        self, sender: str, post_id: str, event: Event, channel: ChannelPort
    ) -> None:
        if self._notify is None:  # `_require_wired` makes this unreachable
            raise RuntimeError("VideoMaker.on_event was never called")
        await self._notify(sender, event, channel)


def failure_reason(error: Exception) -> str:
    match error:
        case VideoGenBlocked():
            return "blocked"
        case VideoGenTimeout():  # before its parent, VideoGenUnavailable
            return "timeout"
        case VideoGenUnavailable():
            return "unavailable"
        case VideoGenRejected():
            return "rejected"
        case VideoGenNoVideo():
            return "no_video"
        case _:
            return "failed"
