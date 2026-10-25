import asyncio
import base64
from collections.abc import Callable
from io import BytesIO
from typing import Any, Literal
from weakref import WeakKeyDictionary

from PIL import Image, ImageDraw, ImageOps, ImageStat, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

# What an Owner can send us (HEIC reads as HEIF); anything else is not decoded.
ACCEPTED_FORMATS = ["JPEG", "PNG", "WEBP", "HEIF"]
# Checked before decoding: a small PNG can expand to hundreds of MB. A decoded 25 MP image takes
# 75-100 MB, so a few of them at once stay inside the one backend instance's memory (ADR 0005).
MAX_PIXELS = 25_000_000
# Decodes running at once across the wizard, the Instagram import, WhatsApp photos and the
# carousel's references; the rest wait their turn.
MAX_CONCURRENT_DECODES = 2
POST_SIZE = (1080, 1350)
REFERENCE_MAX_SIDE = 1536
JPEG_QUALITY = 90
LOGO_MAX_SHARE = (0.22, 0.09)  # of the post's width and height
LOGO_MARGIN_SHARE = 0.04  # of the post's width
# Mean luminance (0–255) a transparent logo must differ from the photo behind it by.
LOGO_MIN_CONTRAST = 64
LOGO_BACKING_PAD_SHARE = 0.3  # of the logo's height
LOGO_BACKING_ALPHA = 220
LIGHT_BACKING = (255, 255, 255)
DARK_BACKING = (31, 31, 31)
OPAQUE_ALPHA = 128
MID_LUMINANCE = 128
RENDER_LOGO_MAX_SIDE = 600
REVIEW_SIZE = (540, 675)  # a designed slide at half size: enough for a model to judge the design
POST_RATIO = POST_SIZE[0] / POST_SIZE[1]

Tone = Literal["light", "dark"]

# A semaphore binds to the event loop it first waits on, so each loop gets its own (the app has
# one; tests run one loop each).
_decode_slots: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = WeakKeyDictionary()


class UnreadableImage(Exception):
    pass


class ImageTooLarge(UnreadableImage):
    """Readable, but over MAX_PIXELS."""


def decode_slot() -> asyncio.Semaphore:
    """The running loop's one semaphore for image decodes, sized by MAX_CONCURRENT_DECODES the
    first time the loop asks (read here, so it doesn't depend on who asks first)."""
    return _decode_slots.setdefault(
        asyncio.get_running_loop(), asyncio.Semaphore(MAX_CONCURRENT_DECODES)
    )


async def decode[T](function: Callable[..., T], *args: Any) -> T:
    """`function` in a thread, at most MAX_CONCURRENT_DECODES decodes at a time. The others wait
    on the event loop, not in a thread, so they don't hold the pool other work needs.

    Never call this (or take the slot) from inside a slot: with few slots that can deadlock.
    """
    async with decode_slot():
        return await asyncio.to_thread(function, *args)


def prepare_reference(data: bytes) -> bytes:
    """The agents' copy of a photo the Owner sent. CPU-bound: run it through `decode`."""
    try:
        with Image.open(BytesIO(data), formats=ACCEPTED_FORMATS) as source:
            if source.width * source.height > MAX_PIXELS:
                raise ImageTooLarge(f"{source.width}x{source.height} is over {MAX_PIXELS} px")
            return reference_from(ImageOps.exif_transpose(source))
    # ValueError: pillow_heif's error for a truncated HEIF.
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise UnreadableImage(str(exc)) from exc


def reference_from(image: Image.Image) -> bytes:
    """The agents' copy of an already decoded image; `image` itself is left as it was."""
    reference = image.convert("RGB")  # a copy, so the thumbnail below doesn't touch `image`
    reference.thumbnail((REFERENCE_MAX_SIDE, REFERENCE_MAX_SIDE), Image.Resampling.LANCZOS)
    return _to_jpeg(reference)


