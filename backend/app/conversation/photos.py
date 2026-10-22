import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Until T02 stores each Business's timezone (conversation-design.md: dates in America/Montevideo).
LOCAL_TZ = ZoneInfo("America/Montevideo")
MAX_PHOTOS = 10
RECENT_FOR = timedelta(minutes=30)


def local_now() -> datetime:
    return datetime.now(LOCAL_TZ)


@dataclass(slots=True)
class Photo:
    id: str
    data: bytes  # JPEG, already through prepare_reference
    caption: str | None
    received_at: datetime
    used: bool = False
    seen: bool = False  # sent to the orchestrator as an image at least once
    description: str | None = None  # the Asset Analyst's, once it has looked at the photo
    low_quality: bool = False  # the Asset Analyst rated it blurry, dark or too small
    asset_id: uuid.UUID | None = None  # the Brand asset it is stored as, when it is one


@dataclass(slots=True)
class _SenderPhotos:
    photos: list[Photo] = field(default_factory=list)
    next_number: int = 1


class InMemoryPhotos:
    """Photos the Owner sent on WhatsApp, per sender, until T02 stores them as Brand assets.

    Ids are short ("f1", "f2", ...) so the model can copy them from `<recent_photos>`, and never
    reused, so a stale id can't point at a newer photo.
    """

    def __init__(
        self,
        max_photos: int = MAX_PHOTOS,
        recent_for: timedelta = RECENT_FOR,
        now: Callable[[], datetime] = local_now,
    ) -> None:
        self._max_photos = max_photos
        self._recent_for = recent_for
        self._now = now
        self._senders: defaultdict[str, _SenderPhotos] = defaultdict(_SenderPhotos)
        # The wizard's photos and logo (`BrandLibrary`), refreshed every turn; they don't expire.
        self._library: dict[str, list[Photo]] = {}
        self._logos: dict[str, bytes] = {}

    def add(self, sender: str, data: bytes, caption: str | None) -> Photo:
        stored = self._senders[sender]
        photo = Photo(f"f{stored.next_number}", data, caption, self._now())
        stored.next_number += 1
        stored.photos.append(photo)
        del stored.photos[: -self._max_photos]
        return photo

    def recent(self, sender: str) -> list[Photo]:
        """Photos from the last 30 minutes that no post uses yet: what `<recent_photos>` lists."""
        return [photo for photo in self._kept(sender) if not photo.used]

    def set_library(self, sender: str, photos: list[Photo]) -> None:
        self._library[sender] = photos

    def library(self, sender: str) -> list[Photo]:
        return self._library.get(sender, [])

    def set_logo(self, sender: str, logo: bytes | None) -> None:
        if logo is None:
            self._logos.pop(sender, None)
        else:
            self._logos[sender] = logo

    def logo(self, sender: str) -> bytes | None:
        """The logo file as the Owner uploaded it, transparency included."""
        return self._logos.get(sender)

    def find(self, sender: str, ids: list[str]) -> tuple[list[Photo], list[str]]:
        """The kept and library photos with these ids, used ones included, and the ids not found."""
        by_id = {photo.id: photo for photo in [*self._kept(sender), *self.library(sender)]}
        found = [by_id[photo_id] for photo_id in ids if photo_id in by_id]
        return found, [photo_id for photo_id in ids if photo_id not in by_id]

    def _kept(self, sender: str) -> list[Photo]:
        stored = self._senders[sender]
        cutoff = self._now() - self._recent_for
        stored.photos = [photo for photo in stored.photos if photo.received_at >= cutoff]
        return stored.photos
