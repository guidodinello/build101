"""What a model call costs, from a dated price table (COST-1, issue #205).

Prices are US$ on the paid Standard tier, from the audit's price table
(docs/research/audit-2026-10/unit-economics.md, read 2026-10-19 from
https://ai.google.dev/gemini-api/docs/pricing). A model or image size missing here is costed as
None, never as 0: an unknown price must not read as free.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .usage import Usage

PER_MILLION = Decimal(1_000_000)
# Flex is half price (unit-economics.md); Priority is 1.8x (models.md, MOD-12)
TIER_MULTIPLIERS = {"standard": Decimal(1), "flex": Decimal("0.5"), "priority": Decimal("1.8")}


@dataclass(frozen=True, slots=True)
class Price:
    since: date
    input: Decimal = Decimal(0)  # per 1M uncached input tokens
    cached: Decimal = Decimal(0)  # per 1M cached input tokens
    output: Decimal = Decimal(0)  # per 1M output tokens, thinking included
    per_image: tuple[tuple[str, Decimal], ...] = ()  # by image size ("1K", "2K", "4K")
    per_second: Decimal = Decimal(0)  # video


# Per model, newest last
PRICES: dict[str, tuple[Price, ...]] = {
    "gemini-3.8-flash": (
        Price(date(2026, 1, 1), Decimal("0.75"), Decimal("0.075"), Decimal("3.75")),
        Price(date(2027, 1, 1), Decimal("1.50"), Decimal("0.15"), Decimal("7.50")),
    ),
    "gemini-3.5-flash-lite": (
        Price(date(2026, 1, 1), Decimal("0.30"), Decimal("0.03"), Decimal("2.50")),
    ),
    "gemini-nano-banana-2.1": (
        Price(
            date(2026, 1, 1),
            input=Decimal("1.50"),
            cached=Decimal("1.50"),
            output=Decimal("7.50"),
            per_image=(
                ("1K", Decimal("0.0336")),
                ("2K", Decimal("0.0504")),
                ("4K", Decimal("0.113")),
            ),
        ),
    ),
    # 720p, ADR 0033
    "veo-3.1-lite-generate-preview": (Price(date(2026, 1, 1), per_second=Decimal("0.05")),),
}


def price_on(model: str, day: date) -> Price | None:
    in_force = [price for price in PRICES.get(model, ()) if price.since <= day]
    return in_force[-1] if in_force else None


def cost_usd(model: str, usage: Usage, day: date) -> Decimal | None:
    price = price_on(model, day)
    multiplier = TIER_MULTIPLIERS.get(usage.service_tier or "standard")
    if price is None or multiplier is None:
        return None
    cached = usage.cached_tokens or 0
    uncached = max((usage.input_tokens or 0) - cached, 0)
    output = (usage.output_tokens or 0) + (usage.thought_tokens or 0)
    tokens = uncached * price.input + cached * price.cached + output * price.output
    cost = tokens / PER_MILLION + (usage.video_seconds or 0) * price.per_second
    if usage.image_count:
        per_image = dict(price.per_image).get(usage.image_size or "")
        if per_image is None:
            return None
        cost += usage.image_count * per_image
    return (cost * multiplier).quantize(Decimal("0.000001"))
