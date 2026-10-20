import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.background import BackgroundWork
from app.channels.base import ChannelPort
from app.channels.inbound import mask
from app.conversation.approval import Approval
from app.conversation.events import Event, Notify, Published, PublishFailed, PublishPending
from app.media.public import PublicImages, PublicVideos
from app.publishing.base import (
    PublisherError,
    PublisherPort,
    PublishInProgress,
    PublishMedia,
    PublishResult,
    PublishRetryable,
)

from .lifecycle import ApprovedPost, PostLifecycle
from .shared_account import SharedAccountGuard
from .store import Post

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
    the model: only the post named by this turn's `Approval` can be published. The publish runs on
    `BackgroundWork`; scheduling it durably is T30.
    """

    def __init__(
        self,
        publisher: PublisherPort,
        posts: PostLifecycle,
        images: PublicImages,
        public_base_url: str,
        account_id: str | None,
        sleep: Sleep = asyncio.sleep,
        *,
        background: BackgroundWork,
        videos: PublicVideos | None = None,
        shared_account: SharedAccountGuard | None = None,
    ) -> None:
        self._publisher = publisher
        self._posts = posts
        self._images = images
        self._videos = videos or PublicVideos()
        self._public_base_url = public_base_url.rstrip("/")
        self._account_id = account_id
        self._sleep = sleep
        self._background = background
        self._shared_account = shared_account

    def approve(
        self,
        sender: str,
        arguments: dict[str, Any],
        approval: Approval,
        channel: ChannelPort,
        notify: Notify,
    ) -> dict[str, Any]:
        """Check the guards and start the publish; the result goes back to the model."""
        try:
            args = ApprovePostArgs.model_validate(arguments)
        except ValidationError as exc:
            return {"error": "invalid_arguments", "detail": str(exc)}
        approved = self._posts.authorize_text(sender, args.post_id, approval)
        if isinstance(approved, dict):
            return approved
        return self._start(approved, channel, notify)

    def publish_approved(
        self, sender: str, post_id: str, channel: ChannelPort, notify: Notify
    ) -> dict[str, Any]:
        """[Publicar ahora]: the tap is the Owner's explicit approval (ADR 0007)."""
        approved = self._posts.authorize_tap(sender, post_id)
        if approved is None:
            return {"error": "post_not_approved"}
        return self._start(approved, channel, notify)

    def retry(
        self, sender: str, post_id: str, channel: ChannelPort, notify: Notify
    ) -> dict[str, Any]:
        """[Reintentar] after a definite failure, under a new idempotency key."""
        approved = self._posts.authorize_retry(sender, post_id)
        if approved is None:
            return {"error": "post_not_failed"}
        return self._start(approved, channel, notify)

    def _start(
        self, approved: ApprovedPost, channel: ChannelPort, notify: Notify
    ) -> dict[str, Any]:
        account_id = self._account_id
        if account_id is None:
            logger.warning("cannot publish post %s: ZERNIO_ACCOUNT_ID is not set", approved.post.id)
            return {"error": "need_ig"}
        if self._shared_account and not self._shared_account.allows(approved.post.sender):
            logger.warning(
                "cannot publish post %s: %s is not the Owner of the shared account (ADR 0024)",
                approved.post.id,
                mask(approved.post.sender),
            )
            return {"error": "need_ig"}
        post = self._posts.begin_publish(approved)
        self._background.start(
            self._publish(post, account_id, channel, notify),
            f"publish {post.id} for {mask(post.sender)}",
        )
        return {"post_id": post.id, "status": "publishing"}

    async def _publish(
        self, post: Post, account_id: str, channel: ChannelPort, notify: Notify
    ) -> None:
        try:
            result = await self._attempt(post, account_id)
        except Exception:
            # The task's boundary: nobody awaits it, so log and tell the Owner.
            logger.exception("publishing post %s failed for %s", post.id, mask(post.sender))
            result = PublishResult(status="failed", error="unexpected error")
        await self._finish(post, result, channel, notify)

    def _media(self, post: Post) -> PublishMedia:
        if post.video is not None:
            return PublishMedia(
                format="reel",
                url=self._public_base_url + post.video.path,
                cover_offset_ms=post.video_cover_offset_ms,
                ai_generated=True,  # every Post.video is a Veo clip (ADR 0033): Instagram labels it
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
            if post.video is not None:
                self._videos.keep(post.video.path, post.video.data)
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

    async def _finish(
        self, post: Post, result: PublishResult, channel: ChannelPort, notify: Notify
    ) -> None:
        event: Event
        match result.status:
            case "published":
                self._posts.published(post, result.permalink, result.external_post_id)
                event = Published(post.id, result.permalink)
            case "failed":
                self._posts.failed(post)
                event = PublishFailed(post.id)
            case _:  # pending (or scheduled): it may be live, so no failure and no re-publish
                self._posts.publish_pending(post, result.external_post_id)
                event = PublishPending(post.id)
        logger.info("post %s: %s (%s)", post.id, post.status, result.error or "ok")
        # The chat handler takes the sender's lock, so the Owner reads "lo subo" first and the
        # note lands after the turn that started this publish.
        await notify(post.sender, event, channel)
