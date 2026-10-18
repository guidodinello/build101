"""What the orchestrator knows about the Business, appended to its system prompt (ADR 0028).

It changes only when the Brand Brain, the Catalog, the notes or the summary change, so the
system prompt stays a stable prefix across turns and Gemini's implicit caching can hit.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.schemas import BrandBrain
from app.db.models import Business, Product
from app.jobs.brand import latest_brand_brain

from .notes import Note

MAX_PRODUCTS = 30
PRODUCT_DESCRIPTION_CHARS = 200


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
class OwnerContext:
    business: BusinessFacts | None = None
    brand: BrandBrain | None = None
    catalog: list[CatalogItem] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    summary: str | None = None


class BusinessContexts:
    """The Business, its latest Brand Brain and its Catalog, read fresh on every turn."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def load(self, sender: str) -> OwnerContext:
        """The Business's part of the context; the notes and the summary are the caller's."""
        async with self._sessions() as db:
            business = await db.scalar(select(Business).where(Business.owner_phone == sender))
            if business is None:
                return OwnerContext()
            brand = await latest_brand_brain(db, business.id)
            products = (
                await db.scalars(
                    select(Product)
                    .where(Product.business_id == business.id, Product.archived_at.is_(None))
                    .order_by(Product.position)
                    .limit(MAX_PRODUCTS)
                )
            ).all()
        preferences = business.onboarding_data.get("preferences") or {}
        facts = BusinessFacts(
            name=business.name,
            owner_name=business.owner_name,
            category=business.category,
            one_liner=business.one_liner,
            location=business.location,
            website=business.website,
            instagram_handle=business.instagram_handle,
            current_offer=preferences.get("current_offer"),
            onboarding_state=business.onboarding_state,
            awaiting=business.conversation_state.get("awaiting"),
        )
        catalog = [
            CatalogItem(
                product.name, product.price, product.description[:PRODUCT_DESCRIPTION_CHARS]
            )
            for product in products
        ]
        return OwnerContext(facts, brand, catalog)


def render(context: OwnerContext, trend_notes: str | None = None) -> str:
    """The blocks the prompt's "What you know" section describes; empty ones are left out."""
    blocks: list[str] = []
    if context.business:
        blocks.append(tagged("business", business_lines(context.business)))
    if context.brand:
        brand = context.brand.model_dump_json(exclude={"whatsapp_summary"})
        blocks.append(tagged("brand_brain", brand))
        blocks.append(tagged("brand_summary_sent", context.brand.whatsapp_summary))
    if context.catalog:
        blocks.append(tagged("catalog", "\n".join(catalog_line(item) for item in context.catalog)))
    if context.notes:
        lines = "\n".join(f"- {note.id}: {note.text}" for note in context.notes)
        blocks.append(tagged("owner_notes", lines))
    if trend_notes:
        blocks.append(tagged("trend_notes", trend_notes))
    if context.summary:
        blocks.append(tagged("conversation_summary", context.summary))
    return "\n".join(blocks)


def business_lines(facts: BusinessFacts) -> str:
    fields = {
        "name": facts.name,
        "owner_name": facts.owner_name,
        "category": facts.category,
        "one_liner": facts.one_liner,
        "location": facts.location,
        "website": facts.website,
        "instagram": facts.instagram_handle,
        "current_offer": facts.current_offer,
        "onboarding_state": facts.onboarding_state,
        "awaiting": facts.awaiting,
    }
    return "\n".join(f"{key}: {value}" for key, value in fields.items() if value)


def catalog_line(item: CatalogItem) -> str:
    price = f" ({item.price})" if item.price else ""
    description = f": {item.description}" if item.description else ""
    return f"- {item.name}{price}{description}"


def tagged(tag: str, body: str) -> str:
    return f"<{tag}>\n{body}\n</{tag}>"
