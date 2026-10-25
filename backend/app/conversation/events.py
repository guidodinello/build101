"""Typed events the code raises for the Owner (ADR 0026).

Code never writes the Owner's message: it emits one of these, the orchestrator reads its `note()`
in the conversation history and answers. Primitives only, so `posts/` can import this module.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from app.channels.base import ChannelPort
from app.copy import messages_es


@dataclass(frozen=True, slots=True)
class PostSent:
    post_id: str
    image_count: int
    style: Literal["photos", "design"]
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
    style: Literal["photos", "design"]
    photo_ids: tuple[str, ...]
    brief: str

    def note(self) -> str:
        return (
            f"[post {self.post_id} failed] A {self.style} post from photos "
            f'{" ".join(self.photo_ids)} (brief "{self.brief}") could not be made. '
            "Nothing reached the Owner."
        )


@dataclass(frozen=True, slots=True)
class VideoSent:
    post_id: str  # the new video Post, next to the Post it animates
    video_url: str  # public, shown as the header of the buttons message
    duration_seconds: int
    text: str  # caption + hashtags, reused from the Post it animates

    def note(self) -> str:
        return (
            f"[post {self.post_id} video sent to the Owner] A {self.duration_seconds} s video "
            "made from the product photo, waiting for their approval.\n"
            f'Text: "{self.text}"'
        )


@dataclass(frozen=True, slots=True)
class VideoFailed:
    post_id: str
    reason: str  # blocked, rejected, unavailable, timeout, no_video or failed
    photo_ids: tuple[str, ...]

    def note(self) -> str:
        return (
            f"[video {self.post_id} failed] A video from photos {' '.join(self.photo_ids)} could "
            f"not be made ({self.reason}). Nothing reached the Owner and nothing can be published."
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
            f"[post {self.post_id} publish failed] Instagram did not take it. The Owner can try "
            "again with the Reintentar button under your message."
        )


@dataclass(frozen=True, slots=True)
class PublishUnconfirmed:
    post_id: str

    def note(self) -> str:
        return (
            f"[post {self.post_id} publish unconfirmed] Instagram never confirmed whether it "
            "went live, after checking for about 2 hours. Tell the Owner once to check their "
            "Instagram account. It will not be published again."
        )


@dataclass(frozen=True, slots=True)
class PublishNotConnected:
    post_id: str

    def note(self) -> str:
        return (
            f"[post {self.post_id} not published] The Owner tapped a button to publish it, but "
            "publishing to their Instagram isn't connected yet. Nothing was published."
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
class PhotoTooLarge:
    def note(self) -> str:
        return "[photo too large] It has more megapixels than we can read."


@dataclass(frozen=True, slots=True)
class PhotoTooBig:
    max_mb: int

    def note(self) -> str:
        return f"[photo too big] It is over the {self.max_mb} MB limit."


@dataclass(frozen=True, slots=True)
class StaleButton:
    def note(self) -> str:
        return "[stale button] The Owner tapped a button that is no longer active."


@dataclass(frozen=True, slots=True)
class BrandConfirmed:
    def note(self) -> str:
        return "[brand confirmed] The Owner confirmed the brand summary. Onboarding is done."


@dataclass(frozen=True, slots=True)
class BrandFixAsked:
    def note(self) -> str:
        return (
            "[brand fix asked] The Owner tapped Corregir algo on the brand summary. Their next "
            "message is the correction."
        )


@dataclass(frozen=True, slots=True)
class JobRetried:
    kind: str

    def note(self) -> str:
        return f"[retrying {self.kind}] The Owner tapped Reintentar; it is running again."


@dataclass(frozen=True, slots=True)
class PostApproved:
    post_id: str

    def note(self) -> str:
        return (
            f"[post {self.post_id} approved] The Owner tapped Aprobar. Scheduling isn't built: "
            "it is published when they tap Publicar ahora under your message."
        )


@dataclass(frozen=True, slots=True)
class PostChangeAsked:
    post_id: str

    def note(self) -> str:
        return (
            f"[post {self.post_id} change asked] The Owner tapped Cambiar. Their next message says "
            f"what to change: revise_post with post_id={self.post_id}."
        )


@dataclass(frozen=True, slots=True)
class PostDiscarded:
    post_id: str

    def note(self) -> str:
        return (
            f"[post {self.post_id} discarded] The Owner tapped Descartar. The buttons under your "
            "message offer another one from the same request."
        )


@dataclass(frozen=True, slots=True)
class PostStarted:
    post_id: str
    origin: str  # what the Owner tapped: "Sí, otro" or "Sí, armalo"

    def note(self) -> str:
        return (
            f'[post {self.post_id} started] From the "{self.origin}" button; it reaches the '
            "Owner in a few minutes."
        )


@dataclass(frozen=True, slots=True)
class PostNotStarted:
    reason: str  # generation_in_progress, daily_limit, video_daily_limit, unknown_asset, no_photos

    def note(self) -> str:
        return f"[post not started] The Owner's tap could not start a post: {self.reason}."


@dataclass(frozen=True, slots=True)
class PublishStarted:
    post_id: str

    def note(self) -> str:
        return (
            f"[post {self.post_id} publishing] The Owner tapped a button to publish it; the "
            "outcome arrives as its own event."
        )


@dataclass(frozen=True, slots=True)
class BrandSummaryReady:
    """The Brand Brain's summary, as the Brand Strategist wrote it, for the Owner to confirm."""

    business_name: str
    summary: str

    def note(self) -> str:
        return (
            "[brand summary sent] The Owner got the summary of their brand (<brand_summary_sent>) "
            "with the buttons Sí, es mi marca and Corregir algo."
        )


