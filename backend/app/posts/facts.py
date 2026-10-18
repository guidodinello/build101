import re

MONEY = re.compile(
    r"(?:U\$S|US\$|\$|UYU)\s?\d[\d.,]*|\d[\d.,]*\s?(?:%|(?:pesos|dólares|dolares|USD|UYU)\b)",
    re.IGNORECASE,
)
DATE = re.compile(r"\b(?:19|20)\d{2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def figures(text: str) -> set[str]:
    """Prices, percentages, years and dates in `text`, as bare digits (`$1.500` → `1500`)."""
    found = {
        re.sub(r"\D", "", match) for pattern in (MONEY, DATE) for match in pattern.findall(text)
    }
    found.discard("")
    return found


def drop_unsupported_figures(caption: str, *sources: str) -> str:
    """Remove the sentences with a price, discount or date that no source states.

    Agents never invent facts (AGENTS.md): the sources are the Owner's brief and the Brand Brain.
    """
    allowed = set().union(*(figures(source) for source in sources))
    kept: list[str] = []
    for line in caption.split("\n"):
        sentences = SENTENCE_END.split(line)
        kept.append(" ".join(s for s in sentences if figures(s) <= allowed))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
