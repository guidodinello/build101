from datetime import date

import httpx
import pytest

from app.agents.data.niches import CURATED_WOOD_FURNITURE_UY
from app.agents.niche_analyst import (
    BusinessProfile,
    HttpRedirectResolver,
    NicheAnalyst,
    is_grounding_redirect,
)
from app.config import get_settings
from app.llm.client import GeminiChat

pytestmark = pytest.mark.live

BUSINESS = BusinessProfile(
    "Roble & Co",
    "muebles de madera maciza",
    "Montevideo, Uruguay",
    "Mesas, aparadores y bibliotecas de roble y eucalipto, hechas a medida en un taller propio.",
)


async def test_a_real_niche_report_has_checked_sources() -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is not set")
    model = GeminiChat.from_api_key(settings.gemini_api_key, settings.gemini_chat_model)

    async with httpx.AsyncClient() as http:
        report = await NicheAnalyst(model, HttpRedirectResolver(http)).report(
            BUSINESS, CURATED_WOOD_FURNITURE_UY, date.today()
        )

    assert 3 <= len(report.insights) <= 8
    assert report.summary
    for insight in report.insights:
        assert insight.source_urls
        assert not any(is_grounding_redirect(url) for url in insight.source_urls)
