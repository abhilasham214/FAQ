"""Declarative base shared by every table in app/models."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
