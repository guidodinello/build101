from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from app.agents.data.niches import CURATED_WOOD_FURNITURE_UY, Niche
from app.agents.niche_analyst import (
    TOOLS,
    HttpRedirectResolver,
    InsightDraft,
    NicheAnalyst,
    NicheReport,
    NicheReportDraft,
    clean_post_idea,
    reference_websites,
    trend_notes,
)
from app.conversation.factory import load_trend_notes
from app.llm.client import Content, Grounded, LLMError, Tool, WebSource

REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AbC123"
LOST_REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/Gone"
ARTICLE = "https://caras.perfil.com/noticias/primavera-2026-una-paleta.phtml"
MONDAY = date(2026, 10, 12)
TODAY = date(2026, 10, 18)  # a Sunday

NICHE = Niche(
    id="test",
    description="Solid-wood furniture",
    location="Uruguay",
    timezone="America/Montevideo",
    reference_websites=("https://www.laiberica.com.uy/", "https://kateiuy.lovable.app"),
    search_themes=("muebles madera maciza Uruguay",),
)


@dataclass
class FakeGroundedModel:
    draft: NicheReportDraft
    sources: list[WebSource] = field(default_factory=list)
    contents: list[list[Content]] = field(default_factory=list)
    tools: list[list[Tool]] = field(default_factory=list)

    async def grounded[T: BaseModel](
        self,
        agent: str,
        system: str,
        content: list[Content],
        schema: type[T],
        thinking_level: str,
        tools: list[Tool],
    ) -> Grounded[T]:
        self.contents.append(content)
        self.tools.append(tools)
        return Grounded(self.draft, self.sources)  # type: ignore[arg-type]


@dataclass
class FakeResolver:
    pages: dict[str, str]
    asked: list[str] = field(default_factory=list)

    async def resolve(self, url: str) -> str | None:
        self.asked.append(url)
        return self.pages.get(url)


def insight(*urls: str, idea: str = "Mostrá la veta del roble de cerca") -> InsightDraft:
    return InsightDraft(
        kind="theme",
        insight="Las tiendas muestran la madera.",
        post_idea=idea,
        source_urls=list(urls),
    )


def analyst_with(
    insights: list[InsightDraft], sources: list[WebSource] | None = None
) -> tuple[NicheAnalyst, FakeGroundedModel, FakeResolver]:
    model = FakeGroundedModel(
        NicheReportDraft(summary=" Esta semana... ", insights=insights), sources or []
    )
    resolver = FakeResolver({REDIRECT: ARTICLE})
    return NicheAnalyst(model, resolver), model, resolver


async def test_sources_are_checked_and_redirects_resolved() -> None:
    analyst, model, resolver = analyst_with(
        [
            insight("https://laiberica.com.uy/ambientes"),  # a reference site's page
            insight(REDIRECT),  # a search result, resolved to the article
            insight("https://blog.example.com/tendencias/"),  # read with url_context
            insight("https://made-up.example.org/trends"),  # nothing returned it: dropped
            insight(LOST_REDIRECT),  # can't be resolved: dropped
        ],
        sources=[WebSource("https://blog.example.com/tendencias")],
    )

    report = await analyst.report(NICHE, TODAY)

    assert [i.source_urls for i in report.insights] == [
        ["https://laiberica.com.uy/ambientes"],
        [ARTICLE],
        ["https://blog.example.com/tendencias/"],
    ]
    assert sorted(resolver.asked) == sorted([REDIRECT, LOST_REDIRECT])
    assert report.week_start == MONDAY
    assert report.summary == "Esta semana..."
    assert model.tools == [TOOLS]


async def test_an_insight_keeps_its_checked_sources_without_repeats() -> None:
    analyst, _, _ = analyst_with(
        [
            insight("https://www.laiberica.com.uy/", "https://laiberica.com.uy", LOST_REDIRECT),
            insight("https://kateiuy.lovable.app"),
            insight(REDIRECT, ARTICLE),
        ]
    )

    report = await analyst.report(NICHE, TODAY)

    assert [i.source_urls for i in report.insights] == [
        ["https://www.laiberica.com.uy/"],
        ["https://kateiuy.lovable.app"],
        [ARTICLE],
    ]


async def test_too_few_sourced_insights_is_an_error() -> None:
    analyst, _, _ = analyst_with(
        [insight("https://kateiuy.lovable.app"), insight("https://made-up.example.org")]
    )

    with pytest.raises(LLMError, match="1 of 2 insights"):
        await analyst.report(NICHE, TODAY)


