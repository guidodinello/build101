"""The web wizard's API, under /api/o/{token} (docs/architecture/api.md § Onboarding, § Uploads).

Files go from the browser straight to Supabase Storage through a signed upload URL; the backend
only issues the URL, then reads the file back once the browser says it finished.
"""

import asyncio
import logging
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import ChannelError, ChannelPort
from app.channels.router import get_channel
from app.config import Settings, get_settings
from app.copy import messages_es
from app.db.models import AssetProduct, BrandAsset, Business, MagicLink, Product, SocialAccount
from app.db.session import get_session
from app.jobs.queue import enqueue
from app.onboarding import schemas
from app.onboarding.links import hash_token
from app.onboarding.uploads import (
    EXTENSIONS,
    UnreadableImage,
    asset_path,
    llm_copy_path,
    process_upload,
)
from app.storage import ASSETS_BUCKET, StoragePort, get_storage

from .errors import ApiError

logger = logging.getLogger(__name__)

SIGNED_URL_TTL_S = 3600
# Supabase signed upload URLs last 2 h; an older ticket that never completed frees its slot.
UPLOAD_TICKET_TTL = timedelta(hours=2)
WIZARD_KINDS = frozenset({"logo", "photo"})
MIN_PHOTOS = 3
MAX_PHOTOS = 15
BYTES_PER_MB = 1024 * 1024

LINK_NOT_FOUND = "Este link no es válido. Escribinos por WhatsApp y te mandamos uno nuevo."
LINK_EXPIRED = 'Este link venció. Escribí "link" en WhatsApp y te mandamos uno nuevo.'
ALREADY_COMPLETED = "Ya completaste el formulario 🙌 Seguimos por WhatsApp."
TOO_MANY_PRODUCTS = f"Hasta {schemas.MAX_PRODUCTS} productos."
UNKNOWN_PRODUCT = "No encontramos uno de los productos. Recargá la página y probá de nuevo."
TOO_MANY_PRODUCT_PHOTOS = f"Hasta {schemas.MAX_PRODUCT_PHOTOS} fotos por producto."
UNKNOWN_ASSET = "No encontramos una de las fotos. Recargá la página y probá de nuevo."
MISSING_COLORS = 'Sumá al menos un color, o elegí "Todavía no tengo logo ni colores".'
UNSUPPORTED_FILE = "Este archivo no lo podemos usar. Subí fotos."
UNREADABLE_FILE = "No pudimos abrir esta foto. Probá con otra."
TOO_MANY_PHOTOS = f"Ya tenés {MAX_PHOTOS} fotos."
ASSET_NOT_FOUND = "No encontramos ese archivo."
UPLOAD_MISSING = "El archivo no terminó de subir. Probá de nuevo."
MISSING_BUSINESS = "Nos faltan los datos de tu negocio."
MISSING_PRODUCTS = f"Sumá entre 1 y {schemas.MAX_PRODUCTS} productos."
MISSING_PHOTOS = f"Sumá al menos {MIN_PHOTOS} fotos."


def file_too_big(max_mb: int) -> str:
    return f"Esta foto pesa más de {max_mb} MB. Probá con otra."


@dataclass(slots=True)
class Onboarding:
    link: MagicLink
    business: Business


