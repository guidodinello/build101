from io import BytesIO

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

POST_SIZE = (1080, 1350)
REFERENCE_MAX_SIDE = 1536
JPEG_QUALITY = 90


def prepare_reference(data: bytes) -> bytes:
    with Image.open(BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    image.thumbnail((REFERENCE_MAX_SIDE, REFERENCE_MAX_SIDE), Image.Resampling.LANCZOS)
    return _to_jpeg(image)


def to_post_image(data: bytes) -> bytes:
    with Image.open(BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    fitted = ImageOps.fit(image, POST_SIZE, method=Image.Resampling.LANCZOS)
    return _to_jpeg(fitted)


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
