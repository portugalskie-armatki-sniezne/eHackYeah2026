from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import auth, users
from app.db import pool
from app.security import jwt_secret


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    jwt_secret()
    pool.open()
    try:
        yield
    finally:
        pool.close()


app = FastAPI(title="eHackYeah2026 API", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(users.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "eHackYeah2026 API"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
