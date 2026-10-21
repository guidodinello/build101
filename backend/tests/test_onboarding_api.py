import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import ratelimit
from app.api import onboarding
from app.background import BackgroundWork, get_background_work
from app.channels.router import get_channel, get_owner_notify
from app.config import Settings, get_settings
from app.conversation.history import InMemoryHistory
from app.conversation.outbound import FixedReplies
from app.copy import messages_es
from app.db.models import BrandAsset, Business, Job, MagicLink, PilotSender
from app.db.session import get_session
from app.jobs.uploads import sweep_orphaned_uploads
from app.main import app
from app.onboarding import uploads
from app.onboarding.links import hash_token
from app.pilot import PilotList, get_pilot_list
from app.storage import StorageError, get_storage
from tests.conftest import make_image, requires_db
from tests.fakes import CountingStorage, FakeChannel, FakeStorage

DEV_TOKEN = "dev-secret"
PHONE = "59899123456"

pytestmark = requires_db

BUSINESS = {
    "name": "Muebles Ramírez",
    "category": "Muebles y deco",
    "one_liner": "Restauramos muebles de roble",
    "location": "Montevideo",
    "instagram_handle": "@mueblesramirez",
}
PREFERENCES = {
    "goal": "sales",
    "audiences": ["Familias"],
    "formality": 4,
    "humor": 2,
    "posts_per_week": 3,
    "emoji_policy": "few",
    "avoid": None,
    "current_offer": "10% en mesas",
}


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def channel() -> FakeChannel:
    return FakeChannel()


@pytest.fixture
def background() -> BackgroundWork:
    return BackgroundWork()


@pytest.fixture
async def client(
    sessions: async_sessionmaker[AsyncSession],
    storage: FakeStorage,
    channel: FakeChannel,
    background: BackgroundWork,
) -> AsyncIterator[httpx.AsyncClient]:
    async def session() -> AsyncIterator[AsyncSession]:
        async with sessions() as db:
            yield db

    settings = Settings(
        enable_dev_endpoints=True,
        dev_token=DEV_TOKEN,
        frontend_url="https://app.test",
        whatsapp_bot_number="59800000000",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_channel] = lambda: channel
    app.dependency_overrides[get_owner_notify] = lambda: FixedReplies(InMemoryHistory())
    app.dependency_overrides[get_background_work] = lambda: background
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    await background.join()
    app.dependency_overrides.clear()


