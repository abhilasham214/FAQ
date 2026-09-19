"""Validated ticket rows and per-row upload errors."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, field_validator


class Ticket(BaseModel):
    ticket_id: str
    title: str
    description: str
    resolution: str
    status: str = "resolved"

    @field_validator("ticket_id", "title", "description", "resolution", "status", mode="before")
    @classmethod
    def _non_blank(cls, value: object) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            raise ValueError("must not be blank")
        return text


class RowError(BaseModel):
    row: int  # 1-based data row (header excluded)
    message: str


class IngestionResult(BaseModel):
    tickets: List[Ticket]
    errors: List[RowError]
