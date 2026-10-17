from fastapi import FastAPI

app = FastAPI(title="build101")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
