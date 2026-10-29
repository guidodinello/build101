from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class TranscriptionError(Exception):
    """The transcriber gave no answer: API error, timeout or an output that isn't a transcript."""


@dataclass(frozen=True, slots=True)
class Vocabulary:
    """Words the Owner is likely to say, so the transcriber spells them right. Data, never
    instructions."""

    business_name: str | None = None
    products: tuple[str, ...] = ()


@runtime_checkable
class TranscriberPort(Protocol):
    async def transcribe(self, audio: bytes, mime_type: str, vocabulary: Vocabulary) -> str:
        """The verbatim transcript of a voice note; empty when nothing is said."""
        ...