async def new_link(client: httpx.AsyncClient, **body: Any) -> str:
    response = await client.post(
        "/dev/onboarding-link",
        json={"phone": PHONE, **body},
        headers={"X-Dev-Token": DEV_TOKEN},
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


async def uploaded_to_storage(
    client: httpx.AsyncClient,
    storage: FakeStorage,
    token: str,
    kind: str = "photo",
    data: bytes | None = None,
    content_type: str = "image/jpeg",
) -> str:
    """The asset id of a file the browser put in Storage, before the wizard completes it."""
    data = data if data is not None else make_image((1200, 900))
    ticket = await client.post(
        f"/api/o/{token}/uploads",
        json={
            "kind": kind,
            "filename": "foto.jpg",
            "content_type": content_type,
            "size_bytes": len(data),
        },
    )
    assert ticket.status_code == 200, ticket.text
    path = ticket.json()["upload_url"].split("/upload/assets/")[1].split("?")[0]
    storage.put("assets", path, data)
    return ticket.json()["asset_id"]


async def upload(
    client: httpx.AsyncClient,
    storage: FakeStorage,
    token: str,
    kind: str = "photo",
    data: bytes | None = None,
    content_type: str = "image/jpeg",
) -> dict[str, Any]:
    asset_id = await uploaded_to_storage(client, storage, token, kind, data, content_type)
    completed = await client.post(f"/api/o/{token}/assets/{asset_id}/complete")
    assert completed.status_code == 200, completed.text
    return completed.json()


def error_code(response: httpx.Response) -> str:
    return response.json()["error"]["code"]


async def test_dev_link_needs_the_dev_token(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/dev/onboarding-link", json={"phone": PHONE}, headers={"X-Dev-Token": "wrong"}
    )

    assert response.status_code == 401


async def test_dev_link_is_off_unless_enabled(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(dev_token=DEV_TOKEN)

    response = await client.post(
        "/dev/onboarding-link", json={"phone": PHONE}, headers={"X-Dev-Token": DEV_TOKEN}
    )

    assert response.status_code == 404


async def test_dev_link_rejects_a_non_ascii_token(client: httpx.AsyncClient) -> None:
    # Bytes: httpx refuses a non-ASCII str header, but a real client can send them (latin-1).
    response = await client.post(
        "/dev/onboarding-link", json={"phone": PHONE}, headers=[(b"x-dev-token", "ñandú".encode())]
    )

    assert response.status_code == 401


async def test_dev_link_is_off_in_prod_even_when_enabled(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        env="prod", enable_dev_endpoints=True, dev_token=DEV_TOKEN
    )

    response = await client.post(
        "/dev/onboarding-link", json={"phone": PHONE}, headers={"X-Dev-Token": DEV_TOKEN}
    )

    assert response.status_code == 404


async def test_dev_link_reuses_the_business_of_a_phone(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    response = await client.post(
        "/dev/onboarding-link",
        json={"phone": "+598 99 123 456", "business_name": "Muebles Ramírez"},
        headers={"X-Dev-Token": DEV_TOKEN},
    )
    await new_link(client)

    assert response.json()["url"] == f"https://app.test/o/{response.json()['token']}"
    async with sessions() as db:
        businesses = (await db.scalars(select(Business))).all()
        links = (await db.scalars(select(MagicLink))).all()
    assert [(b.owner_phone, b.name, b.onboarding_state) for b in businesses] == [
        (PHONE, "Muebles Ramírez", "awaiting_web_form")
    ]
    assert len(links) == 2
    assert response.json()["token"] not in {link.token_hash for link in links}


async def test_new_link_starts_with_an_empty_state(client: httpx.AsyncClient) -> None:
    token = await new_link(client, business_name="Muebles Ramírez")

    response = await client.get(f"/api/o/{token}")

    assert response.status_code == 200
    state = response.json()
    assert state["business"]["name"] == "Muebles Ramírez"
    assert state["products"] == []
    assert state["assets"] == []
    assert state["brand"] == {"three_words": [], "colors": []}
    assert state["preferences"] is None
    assert state["instagram"] == {"status": "not_connected", "handle": None}
    assert state["completed"] is False
    assert state["whatsapp_url"] == "https://wa.me/59800000000"


async def test_unknown_link_is_404_with_the_error_shape(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/o/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "link_not_found"
    assert response.json()["error"]["message"]


async def test_expired_link_is_410(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    async with sessions() as db:
        link = await db.scalar(select(MagicLink))
        assert link
        link.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await db.commit()

    response = await client.get(f"/api/o/{token}")

    assert response.status_code == 410
    assert error_code(response) == "link_expired"


async def test_business_is_saved(client: httpx.AsyncClient) -> None:
    token = await new_link(client)

    response = await client.put(f"/api/o/{token}/business", json=BUSINESS)

    assert response.status_code == 200
    assert response.json()["business"] == {
        **BUSINESS,
        "instagram_handle": "mueblesramirez",
        "description": None,
        "website": None,
    }


async def test_location_is_optional(client: httpx.AsyncClient) -> None:
    token = await new_link(client)
    body = {key: value for key, value in BUSINESS.items() if key != "location"}

    response = await client.put(f"/api/o/{token}/business", json=body)

    assert response.status_code == 200
    assert response.json()["business"]["location"] is None


async def test_saving_the_business_keeps_what_instagram_filled_in(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    async with sessions() as db:
        business = await db.scalar(select(Business))
        assert business
        business.website = "https://roble.uy"
        business.instagram_handle = "roble.taller"
        await db.commit()
    body = {key: value for key, value in BUSINESS.items() if key != "instagram_handle"}

    response = await client.put(f"/api/o/{token}/business", json=body)

    saved = response.json()["business"]
    assert (saved["website"], saved["instagram_handle"]) == ("https://roble.uy", "roble.taller")


async def test_business_needs_its_required_fields(client: httpx.AsyncClient) -> None:
    token = await new_link(client)

    response = await client.put(f"/api/o/{token}/business", json={**BUSINESS, "name": "  "})

    assert response.status_code == 422
    assert error_code(response) == "invalid_request"


async def test_products_are_upserted_in_order_and_left_out_ones_archived(
    client: httpx.AsyncClient,
) -> None:
    token = await new_link(client)
    first = await client.put(
        f"/api/o/{token}/products",
        json={
            "products": [
                {"name": "Mesa", "description": "De roble", "price": "$U 12.000"},
                {"name": "Silla", "description": ""},
            ]
        },
    )
    mesa = first.json()["products"][0]

    second = await client.put(
        f"/api/o/{token}/products",
        json={"products": [{"name": "Banco", "description": ""}, {**mesa, "name": "Mesa ratona"}]},
    )

    products = second.json()["products"]
    assert [(p["name"], p["position"]) for p in products] == [("Banco", 0), ("Mesa ratona", 1)]
    assert products[1]["id"] == mesa["id"]
    assert products[1]["price"] == "$U 12.000"


async def test_more_than_five_products_is_rejected(client: httpx.AsyncClient) -> None:
    token = await new_link(client)
    products = [{"name": f"Producto {n}", "description": ""} for n in range(6)]

    response = await client.put(f"/api/o/{token}/products", json={"products": products})

    assert response.status_code == 422
    assert error_code(response) == "too_many_products"


async def test_a_product_id_from_elsewhere_is_rejected(client: httpx.AsyncClient) -> None:
    token = await new_link(client)

    response = await client.put(
        f"/api/o/{token}/products",
        json={"products": [{"id": str(uuid.uuid4()), "name": "Mesa", "description": ""}]},
    )

    assert response.status_code == 422
    assert error_code(response) == "unknown_product"


async def test_brand_needs_colors_unless_there_is_no_brand_yet(client: httpx.AsyncClient) -> None:
    token = await new_link(client)
    words = ["cálido", "artesanal", "honesto"]

    missing = await client.put(f"/api/o/{token}/brand", json={"three_words": words, "colors": []})
    no_brand = await client.put(
        f"/api/o/{token}/brand",
        json={"three_words": words, "colors": ["#FFFFFF"], "no_brand_yet": True},
    )
    with_colors = await client.put(
        f"/api/o/{token}/brand", json={"three_words": words, "colors": ["#2F3E2C"]}
    )

    assert error_code(missing) == "missing_colors"
    assert no_brand.json()["brand"] == {"three_words": words, "colors": []}
    assert with_colors.json()["brand"] == {"three_words": words, "colors": ["#2f3e2c"]}


@pytest.mark.parametrize(
    ("words", "status"), [([], 422), (["cálido"], 200), (["a", "b", "c", "d"], 422)]
)
async def test_brand_takes_one_to_three_words(
    client: httpx.AsyncClient, words: list[str], status: int
) -> None:
    token = await new_link(client)

    response = await client.put(
        f"/api/o/{token}/brand", json={"three_words": words, "colors": ["#2f3e2c"]}
    )

    assert response.status_code == status


async def test_preferences_can_leave_the_tone_and_frequency_to_us(
    client: httpx.AsyncClient,
) -> None:
    token = await new_link(client)
    left_out = {"goal": "sales", "audiences": [], "avoid": None, "current_offer": None}

    await client.put(f"/api/o/{token}/preferences", json=left_out)
    response = await client.get(f"/api/o/{token}")

    assert response.json()["preferences"] == {
        **left_out,
        "formality": None,
        "humor": None,
        "posts_per_week": None,
        "emoji_policy": None,
    }


async def test_preferences_round_trip(client: httpx.AsyncClient) -> None:
    token = await new_link(client)

    await client.put(f"/api/o/{token}/preferences", json=PREFERENCES)
    response = await client.get(f"/api/o/{token}")

    assert response.json()["preferences"] == PREFERENCES


@pytest.mark.parametrize(
    ("kind", "content_type"),
    [("video", "video/mp4"), ("photo", "application/pdf"), ("photo", "image/gif")],
)
async def test_upload_rejects_what_the_wizard_does_not_take(
    client: httpx.AsyncClient, kind: str, content_type: str
) -> None:
    token = await new_link(client)

    response = await client.post(
        f"/api/o/{token}/uploads",
        json={"kind": kind, "filename": "x", "content_type": content_type, "size_bytes": 10},
    )

    assert response.status_code == 422
    assert error_code(response) == "unsupported_file"


async def test_upload_rejects_a_file_over_the_limit(client: httpx.AsyncClient) -> None:
    token = await new_link(client)

    response = await client.post(
        f"/api/o/{token}/uploads",
        json={
            "kind": "photo",
            "filename": "x.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 10 * 1024 * 1024 + 1,
        },
    )

    assert response.status_code == 422
    assert "10 MB" in response.json()["error"]["message"]


async def test_sixteenth_photo_is_rejected_before_upload(client: httpx.AsyncClient) -> None:
    token = await new_link(client)
    body = {"kind": "photo", "filename": "x.jpg", "content_type": "image/jpeg", "size_bytes": 10}
    for _ in range(15):
        assert (await client.post(f"/api/o/{token}/uploads", json=body)).status_code == 200

    response = await client.post(f"/api/o/{token}/uploads", json=body)

    assert response.status_code == 422
    assert error_code(response) == "too_many_photos"


async def test_ticket_points_to_the_business_folder_of_the_assets_bucket(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)

    response = await client.post(
        f"/api/o/{token}/uploads",
        json={"kind": "photo", "filename": "x.png", "content_type": "image/png", "size_bytes": 10},
    )

    ticket = response.json()
    async with sessions() as db:
        business = await db.scalar(select(Business))
        asset = await db.get(BrandAsset, uuid.UUID(ticket["asset_id"]))
    assert business and asset
    assert asset.storage_path == f"{business.id}/{asset.id}.png"
    assert (asset.status, asset.source, asset.kind) == ("uploading", "web", "photo")
    assert ticket["upload_url"].startswith(f"https://storage.test/upload/assets/{business.id}/")
    assert ticket["resumable"] is False


async def test_completing_an_upload_that_never_arrived_is_409(client: httpx.AsyncClient) -> None:
    token = await new_link(client)
    ticket = await client.post(
        f"/api/o/{token}/uploads",
        json={"kind": "photo", "filename": "x.jpg", "content_type": "image/jpeg", "size_bytes": 10},
    )

    response = await client.post(f"/api/o/{token}/assets/{ticket.json()['asset_id']}/complete")

    assert response.status_code == 409
    assert error_code(response) == "upload_missing"


async def test_completed_photo_is_ready_with_a_copy_for_the_agents_and_a_queued_analysis(
    client: httpx.AsyncClient, storage: FakeStorage, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)

    asset = await upload(client, storage, token)

    assert asset["status"] == "ready"
    assert (asset["width"], asset["height"]) == (1200, 900)
    assert asset["url"].startswith("https://storage.test/sign/assets/")
    assert asset["analyzed"] is False
    async with sessions() as db:
        business = await db.scalar(select(Business))
        jobs = (await db.scalars(select(Job))).all()
    assert business
    assert f"assets/{business.id}/{asset['id']}-llm.jpg" in storage.objects
    assert [(job.kind, job.payload) for job in jobs] == [
        ("analyze_asset", {"asset_id": asset["id"]})
    ]


async def test_heic_photo_is_stored_as_jpeg(
    client: httpx.AsyncClient, storage: FakeStorage, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)

    asset = await upload(
        client,
        storage,
        token,
        data=make_image((400, 300), format="HEIF"),
        content_type="image/heic",
    )

    async with sessions() as db:
        stored = await db.get(BrandAsset, uuid.UUID(asset["id"]))
    assert stored
    assert stored.storage_path.endswith(".jpg")
    assert stored.mime_type == "image/jpeg"
    assert storage.content_types[f"assets/{stored.storage_path}"] == "image/jpeg"


async def test_logo_gets_its_palette_and_no_analysis_job(
    client: httpx.AsyncClient, storage: FakeStorage, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)

    asset = await upload(client, storage, token, kind="logo", data=make_image((300, 300), "white"))

    assert asset["palette"] == ["#ffffff"]
    async with sessions() as db:
        assert (await db.scalars(select(Job))).all() == []


async def test_unreadable_upload_fails(
    client: httpx.AsyncClient, storage: FakeStorage, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    ticket = (
        await client.post(
            f"/api/o/{token}/uploads",
            json={
                "kind": "photo",
                "filename": "x.jpg",
                "content_type": "image/jpeg",
                "size_bytes": 3,
            },
        )
    ).json()
    path = ticket["upload_url"].split("/upload/assets/")[1].split("?")[0]
    storage.put("assets", path, b"nop")

    response = await client.post(f"/api/o/{token}/assets/{ticket['asset_id']}/complete")

    assert response.status_code == 422
    async with sessions() as db:
        asset = await db.get(BrandAsset, uuid.UUID(ticket["asset_id"]))
    assert asset and asset.status == "failed"
    assert storage.objects == {}


async def test_deleted_asset_leaves_the_state(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    token = await new_link(client)
    kept = await upload(client, storage, token)
    deleted = await upload(client, storage, token)

    response = await client.delete(f"/api/o/{token}/assets/{deleted['id']}")
    state = (await client.get(f"/api/o/{token}")).json()

    assert response.status_code == 204
    assert [asset["id"] for asset in state["assets"]] == [kept["id"]]


async def test_complete_checks_the_required_steps(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    token = await new_link(client)

    no_business = await client.post(f"/api/o/{token}/complete")
    await client.put(f"/api/o/{token}/business", json=BUSINESS)
    no_products = await client.post(f"/api/o/{token}/complete")
    await client.put(
        f"/api/o/{token}/products", json={"products": [{"name": "Mesa", "description": ""}]}
    )
    await upload(client, storage, token)
    await upload(client, storage, token)
    two_photos = await client.post(f"/api/o/{token}/complete")

    assert error_code(no_business) == "missing_business"
    assert error_code(no_products) == "missing_products"
    assert error_code(two_photos) == "missing_photos"


async def add_instagram_photo(
    sessions: async_sessionmaker[AsyncSession], kind: str = "photo", source: str = "instagram"
) -> uuid.UUID:
    async with sessions() as db:
        business = await db.scalar(select(Business))
        assert business
        asset = BrandAsset(
            business_id=business.id,
            kind=kind,
            source=source,
            status="ready",
            storage_path=f"{business.id}/{uuid.uuid4()}.jpg",
            mime_type="image/jpeg",
        )
        db.add(asset)
        await db.commit()
        return asset.id


async def test_state_lists_the_photos_imported_from_instagram(
    client: httpx.AsyncClient, storage: FakeStorage, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    uploaded = await upload(client, storage, token)
    imported = await add_instagram_photo(sessions)
    await add_instagram_photo(sessions, kind="logo")

    assets = (await client.get(f"/api/o/{token}")).json()["assets"]
    archived = await client.delete(f"/api/o/{token}/assets/{imported}")
    after = (await client.get(f"/api/o/{token}")).json()["assets"]

    assert [(asset["id"], asset["source"]) for asset in assets] == [
        (uploaded["id"], "web"),
        (str(imported), "instagram"),
    ]
    assert archived.status_code == 204
    assert [asset["id"] for asset in after] == [uploaded["id"]]


async def test_complete_is_404_for_an_asset_not_uploaded_from_the_web(
    client: httpx.AsyncClient, storage: FakeStorage, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    web = await upload(client, storage, token)
    whatsapp = await add_instagram_photo(sessions, source="whatsapp")
    instagram = await add_instagram_photo(sessions)

    whatsapp_response = await client.post(f"/api/o/{token}/assets/{whatsapp}/complete")
    instagram_response = await client.post(f"/api/o/{token}/assets/{instagram}/complete")
    web_response = await client.post(f"/api/o/{token}/assets/{web['id']}/complete")

    assert whatsapp_response.status_code == 404
    assert error_code(whatsapp_response) == "asset_not_found"
    assert instagram_response.status_code == 404
    assert error_code(instagram_response) == "asset_not_found"
    assert web_response.status_code == 200
    assert web_response.json()["source"] == "web"


async def test_photos_from_instagram_count_toward_the_minimum(
    client: httpx.AsyncClient, storage: FakeStorage, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    await client.put(f"/api/o/{token}/business", json=BUSINESS)
    await client.put(
        f"/api/o/{token}/products", json={"products": [{"name": "Mesa", "description": ""}]}
    )
    await upload(client, storage, token)
    await add_instagram_photo(sessions)
    await add_instagram_photo(sessions)

    response = await client.post(f"/api/o/{token}/complete")

    assert response.status_code == 202


async def test_complete_starts_the_brand_and_tells_the_owner_once(
    client: httpx.AsyncClient,
    storage: FakeStorage,
    channel: FakeChannel,
    background: BackgroundWork,
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    token = await new_link(client)
    await client.put(f"/api/o/{token}/business", json=BUSINESS)
    await client.put(
        f"/api/o/{token}/products", json={"products": [{"name": "Mesa", "description": ""}]}
    )
    for _ in range(3):
        await upload(client, storage, token)

    first = await client.post(f"/api/o/{token}/complete")
    again = await client.post(f"/api/o/{token}/complete")
    late_edit = await client.put(f"/api/o/{token}/business", json=BUSINESS)
    state = (await client.get(f"/api/o/{token}")).json()
    await background.join()

    assert (first.status_code, first.json()) == (202, {"status": "generating_brand"})
    assert again.status_code == 202
    assert channel.sent == [(PHONE, messages_es.BRAND_GENERATING)]
    assert late_edit.status_code == 409
    assert error_code(late_edit) == "onboarding_completed"
    assert state["completed"] is True
    async with sessions() as db:
        business = await db.scalar(select(Business))
        kinds = (await db.scalars(select(Job.kind).order_by(Job.created_at))).all()
    assert business and business.onboarding_state == "generating_brand"
    assert kinds.count("generate_brand") == 1


WIZARD_WRITES = [
    ("PUT", "/business", BUSINESS),
    ("PUT", "/products", {"products": [{"name": "Silla", "description": ""}]}),
    ("PUT", "/brand", {"three_words": ["cálido"], "colors": ["#112233"]}),
    ("PUT", "/preferences", PREFERENCES),
    (
        "POST",
        "/uploads",
        {"kind": "photo", "filename": "a.jpg", "content_type": "image/jpeg", "size_bytes": 1},
    ),
    ("POST", "/assets/{asset_id}/complete", None),
    ("DELETE", "/assets/{asset_id}", None),
    ("POST", "/instagram/connect", {}),
]


def off_the_pilot_list() -> PilotList:
    return PilotList(frozenset({"59800000009"}), None, open_when_empty=False)


@pytest.mark.parametrize(("method", "path", "body"), WIZARD_WRITES)
async def test_a_number_not_on_the_pilot_list_saves_uploads_and_imports_nothing(
    client: httpx.AsyncClient,
    storage: FakeStorage,
    sessions: async_sessionmaker[AsyncSession],
    method: str,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    token = await new_link(client)
    asset_id = await uploaded_to_storage(client, storage, token)
    app.dependency_overrides[get_pilot_list] = off_the_pilot_list

    response = await client.request(
        method, f"/api/o/{token}{path.format(asset_id=asset_id)}", json=body
    )

    assert response.status_code == 403
    assert error_code(response) == "not_in_pilot"
    assert response.json()["error"]["message"] == onboarding.NOT_IN_PILOT
    async with sessions() as db:
        business = await db.scalar(select(Business))
        assets = (await db.scalars(select(BrandAsset))).all()
        jobs = (await db.scalars(select(Job))).all()
    assert business and (business.name, business.onboarding_data) == (None, {})
    assert [(asset.status, asset.archived_at) for asset in assets] == [("uploading", None)]
    assert jobs == []


async def ready_to_complete(client: httpx.AsyncClient, storage: FakeStorage) -> str:
    token = await new_link(client)
    await client.put(f"/api/o/{token}/business", json=BUSINESS)
    await client.put(
        f"/api/o/{token}/products", json={"products": [{"name": "Mesa", "description": ""}]}
    )
    for _ in range(3):
        await upload(client, storage, token)
    return token


async def test_a_number_not_on_the_pilot_list_cannot_complete_the_form(
    client: httpx.AsyncClient,
    storage: FakeStorage,
    channel: FakeChannel,
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    token = await ready_to_complete(client, storage)
    app.dependency_overrides[get_pilot_list] = off_the_pilot_list

    response = await client.post(f"/api/o/{token}/complete")
    state = (await client.get(f"/api/o/{token}")).json()

    assert response.status_code == 403
    assert error_code(response) == "not_in_pilot"
    assert response.json()["error"]["message"] == onboarding.NOT_IN_PILOT
    assert state["completed"] is False
    assert channel.sent == []
    async with sessions() as db:
        business = await db.scalar(select(Business))
        kinds = (await db.scalars(select(Job.kind))).all()
    assert business and business.onboarding_state == "awaiting_web_form"
    assert "generate_brand" not in kinds


async def test_a_number_in_pilot_senders_completes_the_form(
    client: httpx.AsyncClient, storage: FakeStorage, sessions: async_sessionmaker[AsyncSession]
) -> None:
    async with sessions() as db:
        db.add(PilotSender(phone=PHONE))
        await db.commit()
    app.dependency_overrides[get_pilot_list] = lambda: PilotList(
        frozenset(), sessions, open_when_empty=False
    )
    token = await ready_to_complete(client, storage)

    response = await client.post(f"/api/o/{token}/complete")

    assert (response.status_code, response.json()) == (202, {"status": "generating_brand"})


async def test_products_link_their_own_photos(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    token = await new_link(client)
    mesa_photos = [(await upload(client, storage, token))["id"] for _ in range(2)]
    general = await upload(client, storage, token)

    saved = await client.put(
        f"/api/o/{token}/products",
        json={
            "products": [
                {"name": "Mesa", "description": "", "asset_ids": mesa_photos},
                {"name": "Silla", "description": "", "asset_ids": []},
            ]
        },
    )

    state = saved.json()
    mesa, silla = state["products"]
    assert (mesa["asset_count"], silla["asset_count"]) == (2, 0)
    product_ids = {asset["id"]: asset["product_ids"] for asset in state["assets"]}
    assert all(product_ids[photo] == [mesa["id"]] for photo in mesa_photos)
    assert product_ids[general["id"]] == []


async def test_saving_products_again_replaces_their_photos(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    token = await new_link(client)
    first, second = [(await upload(client, storage, token))["id"] for _ in range(2)]
    saved = await client.put(
        f"/api/o/{token}/products",
        json={"products": [{"name": "Mesa", "description": "", "asset_ids": [first]}]},
    )
    mesa = saved.json()["products"][0]

    moved = await client.put(
        f"/api/o/{token}/products",
        json={"products": [{**mesa, "asset_ids": [second]}]},
    )
    unchanged = await client.put(
        f"/api/o/{token}/products", json={"products": [{**mesa, "asset_ids": None}]}
    )

    def links(response: httpx.Response) -> dict[str, list[str]]:
        return {asset["id"]: asset["product_ids"] for asset in response.json()["assets"]}

    assert links(moved) == {first: [], second: [mesa["id"]]}
    assert links(unchanged) == links(moved)


async def test_photos_of_a_removed_product_are_no_longer_linked(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    token = await new_link(client)
    photo = (await upload(client, storage, token))["id"]
    await client.put(
        f"/api/o/{token}/products",
        json={"products": [{"name": "Mesa", "description": "", "asset_ids": [photo]}]},
    )

    response = await client.put(
        f"/api/o/{token}/products", json={"products": [{"name": "Banco", "description": ""}]}
    )

    assert response.json()["assets"][0]["product_ids"] == []


async def test_more_than_five_photos_for_a_product_is_rejected(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    token = await new_link(client)
    photos = [(await upload(client, storage, token))["id"] for _ in range(6)]

    response = await client.put(
        f"/api/o/{token}/products",
        json={"products": [{"name": "Mesa", "description": "", "asset_ids": photos}]},
    )

    assert response.status_code == 422
    assert error_code(response) == "too_many_product_photos"


async def test_a_product_photo_must_be_a_ready_photo_of_the_business(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    token = await new_link(client)
    logo = await upload(client, storage, token, kind="logo")
    archived = await upload(client, storage, token)
    await client.delete(f"/api/o/{token}/assets/{archived['id']}")

    for asset_id in [logo["id"], archived["id"], str(uuid.uuid4())]:
        response = await client.put(
            f"/api/o/{token}/products",
            json={"products": [{"name": "Mesa", "description": "", "asset_ids": [asset_id]}]},
        )

        assert response.status_code == 422
        assert error_code(response) == "unknown_asset"


async def test_a_second_link_cannot_start_the_brand_again(
    client: httpx.AsyncClient,
    storage: FakeStorage,
    channel: FakeChannel,
    background: BackgroundWork,
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    first = await new_link(client)
    second = await new_link(client)
    await client.put(f"/api/o/{first}/business", json=BUSINESS)
    await client.put(
        f"/api/o/{first}/products", json={"products": [{"name": "Mesa", "description": ""}]}
    )
    for _ in range(3):
        await upload(client, storage, first)
    await client.post(f"/api/o/{first}/complete")

    again = await client.post(f"/api/o/{second}/complete")
    late_edit = await client.put(f"/api/o/{second}/business", json=BUSINESS)
    await background.join()

    assert again.status_code == 202
    assert late_edit.status_code == 409
    assert channel.sent == [(PHONE, messages_es.BRAND_GENERATING)]
    async with sessions() as db:
        kinds = (await db.scalars(select(Job.kind))).all()
    assert kinds.count("generate_brand") == 1


async def submitted_business_with_a_sibling_link(
    client: httpx.AsyncClient, storage: FakeStorage
) -> tuple[str, str, str]:
    """Link A submits the form; returns A, an untouched link B and a photo's asset id."""
    first = await new_link(client)
    second = await new_link(client)
    await client.put(f"/api/o/{first}/business", json=BUSINESS)
    await client.put(
        f"/api/o/{first}/products", json={"products": [{"name": "Mesa", "description": ""}]}
    )
    assets = [await upload(client, storage, first) for _ in range(3)]
    assert (await client.post(f"/api/o/{first}/complete")).status_code == 202
    return first, second, assets[0]["id"]


@pytest.mark.parametrize(("method", "path", "body"), WIZARD_WRITES)
async def test_a_sibling_link_takes_no_edits_once_the_form_is_submitted(
    client: httpx.AsyncClient,
    storage: FakeStorage,
    method: str,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    _, sibling, asset_id = await submitted_business_with_a_sibling_link(client, storage)

    response = await client.request(
        method, f"/api/o/{sibling}{path.format(asset_id=asset_id)}", json=body
    )

    assert response.status_code == 409
    assert error_code(response) == "onboarding_completed"


async def test_a_sibling_link_shows_the_form_as_completed(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    _, sibling, _ = await submitted_business_with_a_sibling_link(client, storage)

    state = await client.get(f"/api/o/{sibling}")

    assert state.status_code == 200
    assert state.json()["completed"] is True


async def ticket_with_object(
    client: httpx.AsyncClient,
    storage: FakeStorage,
    token: str,
    data: bytes,
    kind: str = "photo",
    content_type: str = "image/png",
    declared_bytes: int | None = None,
) -> str:
    """A ticket whose object the browser already put in Storage; returns the asset id.

    `declared_bytes` is the size the browser claims; the signed URL doesn't enforce it."""
    ticket = (
        await client.post(
            f"/api/o/{token}/uploads",
            json={
                "kind": kind,
                "filename": "x.png",
                "content_type": content_type,
                "size_bytes": declared_bytes or len(data),
            },
        )
    ).json()
    storage.put("assets", ticket["upload_url"].split("/upload/assets/")[1].split("?")[0], data)
    return ticket["asset_id"]


async def test_a_tiff_declared_as_png_is_unsupported(
    client: httpx.AsyncClient, storage: FakeStorage, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    asset_id = await ticket_with_object(client, storage, token, make_image((60, 40), format="TIFF"))

    response = await client.post(f"/api/o/{token}/assets/{asset_id}/complete")

    assert response.status_code == 422
    assert error_code(response) == "unsupported_file"
    async with sessions() as db:
        asset = await db.get(BrandAsset, uuid.UUID(asset_id))
    assert asset and asset.status == "failed"
    assert storage.objects == {}


@pytest.mark.parametrize(
    ("format", "content_type"),
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
async def test_jpeg_png_and_webp_uploads_still_pass(
    client: httpx.AsyncClient, storage: FakeStorage, format: str, content_type: str
) -> None:
    token = await new_link(client)

    asset = await upload(
        client,
        storage,
        token,
        data=make_image((120, 80), format=format),
        content_type=content_type,
    )

    assert asset["status"] == "ready"


async def test_an_object_over_the_size_limit_is_refused_and_fails_the_asset(
    client: httpx.AsyncClient,
    storage: FakeStorage,
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    token = await new_link(client)
    asset_id = await ticket_with_object(
        client,
        storage,
        token,
        b"x" * (10 * 1024 * 1024 + 1),
        content_type="image/jpeg",
        declared_bytes=1024,
    )

    response = await client.post(f"/api/o/{token}/assets/{asset_id}/complete")

    assert response.status_code == 422
    assert error_code(response) == "unsupported_file"
    async with sessions() as db:
        asset = await db.get(BrandAsset, uuid.UUID(asset_id))
    assert asset and asset.status == "failed"
    assert storage.objects == {}


async def test_a_failed_asset_is_refused_again_without_downloading_it(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    counting = CountingStorage()
    app.dependency_overrides[get_storage] = lambda: counting
    token = await new_link(client)
    asset_id = await ticket_with_object(client, counting, token, b"not an image")
    first = await client.post(f"/api/o/{token}/assets/{asset_id}/complete")
    assert first.status_code == 422
    downloads = counting.downloads

    again = await client.post(f"/api/o/{token}/assets/{asset_id}/complete")

    assert again.status_code == 422
    assert error_code(again) == "upload_failed"
    assert again.json()["error"]["message"] == onboarding.UPLOAD_FAILED
    assert counting.downloads == downloads


async def test_a_retried_over_cap_upload_says_upload_failed_not_image_too_large(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(uploads, "MAX_PIXELS", 100 * 100)
    counting = CountingStorage()
    app.dependency_overrides[get_storage] = lambda: counting
    token = await new_link(client)
    asset_id = await ticket_with_object(
        client, counting, token, make_image((101, 100)), content_type="image/jpeg"
    )
    first = await client.post(f"/api/o/{token}/assets/{asset_id}/complete")
    downloads = counting.downloads

    retry = await client.post(f"/api/o/{token}/assets/{asset_id}/complete")

    assert error_code(first) == "image_too_large"
    assert retry.status_code == 422
    assert error_code(retry) == "upload_failed"
    assert counting.downloads == downloads


async def test_an_image_over_the_pixel_cap_gets_its_own_error(
    client: httpx.AsyncClient,
    storage: FakeStorage,
    sessions: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(uploads, "MAX_PIXELS", 100 * 100)
    token = await new_link(client)
    asset_id = await ticket_with_object(
        client, storage, token, make_image((101, 100)), content_type="image/jpeg"
    )

    response = await client.post(f"/api/o/{token}/assets/{asset_id}/complete")

    assert response.status_code == 422
    assert error_code(response) == "image_too_large"
    assert response.json()["error"]["message"] == onboarding.IMAGE_TOO_LARGE
    async with sessions() as db:
        asset = await db.get(BrandAsset, uuid.UUID(asset_id))
    assert asset and asset.status == "failed"
    assert storage.objects == {}


async def upload_complete_delete(
    client: httpx.AsyncClient, storage: FakeStorage, token: str, kind: str = "photo"
) -> None:
    asset = await upload(client, storage, token, kind=kind)
    deleted = await client.delete(f"/api/o/{token}/assets/{asset['id']}")
    assert deleted.status_code == 204


async def request_upload(client: httpx.AsyncClient, token: str, kind: str) -> httpx.Response:
    return await client.post(
        f"/api/o/{token}/uploads",
        json={"kind": kind, "filename": "a.jpg", "content_type": "image/jpeg", "size_bytes": 1},
    )


async def test_archiving_photos_does_not_free_uploads_forever(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    token = await new_link(client)
    for _ in range(onboarding.MAX_PHOTO_UPLOADS):
        await upload_complete_delete(client, storage, token)

    response = await request_upload(client, token, "photo")

    assert response.status_code == 422
    assert error_code(response) == "too_many_photos"
    assert response.json()["error"]["message"] == onboarding.PHOTO_UPLOADS_USED_UP


async def test_photos_in_use_are_still_capped_at_fifteen(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    token = await new_link(client)
    for _ in range(onboarding.MAX_PHOTOS):
        await upload(client, storage, token)

    response = await request_upload(client, token, "photo")

    assert error_code(response) == "too_many_photos"
    assert response.json()["error"]["message"] == onboarding.TOO_MANY_PHOTOS


async def test_logos_are_capped_while_in_use(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    token = await new_link(client)
    for _ in range(onboarding.MAX_LOGOS):
        await upload(client, storage, token, kind="logo", data=make_image((200, 100)))

    response = await request_upload(client, token, "logo")

    assert response.status_code == 422
    assert error_code(response) == "too_many_logos"
    assert response.json()["error"]["message"] == onboarding.TOO_MANY_LOGOS


async def test_archiving_logos_does_not_free_uploads_forever(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    token = await new_link(client)
    for _ in range(onboarding.MAX_LOGO_UPLOADS):
        await upload_complete_delete(client, storage, token, kind="logo")

    response = await request_upload(client, token, "logo")

    assert response.status_code == 422
    assert error_code(response) == "too_many_logos"
    assert response.json()["error"]["message"] == onboarding.LOGO_UPLOADS_USED_UP


async def test_a_new_photo_still_fits_after_deleting_one_below_the_lifetime_cap(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    token = await new_link(client)
    await upload_complete_delete(client, storage, token)

    assert (await request_upload(client, token, "photo")).status_code == 200


async def test_archiving_deletes_the_files_from_storage(
    client: httpx.AsyncClient, storage: FakeStorage
) -> None:
    token = await new_link(client)
    kept = await upload(client, storage, token)
    heic = await upload(
        client,
        storage,
        token,
        data=make_image((120, 80), format="HEIF"),
        content_type="image/heic",
    )
    before = set(storage.objects)
    assert len(before) == 2 + 3  # kept: JPEG and copy; HEIC: original, its JPEG and copy

    response = await client.delete(f"/api/o/{token}/assets/{heic['id']}")

    assert response.status_code == 204
    gone = before - set(storage.objects)
    assert {path.rsplit("/", 1)[1].split(".")[0] for path in gone} == {
        heic["id"],
        f"{heic['id']}-llm",
    }
    assert len(gone) == 3
    assert any(kept["id"] in path for path in storage.objects)


async def test_archiving_still_answers_204_when_storage_fails(
    client: httpx.AsyncClient, storage: FakeStorage, sessions: async_sessionmaker[AsyncSession]
) -> None:
    async def broken(bucket: str, paths: list[str]) -> None:
        raise StorageError("down")

    token = await new_link(client)
    asset = await upload(client, storage, token)
    storage.remove = broken  # type: ignore[method-assign]

    response = await client.delete(f"/api/o/{token}/assets/{asset['id']}")

    assert response.status_code == 204
    async with sessions() as db:
        row = await db.get(BrandAsset, uuid.UUID(asset["id"]))
    assert row and row.archived_at is not None


async def test_an_edit_waiting_on_the_submit_is_refused_once_it_commits(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    """A sibling write that reaches the check while `/complete` holds the Business can't slip in
    after the form was submitted: it waits for the lock, then sees the submit."""
    first = await new_link(client)
    second = await new_link(client)
    async with sessions() as db:
        business = await db.scalar(select(Business))
        assert business is not None
        await db.refresh(business, with_for_update=True)  # what /complete holds while it stamps
        edit = asyncio.create_task(client.put(f"/api/o/{second}/business", json=BUSINESS))
        await asyncio.sleep(0.3)
        assert not edit.done()
        link = await db.scalar(select(MagicLink).where(MagicLink.token_hash == hash_token(first)))
        assert link is not None
        link.completed_at = datetime.now(UTC)
        await db.commit()

    response = await asyncio.wait_for(edit, timeout=5)

    assert response.status_code == 409
    assert error_code(response) == "onboarding_completed"
    async with sessions() as db:
        assert (await db.scalar(select(Business.name))) != BUSINESS["name"]


async def test_a_photo_being_read_does_not_hold_the_business(
    client: httpx.AsyncClient, storage: FakeStorage, sessions: async_sessionmaker[AsyncSession]
) -> None:
    """`/assets/{id}/complete` releases the Business lock before the download and decode, so the
    submit and the other open routes don't wait on a slow photo."""
    token = await new_link(client)
    data = make_image((1200, 900))
    ticket = await client.post(
        f"/api/o/{token}/uploads",
        json={
            "kind": "photo",
            "filename": "foto.jpg",
            "content_type": "image/jpeg",
            "size_bytes": len(data),
        },
    )
    asset_id = ticket.json()["asset_id"]
    storage.put(
        "assets", ticket.json()["upload_url"].split("/upload/assets/")[1].split("?")[0], data
    )
    downloading, release = asyncio.Event(), asyncio.Event()
    download = storage.download

    async def slow_download(
        bucket: str, path: str, *, max_bytes: int | None = None
    ) -> bytes | None:
        downloading.set()
        await release.wait()
        return await download(bucket, path, max_bytes=max_bytes)

    storage.download = slow_download  # type: ignore[method-assign]
    completing = asyncio.create_task(client.post(f"/api/o/{token}/assets/{asset_id}/complete"))
    try:
        await asyncio.wait_for(downloading.wait(), timeout=5)
        async with sessions() as db:
            # NOWAIT fails at once if the photo's request still holds the Business row.
            business = await db.scalar(select(Business).with_for_update(nowait=True))
            assert business is not None
            await db.rollback()
    finally:
        release.set()

    response = await asyncio.wait_for(completing, timeout=5)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ready"


async def test_an_object_put_after_its_asset_was_archived_is_swept(
    client: httpx.AsyncClient, storage: FakeStorage, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    ticket = (await request_upload(client, token, "photo")).json()
    deleted = await client.delete(f"/api/o/{token}/assets/{ticket['asset_id']}")
    assert deleted.status_code == 204
    # The signed URL is still valid: the browser's PUT lands after the DELETE.
    path = ticket["upload_url"].split("/upload/assets/")[1].split("?")[0]
    storage.put("assets", path, make_image((120, 80)))
    assert storage.objects

    await sweep_orphaned_uploads(sessions, storage)

    assert storage.objects == {}


@pytest.fixture
def tight_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two calls per token and no refill, so the third one is over the limit."""
    monkeypatch.setattr(ratelimit, "onboarding_limiter", ratelimit.RateLimiter(2, 0))


async def test_calls_over_the_token_limit_get_429(
    client: httpx.AsyncClient, tight_limit: None
) -> None:
    token = await new_link(client)

    assert (await client.get(f"/api/o/{token}")).status_code == 200
    assert (await client.get(f"/api/o/{token}")).status_code == 200
    limited = await client.get(f"/api/o/{token}")

    assert limited.status_code == 429
    assert limited.json() == {
        "error": {"code": "rate_limited", "message": ratelimit.TOO_MANY_REQUESTS}
    }
    assert "retry-after" not in limited.headers


async def test_the_limit_covers_every_wizard_route_and_each_token_has_its_own(
    client: httpx.AsyncClient, tight_limit: None
) -> None:
    token, other = await new_link(client), await new_link(client, phone="59899000002")
    await client.get(f"/api/o/{token}")
    await client.get(f"/api/o/{token}")

    assert (await client.put(f"/api/o/{token}/business", json=BUSINESS)).status_code == 429
    assert (await client.post(f"/api/o/{token}/complete")).status_code == 429
    assert (await client.post(f"/api/o/{token}/instagram/connect")).status_code == 429
    assert (await client.get(f"/api/o/{token}/instagram/start?ticket=x")).status_code == 429
    assert (await client.get(f"/api/o/{other}")).status_code == 200


async def test_the_limit_is_keyed_on_the_hash_of_the_token(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    limiter = ratelimit.RateLimiter(5, 0)
    monkeypatch.setattr(ratelimit, "onboarding_limiter", limiter)
    token = await new_link(client)

    await client.get(f"/api/o/{token}")

    assert list(limiter._buckets) == [hash_token(token)]
