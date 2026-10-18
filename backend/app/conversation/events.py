"""Typed events the code raises for the Owner (ADR 0025).

Code never writes the Owner's message: it emits one of these, the orchestrator reads its `note()`
in the conversation history and answers. Primitives only, so `posts/` can import this module.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.channels.base import ChannelPort
from app.copy import messages_es


@dataclass(frozen=True, slots=True)
class PostSent:
    post_id: str
    image_count: int
    style: str  # "photos" or "design"
    photo_ids: tuple[str, ...]
    headlines: tuple[str, ...]  # one per slide of a design; empty for photos as they are
    text: str  # caption + hashtags, as the Owner received it

    def note(self) -> str:
        style = "photos as they are" if self.style == "photos" else "design"
        lines = [
            f"[post {self.post_id} sent to the Owner] {self.image_count} image(s), {style}, "
            f"from photos {' '.join(self.photo_ids)}."
        ]
        if self.headlines:
            headlines = "; ".join(f'{n} "{h}"' for n, h in enumerate(self.headlines, start=1))
            lines.append(f"Slide headlines: {headlines}")
        lines.append(f'Text: "{self.text}"')
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class PostFailed:
    post_id: str
    style: str
    photo_ids: tuple[str, ...]
    brief: str

    def note(self) -> str:
        return (
            f"[post {self.post_id} failed] A {self.style} post from photos "
            f'{" ".join(self.photo_ids)} (brief "{self.brief}") could not be made. '
            "Nothing reached the Owner."
        )


@dataclass(frozen=True, slots=True)
class Published:
    post_id: str
    permalink: str | None

    def note(self) -> str:
        link = f"Live on Instagram: {self.permalink}" if self.permalink else "No link came back."
        return f"[post {self.post_id} published] {link}"


@dataclass(frozen=True, slots=True)
class PublishPending:
    post_id: str

    def note(self) -> str:
        return (
            f"[post {self.post_id} publish pending] Instagram is still processing it and it "
            "will show up on the Owner's account soon. Do not publish it again."
        )


@dataclass(frozen=True, slots=True)
class PublishFailed:
    post_id: str

    def note(self) -> str:
        return (
            f"[post {self.post_id} publish failed] Instagram did not take it. It can't be "
            "published again: offer to make a new one."
        )


@dataclass(frozen=True, slots=True)
class PhotosReceived:
    """Photos arrived with no text of their own."""

    photo_ids: tuple[str, ...]

    def note(self) -> str:
        # English on purpose: `[foto f1]` / `[fotos f1 f2]` mean photos with the Owner's caption.
        return f"[photos {' '.join(self.photo_ids)} received, no text]"


@dataclass(frozen=True, slots=True)
class AudioUnclear:
    def note(self) -> str:
        return "[voice note unclear] It could not be transcribed."


@dataclass(frozen=True, slots=True)
class UnsupportedMedia:
    def note(self) -> str:
        return "[unsupported message] The Owner sent something that is not text, audio or a photo."


@dataclass(frozen=True, slots=True)
class PhotoUnreadable:
    def note(self) -> str:
        return "[photo unreadable] The photo could not be opened."


@dataclass(frozen=True, slots=True)
class PhotoTooBig:
    max_mb: int

    def note(self) -> str:
        return f"[photo too big] It is over the {self.max_mb} MB limit."


@dataclass(frozen=True, slots=True)
class StaleButton:
    def note(self) -> str:
        return "[stale button] The Owner tapped a button that is no longer active."


Event = (
    PostSent
    | PostFailed
    | Published
    | PublishPending
    | PublishFailed
    | PhotosReceived
    | AudioUnclear
    | UnsupportedMedia
    | PhotoUnreadable
    | PhotoTooBig
    | StaleButton
)

# Called as (sender, event, channel). Whoever answers it owns the sender's history lock.
Notify = Callable[[str, Event, ChannelPort], Awaitable[None]]


def fallback(event: Event) -> str | None:
    """What the Owner is told when the LLM can't write the message; None sends nothing.

    A post that already arrived needs no message (`PostSent`).
    """
    match event:
        case PostSent():
            return None
        case PostFailed():
            return messages_es.JOB_FAILED
        case Published(permalink=permalink):
            return messages_es.published(permalink or "")
        case PublishPending():
            return messages_es.PUBLISH_PENDING
        case PublishFailed():
            return messages_es.PUBLISH_FAILED
        case PhotosReceived(photo_ids=ids):
            return messages_es.PHOTOS_KEPT if len(ids) > 1 else messages_es.PHOTO_KEPT
        case AudioUnclear():
            return messages_es.AUDIO_UNCLEAR
        case UnsupportedMedia():
            return messages_es.UNSUPPORTED_MEDIA
        case PhotoUnreadable():
            return messages_es.PHOTO_UNREADABLE
        case PhotoTooBig(max_mb=max_mb):
            return messages_es.photo_too_big(max_mb)
        case StaleButton():
            return messages_es.STALE_BUTTON
