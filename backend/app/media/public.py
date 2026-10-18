import secrets
from collections import OrderedDict
from functools import cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

MAX_IMAGES = 200  # about 40 MB of post JPEGs


class PublicImages:
    """Generated JPEGs served at unguessable paths so WhatsApp can fetch them by link.

    In memory until T17 uploads them to the Supabase `renders` bucket; lost on restart.
    """

    def __init__(self, max_images: int = MAX_IMAGES) -> None:
        self._max_images = max_images
        self._images: OrderedDict[str, bytes] = OrderedDict()

    def add(self, data: bytes) -> str:
        """Store a JPEG and return its path, relative to the backend's public URL."""
        token = secrets.token_urlsafe(24)
        self._images[token] = data
        if len(self._images) > self._max_images:
            self._images.popitem(last=False)
        return f"/media/{token}.jpg"

    def keep(self, path: str, data: bytes) -> None:
        """Serve `data` at `path` again as the newest image, so a pending post is not evicted."""
        token = path.removeprefix("/media/").removesuffix(".jpg")
        self._images[token] = data
        self._images.move_to_end(token)
        if len(self._images) > self._max_images:
            self._images.popitem(last=False)

    def get(self, token: str) -> bytes | None:
        return self._images.get(token)


@cache
def get_public_images() -> PublicImages:
    return PublicImages()


router = APIRouter()


# Kapso sends HEAD before it fetches an image. Starlette's Response doesn't drop the body for
# HEAD (only FileResponse does), so HEAD gets the headers of the GET and an empty body here.
@router.api_route("/media/{token}.jpg", methods=["GET", "HEAD"])
async def public_image(
    request: Request, token: str, images: Annotated[PublicImages, Depends(get_public_images)]
) -> Response:
    data = images.get(token)
    if data is None:
        raise HTTPException(status_code=404)
    if request.method == "HEAD":
        return Response(headers={"content-length": str(len(data))}, media_type="image/jpeg")
    return Response(content=data, media_type="image/jpeg")
