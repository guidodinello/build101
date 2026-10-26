import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dev import router as dev_router
from app.api.errors import install_error_handlers
from app.api.instagram import router as instagram_router
from app.api.onboarding import router as onboarding_router
from app.api.ready import router as ready_router
from app.background import get_background_work
from app.channels.router import close_clients, get_channel, get_owner_notify
from app.channels.router import router as whatsapp_router
from app.config import Settings, adapters_in_use, check_production, get_settings
from app.jobs.setup import build_job_runner
from app.log_redaction import RedactAccessLog, RedactQueryTokens
from app.media.public import router as media_router

# uvicorn configures only its own loggers; without this, `app.*` INFO lines are dropped.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s — %(message)s")
# httpx stays at INFO (its lines show Gemini/Kapso status codes) but must not log signed tokens.
logging.getLogger("httpx").addFilter(RedactQueryTokens())
# uvicorn's access log records every path and query: /api/o/{token}/..., the OAuth `code`/`state`.
logging.getLogger("uvicorn.access").addFilter(RedactAccessLog())

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    check_production(get_settings())
    adapters = adapters_in_use(get_settings()).items()
    logger.info("adapters in use: %s", " ".join(f"{name}={adapter}" for name, adapter in adapters))
    try:
        runner = build_job_runner(
            get_settings(),
            get_channel(),
            lambda: app.dependency_overrides.get(get_owner_notify, get_owner_notify)(),
        )
    except ValueError as exc:
        logger.warning("job runner is off: %s", exc, exc_info=True)
        runner = None
    if runner:
        await runner.start()
    app.state.job_runner = runner
    yield
    if runner:
        runner.stop()
    background = app.dependency_overrides.get(get_background_work, get_background_work)()
    await background.drain(get_settings().shutdown_timeout_s)
    # Not in the channel router's lifespan, which ends before this one: work that finishes in the
    # drain still tells the Owner through these clients.
    await close_clients()


class DocsUrls(TypedDict, total=False):
    docs_url: str | None
    redoc_url: str | None
    openapi_url: str | None


def docs_urls(settings: Settings) -> DocsUrls:
    """The FastAPI kwargs that turn off /docs, /redoc and /openapi.json in production."""
    if settings.env == "prod":
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


app = FastAPI(title="Neitor AI", lifespan=lifespan, **docs_urls(get_settings()))
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().frontend_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)
app.include_router(whatsapp_router)
app.include_router(media_router)
app.include_router(onboarding_router)
app.include_router(instagram_router)
app.include_router(dev_router)
app.include_router(ready_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