def to_post_image(data: bytes) -> bytes:
    with Image.open(BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    fitted = ImageOps.fit(image, POST_SIZE, method=Image.Resampling.LANCZOS)
    return _to_jpeg(fitted)


def review_copy(data: bytes) -> bytes:
    """A designed slide at half size, for the Design Critic (fewer image tokens)."""
    with Image.open(BytesIO(data)) as source:
        image = source.convert("RGB")
    return _to_jpeg(ImageOps.fit(image, REVIEW_SIZE, method=Image.Resampling.LANCZOS))


def slice_panorama(data: bytes, count: int) -> list[bytes]:
    """A wide scene cut into `count` side-by-side post images, after a centered crop to N × 4:5."""
    if count < 1:
        raise ValueError(f"a panorama needs at least one slide, got {count}")
    with Image.open(BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    strip = ImageOps.fit(
        image,
        (round(image.height * POST_RATIO * count), image.height),
        method=Image.Resampling.LANCZOS,
    )
    width = strip.width / count
    slices = (
        strip.crop((round(n * width), 0, round((n + 1) * width), strip.height))
        for n in range(count)
    )
    return [_to_jpeg(piece.resize(POST_SIZE, Image.Resampling.LANCZOS)) for piece in slices]


def logo_for_render(data: bytes) -> tuple[bytes, Tone]:
    """The logo as a PNG without transparent margins, and whether it reads as light or dark."""
    with Image.open(BytesIO(data)) as source:
        mark = ImageOps.exif_transpose(source).convert("RGBA")
    bounds = mark.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("the logo is fully transparent")
    mark = mark.crop(bounds)
    mark.thumbnail((RENDER_LOGO_MAX_SIDE, RENDER_LOGO_MAX_SIDE), Image.Resampling.LANCZOS)
    # Pillow stubs type the `point()` lambda argument as an ImagePointTransform, not an int
    shape = mark.getchannel("A").point(
        lambda value: 255 if value >= OPAQUE_ALPHA else 0  # pyright: ignore[reportOperatorIssue]
    )
    if shape.getbbox() is None:
        shape = mark.getchannel("A").point(lambda value: 255 if value else 0)
    luminance = ImageStat.Stat(mark.convert("L"), shape).mean[0]
    buffer = BytesIO()
    mark.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue(), "light" if luminance >= MID_LUMINANCE else "dark"


def data_uri(data: bytes) -> str:
    return f"data:{image_mime(data)};base64,{base64.b64encode(data).decode()}"


def add_logo(post: bytes, logo: bytes) -> bytes:
    """The Owner's logo, resized but otherwise unchanged, in the post's bottom-right corner.

    A transparent logo that would blend into the photo gets a rounded backing; an opaque one
    brings its own background (ADR 0027).
    """
    with Image.open(BytesIO(post)) as source:
        canvas = source.convert("RGBA")
    mark = fit_logo(logo, canvas.size)
    margin = round(canvas.width * LOGO_MARGIN_SHARE)
    x, y = canvas.width - margin - mark.width, canvas.height - margin - mark.height
    backing = logo_backing(canvas.crop((x, y, x + mark.width, y + mark.height)), mark)
    if backing:
        pad = round(mark.height * LOGO_BACKING_PAD_SHARE)
        x, y = x - pad, y - pad  # the backing, not the logo, keeps the margin
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rounded_rectangle(
            (x - pad, y - pad, x + mark.width + pad, y + mark.height + pad),
            radius=pad,
            fill=(*backing, LOGO_BACKING_ALPHA),
        )
        canvas = Image.alpha_composite(canvas, overlay)
    canvas.alpha_composite(mark, (x, y))
    return _to_jpeg(canvas.convert("RGB"))


def fit_logo(data: bytes, post_size: tuple[int, int]) -> Image.Image:
    """The logo without its transparent margins, as large as fits its corner of the post."""
    with Image.open(BytesIO(data)) as source:
        mark = ImageOps.exif_transpose(source).convert("RGBA")
    bounds = mark.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("the logo is fully transparent")
    mark = mark.crop(bounds)
    (width, height), (width_share, height_share) = post_size, LOGO_MAX_SHARE
    scale = min(width * width_share / mark.width, height * height_share / mark.height)
    size = (max(1, round(mark.width * scale)), max(1, round(mark.height * scale)))
    return mark.resize(size, Image.Resampling.LANCZOS)


def logo_backing(behind: Image.Image, mark: Image.Image) -> tuple[int, int, int] | None:
    """The backing color a transparent logo needs to stand out from `behind`, if any."""
    alpha = mark.getchannel("A")
    # Pillow stubs: `getextrema()` is `float | tuple[int, int]`; a single band gives ints.
    if alpha.getextrema()[0] >= OPAQUE_ALPHA:  # pyright: ignore[reportOperatorIssue]
        return None
    # A logo that is semi-transparent everywhere has no opaque pixel: measure all visible ones.
    threshold = (
        OPAQUE_ALPHA
        if alpha.getextrema()[1] >= OPAQUE_ALPHA  # pyright: ignore[reportOperatorIssue]
        else 1
    )
    shape = alpha.point(
        lambda value: 255 if value >= threshold else 0  # pyright: ignore[reportOperatorIssue]
    )
    logo_luminance = ImageStat.Stat(mark.convert("L"), shape).mean[0]
    behind_luminance = ImageStat.Stat(behind.convert("L"), shape).mean[0]
    if abs(logo_luminance - behind_luminance) >= LOGO_MIN_CONTRAST:
        return None
    return LIGHT_BACKING if logo_luminance < MID_LUMINANCE else DARK_BACKING


def image_mime(data: bytes) -> str:
    with Image.open(BytesIO(data)) as image:
        return Image.MIME.get(image.format or "", "image/jpeg")


def image_size(data: bytes) -> tuple[int, int]:
    with Image.open(BytesIO(data)) as image:
        return image.size


def _to_jpeg(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()
