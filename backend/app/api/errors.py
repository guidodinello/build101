import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.storage import StorageError

logger = logging.getLogger(__name__)

INVALID_REQUEST = "Revisá los datos e intentá de nuevo."
ERROR_DETAIL_KEYS = ("type", "loc", "msg")
STORAGE_UNAVAILABLE = "No pudimos guardar el archivo. Probá de nuevo en un ratito."


class ApiError(Exception):
    """An error the web app shows as is: `message` is Spanish copy for the Owner (api.md)."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message


def _error_body(code: str, message: str, **extra: Any) -> dict[str, dict[str, Any]]:
    return {"error": {"code": code, "message": message, **extra}}


def error_response(exc: ApiError) -> JSONResponse:
    """The response of an ApiError, for a handler that must add to it (e.g. clear a cookie)."""
    return JSONResponse(_error_body(exc.code, exc.message), status_code=exc.status)


async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc)


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Only where and why: an error's `input` is the submitted value, `ctx` and `url` are noise.
    details = [{key: error[key] for key in ERROR_DETAIL_KEYS} for error in exc.errors()]
    body = _error_body("invalid_request", INVALID_REQUEST, details=jsonable_encoder(details))
    return JSONResponse(body, status_code=422)


async def _storage_error(_: Request, exc: StorageError) -> JSONResponse:
    logger.error("storage call failed: %s", exc)
    return JSONResponse(_error_body("storage_unavailable", STORAGE_UNAVAILABLE), status_code=502)


def install_error_handlers(app: FastAPI) -> None:
    # Starlette types handlers as taking `Exception`; it calls each with its registered class.
    app.add_exception_handler(ApiError, _api_error)  # pyright: ignore[reportArgumentType]
    app.add_exception_handler(
        RequestValidationError,
        _validation_error,  # pyright: ignore[reportArgumentType]
    )
    app.add_exception_handler(StorageError, _storage_error)  # pyright: ignore[reportArgumentType]
