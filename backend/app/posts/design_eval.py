"""Design eval (ADR 0035): the same briefs through the Art Director, the image service, the
renderer and the Design Critic, saved for a blind side-by-side comparison.

    uv run python -m app.posts.design_eval run --label flash --out ../.design-eval
    uv run python -m app.posts.design_eval run --label opus --art-director claude-opus-5-5 \\
        --critic claude-opus-5-5 --out ../.design-eval
    uv run python -m app.posts.design_eval compare ../.design-eval/flash ../.design-eval/opus

Each run calls the real services from `.env` (IMAGE_GEN=gemini, RENDERER=takumi): it costs one
design call, one image per slide and one review per case.
"""

import argparse
import asyncio
import json
import logging
import random
import time
from html import escape
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from app.agents.schemas import BrandBrain
from app.carousel.generator import CarouselGenerator
from app.config import get_settings
from app.imagegen.factory import build_image_gen
from app.llm.client import GeminiChat
from app.llm.factory import build_structured
from app.rendering.factory import build_renderer
from app.rendering.slides import render_slides

from .critic import DesignCritic
from .drafts import PostDrafter
from .maker import reviewed

logger = logging.getLogger("app.posts.design_eval")

EVAL_DIR = Path(__file__).resolve().parents[2] / "evals" / "design"
NO_CRITIC = "none"


class EvalCase(BaseModel):
    id: str
    brief: str
    photos: list[Path]  # relative to the cases file
    slide_count: int | None = None


async def run_case(
    case: EvalCase,
    cases_dir: Path,
    brand: BrandBrain,
    drafter: PostDrafter,
    critic: DesignCritic | None,
    out: Path,
) -> dict[str, object]:
    settings = get_settings()
    generator = CarouselGenerator(build_image_gen(settings))
    renderer = build_renderer(settings)
    references = [(cases_dir / photo).read_bytes() for photo in case.photos]
    count = case.slide_count or len(references)
    started = time.perf_counter()
    copy, brief = await drafter.design(
        case.brief, references, [f"f{n}" for n in range(1, len(references) + 1)], count, brand
    )
    drafted = time.perf_counter()
    per_slide = (
        {n: [data] for n, data in enumerate(references, start=1)}
        if len(references) == count
        else None
    )
    scenes = await generator.generate(copy, brief, references, per_slide)
    generated = time.perf_counter()
    rendered = await render_slides(renderer, copy, brief, scenes, brand, None)
    out.mkdir(parents=True, exist_ok=True)
    for n, slide in enumerate(rendered, start=1):
        (out / f"draft-{n}.jpg").write_bytes(slide.image)
        if slide.report:
            (out / f"draft-{n}.report.json").write_text(slide.report.model_dump_json(indent=2))
    revision = await reviewed(critic, copy, brief, rendered) if critic else None
    if revision is not None:
        brief = revision.brief
        if revision.new_scenes:
            scenes = await generator.redo(
                copy, brief, references, scenes, revision.new_scenes, per_slide
            )
        rendered = await render_slides(renderer, copy, brief, scenes, brand, None)
    for n, slide in enumerate(rendered, start=1):
        (out / f"slide-{n}.jpg").write_bytes(slide.image)
    (out / "spec.json").write_text(
        json.dumps(
            {"copy": copy.model_dump(), "brief": brief.model_dump()}, ensure_ascii=False, indent=2
        )
    )
    return {
        "id": case.id,
        "family": brief.family,
        "slides": len(rendered),
        "revised": revision is not None,
        "new_scenes": revision.new_scenes if revision else [],
        "seconds": {
            "design": round(drafted - started, 1),
            "scenes": round(generated - drafted, 1),
            "total": round(time.perf_counter() - started, 1),
        },
    }


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise SystemExit("the design eval needs GEMINI_API_KEY")
    chat = GeminiChat.from_api_key(settings.gemini_api_key, settings.gemini_chat_model)
    drafter = PostDrafter(chat, build_structured(settings, args.art_director, chat))
    critic = (
        None
        if args.critic == NO_CRITIC
        else DesignCritic(build_structured(settings, args.critic, chat))
    )
    cases_file: Path = args.cases
    cases = TypeAdapter(list[EvalCase]).validate_json(cases_file.read_text())
    brand = BrandBrain.model_validate_json((cases_file.parent / "brand.json").read_text())
    if args.only:
        cases = [case for case in cases if case.id in args.only]
    out: Path = args.out / args.label
    results = []
    for case in cases:
        logger.info("case %s", case.id)
        results.append(
            await run_case(case, cases_file.parent, brand, drafter, critic, out / case.id)
        )
    summary = {
        "art_director": args.art_director or settings.gemini_chat_model,
        "critic": args.critic or settings.gemini_chat_model,
        "cases": results,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    logger.info("saved %d cases to %s", len(results), out)


def compare(args: argparse.Namespace) -> None:
    """A blind A/B page: each case's two carousels in random order; the key is a separate file."""
    first, second = args.runs
    rng = random.Random(args.seed)
    key: dict[str, dict[str, str]] = {}
    sections = []
    cases = sorted(path.name for path in first.iterdir() if (second / path.name).is_dir())
    for case in cases:
        pair = [first, second]
        rng.shuffle(pair)
        key[case] = {"A": pair[0].name, "B": pair[1].name}
        rows = []
        for label, run_dir in zip("AB", pair, strict=True):
            slides = sorted((run_dir / case).glob("slide-*.jpg"))
            images = "".join(
                f'<img src="{escape(str(slide.resolve()))}" width="270">' for slide in slides
            )
            rows.append(f"<h3>{label}</h3><div class='row'>{images}</div>")
        sections.append(f"<section><h2>{escape(case)}</h2>{''.join(rows)}</section>")
    style = (
        "body{font-family:sans-serif;margin:24px}.row{display:flex;gap:8px;overflow-x:auto}"
        "section{margin-bottom:48px}"
    )
    page = (
        f"<!doctype html><meta charset='utf-8'><title>Design eval</title><style>{style}</style>"
        f"<p>Score each carousel 1–5 for a professional look before opening key.json.</p>"
        f"{''.join(sections)}"
    )
    args.out.write_text(page)
    (args.out.parent / "key.json").write_text(json.dumps(key, indent=2))
    logger.info("compare page at %s, key next to it", args.out)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(prog="design_eval")
    commands = parser.add_subparsers(dest="command", required=True)
    runner = commands.add_parser("run", help="design every case with one model setup")
    runner.add_argument("--label", required=True)
    runner.add_argument("--out", type=Path, required=True)
    runner.add_argument("--cases", type=Path, default=EVAL_DIR / "cases.json")
    runner.add_argument("--art-director", default=None, help="unset: GEMINI_CHAT_MODEL")
    runner.add_argument("--critic", default=None, help=f"unset: GEMINI_CHAT_MODEL; {NO_CRITIC}")
    runner.add_argument("--only", nargs="*", default=None, help="case ids")
    comparer = commands.add_parser("compare", help="blind A/B page of two runs")
    comparer.add_argument("runs", type=Path, nargs=2)
    comparer.add_argument("--out", type=Path, default=Path("design-eval.html"))
    comparer.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    if args.command == "run":
        asyncio.run(run(args))
    else:
        compare(args)


if __name__ == "__main__":
    main()
