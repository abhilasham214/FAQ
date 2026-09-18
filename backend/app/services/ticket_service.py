from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DuplicateUploadError
from app.models import TicketRow, UploadRecord
from app.schemas.api import UploadOut
from app.schemas.ticket import Ticket
from app.services.ingestion import parse_tickets_csv


def ticket_from_row(row: TicketRow) -> Ticket:
    return Ticket(
        ticket_id=row.ticket_id, title=row.title, description=row.description,
        resolution=row.resolution, status=row.status,
    )


def save_upload(db: Session, content: bytes, filename: str) -> UploadOut:
    """Validate a CSV and store its new tickets.

    Duplicates are handled at two levels: an identical file is rejected outright
    (content hash), and ticket_ids that already exist are skipped.
    """
    file_hash = hashlib.sha256(content).hexdigest()
    if db.scalar(select(UploadRecord).where(UploadRecord.file_hash == file_hash)):
        raise DuplicateUploadError("This exact file has already been uploaded")

    result = parse_tickets_csv(content)  # raises on malformed / empty input
    ids = [t.ticket_id for t in result.tickets]
    existing = set(db.scalars(select(TicketRow.ticket_id).where(TicketRow.ticket_id.in_(ids))))
    new_tickets = [t for t in result.tickets if t.ticket_id not in existing]

    db.add_all(TicketRow(**t.model_dump()) for t in new_tickets)
    db.add(UploadRecord(file_hash=file_hash, filename=filename, tickets_added=len(new_tickets)))
    db.commit()
    return UploadOut(
        tickets_added=len(new_tickets),
        tickets_skipped_existing=len(result.tickets) - len(new_tickets),
        rejected_rows=result.errors,
    )
