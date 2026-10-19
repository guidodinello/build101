import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel, ValidationError

from app.api.errors import install_error_handlers
from app.config import Settings
from app.main import app, docs_urls
from app.onboarding.schemas import MAX_LIST_ITEMS, ProductInput, ProductsInput


def test_docs_and_openapi_are_off_in_prod() -> None:
    assert docs_urls(Settings(env="prod")) == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }


def test_docs_and_openapi_stay_on_locally() -> None:
    assert docs_urls(Settings(env="local")) == {}


async def test_an_app_built_with_the_prod_urls_serves_no_docs() -> None:
    prod = FastAPI(**docs_urls(Settings(env="prod")))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=prod), base_url="http://t") as c:
        statuses = [
            (await c.get(path)).status_code for path in ("/docs", "/redoc", "/openapi.json")
        ]

    assert statuses == [404, 404, 404]


def test_the_schema_does_not_list_the_dev_routes() -> None:
    assert not [path for path in app.openapi()["paths"] if path.startswith("/dev")]


class Body(BaseModel):
    phone: str


async def test_a_validation_error_does_not_echo_the_submitted_value() -> None:
    api = FastAPI()
    install_error_handlers(api)

    @api.post("/x")
    async def route(body: Body) -> None: ...

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://t") as c:
        response = await c.post("/x", json={"phone": {"secret": "owner-private-value"}})

    assert response.status_code == 422
    assert "owner-private-value" not in response.text
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert set(error["details"][0]) == {"type", "loc", "msg"}


def product(name: str = "Banco") -> dict[str, object]:
    return {"name": name}


def test_the_product_list_is_capped_at_the_schema() -> None:
    ProductsInput.model_validate({"products": [product()] * MAX_LIST_ITEMS})

    with pytest.raises(ValidationError):
        ProductsInput.model_validate({"products": [product()] * (MAX_LIST_ITEMS + 1)})


def test_a_products_photo_list_is_capped_at_the_schema() -> None:
    ids = [str(n) for n in range(MAX_LIST_ITEMS + 1)]

    with pytest.raises(ValidationError):
        ProductInput.model_validate({"name": "Banco", "asset_ids": ids})
