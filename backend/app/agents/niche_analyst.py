"""The Niche Analyst: what is working in a Business's niche this week (ADR 0025).

One grounded Gemini call (url_context + google_search) through `app/llm/client.py`, then code
checks every source: links come from what the tools returned, never from the model's memory.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field

from app.llm.client import GroundedModel, LLMError, Tool, WebSource, text_content

from .data.niches import Niche

logger = logging.getLogger(__name__)

AGENT = "niche_analyst"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "niche_analyst.md").read_text()
TOOLS: list[Tool] = [{"type": "url_context"}, {"type": "google_search"}]

MIN_INSIGHTS = 3
MAX_INSIGHTS = 8
MAX_URLS = 20  # url_context reads up to 20 URLs per request

# Google Search grounding hands out its results as these redirect links, not the page URL
# (hands-on run, docs/research/niche-trend-sources.md).
REDIRECT_HOST = "vertexaisearch.cloud.google.com"
REDIRECT_PATH = "/grounding-api-redirect/"
REDIRECT_TIMEOUT_S = 10.0

# A post idea never carries prices, discounts or dates (agents.md § Niche Analyst).
MONTHS = (
    "enero|febrero|marzo|abril|mayo|junio|julio|agosto|setiembre|septiembre|octubre"
    "|noviembre|diciembre"
)
COMMERCIAL_TERMS = re.compile(
    r"\$|%|\bU\$S\b|\bUSD\b|\bprecios?\b|\bdescuentos?\b|\bofertas?\b|\bcuotas\b"
    rf"|\b\d{{1,2}} de ({MONTHS})\b|\b\d{{1,2}}/\d{{1,2}}/\d{{2,4}}\b",
    re.IGNORECASE,
)

InsightKind = Literal["theme", "format", "hook", "visual"]


class InsightDraft(BaseModel):
    """An insight as the model writes it; its sources are checked before it is kept."""

    kind: InsightKind
    insight: str
    post_idea: str  # empty when there is none (the schema stays simple: no nulls)
    source_urls: list[str]


class NicheReportDraft(BaseModel):
    summary: str
    insights: list[InsightDraft]


class NicheInsight(BaseModel):
    kind: InsightKind
    insight: str  # Spanish, one or two sentences
    post_idea: str | None  # how this Business could use it
    source_urls: list[str] = Field(min_length=1)  # checked against what the tools returned


class NicheReport(BaseModel):
    week_start: date
    summary: str  # Spanish, 3–5 lines, for the chat (F3.7)
    insights: list[NicheInsight] = Field(min_length=MIN_INSIGHTS, max_length=MAX_INSIGHTS)


@dataclass(frozen=True, slots=True)
class BusinessProfile:
    """What the analyst knows about the Business until the Brand Brain exists (T09)."""

    name: str
    category: str
    location: str
    about: str = ""  # products, audience, what sets it apart


class RedirectResolver(Protocol):
    async def resolve(self, url: str) -> str | None: ...


class HttpRedirectResolver:
    """Follows one grounding redirect to the page it points to, without fetching the page."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def resolve(self, url: str) -> str | None:
        try:
            response = await self._client.get(
                url, follow_redirects=False, timeout=REDIRECT_TIMEOUT_S
            )
        except httpx.HTTPError as exc:
            logger.info("grounding redirect not resolved: %s", exc)
            return None
        location = response.headers.get("location")
        if not response.is_redirect or not location or not is_web_url(location):
            return None
        return location


class NicheAnalyst:
    def __init__(self, model: GroundedModel, redirects: RedirectResolver) -> None:
        self._model = model
        self._redirects = redirects

    async def report(
        self,
        business: BusinessProfile,
        niche: Niche,
        today: date,
        owner_websites: list[str] | None = None,
    ) -> NicheReport:
        """This week's Niche Report. Raises `LLMError` when too few insights have a source."""
        websites = reference_websites(niche, owner_websites or [])
        grounded = await self._model.grounded(
            AGENT,
            SYSTEM_PROMPT,
            [text_content(request_text(business, niche, websites, today))],
            NicheReportDraft,
            "medium",
            TOOLS,
        )
        draft = grounded.output
        redirects = {
            url
            for insight in draft.insights
            for url in insight.source_urls
            if is_grounding_redirect(url)
        }
        resolved = await self._resolve(redirects)
        insights = keep_sourced(draft.insights, grounded.sources, websites, resolved)
        if len(insights) < MIN_INSIGHTS:
            raise LLMError(
                f"{AGENT}: {len(insights)} of {len(draft.insights)} insights have a source"
            )
        return NicheReport(
            week_start=week_start(today),
            summary=draft.summary.strip(),
            insights=insights[:MAX_INSIGHTS],
        )

    async def _resolve(self, urls: set[str]) -> dict[str, str]:
        ordered = sorted(urls)
        results = await asyncio.gather(*(self._redirects.resolve(url) for url in ordered))
        return {url: page for url, page in zip(ordered, results, strict=True) if page}


