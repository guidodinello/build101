import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.channels.base import ChannelPort
from app.channels.inbound import mask
from app.conversation.approval import Approval
from app.conversation.events import Event, Notify, Published, PublishFailed, PublishPending
from app.media.public import PublicImages
from app.publishing.base import (
    PublisherError,
    PublisherPort,
    PublishInProgress,
    PublishMedia,
    PublishResult,
    PublishRetryable,
)

from .store import APPROVABLE, InMemoryPosts, Post

logger = logging.getLogger(__name__)

# The first attempt, one retry after a timeout/5xx, and one wait for a request still in flight.
MAX_PUBLISH_ATTEMPTS = 3
DEFAULT_RETRY_AFTER_S = 5.0
MAX_RETRY_AFTER_S = 30.0

Sleep = Callable[[float], Awaitable[None]]


class ApprovePostArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_id: str = Field(min_length=1)
    next: Literal["publish_now"]


class PostPublisher:
    """`approve_post` before the database: guards in code, then a background publish.

    The Owner's explicit approval is computed from their message (`approval.decide`), never by
    the model: only the post named by this turn's `Approval` can be published. T30 moves this onto
    the job runner.
    """

    def __init__(
        self,
        publisher: PublisherPort,
        posts: InMemoryPosts,
        images: PublicImages,
        public_base_url: str,
        account_id: str | None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._publisher = publisher
        self._posts = posts
        self._images = images
        self._public_base_url = public_base_url.rstrip("/")
        self._account_id = account_id
        self._sleep = sleep
        self._tasks: set[asyncio.Task[None]] = set()
        self._notify: Notify | None = None

    def on_event(self, callback: Notify) -> None:
        """Register who tells the Owner how a publish ended (wired with the chat handler)."""
        self._notify = callback

    def approve(
        self, sender: str, arguments: dict[str, Any], approval: Approval, channel: ChannelPort
    ) -> dict[str, Any]:
        """Check the guards and start the publish; the result goes back to the model."""
        try:
            args = ApprovePostArgs.model_validate(arguments)
        except ValidationError as exc:
            return {"error": "invalid_arguments", "detail": str(exc)}
        post = self._posts.get(sender, args.post_id)
        if post is None:
            return {"error": "unknown_post"}
        if post.status not in APPROVABLE:
            return {"error": "post_not_pending", "status": post.status}
        if approval.post_id != post.id:
            result: dict[str, Any] = {"error": approval.reason}
            if approval.pending:
                result["pending"] = approval.pending
            return result
        return self._start(post, channel)

    def publish_approved(self, post: Post, channel: ChannelPort) -> dict[str, Any]:
        """[Publicar ahora]: the tap is the Owner's explicit approval (ADR 0007)."""
        if post.status != "approved":
            return {"error": "post_not_approved", "status": post.status}
        return self._start(post, channel)

    def retry(self, post: Post, channel: ChannelPort) -> dict[str, Any]:
        """[Reintentar] after a definite failure, under a new idempotency key."""
        if post.status != "failed":
            return {"error": "post_not_failed", "status": post.status}
        return self._start(post, channel)

    def _start(self, post: Post, channel: ChannelPort) -> dict[str, Any]:
        account_id = self._account_id
        if account_id is None:
            logger.warning("cannot publish post %s: ZERNIO_ACCOUNT_ID is not set", post.id)
            return {"error": "need_ig"}
        post.status = "publishing"  # before the task starts, so a second "subilo" finds it busy
        post.publish_attempts += 1
        task = asyncio.create_task(self._publish(post, account_id, channel))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return {"post_id": post.id, "status": "publishing"}

    async def join(self) -> None:
        """Wait for the running publishes (tests, shutdown)."""
        await asyncio.gather(*self._tasks)

    async def _publish(self, post: Post, account_id: str, channel: ChannelPort) -> None:
        try:
            result = await self._attempt(post, account_id)
        except Exception:
            # The task's boundary: nobody awaits it, so log and tell the Owner.
            logger.exception("publishing post %s failed for %s", post.id, mask(post.sender))
            result = PublishResult(status="failed", error="unexpected error")
        await self._finish(post, result, channel)

    def _media(self, post: Post) -> PublishMedia:
        if post.video is not None:
            return PublishMedia(
                format="reel",
                url=self._public_base_url + post.video.path,
                cover_offset_ms=post.video_cover_offset_ms,
            )
        urls = [self._public_base_url + image.path for image in post.images]
        if post.format == "image":
            return PublishMedia(format="image", url=urls[0])
        return PublishMedia(format="carousel", urls=urls)

    async def _attempt(self, post: Post, account_id: str) -> PublishResult:
        """Publish with the same idempotency key every time, so a retry can't post twice.

        Only a definite failure comes back as `failed`. When the outcome stays unknown (timeouts,
        5xx, a request still in flight) the post may be live, so that is `pending`.
        """
        media = self._media(post)
        uncertain: PublisherError | None = None
        retried = False
        for attempt in range(1, MAX_PUBLISH_ATTEMPTS + 1):
            for image in post.images:  # still served, however many images came after it
                self._images.keep(image.path, image.data)
            try:
                return await self._publisher.publish(
                    account_id, post.caption, media, idempotency_key=post.idempotency_key
                )
            except PublishInProgress as exc:
                uncertain = exc
                wait_s = min(exc.retry_after_s or DEFAULT_RETRY_AFTER_S, MAX_RETRY_AFTER_S)
                logger.info(
                    "post %s in flight (attempt %d), waiting %.0fs", post.id, attempt, wait_s
                )
                await self._sleep(wait_s)
            except PublishRetryable as exc:
                uncertain = exc
                logger.warning("post %s outcome unknown (attempt %d): %s", post.id, attempt, exc)
                if retried:
                    break
                retried = True
            except (PublisherError, ValueError) as exc:
                logger.warning("post %s was not published: %s", post.id, exc)
                return PublishResult(status="failed", error=str(exc))
        return PublishResult(status="pending", error=str(uncertain))

    async def _finish(self, post: Post, result: PublishResult, channel: ChannelPort) -> None:
        event: Event
        match result.status:
            case "published":
                post.status = "published"
                post.permalink = result.permalink
                post.external_post_id = result.external_post_id
                event = Published(post.id, result.permalink)
            case "failed":
                post.status = "failed"
                event = PublishFailed(post.id)
            case _:  # pending (or scheduled): it may be live, so no failure and no re-publish
                post.status = "publish_pending"
                post.external_post_id = result.external_post_id
                event = PublishPending(post.id)
        logger.info("post %s: %s (%s)", post.id, post.status, result.error or "ok")
        if self._notify is None:
            raise RuntimeError("PostPublisher.on_event was never called: nobody can tell the Owner")
        # The chat handler takes the sender's lock, so the Owner reads "lo subo" first and the
        # note lands after the turn that started this publish.
        await self._notify(post.sender, event, channel)
