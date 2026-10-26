"""Request and response bodies of the onboarding API (docs/architecture/api.md § Onboarding)."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
RequiredText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None
HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
Scale = Literal[1, 2, 3, 4, 5]

MAX_PRODUCTS = 5
MAX_PRODUCT_PHOTOS = 5
MAX_COLORS = 5
# A hard ceiling on the request lists, above the caps the route checks itself (MAX_PRODUCTS,
# MAX_PRODUCT_PHOTOS), which have their own error codes. It bounds validation, not JSON parsing.
MAX_LIST_ITEMS = 20


class BusinessInfo(BaseModel):
    name: str | None
    category: str | None
    one_liner: str | None
    description: str | None
    location: str | None
    website: str | None
    instagram_handle: str | None


class BusinessInput(BaseModel):
    name: RequiredText
    category: RequiredText
    one_liner: RequiredText
    description: Text | None = None
    location: OptionalText = None
    website: OptionalText = None
    instagram_handle: OptionalText = None


class Product(BaseModel):
    id: str
    name: str
    description: str
    price: str | None
    category: str | None
    position: int
    asset_count: int
    archived: bool


class ProductInput(BaseModel):
    id: str | None = None
    name: RequiredText
    description: Text = ""
    price: OptionalText = None
    category: OptionalText = None
    # The Product's own photos, linked by the Owner; left out, the links don't change.
    asset_ids: Annotated[list[str], Field(max_length=MAX_LIST_ITEMS)] | None = None


class ProductsInput(BaseModel):
    # The 5-product and 5-photo caps are checked in the route, so they get their own error codes.
    products: list[ProductInput] = Field(min_length=1, max_length=MAX_LIST_ITEMS)


class Brand(BaseModel):
    three_words: list[str]
    colors: list[str]


class BrandInput(BaseModel):
    three_words: Annotated[list[RequiredText], Field(min_length=1, max_length=3)]
    colors: Annotated[list[HexColor], Field(max_length=MAX_COLORS)]
    no_brand_yet: bool = False


class Questionnaire(BaseModel):
    goal: Literal["sales", "awareness", "launch", "loyalty"]
    audiences: Annotated[list[RequiredText], Field(max_length=10)]
    # Left out when the Owner connected Instagram and kept its voice, so the import decides.
    formality: Scale | None = None
    humor: Scale | None = None
    posts_per_week: Literal[2, 3, 5] | None = None
    emoji_policy: Literal["many", "few", "none"] | None = None
    avoid: OptionalText = None
    current_offer: OptionalText = None


class Asset(BaseModel):
    id: str
    kind: Literal["logo", "photo", "video"]
    source: Literal["web", "instagram"]
    status: Literal["uploading", "ready", "failed"]
    url: str
    thumbnail_url: str | None
    width: int | None
    height: int | None
    duration_ms: int | None
    derived_from_asset_id: str | None
    owner_hint: str | None
    palette: list[str] | None
    product_ids: list[str]
    reel_suitable: bool | None
    analyzed: bool
    archived: bool


class Instagram(BaseModel):
    status: Literal["not_connected", "pending", "connected", "error"]
    handle: str | None
    # False with INSTAGRAM=off: the wizard leaves out its Instagram step
    available: bool


class OnboardingState(BaseModel):
    business: BusinessInfo
    products: list[Product]
    brand: Brand
    assets: list[Asset]
    preferences: Questionnaire | None
    instagram: Instagram
    completed: bool
    whatsapp_url: str


class UploadRequest(BaseModel):
    kind: Literal["logo", "photo", "video"]
    filename: Annotated[str, StringConstraints(max_length=255)]
    content_type: Annotated[str, StringConstraints(max_length=100)]
    size_bytes: int = Field(gt=0)
    owner_hint: OptionalText = None


class UploadTicket(BaseModel):
    asset_id: str
    upload_url: str
    upload_token: str
    resumable: bool


class CompleteResponse(BaseModel):
    status: Literal["generating_brand"]
