import argparse
import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config import get_settings
from app.imagegen.base import GeneratedImage, ImageGenPort
from app.imagegen.factory import build_image_gen
from app.media import images
from app.rendering.factory import build_renderer
from app.rendering.slides import render_slides

from .generator import CarouselGenerator
from .schemas import CarouselBrief, CarouselCopy

logger = logging.getLogger("app.carousel.cli")


@dataclass(slots=True)
class CallRecord:
    seconds: float
    width: int
    height: int
    usage: dict[str, int]


@dataclass(slots=True)
class RecordingImageGen:
    inner: ImageGenPort
    records: list[CallRecord] = field(default_factory=list)

    async def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        style_image: bytes | None = None,
        *,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
    ) -> GeneratedImage:
        started = time.perf_counter()
        generated = await self.inner.generate(
            prompt,
            reference_images,
            style_image,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
        width, height = images.image_size(generated.data)
        self.records.append(
            CallRecord(time.perf_counter() - started, width, height, generated.usage)
        )
        return generated


async def run(
    spec_path: Path, photo_paths: list[Path], out_dir: Path, slide_count: int | None
) -> None:
    spec = json.loads(spec_path.read_text())
    copy = CarouselCopy.model_validate(spec["copy"])
    brief = CarouselBrief.model_validate(spec["brief"])
    if slide_count is not None:
        copy = copy.model_copy(update={"slides": copy.slides[:slide_count]})
        brief = brief.model_copy(update={"slides": brief.slides[:slide_count]})

    settings = get_settings()
    image_gen = RecordingImageGen(build_image_gen(settings))
    started = time.perf_counter()
    slides = await CarouselGenerator(image_gen).generate(
        copy, brief, [path.read_bytes() for path in photo_paths]
    )
    total_seconds = time.perf_counter() - started
    designed = await render_slides(build_renderer(settings), copy, brief, slides, None, None)

    out_dir.mkdir(parents=True, exist_ok=True)
    for slide, image in zip(slides, designed, strict=True):
        (out_dir / f"scene-{slide.index}.jpg").write_bytes(slide.image)
        (out_dir / f"slide-{slide.index}.jpg").write_bytes(image)
        (out_dir / f"slide-{slide.index}.prompt.txt").write_text(slide.prompt)
    report = {
        "total_seconds": round(total_seconds, 1),
        "calls": [asdict(record) for record in image_gen.records],
        "slides": [
            {"index": slide.index, "model": slide.model, "attempts": slide.attempts}
            for slide in slides
        ],
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    for record in image_gen.records:
        logger.info(
            "call: %.1fs, raw %dx%d, usage %s",
            record.seconds,
            record.width,
            record.height,
            record.usage,
        )
    logger.info("%d slides in %.1fs, written to %s", len(slides), total_seconds, out_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a carousel from a copy + brief spec.")
    parser.add_argument("--spec", type=Path, required=True, help="JSON with 'copy' and 'brief'")
    parser.add_argument("--photos", type=Path, nargs="+", required=True, help="product photos")
    parser.add_argument("--out", type=Path, required=True, help="output directory")
    parser.add_argument("--slides", type=int, help="only the first N slides, to save cost")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
    asyncio.run(run(args.spec, args.photos, args.out, args.slides))


if __name__ == "__main__":
    main()
