from fastapi import FastAPI

from app.channels.router import router as whatsapp_router

app = FastAPI(title="build101")
app.include_router(whatsapp_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
