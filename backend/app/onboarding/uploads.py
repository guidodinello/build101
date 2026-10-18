from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.media.images import prepare_reference

HEIC = "image/heic"
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", HEIC: "heic"}
PALETTE_SIZE = 5
PALETTE_SAMPLE_SIDE = 128
OPAQUE_ALPHA = 128
JPEG_QUALITY = 90
# A 50 MP phone photo fits. Checked before decoding: a small PNG can expand to hundreds of MB.
MAX_PIXELS = 60_000_000


class UnreadableImage(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ProcessedUpload:
    width: int
    height: int
    llm_copy: bytes
    jpeg: bytes | None  # the original as JPEG, only when it was HEIC
    palette: list[str] | None  # logos only


def asset_path(business_id: object, asset_id: object, content_type: str) -> str:
    return f"{business_id}/{asset_id}.{EXTENSIONS[content_type]}"


def llm_copy_path(business_id: object, asset_id: object) -> str:
    """Where the agents read a photo or logo from: a JPEG of at most 1536 px a side."""
    return f"{business_id}/{asset_id}-llm.jpg"


def process_upload(data: bytes, content_type: str, kind: str) -> ProcessedUpload:
    """Read an uploaded photo or logo once it is in Storage. CPU-bound: run it in a thread."""
    try:
        with Image.open(BytesIO(data)) as source:
            if source.width * source.height > MAX_PIXELS:
                raise UnreadableImage(f"{source.width}x{source.height} is over {MAX_PIXELS} px")
            image = ImageOps.exif_transpose(source)
            image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise UnreadableImage(str(exc)) from exc
    return ProcessedUpload(
        width=image.width,
        height=image.height,
        llm_copy=prepare_reference(data),
        jpeg=_to_jpeg(image) if content_type == HEIC else None,
        palette=logo_palette(image) if kind == "logo" else None,
    )


def logo_palette(image: Image.Image) -> list[str]:
    """The logo's main colors as hex, most used first; transparent pixels don't count."""
    sample = image.convert("RGBA")
    # NEAREST keeps the logo's own colors; smoother filters blend edges into new ones.
    sample.thumbnail((PALETTE_SAMPLE_SIDE, PALETTE_SAMPLE_SIDE), Image.Resampling.NEAREST)
    # One extra color, so a transparent background doesn't take a slot from a real one.
    quantized = sample.quantize(colors=PALETTE_SIZE + 1, method=Image.Quantize.FASTOCTREE)
    rgba = quantized.getpalette(rawmode="RGBA") or []
    used = sorted(quantized.getcolors() or [], reverse=True)
    colors: list[str] = []
    for _, index in used:
        r, g, b, a = rgba[index * 4 : index * 4 + 4]
        color = f"#{r:02x}{g:02x}{b:02x}"
        if a >= OPAQUE_ALPHA and color not in colors:
            colors.append(color)
    return colors[:PALETTE_SIZE]


def _to_jpeg(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()
