"""Whether the Owner's words explicitly approve a post (ADR 0007), decided without the LLM."""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

from app.posts.store import Post

Intent = Literal["approve", "approve_later", "none"]

PRONOUNS = ("lo", "la", "los", "las")
APPROVE_STEMS = ("subi", "publica", "postea")  # imperative: "subilo" (accents are stripped)
INFINITIVE_STEMS = ("subir", "publicar", "postear")  # "ya podés subirlo"
APPROVE_WORDS = frozenset(
    {f"{stem}{pronoun}" for stem in (*APPROVE_STEMS, *INFINITIVE_STEMS) for pronoun in PRONOUNS}
    | {"aprobado", "aprobada", "apruebo"}
)
NEGATIONS = frozenset({"no", "nunca", "todavia", "aun"})
NOW_WORDS = frozenset({"ahora", "ya"})
TIME_WORDS = frozenset(
    {"manana", "tarde", "noche", "hs", "lunes", "martes", "miercoles", "jueves", "viernes"}
    | {"sabado", "domingo", "hoy"}
    | {"despues", "luego", "cuando", "rato", "ratito"}  # "subilo después", "cuando termine"
)
# Asking about publishing, or only willing to: when unsure it is not an approval.
QUESTION_WORDS = frozenset({"como", "puedo", "podes", "puedes", "debo", "deberia", "quiero"})
CLOCK = re.compile(r"\b\d{1,2}[:.]\d{2}\b|\ba las\b")  # "18:30", "a las 8"
ORDINALS = {
    "primero": 1,
    "primera": 1,
    "segundo": 2,
    "segunda": 2,
    "tercero": 3,
    "tercera": 3,
    "cuarto": 4,
    "cuarta": 4,
    "quinto": 5,
    "quinta": 5,
}
LAST_WORDS = frozenset({"ultimo", "ultima"})
# A whole reply made of these answers yes to the publish question the Owner was just asked.
YES_WORDS = frozenset(
    {"si", "dale", "ok", "okay", "oka", "okey", "va", "joya", "perfecto", "listo", "genial"}
    | {"buenisimo", "barbaro", "excelente", "mandale", "metele", "adelante", "claro", "obvio"}
    | {"bueno", "bien", "seguro", "sale", "anda", "andale"}
)
YES_FILLER = frozenset(
    {"de", "una", "nomas", "ya", "ahora", "porfa", "por", "favor", "gracias", "para", "che"}
    | {"esta", "asi", "todo", "que", "lo", "la", "re", "mil", "muy"}
)
YES_EMOJI = frozenset({"👍", "👌", "✅", "🙌", "💪"})
# The question a reply ends on when it offers to publish: "¿Lo subo?", "¿Lo publico ya?"
# (`asks_to_publish` checks it is the reply's last sentence).
PUBLISH_QUESTION = re.compile(
    r"\b(lo|la|los|las) (subo|publico|subimos|publicamos)\b"
    r"|\b(subirlo|subirla|subirlos|subirlas|publicarlo|publicarla|publicarlos|publicarlas)\b"
)
KEYCAP = re.compile(r"[0-9#*]\ufe0f?\u20e3")  # "1️⃣": a digit that is an emoji
# Everything after the last word: spaces, "?", "!", emoji, WhatsApp's _*~ formatting.
TRAILING_NOISE = re.compile(r"[\W_]+$")
# A sentence ends at ".", "!", "?" or "…" before a space, at a line break, or at "?¿" / "!¡":
# not at the dot of "$1.500" or "x.com".
SENTENCE_END = re.compile(r"[.!?…]+\s|\n|(?<=[?!])(?=[¿¡])")
ORDINAL_FILLER = frozenset({"el", "la", "lo", "los", "las", "numero", "opcion", "subi", "subo"})
CAPTION_START_CHARS = 60


