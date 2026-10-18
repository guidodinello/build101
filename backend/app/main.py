import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dev import router as dev_router
from app.api.errors import install_error_handlers
from app.api.onboarding import router as onboarding_router
from app.channels.router import router as whatsapp_router
from app.config import get_settings
from app.media.public import router as media_router

# uvicorn configures only its own loggers; without this, `app.*` INFO lines are dropped.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s — %(message)s")

app = FastAPI(title="build101")
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
app.include_router(dev_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