SessionDep = Annotated[AsyncSession, Depends(get_session)]
StorageDep = Annotated[StoragePort, Depends(get_storage)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_onboarding(token: str, session: SessionDep) -> Onboarding:
    link = await session.scalar(
        select(MagicLink).where(
            MagicLink.token_hash == hash_token(token), MagicLink.purpose == "onboarding"
        )
    )
    if link is None:
        raise ApiError(404, "link_not_found", LINK_NOT_FOUND)
    if link.expires_at <= datetime.now(UTC):
        raise ApiError(410, "link_expired", LINK_EXPIRED)
    business = await session.get_one(Business, link.business_id)
    return Onboarding(link, business)


async def get_open_onboarding(
    onboarding: Annotated[Onboarding, Depends(get_onboarding)],
) -> Onboarding:
    """The link is reusable until the form is submitted (user-flows.md, Flow 1)."""
    if onboarding.link.completed_at is not None:
        raise ApiError(409, "onboarding_completed", ALREADY_COMPLETED)
    return onboarding


OnboardingDep = Annotated[Onboarding, Depends(get_onboarding)]
OpenOnboardingDep = Annotated[Onboarding, Depends(get_open_onboarding)]

router = APIRouter(prefix="/api/o/{token}")


@router.get("")
async def get_state(
    onboarding: OnboardingDep, session: SessionDep, storage: StorageDep, settings: SettingsDep
) -> schemas.OnboardingState:
    return await _state(onboarding, session, storage, settings)


@router.put("/business")
async def save_business(
    body: schemas.BusinessInput,
    onboarding: OpenOnboardingDep,
    session: SessionDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> schemas.OnboardingState:
    business = onboarding.business
    business.name = body.name
    business.category = body.category
    business.one_liner = body.one_liner
    business.location = body.location or None
    # Left out, these keep what the Instagram import filled in.
    if body.description is not None:
        business.description = body.description or None
    if body.website is not None:
        business.website = body.website or None
    if body.instagram_handle is not None:
        business.instagram_handle = body.instagram_handle.lstrip("@") or None
    await session.commit()
    return await _state(onboarding, session, storage, settings)


@router.put("/products")
async def save_products(
    body: schemas.ProductsInput,
    onboarding: OpenOnboardingDep,
    session: SessionDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> schemas.OnboardingState:
    if len(body.products) > schemas.MAX_PRODUCTS:
        raise ApiError(422, "too_many_products", TOO_MANY_PRODUCTS)
    if any(len(item.asset_ids or []) > schemas.MAX_PRODUCT_PHOTOS for item in body.products):
        raise ApiError(422, "too_many_product_photos", TOO_MANY_PRODUCT_PHOTOS)
    business_id = onboarding.business.id
    photos = await _ready_photos(session, business_id)
    existing = {
        str(product.id): product
        for product in await session.scalars(
            select(Product).where(Product.business_id == business_id)
        )
    }
    kept: set[str] = set()
    linked: list[tuple[Product, list[str]]] = []
    for position, item in enumerate(body.products):
        if item.id is None:
            product = Product(business_id=business_id, name=item.name)
            session.add(product)
        elif item.id in existing:
            product = existing[item.id]
            kept.add(item.id)
        else:
            raise ApiError(422, "unknown_product", UNKNOWN_PRODUCT)
        product.name = item.name
        product.description = item.description
        product.price = item.price or None
        product.category = item.category or None
        product.position = position
        product.archived_at = None
        if item.asset_ids is not None:
            if not set(item.asset_ids) <= photos:
                raise ApiError(422, "unknown_asset", UNKNOWN_ASSET)
            linked.append((product, item.asset_ids))
    now = datetime.now(UTC)
    for product_id, product in existing.items():
        if product_id not in kept and product.archived_at is None:
            product.archived_at = now
    await session.flush()
    for product, asset_ids in linked:
        await _link_owner_photos(session, product, asset_ids)
    await session.commit()
    return await _state(onboarding, session, storage, settings)


async def _link_owner_photos(session: AsyncSession, product: Product, asset_ids: list[str]) -> None:
    """Replace the Owner's links of a Product; the Asset Analyst's own links stay."""
    await session.execute(
        delete(AssetProduct).where(
            AssetProduct.product_id == product.id, AssetProduct.source == "owner"
        )
    )
    session.add_all(
        AssetProduct(asset_id=uuid.UUID(asset_id), product_id=product.id, source="owner")
        for asset_id in dict.fromkeys(asset_ids)
    )


async def _ready_photos(session: AsyncSession, business_id: uuid.UUID) -> set[str]:
    ids = await session.scalars(
        select(BrandAsset.id).where(
            BrandAsset.business_id == business_id,
            BrandAsset.kind == "photo",
            BrandAsset.status == "ready",
            BrandAsset.archived_at.is_(None),
        )
    )
    return {str(asset_id) for asset_id in ids}


@router.put("/brand")
async def save_brand(
    body: schemas.BrandInput,
    onboarding: OpenOnboardingDep,
    session: SessionDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> schemas.OnboardingState:
    if not body.no_brand_yet and not body.colors:
        raise ApiError(422, "missing_colors", MISSING_COLORS)
    brand = {
        "three_words": body.three_words,
        "colors": [] if body.no_brand_yet else [color.lower() for color in body.colors],
        "no_brand_yet": body.no_brand_yet,
    }
    business = onboarding.business
    business.onboarding_data = {**business.onboarding_data, "brand": brand}
    await session.commit()
    return await _state(onboarding, session, storage, settings)


@router.put("/preferences")
async def save_preferences(
    body: schemas.Questionnaire,
    onboarding: OpenOnboardingDep,
    session: SessionDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> schemas.OnboardingState:
    business = onboarding.business
    business.onboarding_data = {**business.onboarding_data, "preferences": body.model_dump()}
    await session.commit()
    return await _state(onboarding, session, storage, settings)


@router.post("/uploads")
async def request_upload(
    body: schemas.UploadRequest,
    onboarding: OpenOnboardingDep,
    session: SessionDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> schemas.UploadTicket:
    if body.kind not in WIZARD_KINDS or body.content_type not in EXTENSIONS:
        raise ApiError(422, "unsupported_file", UNSUPPORTED_FILE)
    if body.size_bytes > settings.max_photo_mb * BYTES_PER_MB:
        raise ApiError(422, "unsupported_file", file_too_big(settings.max_photo_mb))
    business = onboarding.business
    if body.kind == "photo":
        # The wizard uploads several photos at once; the row lock makes the cap hold for all.
        await session.refresh(business, with_for_update=True)
        if await _photos_holding_a_slot(session, business.id) >= MAX_PHOTOS:
            raise ApiError(422, "too_many_photos", TOO_MANY_PHOTOS)

    asset_id = uuid.uuid4()
    path = asset_path(business.id, asset_id, body.content_type)
    signed = await storage.create_signed_upload_url(ASSETS_BUCKET, path)
    session.add(
        BrandAsset(
            id=asset_id,
            business_id=business.id,
            kind=body.kind,
            source="web",
            status="uploading",
            storage_path=path,
            mime_type=body.content_type,
            owner_hint=body.owner_hint,
        )
    )
    await session.commit()
    # Photos and logos are capped at MAX_PHOTO_MB (10 MB), so a single PUT is enough; resumable
    # TUS uploads only matter for videos (Could).
    return schemas.UploadTicket(
        asset_id=str(asset_id), upload_url=signed.url, upload_token=signed.token, resumable=False
    )


@router.post("/assets/{asset_id}/complete")
async def complete_upload(
    asset_id: uuid.UUID,
    onboarding: OpenOnboardingDep,
    session: SessionDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> schemas.Asset:
    business = onboarding.business
    asset = await _active_asset(session, business.id, asset_id)
    if asset.status != "ready":
        await _finish_upload(asset, business, session, storage, settings)
    urls = await storage.create_signed_urls(ASSETS_BUCKET, [asset.storage_path], SIGNED_URL_TTL_S)
    return _to_asset(asset, urls.get(asset.storage_path, ""), [])


@router.delete("/assets/{asset_id}", status_code=204)
async def archive_asset(
    asset_id: uuid.UUID, onboarding: OpenOnboardingDep, session: SessionDep
) -> Response:
    asset = await session.get(BrandAsset, asset_id)
    if asset is not None and asset.business_id == onboarding.business.id:
        asset.archived_at = asset.archived_at or datetime.now(UTC)
        await session.commit()
    return Response(status_code=204)


@router.post("/complete", status_code=202)
async def complete_onboarding(
    onboarding: OnboardingDep,
    session: SessionDep,
    background: BackgroundTasks,
    channel: Annotated[ChannelPort, Depends(get_channel)],
) -> schemas.CompleteResponse:
    link, business = onboarding.link, onboarding.business
    # The lock serializes a double submit; any completed link of the Business counts, so a
    # second open link can't start the brand again.
    await session.refresh(business, with_for_update=True)
    already_completed = await session.scalar(
        select(MagicLink.id)
        .where(
            MagicLink.business_id == business.id,
            MagicLink.purpose == "onboarding",
            MagicLink.completed_at.is_not(None),
        )
        .limit(1)
    )
    if already_completed is not None:
        if link.completed_at is None:
            link.completed_at = datetime.now(UTC)
            await session.commit()
        return schemas.CompleteResponse(status="generating_brand")

    await _check_complete(session, business)
    link.completed_at = datetime.now(UTC)
    business.onboarding_state = "generating_brand"
    enqueue(session, "generate_brand", business.id, {})
    await session.commit()
    if business.channel == "whatsapp":
        background.add_task(_send_brand_generating, channel, business.owner_phone)
    return schemas.CompleteResponse(status="generating_brand")


async def _finish_upload(
    asset: BrandAsset,
    business: Business,
    session: AsyncSession,
    storage: StoragePort,
    settings: Settings,
) -> None:
    data = await storage.download(ASSETS_BUCKET, asset.storage_path)
    if data is None:
        raise ApiError(409, "upload_missing", UPLOAD_MISSING)
    # The signed URL doesn't enforce the size the browser declared.
    if len(data) > settings.max_photo_mb * BYTES_PER_MB:
        await _fail(asset, session)
        raise ApiError(422, "unsupported_file", file_too_big(settings.max_photo_mb))
    try:
        processed = await asyncio.to_thread(process_upload, data, asset.mime_type, asset.kind)
    except UnreadableImage:
        await _fail(asset, session)
        raise ApiError(422, "unsupported_file", UNREADABLE_FILE) from None

    if processed.jpeg is not None:
        jpeg_path = asset_path(business.id, asset.id, "image/jpeg")
        await storage.upload(ASSETS_BUCKET, jpeg_path, processed.jpeg, "image/jpeg")
        asset.storage_path, asset.mime_type = jpeg_path, "image/jpeg"
    await storage.upload(
        ASSETS_BUCKET, llm_copy_path(business.id, asset.id), processed.llm_copy, "image/jpeg"
    )
    asset.status = "ready"
    asset.size_bytes = len(data)
    asset.width, asset.height = processed.width, processed.height
    asset.palette = processed.palette
    if asset.kind == "photo":
        enqueue(session, "analyze_asset", business.id, {"asset_id": str(asset.id)})
    await session.commit()


async def _fail(asset: BrandAsset, session: AsyncSession) -> None:
    asset.status = "failed"
    await session.commit()


async def _active_asset(
    session: AsyncSession, business_id: uuid.UUID, asset_id: uuid.UUID
) -> BrandAsset:
    """The asset, locked: a second /complete of it waits and then finds it ready."""
    asset = await session.scalar(
        select(BrandAsset).where(BrandAsset.id == asset_id).with_for_update()
    )
    if asset is None or asset.business_id != business_id or asset.archived_at is not None:
        raise ApiError(404, "asset_not_found", ASSET_NOT_FOUND)
    return asset


async def _photos_holding_a_slot(session: AsyncSession, business_id: uuid.UUID) -> int:
    recent_ticket = BrandAsset.created_at > datetime.now(UTC) - UPLOAD_TICKET_TTL
    return (
        await session.scalar(
            select(func.count()).where(
                BrandAsset.business_id == business_id,
                BrandAsset.kind == "photo",
                BrandAsset.source == "web",
                BrandAsset.archived_at.is_(None),
                (BrandAsset.status == "ready")
                | ((BrandAsset.status == "uploading") & recent_ticket),
            )
        )
        or 0
    )


async def _check_complete(session: AsyncSession, business: Business) -> None:
    if not business.name or not business.category:
        raise ApiError(422, "missing_business", MISSING_BUSINESS)
    products = await session.scalar(
        select(func.count()).where(
            Product.business_id == business.id, Product.archived_at.is_(None)
        )
    )
    if not 1 <= (products or 0) <= schemas.MAX_PRODUCTS:
        raise ApiError(422, "missing_products", MISSING_PRODUCTS)
    photos = Counter(
        (
            await session.scalars(
                select(BrandAsset.source).where(
                    BrandAsset.business_id == business.id,
                    BrandAsset.kind == "photo",
                    BrandAsset.status == "ready",
                    BrandAsset.archived_at.is_(None),
                )
            )
        ).all()
    )
    # Photos imported from Instagram count toward the minimum; the cap is on uploads only.
    if photos["web"] + photos["instagram"] < MIN_PHOTOS or photos["web"] > MAX_PHOTOS:
        raise ApiError(422, "missing_photos", MISSING_PHOTOS)


async def _send_brand_generating(channel: ChannelPort, owner_phone: str) -> None:
    try:
        await channel.send_text(owner_phone, messages_es.BRAND_GENERATING)
    except ChannelError:
        logger.exception("brand_generating was not sent")


async def _state(
    onboarding: Onboarding, session: AsyncSession, storage: StoragePort, settings: Settings
) -> schemas.OnboardingState:
    business = onboarding.business
    products = (
        await session.scalars(
            select(Product)
            .where(Product.business_id == business.id, Product.archived_at.is_(None))
            .order_by(Product.position)
        )
    ).all()
    assets = (
        await session.scalars(
            select(BrandAsset)
            .where(
                BrandAsset.business_id == business.id,
                (BrandAsset.source == "web")
                | ((BrandAsset.source == "instagram") & (BrandAsset.kind == "photo")),
                BrandAsset.status == "ready",
                BrandAsset.archived_at.is_(None),
            )
            .order_by(BrandAsset.created_at)
        )
    ).all()
    asset_ids = [asset.id for asset in assets]
    product_ids = [product.id for product in products]
    pairs = (
        await session.execute(
            select(AssetProduct.asset_id, AssetProduct.product_id).where(
                AssetProduct.asset_id.in_(asset_ids), AssetProduct.product_id.in_(product_ids)
            )
        )
    ).all()
    product_ids_by_asset: dict[uuid.UUID, list[str]] = {}
    for asset_id, product_id in pairs:
        product_ids_by_asset.setdefault(asset_id, []).append(str(product_id))
    asset_count = Counter(product_id for _, product_id in pairs)
    urls = await storage.create_signed_urls(
        ASSETS_BUCKET, [asset.storage_path for asset in assets], SIGNED_URL_TTL_S
    )
    brand = business.onboarding_data.get("brand", {})
    preferences = business.onboarding_data.get("preferences")
    return schemas.OnboardingState(
        business=schemas.BusinessInfo(
            name=business.name,
            category=business.category,
            one_liner=business.one_liner,
            description=business.description,
            location=business.location,
            website=business.website,
            instagram_handle=business.instagram_handle,
        ),
        products=[
            schemas.Product(
                id=str(product.id),
                name=product.name,
                description=product.description,
                price=product.price,
                category=product.category,
                position=product.position,
                asset_count=asset_count[product.id],
                archived=False,
            )
            for product in products
        ],
        brand=schemas.Brand(
            three_words=brand.get("three_words", []), colors=brand.get("colors", [])
        ),
        assets=[
            _to_asset(
                asset, urls.get(asset.storage_path, ""), product_ids_by_asset.get(asset.id, [])
            )
            for asset in assets
        ],
        preferences=schemas.Questionnaire.model_validate(preferences) if preferences else None,
        instagram=await _instagram(session, business),
        completed=onboarding.link.completed_at is not None,
        whatsapp_url=settings.whatsapp_url,
    )


async def _instagram(session: AsyncSession, business: Business) -> schemas.Instagram:
    """The connection that reads the account for the Brand Brain (ADR 0028); publishing still
    goes to the one demo account (ADR 0024)."""
    account = await session.scalar(
        select(SocialAccount)
        .where(SocialAccount.business_id == business.id, SocialAccount.platform == "instagram")
        .order_by(SocialAccount.updated_at.desc())
        .limit(1)
    )
    if account is None:
        return schemas.Instagram(status="not_connected", handle=business.instagram_handle)
    return schemas.Instagram(status=account.status, handle=account.handle)


def _to_asset(asset: BrandAsset, url: str, product_ids: list[str]) -> schemas.Asset:
    return schemas.Asset(
        id=str(asset.id),
        kind=asset.kind,
        source=asset.source,
        status=asset.status,
        url=url,
        thumbnail_url=None,
        width=asset.width,
        height=asset.height,
        duration_ms=asset.duration_ms,
        derived_from_asset_id=str(asset.derived_from_asset_id)
        if asset.derived_from_asset_id
        else None,
        owner_hint=asset.owner_hint,
        palette=asset.palette,
        product_ids=product_ids,
        reel_suitable=None,
        analyzed=asset.analysis is not None,
        archived=asset.archived_at is not None,
    )