def plain(text: str) -> str:
    """Lowercase, no accents, no letter repeated 3+ times ("Súbiloooo" -> "subilo")."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"(.)\1{2,}", r"\1", stripped)


def normalize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", plain(text))


def classify(text: str) -> Intent:
    """ "subilo" and its close variants approve; praise alone never does."""
    words = normalize(text)
    if not APPROVE_WORDS.intersection(words) or NEGATIONS.intersection(words):
        return "none"
    if "?" in text or QUESTION_WORDS.intersection(words):
        return "none"
    wants_later = TIME_WORDS.intersection(words) or CLOCK.search(plain(text))
    return "approve_later" if wants_later and not NOW_WORDS.intersection(words) else "approve"


def is_yes(text: str) -> bool:
    """A reply that is only a yes: "sí", "dale!", "ok, de una", "👍"."""
    if "?" in text:
        return False
    words = normalize(text)
    if not words:
        return any(emoji in text for emoji in YES_EMOJI)
    return bool(YES_WORDS.intersection(words)) and all(
        word in YES_WORDS or word in YES_FILLER for word in words
    )


def asks_to_publish(text: str) -> bool:
    """Whether the assistant's message ends by asking the Owner if it should publish a post.

    Only the last sentence counts: a publish question in the middle of a reply (or followed by
    another question) must not turn the Owner's next "bien" into an approval.
    """
    body = plain(KEYCAP.sub("", text))
    ending = TRAILING_NOISE.search(body)
    if ending is None or "?" not in ending.group():  # "¿Lo subo? 🙌" still ends on its question
        return False
    last_sentence = SENTENCE_END.split(body[: ending.start()])[-1]
    return PUBLISH_QUESTION.search(last_sentence) is not None


def ordinal(text: str, count: int) -> int | None:
    """The 1-based post number a short reply names ("2", "la segunda", "el último"), if any."""
    words = [word for word in normalize(text) if word not in ORDINAL_FILLER]
    if len(words) != 1:
        return None
    word = words[0]
    number = int(word) if word.isdigit() else ORDINALS.get(word, count if word in LAST_WORDS else 0)
    return number if 1 <= number <= count else None


@dataclass(frozen=True, slots=True)
class Approval:
    """What this turn's message allows: the one post to publish, or why nothing may be.

    `approve_post` publishes only the post named here, whatever the model passes.
    """

    post_id: str | None = None
    reason: str = "approval_not_explicit"
    pending: list[dict[str, Any]] = field(default_factory=list)


def decide(
    text: str,
    pending: list[Post],
    listed: list[str] | None,
    has_photos: bool,
    offered: str | None = None,
) -> tuple[Approval, list[str] | None]:
    """The Approval for one turn and the post ids the next turn may name by number.

    `listed`: the ids of the numbered list the Owner was last shown, in that order. A number is
    resolved against it, not against `pending`, which may have changed since: a post that is no
    longer pending is not approved, and the number never slides to another post.

    `has_photos`: photos came with this turn or arrived after the pending posts, so "subilas
    así" is a post request, not an approval of an older post.

    `offered`: the post the assistant's last message asked to publish ("¿Lo subo?"), so a bare
    "sí" or "dale" is an explicit answer to that question.
    """
    if has_photos:
        return Approval(), None
    if listed and (number := ordinal(text, len(listed))):
        return approve_if_pending(listed[number - 1], pending), None
    if offered and is_yes(text):
        return approve_if_pending(offered, pending), None
    match classify(text):
        case "approve" if len(pending) == 1:
            return Approval(post_id=pending[0].id), None
        case "approve" if pending:
            return (
                Approval(reason="several_pending", pending=numbered(pending)),
                [post.id for post in pending],
            )
        case "approve":
            return Approval(reason="no_pending_post"), None
        case "approve_later":
            return Approval(reason="scheduling_not_available"), None
        case _:
            return Approval(), None


def approve_if_pending(post_id: str, pending: list[Post]) -> Approval:
    if any(post.id == post_id for post in pending):
        return Approval(post_id=post_id)
    return Approval(reason="post_not_pending")


def numbered(pending: list[Post]) -> list[dict[str, Any]]:
    return [
        {
            "n": number,
            "post_id": post.id,
            "format": post.format,
            "caption_start": post.caption[:CAPTION_START_CHARS],
        }
        for number, post in enumerate(pending, start=1)
    ]