async def test_at_most_eight_insights_are_kept() -> None:
    analyst, _, _ = analyst_with([insight("https://kateiuy.lovable.app")] * 10)

    report = await analyst.report(NICHE, TODAY)

    assert len(report.insights) == 8


async def test_the_request_names_the_niche_websites_themes_and_date() -> None:
    analyst, model, _ = analyst_with([insight("https://kateiuy.lovable.app")] * 3)

    await analyst.report(NICHE, TODAY)

    text = model.contents[0][0]["text"]
    assert "Niche: Solid-wood furniture. Location: Uruguay." in text
    assert "- https://www.laiberica.com.uy/\n- https://kateiuy.lovable.app" in text
    assert "- muebles madera maciza Uruguay" in text
    assert "Today is 2026-10-18" in text
    assert "business:" not in text.lower()  # one report for the whole niche


def test_reference_websites_skip_repeats_and_stop_at_twenty() -> None:
    sites = ("https://laiberica.com.uy", "https://www.laiberica.com.uy/")
    niche = replace(
        NICHE, reference_websites=(*sites, *(f"https://store{n}.uy" for n in range(25)))
    )

    websites = reference_websites(niche)

    assert len(websites) == 20
    assert websites[0] == "https://laiberica.com.uy"
    assert "https://www.laiberica.com.uy/" not in websites


def test_the_furniture_niche_has_its_reference_sites() -> None:
    assert "https://www.laiberica.com.uy/" in CURATED_WOOD_FURNITURE_UY.reference_websites
    assert "https://kateiuy.lovable.app" in CURATED_WOOD_FURNITURE_UY.reference_websites


@pytest.mark.parametrize(
    "idea",
    [
        "Mostrá la mesa a $U 25.900",
        "Un 20% off en sillas",
        "Anunciá el descuento de primavera",
        "Contá que hay cuotas sin recargo",
        "Lanzalo el 15 de noviembre",
        "Publicalo el 15/11/2026",
    ],
)
def test_a_post_idea_with_prices_discounts_or_dates_is_dropped(idea: str) -> None:
    assert clean_post_idea(idea) is None


@pytest.mark.parametrize(
    "idea", ["Un carrusel con la regla del 80/20", "Antes y después de restaurar 3 sillas"]
)
def test_a_plain_post_idea_is_kept(idea: str) -> None:
    assert clean_post_idea(f" {idea} ") == idea


def test_an_empty_post_idea_is_none() -> None:
    assert clean_post_idea("  ") is None


def sample_report() -> NicheReport:
    return NicheReport.model_validate(
        {
            "week_start": "2026-10-12",
            "summary": "Esta semana pega la madera cálida.",
            "insights": [
                {
                    "kind": "visual",
                    "insight": "Roble con lino.",
                    "post_idea": None,
                    "source_urls": ["https://kateiuy.lovable.app"],
                },
                {
                    "kind": "hook",
                    "insight": "Pieza heredable.",
                    "post_idea": "Abrí con eso.",
                    "source_urls": [ARTICLE],
                },
                {
                    "kind": "format",
                    "insight": "Antes y después.",
                    "post_idea": None,
                    "source_urls": [ARTICLE],
                },
            ],
        }
    )


def test_trend_notes_list_each_insight_with_its_kind() -> None:
    assert trend_notes(sample_report()) == (
        "- [visual] Roble con lino.\n"
        "- [hook] Pieza heredable. Idea: Abrí con eso.\n"
        "- [format] Antes y después."
    )


def test_trend_notes_load_from_a_saved_report(tmp_path: Path) -> None:
    path = tmp_path / "niche-report.json"
    path.write_text(sample_report().model_dump_json())

    assert load_trend_notes(path) == trend_notes(sample_report())
    assert load_trend_notes(None) is None


def resolver_answering(response: httpx.Response | Exception) -> HttpRedirectResolver:
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(response, Exception):
            raise response
        return response

    return HttpRedirectResolver(httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_a_redirect_resolves_to_its_location() -> None:
    resolver = resolver_answering(httpx.Response(302, headers={"location": ARTICLE}))

    assert await resolver.resolve(REDIRECT) == ARTICLE


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html></html>"),
        httpx.Response(302, headers={"location": "/relative"}),
        httpx.Response(404),
        httpx.ConnectError("down"),
    ],
)
async def test_a_redirect_that_does_not_point_to_a_page_resolves_to_none(
    response: httpx.Response | Exception,
) -> None:
    assert await resolver_answering(response).resolve(REDIRECT) is None
