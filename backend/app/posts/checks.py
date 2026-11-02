"""Rules every Post draft goes through in code, so they don't rest on the prompt alone (#194).

Hashtags are cleaned and capped at Instagram's limit. A price, percentage or date the drafter
wrote is kept only when its digits appear in a valid source: the brief, the Brand Brain, the
Catalog prices or the Owner notes (AGENTS.md: agents never invent facts).
"""

import logging
import re

logger = logging.getLogger(__name__)

# Instagram allows 5 hashtags per Post since December 2025.
MAX_HASHTAGS = 5

_NUMBER = r"\d+(?:[.,]\d+)*"
_MONTHS = (
    "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|"
    "noviembre|diciembre"
)
FIGURE = re.compile(
    rf"(?:US\$|U\$S|\$U|\$)\s?{_NUMBER}"
    rf"|{_NUMBER}\s?(?:%|por\s?ciento\b)(?:\s?off\b|\s+de\s+descuento\b)?"
    rf"|{_NUMBER}\s?(?:pesos|d[oó]lares|usd|uyu)\b"
    rf"|\b\d{{1,2}}/\d{{1,2}}(?:/\d{{2,4}})?\b"
    rf"|\b\d{{1,2}}\s+de\s+(?:{_MONTHS})\b",
    re.IGNORECASE,
)
_SOURCE_NUMBER = re.compile(r"\d+(?:[.,/]\d+)*")
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
# Words left dangling at the end of a headline once its figure is cut ("Sillas a").
_DANGLING = {"a", "al", "con", "de", "del", "desde", "el", "en", "hasta", "la", "por", "y"}


def clean_hashtags(tags: list[str]) -> list[str]:
    """Each one `#` plus letters, digits or `_`, no number-only tags, no case-insensitive
    repeats, at most `MAX_HASHTAGS`, in the drafter's order."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        word = "".join(char for char in tag if char.isalnum() or char == "_")
        key = word.casefold()
        if not word or word.isdigit() or key in seen:
            continue
        seen.add(key)
        cleaned.append(f"#{word}")
        if len(cleaned) == MAX_HASHTAGS:
            break
    if cleaned != tags:
        logger.info("hashtags cleaned: %d from the draft, %d kept", len(tags), len(cleaned))
    return cleaned


def digits(text: str) -> str:
    """The number a figure states, so "$4.900", "4900" and "4,900" compare equal."""
    return re.sub(r"\D", "", text).lstrip("0") or "0"


def known_figures(sources: list[str]) -> set[str]:
    """Every number in the valid sources, compared by its digits."""
    return {digits(number) for text in sources for number in _SOURCE_NUMBER.findall(text)}


def unsourced(text: str, known: set[str]) -> list[str]:
    return [match.group() for match in FIGURE.finditer(text) if digits(match.group()) not in known]


def drop_unsourced(text: str, known: set[str], field: str) -> str:
    """`text` without the sentences that state a figure no source has; line breaks stay."""
    removed = 0
    lines: list[str] = []
    for line in text.split("\n"):
        kept: list[str] = []
        for sentence in _SENTENCE_END.split(line):
            if unsourced(sentence, known):
                removed += 1
            else:
                kept.append(sentence)
        if kept or not line.strip():
            lines.append(" ".join(kept))
    if not removed:
        return text
    logger.info("removed %d sentence(s) with an unsourced figure from the %s", removed, field)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def cut_unsourced(text: str, known: set[str], field: str) -> str:
    """`text` with only its unsourced figures cut, for a slot that can't be left empty."""
    cut = FIGURE.sub(lambda m: "" if digits(m.group()) not in known else m.group(), text)
    if cut == text:
        return text
    logger.info("cut an unsourced figure from the %s", field)
    words = cut.split()
    while words and words[-1].strip(",:;-–—").casefold() in _DANGLING | {""}:
        words.pop()
    return " ".join(words).strip(" ,:;-–—")
