import logging
from functools import cache
from pathlib import Path

from app.channels.base import ChannelError, ChannelPort, InboundMessage
from app.channels.inbound import mask
from app.copy import messages_es
from app.llm.client import ChatModel, LLMError, user_step

from .history import InMemoryHistory

logger = logging.getLogger(__name__)

AGENT = "orchestrator"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


@cache
def system_prompt(assistant_name: str) -> str:
    return SYSTEM_PROMPT_PATH.read_text().format(assistant_name=assistant_name)


class ChatHandler:
    """InboundHandler that answers free text and voice notes with the LLM.

    Orchestrator v0: no tools yet (T19), and no onboarding or button routing (T23, T18),
    so buttons, photos and other kinds get fixed messages.
    """

    def __init__(self, model: ChatModel, history: InMemoryHistory, assistant_name: str) -> None:
        self._model = model
        self._history = history
        self._system = system_prompt(assistant_name)

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        async with self._history.lock(message.sender):
            try:
                await channel.mark_read(message.message_id, typing=True)
            except ChannelError:
                logger.warning("mark_read failed for %s", message.message_id, exc_info=True)
            await channel.send_text(message.sender, await self._answer(message))

    async def _answer(self, message: InboundMessage) -> str:
        match message.kind:
            case "text" if message.text:
                return await self._llm_turn(message.sender, message.text)
            case "audio" if message.audio and message.audio.provider_transcript:
                # ADR 0021: a voice note is handled as its transcript. The Gemini fallback
                # transcriber (TranscriberPort) isn't built yet, so no transcript = unclear.
                return await self._llm_turn(message.sender, message.audio.provider_transcript)
            case "audio":
                return messages_es.AUDIO_UNCLEAR
            case "button":
                return messages_es.STALE_BUTTON
            case "image":
                return messages_es.PHOTO_NOT_SAVED_YET
            case _:
                return messages_es.UNSUPPORTED_MEDIA

    async def _llm_turn(self, sender: str, text: str) -> str:
        user = user_step(text)
        try:
            reply = await self._model.reply(
                AGENT, self._system, [*self._history.get(sender), user], thinking_level="low"
            )
        except LLMError:
            logger.warning("%s failed for %s", AGENT, mask(sender), exc_info=True)
            return messages_es.REPLY_FAILED
        # Only a completed turn enters the history, so a failure leaves no dangling user step.
        self._history.extend(sender, [user, *reply.steps])
        return reply.text
