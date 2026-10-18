"""Button replies (api.md § Button IDs): `<action>:<entity_id>`, checked against the entity's state.

An unknown action, or one the entity's state doesn't allow, gets `stale_button` and nothing
else. Posts still live in memory (T56, T57) and the Brand Brain in the database, so the router
takes both; T19 moves the posts.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.base import Button, ChannelPort
from app.channels.inbound import mask
from app.copy import messages_es
from app.jobs.queue import retry_failed
from app.llm.client import user_step
from app.posts.maker import PostMaker
from app.posts.publish import PostPublisher
from app.posts.store import APPROVABLE, InMemoryPosts, Post

from .brand import BrandFlow
from .history import InMemoryHistory

logger = logging.getLogger(__name__)

# The reply to send, or None when the handler sent its own messages (or nothing, for `noop`).
Handler = Callable[[str, str, ChannelPort], Awaitable[str | None]]

POST_START_ERRORS = {
    "generation_in_progress": messages_es.GENERATION_BUSY,
    "daily_limit": messages_es.DAILY_LIMIT,
    "unknown_asset": messages_es.PHOTOS_GONE,
    "no_photos": messages_es.PHOTOS_GONE,
}


class ButtonRouter:
    def __init__(
        self,
        posts: InMemoryPosts,
        maker: PostMaker,
        publisher: PostPublisher,
        history: InMemoryHistory,
        sessions: async_sessionmaker[AsyncSession] | None,
    ) -> None:
        self._posts = posts
        self._maker = maker
        self._publisher = publisher
        self._history = history
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

    async def handle(self, sender: str, button_id: str, channel: ChannelPort) -> str | None:
        """Run the button's action. The caller holds the sender's history lock."""
        action, _, entity = button_id.partition(":")
        handler = self._handlers.get(action)
        reply = await handler(sender, entity, channel) if handler else messages_es.STALE_BUTTON
        if reply == messages_es.STALE_BUTTON:
            logger.info("stale button %s from %s", button_id, mask(sender))
        return reply

    async def _noop(self, sender: str, entity: str, channel: ChannelPort) -> None:
        return None

    async def _brand_ok(self, sender: str, entity: str, channel: ChannelPort) -> str:
        if self._brand is None or not await self._brand.confirm(sender):
            return messages_es.STALE_BUTTON
        self._note(sender, "[brand confirmed] The Owner confirmed the brand summary.")
        return messages_es.READY_OPEN_CHAT

    async def _brand_fix(self, sender: str, entity: str, channel: ChannelPort) -> str:
        if self._brand is None or not await self._brand.ask_for_correction(sender):
            return messages_es.STALE_BUTTON
        return messages_es.BRAND_FIX_PROMPT

    async def _retry(self, sender: str, entity: str, channel: ChannelPort) -> str:
        if self._sessions is None or await retry_failed(self._sessions, sender, entity) is None:
            return messages_es.STALE_BUTTON
        return messages_es.RETRYING

    async def _post_approve(self, sender: str, entity: str, channel: ChannelPort) -> str | None:
        post = self._post(sender, entity, {"pending_approval"})
        if post is None:
            return messages_es.STALE_BUTTON
        post.status = "approved"
        self._note(sender, f"[post {post.id} approved] The Owner tapped Aprobar.")
        publish = Button(id=f"post_publish:{post.id}", title=messages_es.BUTTON_PUBLISH_NOW)
        await channel.send_buttons(sender, messages_es.PUBLISH_NOW_ASK, [publish])
        return None

    async def _post_change(self, sender: str, entity: str, channel: ChannelPort) -> str:
        post = self._post(sender, entity, APPROVABLE)
        if post is None:
            return messages_es.STALE_BUTTON
        self._note(
            sender,
            f"[post {post.id} change requested] The Owner tapped Cambiar. Their next message "
            f"says what to change: remake it with create_post, replaces={post.id}.",
        )
        return messages_es.POST_CHANGE_PROMPT

    async def _post_discard(self, sender: str, entity: str, channel: ChannelPort) -> None | str:
        post = self._post(sender, entity, APPROVABLE)
        if post is None:
            return messages_es.STALE_BUTTON
        post.status = "discarded"
        self._note(sender, f"[post {post.id} discarded] The Owner tapped Descartar.")
        buttons = [
            Button(id=f"post_replace:{post.id}", title=messages_es.BUTTON_ANOTHER),
            Button(id="noop", title=messages_es.BUTTON_NO_THANKS),
        ]
        await channel.send_buttons(sender, messages_es.POST_DISCARDED, buttons)
        return None

    async def _post_replace(self, sender: str, entity: str, channel: ChannelPort) -> str:
        post = self._post(sender, entity, {"discarded"})
        if post is None:
            return messages_es.STALE_BUTTON
        return self._started(sender, self._maker.remake(post, channel), f"replacing {post.id}")

    async def _post_publish(self, sender: str, entity: str, channel: ChannelPort) -> str:
        post = self._post(sender, entity, {"approved"})
        if post is None:
            return messages_es.STALE_BUTTON
        return self._published(self._publisher.publish_approved(post, channel))

    async def _post_retry(self, sender: str, entity: str, channel: ChannelPort) -> str:
        post = self._post(sender, entity, {"failed"})
        if post is None:
            return messages_es.STALE_BUTTON
        return self._published(self._publisher.retry(post, channel))

    async def _photo_post(self, sender: str, entity: str, channel: ChannelPort) -> str:
        photo_ids = [photo_id for photo_id in entity.split(",") if photo_id]
        if not photo_ids:
            return messages_es.STALE_BUTTON
        brief = "Post con esta foto" if len(photo_ids) == 1 else "Post con estas fotos"
        arguments = {"brief": brief, "asset_ids": photo_ids, "style": "photos"}
        result = self._maker.create_post(sender, arguments, channel)
        return self._started(sender, result, f"from photos {' '.join(photo_ids)}")

    def _post(self, sender: str, post_id: str, allowed: frozenset[str] | set[str]) -> Post | None:
        post = self._posts.get(sender, post_id)
        return post if post is not None and post.status in allowed else None

    def _started(self, sender: str, result: dict[str, Any], what: str) -> str:
        error = result.get("error")
        if error:
            return POST_START_ERRORS.get(error, messages_es.STALE_BUTTON)
        self._note(sender, f"[post {result['post_id']} generating] Started from a button, {what}.")
        return messages_es.POST_GENERATING

    def _published(self, result: dict[str, Any]) -> str:
        if result.get("error"):
            return messages_es.STALE_BUTTON
        return messages_es.PUBLISHING

    def _note(self, sender: str, text: str) -> None:
        """Tell the orchestrator what a button did, so a later message has the context."""
        self._history.extend(sender, [user_step(text)])
