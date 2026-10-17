import logging

from fastapi import FastAPI

from app.channels.router import router as whatsapp_router

# uvicorn configures only its own loggers; without this, `app.*` INFO lines are dropped.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s — %(message)s")

app = FastAPI(title="build101")
app.include_router(whatsapp_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
