"""The Post lifecycle: the one module that changes a Post's status and applies the Approval rule.

Allowed moves (ADR 0007 keeps the publisher behind the Owner's explicit approval):

    pending_approval -> approved -> publishing   ([Aprobar], then [Publicar ahora])
    pending_approval | approved -> publishing    (the Owner's words: a plain "subilo")
    publishing -> published | failed | publish_pending
    pending_approval | approved -> discarded | replaced
    pending_approval | approved -> revising -> replaced   (a change was asked; the new one arrived)
    revising -> pending_approval | approved              (the new version failed: back as it was)
    failed -> publishing   ([Reintentar])

Nothing else assigns `Post.status`, and the publisher takes only an `ApprovedPost`, which only
this module mints. The Approval inputs (`listed`, `offered`, `has_photos`) live here too, so the
chat asks "what may this message publish?" instead of computing it.
"""

from dataclasses import dataclass, field
from typing import Any

from app.conversation.approval import Approval, asks_to_publish, decide
from app.conversation.photos import Photo

from .store import APPROVABLE, InMemoryPosts, Post, PostStatus

_MINT = object()


@dataclass(frozen=True, slots=True)
class ApprovedPost:
    """A Post the Owner approved, or one whose publish failed and may be retried (ADR 0007).

    `PostPublisher` starts a publish only from one of these. Only `PostLifecycle` builds them.
    """

    post: Post
    _mint: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._mint is not _MINT:
            raise TypeError("an ApprovedPost comes from PostLifecycle.authorize_*")


