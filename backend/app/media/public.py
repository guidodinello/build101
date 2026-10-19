import secrets
from collections import OrderedDict
from collections.abc import Callable
from functools import cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

MAX_IMAGES = 200  # about 40 MB of post JPEGs
MAX_VIDEOS = 20  # clips run to several MB each


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


class PublicVideos:
    """Generated MP4s served at unguessable paths so Zernio and WhatsApp can fetch them by link.

    Same shape as `PublicImages`, with a small cap because a clip is several MB. In memory;
    lost on restart. No `Range` support yet (ADR 0033): check it when the flag is first turned on.
    """

    def __init__(self, max_videos: int = MAX_VIDEOS) -> None:
        self._max_videos = max_videos
        self._videos: OrderedDict[str, bytes] = OrderedDict()
        self._lookup: Callable[[str], bytes | None] | None = None

    def serve_from(self, lookup: Callable[[str], bytes | None]) -> None:
        """Where to find a clip the LRU dropped: the Post that still holds it (same bytes object).

        A clip stays served while its Post exists, so the Owner's WhatsApp header and Zernio's
        fetch never 404 just because 20 later clips came in. Wired where the store is built.
        """
        self._lookup = lookup

    def add(self, data: bytes) -> str:
        """Store an MP4 and return its path, relative to the backend's public URL."""
        token = secrets.token_urlsafe(24)
        self._videos[token] = data
        if len(self._videos) > self._max_videos:
            self._videos.popitem(last=False)
        return f"/media/{token}.mp4"

    def keep(self, path: str, data: bytes) -> None:
        """Serve `data` at `path` again as the newest video, so a pending post is not evicted."""
        token = path.removeprefix("/media/").removesuffix(".mp4")
        self._videos[token] = data
        self._videos.move_to_end(token)
        if len(self._videos) > self._max_videos:
            self._videos.popitem(last=False)

    def get(self, token: str) -> bytes | None:
        data = self._videos.get(token)
        if data is None and self._lookup is not None:
            return self._lookup(f"/media/{token}.mp4")
        return data


@cache
def get_public_videos() -> PublicVideos:
    return PublicVideos()


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


@router.api_route("/media/{token}.mp4", methods=["GET", "HEAD"])
async def public_video(
    request: Request, token: str, videos: Annotated[PublicVideos, Depends(get_public_videos)]
) -> Response:
    data = videos.get(token)
    if data is None:
        raise HTTPException(status_code=404)
    if request.method == "HEAD":
        return Response(headers={"content-length": str(len(data))}, media_type="video/mp4")
    return Response(content=data, media_type="video/mp4")
