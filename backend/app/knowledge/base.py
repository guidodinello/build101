"""What the Agency knows about a Business right now: the interface its readers share (ADR 0030).

One read answers for the orchestrator's context and for the posts made in the chat. `DbKnowledge`
(`db.py`) reads Postgres; `LocalKnowledge` (`local.py`) serves the runs without a database.
"""

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from app.agents.schemas import BrandBrain

NOTE_ID_CHARS = 8


@dataclass(frozen=True, slots=True)
class Note:
    id: str  # short, so the model can copy it into `forget`
    text: str


def short_id(note_id: uuid.UUID) -> str:
    return f"n{note_id.hex[:NOTE_ID_CHARS]}"


@dataclass(frozen=True, slots=True)
class CatalogItem:
    name: str
    price: str | None
    description: str


@dataclass(frozen=True, slots=True)
class BusinessFacts:
    """The Business row and its onboarding answers, as the Owner gave them."""

    name: str | None
    owner_name: str | None
    category: str | None
    one_liner: str | None
    location: str | None
    website: str | None
    instagram_handle: str | None
    current_offer: str | None
    onboarding_state: str
    awaiting: str | None  # conversation_state["awaiting"], e.g. "brand_correction"


@dataclass(frozen=True, slots=True)
class BusinessKnowledge:
    business: BusinessFacts | None = None
    brand: BrandBrain | None = None
    catalog: list[CatalogItem] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    summary: str | None = None
    trend_notes: str | None = None  # the latest Niche Report of the Business's niche


class Knowledge(Protocol):
    """Resolves the sender once and answers with all the Agency knows about their Business."""

    async def of(self, sender: str) -> BusinessKnowledge:
        """Empty knowledge for a sender with no Business. Never raises on a database failure: a
        post or a turn goes ahead with what it has rather than not at all."""
        ...
