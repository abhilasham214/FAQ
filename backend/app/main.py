"""FastAPI entry point: app, CORS, routers, and the domain-error -> HTTP-status mapping.

Request path: router (app/api) -> service (app/services) -> SQLAlchemy models (app/models).
Routes never catch domain errors; they bubble up to `domain_error_handler` below, which picks
the status code from STATUS_BY_ERROR. Wrong status code? Start with that table.

Run locally:  cd backend && uvicorn app.main:app --reload --port 8000   (docs at /docs)
"""
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
logger = logging.getLogger(__name__)

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
    # Runs once at startup. A crash here with a connection error means DATABASE_URL is wrong
    # or the database is not reachable yet.
    init_db()
    yield


app = FastAPI(title="Knowledge Base FAQ Auto Builder", lifespan=lifespan)
# The browser blocks responses whose Origin is not listed here; the UI then only says
# "Cannot reach the backend". CORS_ORIGINS must match the frontend URL exactly
# (scheme + host, no trailing slash), and changes need a restart.
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
    # isinstance match, so subclasses inherit their parent's status; unlisted errors become 500.
    status = next((code for cls, code in STATUS_BY_ERROR.items() if isinstance(exc, cls)), 500)
    return JSONResponse(status_code=status, content={"detail": str(exc)})


# Clients get a generic message; the full exception and traceback go to the server log.
# Search the log for "Database error on" to find it.
@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("Database error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "Database error; please try again"})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
