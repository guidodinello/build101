import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.channels.base import ChannelPort
from app.channels.inbound import mask
from app.llm.client import FunctionCall
from app.posts.lifecycle import PostLifecycle
from app.posts.maker import PostMaker
from app.posts.publish import PostPublisher
from app.posts.store import Post
from app.posts.video_maker import VideoMaker

from .approval import CAPTION_START_CHARS, Approval
from .brand import BrandFlow
from .events import Notify
from .notes import OwnerNotes
from .tools import CREATE_VIDEO, TOOLS

logger = logging.getLogger(__name__)

# Tools that act on the Owner's words: an event turn has none.
OWNER_TOOLS = frozenset(
    {"create_post", "create_video", "revise_post", "remember", "forget", "update_brand"}
)


class Toolbox:
    """The orchestrator's tools: what the model may call (`declarations`) and what each call does.

    `run` is the one way in. It never raises for a database failure: the model reads
    `{"error": "action_failed"}` and tells the Owner. `notify` is how the background work a tool
    starts reports back, so it travels with each call (the toolbox is built before the chat that
    owns it).
    """

    def __init__(
        self,
        posts: PostMaker,
        publisher: PostPublisher,
        lifecycle: PostLifecycle,
        notes: OwnerNotes,
        brand: BrandFlow | None,
        videos: VideoMaker | None,
    ) -> None:
        self._posts = posts
        self._publisher = publisher
        self._lifecycle = lifecycle
        self._notes = notes
        self._brand = brand
        self._videos = videos
        self.declarations = [*TOOLS, CREATE_VIDEO] if videos else TOOLS

    @property
    def with_video(self) -> bool:
        return self._videos is not None

    async def run(
        self,
        call: FunctionCall,
        sender: str,
        channel: ChannelPort,
        notify: Notify,
        approval: Approval,
        owner_request: bool,
    ) -> dict[str, Any]:
        logger.info("tool %s for %s: %s", call.name, mask(sender), call.arguments)
        try:
            result = await self._dispatch(call, sender, channel, notify, approval, owner_request)
        except SQLAlchemyError:
            logger.warning("tool %s failed for %s", call.name, mask(sender), exc_info=True)
            result = {"error": "action_failed"}
        logger.info("tool %s result: %s", call.name, result)
        return result

    async def _dispatch(
        self,
        call: FunctionCall,
        sender: str,
        channel: ChannelPort,
        notify: Notify,
        approval: Approval,
        owner_request: bool,
    ) -> dict[str, Any]:
        arguments = call.arguments
        if call.name in OWNER_TOOLS and not owner_request:
            # A note turn has no Owner words: acting on them isn't their intent.
            return {"error": "not_owner_request"}
        match call.name:
            case "create_post":
                return self._posts.create_post(sender, arguments, channel, notify)
            case "create_video" if self._videos is not None:
                return self._videos.create_video(sender, arguments, channel, notify)
            case "revise_post":
                return self._posts.revise_post(sender, arguments, channel, notify)
            case "approve_post":
                return self._publisher.approve(sender, arguments, approval, channel, notify)
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
        if self._brand is None:
            return {"error": "not_available"}
        if not change:
            return {"error": "invalid_arguments"}
        if not await self._brand.revise(sender, change):
            return {"error": "brand_not_ready"}
        return {"status": "revising"}


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
