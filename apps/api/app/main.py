from fastapi import FastAPI

app = FastAPI(title="eHackYeah2026 API")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "eHackYeah2026 API"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
