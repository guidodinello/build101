import secrets
from collections import OrderedDict
from functools import cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

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

    def get(self, token: str) -> bytes | None:
        return self._images.get(token)


@cache
def get_public_images() -> PublicImages:
    return PublicImages()


router = APIRouter()


@router.get("/media/{token}.jpg")
async def public_image(
    token: str, images: Annotated[PublicImages, Depends(get_public_images)]
) -> Response:
    data = images.get(token)
    if data is None:
        raise HTTPException(status_code=404)
    return Response(content=data, media_type="image/jpeg")
