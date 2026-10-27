"""Prices and discounts in a draft that the Owner never gave: agents never invent facts.

The draft prompt forbids them; this is the check in code. A figure counts as given when it appears
in the brief, the Brand Brain, the Catalog, the Owner's notes or the Business's facts.
"""

import re
from dataclasses import asdict

from app.knowledge.base import BusinessKnowledge

NUMBER = r"\d[\d.,]*"
CURRENCY = r"(?:u\$s|us\$|usd|uyu|\$u|\$)"
# a promo ("2x1"), a percentage, or an amount next to a currency or a promo word
FIGURE = re.compile(
    rf"\b(?P<promo>\d+\s?x\s?\d+)\b"
    rf"|(?P<percent>{NUMBER})\s?%"
    rf"|{CURRENCY}\s?(?P<before>{NUMBER})"
    rf"|(?P<after>{NUMBER})\s?(?:{CURRENCY}|pesos|d[oó]lares|off|cuotas|sin inter[eé]s)\b",
    re.IGNORECASE,
)
SEPARATORS = re.compile(r"[.,]")
DECIMALS = re.compile(r"[.,]\d{1,2}$")
ANY_NUMBER = re.compile(NUMBER)


def key(figure: re.Match[str]) -> str:
    promo = figure.group("promo")
    if promo:
        return re.sub(r"\s", "", promo.lower())
    number = figure.group("percent") or figure.group("before") or figure.group("after")
    return digits(number)


def digits(number: str) -> str:
    """The digits of an amount without separators or cents: `1.250,50` and `1250` are the same."""
    return SEPARATORS.sub("", DECIMALS.sub("", number.rstrip(".,")))


def unsupported_figures(draft: str, given: str) -> list[str]:
    """The figures of `draft` that appear nowhere in `given`, in order, without repeats."""
    known = {digits(number) for number in ANY_NUMBER.findall(given)}
    known |= {key(figure) for figure in FIGURE.finditer(given)}
    found: list[str] = []
    for figure in FIGURE.finditer(draft):
        text = figure.group(0).strip()
        if key(figure) not in known and text not in found:
            found.append(text)
    return found


def given_facts(brief: str, known: BusinessKnowledge, notes: list[str] | None = None) -> str:
    """Everything the Owner told the Agency that a draft may state figures from."""
    parts = [brief, *(notes or [])]
    if known.brand is not None:
        parts.append(known.brand.model_dump_json(exclude={"whatsapp_summary"}))
    parts.extend(f"{item.name} {item.price or ''} {item.description}" for item in known.catalog)
    if known.business is not None:
        parts.extend(str(value) for value in asdict(known.business).values() if value)
    return "\n".join(parts)
