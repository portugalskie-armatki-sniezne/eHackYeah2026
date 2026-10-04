import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app import (
    auth,
    comments,
    institution_contacts,
    master_reports,
    notifications,
    photo_proposals,
    photos,
    projects,
    reference,
    reports,
    service_entities,
    storage,
    users,
)
from app.db import pool
from app.inference.contracts import InferenceInputError, InferenceUnavailableError, InvalidInferenceResultError
from app.inference.router import router as inference_router
from app.inference.warmup import warmup
from app.security import jwt_secret


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    application.state.ready = False
    jwt_secret()
    storage.check_upload_dir()
    pool.open()
    try:
        if os.getenv("INFERENCE_REQUIRED", "false").lower() == "true":
            await run_in_threadpool(warmup)
        application.state.ready = True
        yield
    finally:
        application.state.ready = False
        pool.close()


app = FastAPI(title="eHackYeah2026 API", lifespan=lifespan)
app.state.ready = False
# every origin is allowed for now, requests carry a bearer token and no cookies.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(InferenceUnavailableError)
async def inference_unavailable(_request, _error) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Inference provider is unavailable"})


@app.exception_handler(InvalidInferenceResultError)
async def inference_invalid(_request, _error) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": "Inference provider returned an invalid result"})


@app.exception_handler(InferenceInputError)
async def inference_input_invalid(_request, _error) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": "Input is unsupported or exceeds model limits"})


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(reports.router)
app.include_router(photos.router)
app.include_router(master_reports.router)
app.include_router(photo_proposals.router)
app.include_router(comments.router)
app.include_router(notifications.router)
app.include_router(reference.router)
app.include_router(institution_contacts.router)
app.include_router(service_entities.router)
app.include_router(projects.router)
app.include_router(inference_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "eHackYeah2026 API"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> JSONResponse:
    if not app.state.ready:
        return JSONResponse(status_code=503, content={"status": "starting"})
    return JSONResponse(content={"status": "ok"})
