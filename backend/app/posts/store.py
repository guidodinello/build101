from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.conversation.photos import local_now

MAX_POSTS_PER_SENDER = 10  # each holds its JPEGs until it is published or dropped

PostStatus = Literal[
    "pending_approval",
    "publishing",
    "publish_pending",  # not final or not known: the post may be live, never report a failure
    "published",
    "failed",  # definite failure only; terminal in T57
    "replaced",  # a newer revision was sent; no longer approvable
]
# Statuses a post keeps while a publish may still be running or resolving.
BUSY: frozenset[PostStatus] = frozenset({"publishing", "publish_pending"})


@dataclass(frozen=True, slots=True)
class PostImage:
    path: str  # where PublicImages served it, relative to the public URL
    data: bytes


@dataclass(slots=True)
class Post:
    id: str
    sender: str
    images: list[PostImage]  # slide order
    caption: str  # caption + hashtags, as the Owner received it
    status: PostStatus = "pending_approval"
    permalink: str | None = None
    external_post_id: str | None = None
    created_at: datetime = field(default_factory=local_now)

    @property
    def format(self) -> Literal["image", "carousel"]:
        return "image" if len(self.images) == 1 else "carousel"


class InMemoryPosts:
    """Posts sent to the Owner, per sender, until T19 moves them onto `posts` (ADR 0005)."""

    def __init__(self, max_per_sender: int = MAX_POSTS_PER_SENDER) -> None:
        self._max_per_sender = max_per_sender
        self._posts: defaultdict[str, list[Post]] = defaultdict(list)
        # Set when "subilo" met several pending posts: the ids of the numbered list the Owner was
        # shown, which the next turn may name by number.
        self._listed: dict[str, list[str]] = {}

    def add(self, post: Post) -> None:
        posts = self._posts[post.sender]
        posts.append(post)
        while len(posts) > self._max_per_sender:
            # Oldest first, but never one whose publish is still running or unresolved.
            droppable = next((p for p in posts if p.status not in BUSY), None)
            if droppable is None:
                break
            posts.remove(droppable)

    def get(self, sender: str, post_id: str) -> Post | None:
        return next((post for post in self._posts[sender] if post.id == post_id), None)

    def pending(self, sender: str) -> list[Post]:
        """The posts awaiting approval, oldest first: the numbering the Owner sees."""
        return [post for post in self._posts[sender] if post.status == "pending_approval"]

    def listed(self, sender: str) -> list[str] | None:
        return self._listed.get(sender)

    def set_listed(self, sender: str, post_ids: list[str] | None) -> None:
        if post_ids:
            self._listed[sender] = post_ids
        else:
            self._listed.pop(sender, None)
