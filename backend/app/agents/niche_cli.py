"""Run the Niche Analyst by hand and save the report to a file (ADR 0025).

With the database, the `generate_niche_report` job writes the weekly report to niche_reports
(app/jobs/niche.py). Without it, the chat reads this file as trend notes when NICHE_REPORT_PATH
points to it.
"""

import argparse
import asyncio
import logging
import time
from datetime import date
from pathlib import Path

import httpx

from app.config import get_settings
from app.llm.client import GeminiChat

from .data.niches import NICHES
from .niche_analyst import HttpRedirectResolver, NicheAnalyst

logger = logging.getLogger("app.agents.niche_cli")


async def run(niche_id: str, out: Path) -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise SystemExit("GEMINI_API_KEY is not set")
    model = GeminiChat.from_api_key(settings.gemini_api_key, settings.gemini_chat_model)
    started = time.perf_counter()
    async with httpx.AsyncClient() as http:
        analyst = NicheAnalyst(model, HttpRedirectResolver(http))
        report = await analyst.report(NICHES[niche_id], date.today())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.model_dump_json(indent=2))
    logger.info(
        "%d insights in %.1fs, written to %s",
        len(report.insights),
        time.perf_counter() - started,
        out,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Write this week's Niche Report to a file.")
    parser.add_argument("--niche", choices=sorted(NICHES), required=True)
    parser.add_argument("--out", type=Path, required=True, help="the report's JSON file")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
    asyncio.run(run(args.niche, args.out))


if __name__ == "__main__":
    main()
