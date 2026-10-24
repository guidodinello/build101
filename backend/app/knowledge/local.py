"""The adapter of `Knowledge` for runs without a database (local runs, tests)."""

import logging
import uuid
from pathlib import Path
from typing import Protocol

from app.agents.niche_analyst import NicheReport, trend_notes

from .base import BusinessKnowledge, CatalogItem, Note

logger = logging.getLogger(__name__)


class NoteSource(Protocol):
    async def list(self, sender: str) -> list[Note]: ...


class SummarySource(Protocol):
    async def summary(self, sender: str) -> str | None: ...


class LocalKnowledge:
    """The notes and the summary the chat keeps in memory, and the same trend notes for every
    sender (`NICHE_REPORT_PATH`). There is no Business row, so no brand, catalog or facts."""

    def __init__(
        self, notes: NoteSource, history: SummarySource, trend_notes: str | None = None
    ) -> None:
        self._notes = notes
        self._history = history
        self._trend_notes = trend_notes

    async def of(self, sender: str) -> BusinessKnowledge:
        return BusinessKnowledge(
            notes=await self._notes.list(sender),
            summary=await self._history.summary(sender),
            trend_notes=self._trend_notes,
        )

    async def products(self, sender: str, asset_ids: list[uuid.UUID]) -> list[CatalogItem]:
        return []


def load_trend_notes(path: Path | None) -> str | None:
    """The saved Niche Report's insights as trend notes; a missing file is a config error."""
    if path is None:
        return None
    report = NicheReport.model_validate_json(path.read_text())
    logger.info("trend notes from the Niche Report of the week of %s", report.week_start)
    return trend_notes(report)
