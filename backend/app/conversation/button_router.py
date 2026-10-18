"""Button replies (api.md § Button IDs): `<action>:<entity_id>`, checked against the entity's state.

Each tap does its work in code and returns the event the orchestrator answers (ADR 0026), with
the next buttons attached by `events.buttons`. An unknown action, or one the entity's state
doesn't allow, is a `StaleButton`. Posts still live in memory (T56, T57) and the Brand Brain in
the database; T19 moves the posts.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.base import ChannelPort
from app.channels.inbound import mask
from app.jobs.queue import retry_failed
from app.posts.maker import PostMaker
from app.posts.publish import PostPublisher
from app.posts.store import APPROVABLE, InMemoryPosts, Post

from .brand import BrandFlow
from .events import (
    ActionFailed,
    BrandConfirmed,
    BrandFixAsked,
    Event,
    JobRetried,
    PostApproved,
    PostChangeAsked,
    PostDiscarded,
    PostNotStarted,
    PostStarted,
    PublishStarted,
    StaleButton,
)

logger = logging.getLogger(__name__)

# The event to answer, or None for a tap that needs no answer (`noop`).
Handler = Callable[[str, str, ChannelPort], Awaitable[Event | None]]


class ButtonRouter:
    def __init__(
        self,
        posts: InMemoryPosts,
        maker: PostMaker,
        publisher: PostPublisher,
        sessions: async_sessionmaker[AsyncSession] | None,
    ) -> None:
        self._posts = posts
        self._maker = maker
        self._publisher = publisher
        self._sessions = sessions
        self._brand = BrandFlow(sessions) if sessions else None
        self._handlers: dict[str, Handler] = {
            "noop": self._noop,
            "brand_ok": self._brand_ok,
            "brand_fix": self._brand_fix,
            "retry": self._retry,
            "post_approve": self._post_approve,
            "post_change": self._post_change,
            "post_discard": self._post_discard,
            "post_replace": self._post_replace,
            "post_publish": self._post_publish,
            "post_retry": self._post_retry,
            "photo_post": self._photo_post,
        }

    @property
    def brand(self) -> BrandFlow | None:
        return self._brand

    async def handle(self, sender: str, button_id: str, channel: ChannelPort) -> Event | None:
        """Run the button's action. The caller holds the sender's history lock."""
        action, _, entity = button_id.partition(":")
        handler = self._handlers.get(action)
        if handler is None:
            event: Event | None = StaleButton()
        else:
            try:
                event = await handler(sender, entity, channel)
            except SQLAlchemyError:
                # Like the chat's own database calls: answer rather than drop the tap.
                logger.warning("button %s failed for %s", button_id, mask(sender), exc_info=True)
                event = ActionFailed()
        if isinstance(event, StaleButton):
            logger.info("stale button %s from %s", button_id, mask(sender))
        return event

    async def _noop(self, sender: str, entity: str, channel: ChannelPort) -> None:
        return None

    async def _brand_ok(self, sender: str, entity: str, channel: ChannelPort) -> Event:
        if self._brand is None or not await self._brand.confirm(sender):
            return StaleButton()
        return BrandConfirmed()

    async def _brand_fix(self, sender: str, entity: str, channel: ChannelPort) -> Event:
        if self._brand is None or not await self._brand.ask_for_correction(sender):
            return StaleButton()
        return BrandFixAsked()

    async def _retry(self, sender: str, entity: str, channel: ChannelPort) -> Event:
        job = await retry_failed(self._sessions, sender, entity) if self._sessions else None
        return StaleButton() if job is None else JobRetried(job.kind)

    async def _post_approve(self, sender: str, entity: str, channel: ChannelPort) -> Event:
        post = self._post(sender, entity, {"pending_approval"})
        if post is None:
            return StaleButton()
        post.status = "approved"
        return PostApproved(post.id)

    async def _post_change(self, sender: str, entity: str, channel: ChannelPort) -> Event:
        post = self._post(sender, entity, APPROVABLE)
        return StaleButton() if post is None else PostChangeAsked(post.id)

    async def _post_discard(self, sender: str, entity: str, channel: ChannelPort) -> Event:
        post = self._post(sender, entity, APPROVABLE)
        if post is None:
            return StaleButton()
        post.status = "discarded"
        return PostDiscarded(post.id)

    async def _post_replace(self, sender: str, entity: str, channel: ChannelPort) -> Event:
        post = self._post(sender, entity, {"discarded"})
        if post is None:
            return StaleButton()
        return started(self._maker.remake(post, channel), "Sí, otro")

    async def _post_publish(self, sender: str, entity: str, channel: ChannelPort) -> Event:
        post = self._post(sender, entity, {"approved"})
        if post is None:
            return StaleButton()
        return publishing(post, self._publisher.publish_approved(post, channel))

    async def _post_retry(self, sender: str, entity: str, channel: ChannelPort) -> Event:
        post = self._post(sender, entity, {"failed"})
        if post is None:
            return StaleButton()
        return publishing(post, self._publisher.retry(post, channel))

    async def _photo_post(self, sender: str, entity: str, channel: ChannelPort) -> Event:
        photo_ids = [photo_id for photo_id in entity.split(",") if photo_id]
        if not photo_ids:
            return StaleButton()
        brief = "Post con esta foto" if len(photo_ids) == 1 else "Post con estas fotos"
        arguments = {"brief": brief, "asset_ids": photo_ids, "style": "photos"}
        return started(self._maker.create_post(sender, arguments, channel), "Sí, armalo")

    def _post(self, sender: str, post_id: str, allowed: frozenset[str] | set[str]) -> Post | None:
        post = self._posts.get(sender, post_id)
        return post if post is not None and post.status in allowed else None


def started(result: dict[str, Any], origin: str) -> Event:
    error = result.get("error")
    return PostNotStarted(error) if error else PostStarted(result["post_id"], origin)


def publishing(post: Post, result: dict[str, Any]) -> Event:
    return StaleButton() if result.get("error") else PublishStarted(post.id)
