from .base import Vocabulary

MOCK_TRANSCRIPT = "Quiero un post para la promo del sábado"


class MockTranscriber:
    """A fixed transcript, for local development (TRANSCRIBE_FALLBACK=mock)."""

    def __init__(self, text: str = MOCK_TRANSCRIPT) -> None:
        self.text = text
        self.calls: list[tuple[int, str, Vocabulary]] = []

    async def transcribe(self, audio: bytes, mime_type: str, vocabulary: Vocabulary) -> str:
        self.calls.append((len(audio), mime_type, vocabulary))
        return self.text
