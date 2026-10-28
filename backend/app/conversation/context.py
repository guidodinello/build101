"""What the orchestrator knows about the Business, appended to its system prompt (ADR 0030).

It changes only when the Brand Brain, the Catalog, the notes or the summary change, so the
system prompt stays a stable prefix across turns and Gemini's implicit caching can hit.
"""

from app.knowledge.base import BusinessFacts, BusinessKnowledge, CatalogItem
from app.prompts import tagged as escaped


def render(context: BusinessKnowledge) -> str:
    """The blocks the prompt's "What you know" section describes; empty ones are left out."""
    blocks: list[str] = []
    if context.business:
        blocks.append(tagged("business", business_lines(context.business)))
    if context.brand:
        brand = context.brand.model_dump_json(exclude={"whatsapp_summary"})
        blocks.append(tagged("brand_brain", brand))
        if context.brand_summary_sent:
            blocks.append(tagged("brand_summary_sent", context.brand.whatsapp_summary))
    if context.catalog:
        blocks.append(tagged("catalog", "\n".join(catalog_line(item) for item in context.catalog)))
    if context.notes:
        lines = "\n".join(f"- {note.id}: {note.text}" for note in context.notes)
        blocks.append(tagged("owner_notes", lines))
    if context.trend_notes:
        # Escaped, unlike the blocks above: the notes come from web pages, not from the Owner.
        blocks.append(escaped("trend_notes", context.trend_notes.splitlines()))
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
