import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dev import router as dev_router
from app.api.errors import install_error_handlers
from app.api.instagram import router as instagram_router
from app.api.onboarding import router as onboarding_router
from app.channels.router import get_channel, get_owner_notify
from app.channels.router import router as whatsapp_router
from app.config import get_settings
from app.jobs.setup import build_job_runner
from app.log_redaction import RedactQueryTokens
from app.media.public import router as media_router

# uvicorn configures only its own loggers; without this, `app.*` INFO lines are dropped.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s — %(message)s")
# httpx stays at INFO (its lines show Gemini/Kapso status codes) but must not log signed tokens.
logging.getLogger("httpx").addFilter(RedactQueryTokens())

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        runner = build_job_runner(
            get_settings(),
            get_channel(),
            lambda: app.dependency_overrides.get(get_owner_notify, get_owner_notify)(),
        )
    except ValueError:
        logger.warning("job runner is off: no WhatsApp channel", exc_info=True)
        runner = None
    if runner:
        await runner.start()
    yield
    if runner:
        await runner.stop()


app = FastAPI(title="Neitor AI", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in get_settings().frontend_origins.split(",") if origin.strip()
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)
app.include_router(whatsapp_router)
app.include_router(media_router)
app.include_router(onboarding_router)
app.include_router(instagram_router)
app.include_router(dev_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
