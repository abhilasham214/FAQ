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
