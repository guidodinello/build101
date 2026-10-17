import pytest

from app.config import get_settings
from app.llm.client import GeminiChat, user_step

pytestmark = pytest.mark.live


async def test_gemini_remembers_the_previous_turn() -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is not set")
    model = GeminiChat.from_api_key(settings.gemini_api_key, settings.gemini_chat_model)
    system = "Answer in one short sentence of Rioplatense Spanish."
    first_user = user_step("Hola, tengo una mueblería. ¿Me ayudás con Instagram?")

    first = await model.reply("live_test", system, [first_user], thinking_level="low")
    second = await model.reply(
        "live_test",
        system,
        [first_user, *first.steps, user_step("¿Qué te dije que vendo?")],
        thinking_level="low",
    )

    assert first.text
    assert "mueble" in second.text.lower()
