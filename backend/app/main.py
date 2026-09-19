from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api import clusters, faqs, stats, tickets
from app.core.errors import (
    DuplicateUploadError,
    EmbeddingError,
    EmptyDatasetError,
    FaqAlreadyExistsError,
    FaqBuilderError,
    FaqRegenerationError,
    InsufficientTicketsError,
    LLMError,
    MalformedCsvError,
    NotFoundError,
)
from app.core.config import get_settings
from app.database.session import init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")

# Domain error -> HTTP status. Routes stay free of try/except.
STATUS_BY_ERROR = {
    MalformedCsvError: 400,
    NotFoundError: 404,
    DuplicateUploadError: 409,
    FaqAlreadyExistsError: 409,
    EmptyDatasetError: 422,
    InsufficientTicketsError: 422,
    EmbeddingError: 502,
    LLMError: 502,
    FaqRegenerationError: 502,
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Knowledge Base FAQ Auto Builder", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
for router in (tickets.router, clusters.router, faqs.router, stats.router):
    app.include_router(router)


@app.exception_handler(FaqBuilderError)
async def domain_error_handler(_: Request, exc: FaqBuilderError) -> JSONResponse:
    status = next((code for cls, code in STATUS_BY_ERROR.items() if isinstance(exc, cls)), 500)
    return JSONResponse(status_code=status, content={"detail": str(exc)})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Database error; please try again"})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