@dataclass(frozen=True, slots=True)
class JobFailed:
    job_id: uuid.UUID
    kind: str

    def note(self) -> str:
        return (
            f"[job {self.kind} failed] It could not be finished. The Owner can try again with "
            "the Reintentar button under the message they got."
        )


@dataclass(frozen=True, slots=True)
class BrandGenerating:
    def note(self) -> str:
        return (
            "[brand generating] The Owner submitted the form; the summary of their brand "
            "arrives in about a minute."
        )


@dataclass(frozen=True, slots=True)
class ActionFailed:
    def note(self) -> str:
        return "[action failed] Something broke handling the Owner's tap; nothing changed."


Event = (
    PostSent
    | PostFailed
    | VideoSent
    | VideoFailed
    | Published
    | PublishPending
    | PublishFailed
    | PublishUnconfirmed
    | PublishNotConnected
    | PhotosReceived
    | AudioUnclear
    | UnsupportedMedia
    | PhotoUnreadable
    | PhotoTooBig
    | PhotoTooLarge
    | StaleButton
    | BrandConfirmed
    | BrandFixAsked
    | JobRetried
    | PostApproved
    | PostChangeAsked
    | PostDiscarded
    | PostStarted
    | PostNotStarted
    | PublishStarted
    | BrandSummaryReady
    | JobFailed
    | BrandGenerating
    | ActionFailed
)

# Called as (sender, event, channel). Whoever answers it owns the sender's history lock. A verbatim
# event's failure reaches the caller; any other failure is logged by the notifier.
Notify = Callable[[str, Event, ChannelPort], Awaitable[None]]

# The events whose fixed text is the message itself: the model never writes them, it only reads
# their note. The summary is the Brand Strategist's own text and what `<brand_summary_sent>` says
# the Owner saw; the other two are what jobs and the onboarding API have always sent.
VERBATIM = (BrandSummaryReady, JobFailed, BrandGenerating)


def verbatim(event: Event) -> bool:
    return isinstance(event, VERBATIM)


POST_NOT_STARTED = {
    "generation_in_progress": messages_es.GENERATION_BUSY,
    "daily_limit": messages_es.DAILY_LIMIT,
    "unknown_asset": messages_es.PHOTOS_GONE,
    "no_photos": messages_es.PHOTOS_GONE,
    "video_daily_limit": messages_es.VIDEO_DAILY_LIMIT,
}


def fallback(event: Event) -> str | None:
    """What the Owner is told when the LLM can't write the message; None sends nothing.

    A post that already arrived needs no message (`PostSent`), unless it carries its buttons:
    then `post_actions` goes with them.
    """
    match event:
        case PostSent():
            return messages_es.post_actions()
        case PostFailed():
            return messages_es.JOB_FAILED
        case VideoSent():
            return messages_es.VIDEO_ACTIONS
        case VideoFailed(reason="blocked"):
            return messages_es.VIDEO_BLOCKED
        case VideoFailed():
            return messages_es.VIDEO_FAILED
        case Published(permalink=permalink):
            return messages_es.published(permalink or "")
        case PublishPending():
            return messages_es.PUBLISH_PENDING
        case PublishFailed():
            return messages_es.PUBLISH_FAILED
        case PublishUnconfirmed():
            return messages_es.PUBLISH_UNCONFIRMED
        case PublishNotConnected():
            return messages_es.NEED_IG
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
        case PhotoTooLarge():
            return messages_es.PHOTO_TOO_LARGE
        case StaleButton():
            return messages_es.STALE_BUTTON
        case BrandConfirmed():
            return messages_es.READY_OPEN_CHAT
        case BrandFixAsked():
            return messages_es.BRAND_FIX_PROMPT
        case JobRetried():
            return messages_es.RETRYING
        case PostApproved():
            return messages_es.PUBLISH_NOW_ASK
        case PostChangeAsked():
            return messages_es.POST_CHANGE_PROMPT
        case PostDiscarded():
            return messages_es.POST_DISCARDED
        case PostStarted():
            return messages_es.POST_GENERATING
        case PostNotStarted(reason=reason):
            return POST_NOT_STARTED.get(reason, messages_es.REPLY_FAILED)
        case PublishStarted():
            return messages_es.PUBLISHING
        case ActionFailed():
            return messages_es.REPLY_FAILED
        case BrandSummaryReady(business_name=name, summary=summary):
            return messages_es.brand_summary(name, summary)
        case JobFailed():
            return messages_es.JOB_FAILED
        case BrandGenerating():
            return messages_es.BRAND_GENERATING
