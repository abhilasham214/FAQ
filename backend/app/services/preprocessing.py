from __future__ import annotations

import re

from app.schemas.ticket import Ticket


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def ticket_to_text(ticket: Ticket) -> str:
    """Text that gets embedded: title + description + resolution.

    The resolution is included on purpose: tickets that were fixed the same
    way belong in the same FAQ, even if customers describe them differently.
    """
    parts = (ticket.title, ticket.description, ticket.resolution)
    return ". ".join(_clean(p).rstrip(".") for p in parts) + "."
