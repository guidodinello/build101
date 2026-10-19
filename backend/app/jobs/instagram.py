import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

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
    process_upload,
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

        The Owner's token is used here once and then deleted: when the import ends, fails or is
        cancelled, the job clears the token it read. Nothing else reads it, and a reconnect
        stores a fresh one, which a job still running on the old one must not clear (#102).
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
            account_id = account.id
            access_token = account.access_token or ""

        try:
            async with context.sessions() as db:
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
                await _clear_token(db, account_id, access_token)
                await db.commit()
        except BaseException:
            # BaseException: a deploy cancels the job (CancelledError) and must not leave the token
            await _drop_token(context, account_id, access_token)
            raise
        return {"posts": len(media), "images": len(images), "skipped": len(wanted) - len(images)}

    return import_instagram


async def _clear_token(db: AsyncSession, account_id: uuid.UUID, token: str) -> None:
    """Null the token only if it is still the one this job read: a reconnect in the meantime
    stored a fresh one for the next import, and that one is not ours to clear."""
    await db.execute(
        update(SocialAccount)
        .where(SocialAccount.id == account_id, SocialAccount.access_token == token)
        .values(access_token=None)
    )


async def _drop_token(context: JobContext, account_id: uuid.UUID, token: str) -> None:
    """Clear the token after a failed or cancelled import. A failure here is logged and
    swallowed so the caller still re-raises the error that ended the import."""
    try:
        async with context.sessions() as db:
            await _clear_token(db, account_id, token)
            await db.commit()
    except Exception:
        logger.exception("could not clear the instagram token of account %s", account_id)


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
        processed = await asyncio.to_thread(process_upload, data, content_type, "photo")
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
