"""Pipeline step 1: parse and validate an uploaded CSV (no database access here)."""
from __future__ import annotations

import csv
import io
from typing import Union

from pydantic import ValidationError

from app.core.errors import EmptyDatasetError, MalformedCsvError
from app.schemas.ticket import IngestionResult, RowError, Ticket

REQUIRED_COLUMNS = ("ticket_id", "title", "description", "resolution", "status")


def parse_tickets_csv(source: Union[bytes, str]) -> IngestionResult:
    """Parse and validate a tickets CSV.

    Bad rows are collected as `errors` instead of failing the whole file.
    Raises MalformedCsvError for undecodable files / missing columns and
    EmptyDatasetError when no valid ticket remains.
    """
    if isinstance(source, bytes):
        try:
            text = source.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise MalformedCsvError("File is not valid UTF-8 text") from exc
    else:
        text = source

    if not text.strip():
        raise EmptyDatasetError("The CSV file is empty")

    reader = csv.DictReader(io.StringIO(text))
    header = [name.strip() for name in (reader.fieldnames or [])]
    missing = [col for col in REQUIRED_COLUMNS if col not in header]
    if missing:
        raise MalformedCsvError(f"Missing required column(s): {', '.join(missing)}")
    reader.fieldnames = header

    tickets: list[Ticket] = []
    errors: list[RowError] = []
    seen_ids: set[str] = set()

    try:
        for row_number, row in enumerate(reader, start=1):
            if None in row:  # more fields than header columns
                errors.append(RowError(row=row_number, message="Row has too many columns"))
                continue
            try:
                ticket = Ticket(**{col: row.get(col) for col in REQUIRED_COLUMNS})
            except ValidationError as exc:
                fields = ", ".join(str(e["loc"][0]) for e in exc.errors())
                errors.append(RowError(row=row_number, message=f"Invalid or missing: {fields}"))
                continue
            if ticket.ticket_id in seen_ids:
                errors.append(RowError(row=row_number, message=f"Duplicate ticket_id {ticket.ticket_id}"))
                continue
            seen_ids.add(ticket.ticket_id)
            tickets.append(ticket)
    except csv.Error as exc:
        raise MalformedCsvError(f"Could not parse CSV: {exc}") from exc

    if not tickets:
        raise EmptyDatasetError("No valid tickets found in the CSV")
    return IngestionResult(tickets=tickets, errors=errors)