class PostLifecycle:
    """Posts sent to the Owner, their state changes and the Approval inputs, per sender.

    In memory behind this interface until T19 moves Posts onto `posts` (ADR 0005): callers never
    touch the store, so that swap changes this module only.
    """

    def __init__(self, store: InMemoryPosts | None = None) -> None:
        self._store = store or InMemoryPosts()
        # Set when "subilo" met several pending posts: the ids of the numbered list the Owner was
        # shown, which the next turn may name by number.
        self._listed: dict[str, list[str]] = {}
        # The post the assistant's last message asked to publish, which a bare "sí" approves.
        self._offered: dict[str, str] = {}
        # The status a post being revised had, which it gets back if the revision fails.
        self._before_revision: dict[tuple[str, str], PostStatus] = {}

    # Reading

    def add(self, post: Post) -> None:
        self._store.add(post)

    def get(self, sender: str, post_id: str) -> Post | None:
        return self._store.get(sender, post_id)

    def all(self, sender: str) -> list[Post]:
        return self._store.all(sender)

    def video(self, path: str) -> bytes | None:
        """The clip served at `path`, if a Post still held here has it."""
        return self._store.video(path)

    def pending(self, sender: str) -> list[Post]:
        """The posts "subilo" can publish, oldest first: the numbering the Owner sees."""
        return [post for post in self._store.all(sender) if post.status in APPROVABLE]

    def revising(self, sender: str, post_id: str) -> bool:
        """Whether the post's new version is being made, so nothing may approve it."""
        post = self.get(sender, post_id)
        return post is not None and post.status == "revising"

    def awaiting_approval(self, post: Post) -> bool:
        """Still as the Owner first saw it: not approved, discarded, replaced or published."""
        return post.status == "pending_approval"

    def approvable_post(self, sender: str, post_id: str) -> Post | dict[str, Any]:
        """The post a revision or a video may start from, or the error to give the model."""
        post = self.get(sender, post_id)
        if post is None:
            return {"error": "unknown_post"}
        if post.status == "revising":
            return {"error": "revision_in_progress"}
        if post.status not in APPROVABLE:
            return {"error": "post_not_pending", "status": post.status}
        return post

    # Buttons: each returns the post the tap applies to, or None for a stale button

    def approve(self, sender: str, post_id: str) -> Post | None:
        """[Aprobar]: the tap is the approval, and only of a post still waiting for it."""
        post = self.get(sender, post_id)
        if post is None or post.status != "pending_approval":
            return None
        post.status = "approved"
        return post

    def discard(self, sender: str, post_id: str) -> Post | None:
        post = self.pending_post(sender, post_id)
        if post is not None:
            post.status = "discarded"
        return post

    def pending_post(self, sender: str, post_id: str) -> Post | None:
        """The post if it can still be approved, changed or discarded."""
        post = self.get(sender, post_id)
        return post if post is not None and post.status in APPROVABLE else None

    def discarded_post(self, sender: str, post_id: str) -> Post | None:
        """The post if the Owner discarded it ([Sí, otro] makes another from the same request)."""
        post = self.get(sender, post_id)
        return post if post is not None and post.status == "discarded" else None

    def replace(self, post: Post) -> None:
        """Retire a post a newer one stands in for: no longer approvable."""
        post.status = "replaced"

    def retire(self, sender: str, post_id: str) -> bool:
        """`replace` for the post a remake replaces, if it is still pending or being revised."""
        self._before_revision.pop((sender, post_id), None)
        post = self.get(sender, post_id)
        if post is None or post.status not in APPROVABLE | {"revising"}:
            return False
        self.replace(post)
        return True

    def begin_revision(self, sender: str, post_id: str) -> None:
        """Lock a pending post while its new version is made: no path may approve it (BUG-3)."""
        post = self.pending_post(sender, post_id)
        if post is None:
            return
        self._before_revision[(sender, post_id)] = post.status
        post.status = "revising"

    def cancel_revision(self, sender: str, post_id: str) -> bool:
        """The new version failed: the post gets back its status. False if it wasn't locked."""
        before = self._before_revision.pop((sender, post_id), None)
        post = self.get(sender, post_id)
        if before is None or post is None or post.status != "revising":
            return False
        post.status = before
        return True

    # Publishing: the publisher takes an ApprovedPost and reports how it ended

    def authorize_text(
        self, sender: str, post_id: str, approval: Approval
    ) -> ApprovedPost | dict[str, Any]:
        """The Owner's words approved `post_id`: this turn's `Approval` names it (ADR 0007)."""
        post = self.get(sender, post_id)
        if post is None:
            return {"error": "unknown_post"}
        if post.status == "revising":
            return {"error": "revision_in_progress"}
        if post.status not in APPROVABLE:
            return {"error": "post_not_pending", "status": post.status}
        if approval.post_id != post.id:
            result: dict[str, Any] = {"error": approval.reason}
            if approval.pending:
                result["pending"] = approval.pending
            return result
        return ApprovedPost(post, _MINT)

    def authorize_tap(self, sender: str, post_id: str) -> ApprovedPost | None:
        """[Publicar ahora]: the post was approved with [Aprobar], and that was the approval."""
        post = self.get(sender, post_id)
        if post is None or post.status != "approved":
            return None
        return ApprovedPost(post, _MINT)

    def authorize_retry(self, sender: str, post_id: str) -> ApprovedPost | None:
        """[Reintentar] after a definite failure."""
        post = self.get(sender, post_id)
        if post is None or post.status != "failed":
            return None
        return ApprovedPost(post, _MINT)

    def begin_publish(self, approved: ApprovedPost) -> Post:
        """Busy before the task starts, so a second "subilo" finds the post taken."""
        post = approved.post
        post.status = "publishing"
        post.publish_attempts += 1
        return post

    def published(self, post: Post, permalink: str | None, external_post_id: str | None) -> None:
        post.status = "published"
        post.permalink = permalink
        post.external_post_id = external_post_id

    def failed(self, post: Post) -> None:
        post.status = "failed"

    def publish_pending(self, post: Post, external_post_id: str | None) -> None:
        """Not final or not known: the post may be live, so no failure and no re-publish."""
        post.status = "publish_pending"
        post.external_post_id = external_post_id

    # Approval inputs

    def approval_for(
        self, sender: str, words: str, *, attached: bool, recent_photos: list[Photo]
    ) -> Approval:
        """What this turn's message allows `approve_post` to publish, computed in code (ADR 0007).

        Photos came with it, or arrived after the pending posts: the Owner is asking for a post,
        not approving one.
        """
        pending = self.pending(sender)
        approval, listed = decide(
            words,
            pending,
            self._listed.get(sender),
            has_photos=attached or bool(photos_after(recent_photos, pending)),
            offered=self._offered.get(sender),
            revising=frozenset(
                post.id for post in self._store.all(sender) if post.status == "revising"
            ),
        )
        if listed:
            self._listed[sender] = listed
        else:
            self._listed.pop(sender, None)
        return approval

    def note_reply(self, sender: str, text: str, post_id: str | None = None) -> None:
        """Remember which post the reply asked to publish, so the next "sí" approves it.

        `post_id` is the post an event was about; otherwise it is the only pending post.
        """
        pending = [post.id for post in self.pending(sender)]
        target = post_id or (pending[0] if len(pending) == 1 else None)
        if target in pending and asks_to_publish(text):
            self._offered[sender] = target
        else:
            self._offered.pop(sender, None)


def photos_after(photos: list[Photo], pending: list[Post]) -> list[Photo]:
    """The photos sent after every pending post: with them, "subilas" asks for a new post."""
    latest = max((post.created_at for post in pending), default=None)
    return [photo for photo in photos if latest is None or photo.received_at > latest]
