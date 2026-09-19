"""Database engine and per-request sessions.

- DATABASE_URL unset -> SQLite file `faq_dev.db` in the working directory (handy for dev).
- Tables are created by init_db() at startup (main.lifespan). There are no migrations: after
  changing a model, reset the affected tables (see README "Resetting the database").
- "Database error; please try again" (HTTP 503) in the UI = a SQLAlchemyError. The handler in
  main.py does not log the underlying exception, so reproduce locally (or log it there) to see it.
  Most common cause in production: a wrong DATABASE_URL or the database being unreachable.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.database.base import Base

DEV_FALLBACK_URL = "sqlite:///./faq_dev.db"  # only used when DATABASE_URL is unset


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url or DEV_FALLBACK_URL
    # Hosted Postgres providers hand out postgres:// URLs, which SQLAlchemy 2 rejects.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    # SQLite: FastAPI runs sync routes on several threads, which SQLite refuses by default.
    # Postgres: pre-ping replaces connections the server closed while idle, instead of
    # failing the next request with a 503.
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    return create_engine(url, **kwargs)


@lru_cache
def _session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def init_db() -> None:
    """Create tables if missing. (A real deployment would use Alembic migrations.)"""
    import app.models  # noqa: F401  (registers all tables on Base.metadata)

    Base.metadata.create_all(get_engine())


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = _session_factory()()
    try:
        yield db
    finally:
        db.close()