def request_text(business: BusinessProfile, niche: Niche, websites: list[str], today: date) -> str:
    lines = [
        f"Niche: {niche.description}. Location: {niche.location}.",
        "",
        "Reference websites (read each with URL context):",
        *(f"- {url}" for url in websites),
        "",
        "Search themes (search Google for these, in Spanish):",
        *(f"- {theme}" for theme in niche.search_themes),
        "",
        f"The business: {business.name}, {business.category}, in {business.location}.",
    ]
    if business.about:
        lines.append(f"About it: {business.about}")
    lines += ["", f"Today is {today.isoformat()}. Write this week's Niche Report."]
    return "\n".join(lines)


def reference_websites(niche: Niche, owner_websites: list[str]) -> list[str]:
    """The niche's sites, then the ones the Owner named, without repeats, up to 20."""
    seen: dict[str, str] = {}
    for url in [*owner_websites, *niche.reference_websites]:
        if is_web_url(url):
            seen.setdefault(page_key(url), url)
    return list(seen.values())[:MAX_URLS]


def keep_sourced(
    insights: list[InsightDraft],
    sources: list[WebSource],
    websites: list[str],
    resolved: dict[str, str],
) -> list[NicheInsight]:
    """Insights whose sources check out, each source as the real page URL; others dropped.

    A source is kept when the tools returned it (`sources`), when it is a page of a reference
    website, or when it is a grounding redirect that resolved to a page.
    """
    known = {page_key(source.url) for source in sources}
    hosts = {site_host(url) for url in websites}
    kept: list[NicheInsight] = []
    for draft in insights:
        urls: dict[str, str] = {}
        for url in draft.source_urls:
            page = checked_source(url.strip(), known, hosts, resolved)
            if page is not None:
                urls.setdefault(page_key(page), page)
        if not urls:
            logger.info("dropped an insight with no checked source: %s", draft.source_urls)
            continue
        kept.append(
            NicheInsight(
                kind=draft.kind,
                insight=draft.insight.strip(),
                post_idea=clean_post_idea(draft.post_idea),
                source_urls=list(urls.values()),
            )
        )
    return kept


def checked_source(
    url: str, known: set[str], hosts: set[str], resolved: dict[str, str]
) -> str | None:
    if is_grounding_redirect(url):
        # Either we can name the page, or the link is useless: it expires and says nothing.
        return resolved.get(url)
    if not is_web_url(url):
        return None
    if page_key(url) in known or site_host(url) in hosts:
        return url
    return None


def clean_post_idea(idea: str) -> str | None:
    idea = idea.strip()
    if not idea:
        return None
    if COMMERCIAL_TERMS.search(idea):
        logger.info("dropped a post idea with a price, discount or date: %s", idea)
        return None
    return idea


def trend_notes(report: NicheReport) -> str:
    """The report as the trend notes input of the agents that make content."""
    lines = []
    for insight in report.insights:
        line = f"- [{insight.kind}] {insight.insight}"
        if insight.post_idea:
            line += f" Idea: {insight.post_idea}"
        lines.append(line)
    return "\n".join(lines)


def week_start(today: date) -> date:
    return today - timedelta(days=today.weekday())


def is_web_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def is_grounding_redirect(url: str) -> bool:
    parts = urlsplit(url)
    return parts.hostname == REDIRECT_HOST and parts.path.startswith(REDIRECT_PATH)


def site_host(url: str) -> str:
    """The site's host without `www.` or `mobile.` (La Ibérica also serves mobile.laiberica)."""
    host = urlsplit(url).hostname or ""
    return host.removeprefix("www.").removeprefix("mobile.")


def page_key(url: str) -> str:
    """Compares pages: ignores the scheme, `www.`, a trailing slash and the fragment."""
    parts = urlsplit(url)
    query = f"?{parts.query}" if parts.query else ""
    return f"{site_host(url)}{parts.path.rstrip('/')}{query}"
