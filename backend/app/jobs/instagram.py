import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.db.models import BrandAsset, Business, SocialAccount
from app.instagram.base import (
    InstagramError,
    InstagramImage,
    InstagramMedia,
    InstagramPort,
    InstagramProfile,
)
from app.onboarding.uploads import (
    EXTENSIONS,
    HEIC,
    ProcessedUpload,
    UnreadableImage,
    asset_path,
    llm_copy_path,
    read_upload,
)
from app.storage import ASSETS_BUCKET

from .queue import enqueue
from .runner import JobContext, JobFunction

logger = logging.getLogger(__name__)

MAX_CONCURRENT_DOWNLOADS = 4
MAX_CAPTION_CHARS = 1000
MAX_HINT_CHARS = 200


@dataclass(frozen=True, slots=True)
class ImportedImage:
    asset_id: uuid.UUID
    external_id: str
    caption: str | None
    storage_path: str
    mime_type: str
    size_bytes: int
    processed: ProcessedUpload


def import_instagram_job(instagram: InstagramPort, max_posts: int, max_images: int) -> JobFunction:
    async def import_instagram(context: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
        """Read the connected account into the Brand Brain's inputs (ADR 0028).

        The profile and the captions go to `onboarding_data["instagram"]`; the newest images
        become Brand assets (`source = 'instagram'`) with an Asset Analyst job each. Images
        imported before are skipped, so a reconnect only adds what is new.
        """
        if context.business_id is None:
            raise ValueError("import_instagram needs a business")
        business_id = context.business_id
        async with context.sessions() as db:
            account = await db.scalar(
                select(SocialAccount).where(
                    SocialAccount.business_id == business_id,
                    SocialAccount.platform == "instagram",
                    SocialAccount.status == "connected",
                    SocialAccount.access_token.is_not(None),
                )
            )
            if account is None:
                return {"skipped": "no connected instagram"}
            access_token = account.access_token or ""
            imported = set(
                (
                    await db.scalars(
                        select(BrandAsset.external_id).where(
                            BrandAsset.business_id == business_id,
                            BrandAsset.source == "instagram",
                            BrandAsset.external_id.is_not(None),
                        )
                    )
                ).all()
            )

        profile = await instagram.profile(access_token)
        media = await instagram.recent_media(access_token, max_posts)
        wanted = _images_to_import(media, imported, max_images)
        limit = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

        async def fetch(item: tuple[InstagramImage, str | None]) -> ImportedImage | None:
            async with limit:
                return await _store_image(context, instagram, business_id, *item)

        images = [image for image in await asyncio.gather(*map(fetch, wanted)) if image]

        async with context.sessions() as db:
            business = await db.get_one(Business, business_id)
            business.onboarding_data = {
                **business.onboarding_data,
                "instagram": _summary(profile, media),
            }
            business.instagram_handle = business.instagram_handle or profile.username
            business.website = business.website or profile.website
            for image in images:
                db.add(
                    BrandAsset(
                        id=image.asset_id,
                        business_id=business_id,
                        kind="photo",
                        source="instagram",
                        status="ready",
                        storage_path=image.storage_path,
                        mime_type=image.mime_type,
                        size_bytes=image.size_bytes,
                        width=image.processed.width,
                        height=image.processed.height,
                        owner_hint=(image.caption or "")[:MAX_HINT_CHARS] or None,
                        external_id=image.external_id,
                    )
                )
                enqueue(db, "analyze_asset", business_id, {"asset_id": str(image.asset_id)})
            await db.commit()
        return {"posts": len(media), "images": len(images), "skipped": len(wanted) - len(images)}

    return import_instagram


def _images_to_import(
    media: list[InstagramMedia], imported: set[str | None], max_images: int
) -> list[tuple[InstagramImage, str | None]]:
    """The newest images not imported yet, each with its post's caption."""
    wanted = [
        (image, post.caption) for post in media for image in post.images if image.id not in imported
    ]
    return wanted[:max_images]


async def _store_image(
    context: JobContext,
    instagram: InstagramPort,
    business_id: uuid.UUID,
    image: InstagramImage,
    caption: str | None,
) -> ImportedImage | None:
    """Download one image and store it with the agents' copy; None (logged) when it can't be."""
    try:
        data, content_type = await instagram.download(image.url)
        if content_type not in EXTENSIONS or content_type == HEIC:
            raise UnreadableImage(f"unexpected content type {content_type!r}")
        processed = await read_upload(data, content_type, "photo")
    except (InstagramError, UnreadableImage) as exc:
        logger.warning("instagram image %s not imported: %s", image.id, exc)
        return None
    asset_id = uuid.uuid4()
    path = asset_path(business_id, asset_id, content_type)
    await context.storage.upload(ASSETS_BUCKET, path, data, content_type)
    await context.storage.upload(
        ASSETS_BUCKET, llm_copy_path(business_id, asset_id), processed.llm_copy, "image/jpeg"
    )
    return ImportedImage(
        asset_id=asset_id,
        external_id=image.id,
        caption=caption,
        storage_path=path,
        mime_type=content_type,
        size_bytes=len(data),
        processed=processed,
    )


def _summary(profile: InstagramProfile, media: list[InstagramMedia]) -> dict[str, Any]:
    return {
        "username": profile.username,
        "name": profile.name,
        "biography": profile.biography,
        "website": profile.website,
        "followers_count": profile.followers_count,
        "media_count": profile.media_count,
        "imported_at": datetime.now(UTC).isoformat(),
        "posts": [
            {
                "type": post.media_type,
                "caption": (post.caption or "")[:MAX_CAPTION_CHARS],
                "likes": post.like_count,
                "comments": post.comments_count,
                "timestamp": post.timestamp.isoformat() if post.timestamp else None,
                "permalink": post.permalink,
            }
            for post in media
        ],
    }
