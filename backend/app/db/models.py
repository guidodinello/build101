"""ORM models for the tables the code uses so far.

The schema itself is migrations/versions/0001_initial.sql (data-model.md); a table gets a model
here when a task starts writing it.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {
        dict[str, Any]: JSONB,
        list[str]: JSONB,
        datetime: DateTime(timezone=True),
    }


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_phone: Mapped[str]
    owner_name: Mapped[str | None]
    name: Mapped[str | None]
    category: Mapped[str | None]
    one_liner: Mapped[str | None]
    description: Mapped[str | None]
    location: Mapped[str | None]
    website: Mapped[str | None]
    instagram_handle: Mapped[str | None]
    timezone: Mapped[str] = mapped_column(server_default="America/Montevideo")
    onboarding_state: Mapped[str] = mapped_column(server_default="new")
    # Raw wizard answers: {"brand": {...}, "preferences": {...}}. Reassign, don't mutate in place:
    # SQLAlchemy only notices a new dict.
    onboarding_data: Mapped[dict[str, Any]] = mapped_column(server_default="{}")
    conversation_state: Mapped[dict[str, Any]] = mapped_column(server_default="{}")
    channel: Mapped[str] = mapped_column(server_default="whatsapp")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class MagicLink(Base):
    __tablename__ = "magic_links"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"))
    token_hash: Mapped[str]
    purpose: Mapped[str] = mapped_column(server_default="onboarding")
    expires_at: Mapped[datetime]
    completed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"))
    name: Mapped[str]
    description: Mapped[str] = mapped_column(server_default="")
    price: Mapped[str | None]
    category: Mapped[str | None]
    position: Mapped[int] = mapped_column(server_default="0")
    archived_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class BrandAsset(Base):
    __tablename__ = "brand_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"))
    kind: Mapped[str]
    source: Mapped[str]
    status: Mapped[str] = mapped_column(server_default="uploading")
    storage_path: Mapped[str]
    mime_type: Mapped[str]
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    width: Mapped[int | None]
    height: Mapped[int | None]
    duration_ms: Mapped[int | None]
    derived_from_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("brand_assets.id"))
    owner_hint: Mapped[str | None]
    analysis: Mapped[dict[str, Any] | None]
    palette: Mapped[list[str] | None]
    archived_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AssetProduct(Base):
    __tablename__ = "asset_products"

    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brand_assets.id"), primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), primary_key=True)
    source: Mapped[str]


class BrandBrainVersion(Base):
    __tablename__ = "brand_brains"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"))
    version: Mapped[int]
    data: Mapped[dict[str, Any]]
    reason: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id"))
    kind: Mapped[str]
    payload: Mapped[dict[str, Any]] = mapped_column(server_default="{}")
    status: Mapped[str] = mapped_column(server_default="queued")
    result: Mapped[dict[str, Any] | None]
    error: Mapped[str | None]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
