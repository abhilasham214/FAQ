import pytest
from pydantic import ValidationError

from app.core.errors import EmptyDatasetError, MalformedCsvError
from app.schemas.ticket import Ticket
from app.services.ingestion import parse_tickets_csv

HEADER = "ticket_id,title,description,resolution,status\n"


def test_valid_csv():
    csv_text = HEADER + "T1,Title,Desc,Fixed it,resolved\nT2,Title2,Desc2,Fixed 2,resolved\n"
    result = parse_tickets_csv(csv_text.encode())
    assert [t.ticket_id for t in result.tickets] == ["T1", "T2"]
    assert result.errors == []


def test_missing_column_is_malformed():
    with pytest.raises(MalformedCsvError, match="resolution"):
        parse_tickets_csv("ticket_id,title,description,status\nT1,a,b,resolved\n")


def test_non_utf8_is_malformed():
    with pytest.raises(MalformedCsvError):
        parse_tickets_csv(b"\xff\xfe\x00bad")


def test_empty_file():
    with pytest.raises(EmptyDatasetError):
        parse_tickets_csv(b"   \n")


def test_header_only_is_empty_dataset():
    with pytest.raises(EmptyDatasetError):
        parse_tickets_csv(HEADER)


def test_rows_with_missing_fields_are_reported_not_fatal():
    csv_text = HEADER + "T1,Title,Desc,Fixed,resolved\nT2,,Desc,Fixed,resolved\nT3,Title,Desc,,resolved\n"
    result = parse_tickets_csv(csv_text)
    assert [t.ticket_id for t in result.tickets] == ["T1"]
    assert [e.row for e in result.errors] == [2, 3]


def test_duplicate_ids_are_rejected():
    csv_text = HEADER + "T1,A,B,C,resolved\nT1,A2,B2,C2,resolved\n"
    result = parse_tickets_csv(csv_text)
    assert len(result.tickets) == 1
    assert "Duplicate" in result.errors[0].message


def test_ticket_rejects_blank_fields():
    with pytest.raises(ValidationError):
        Ticket(ticket_id="T1", title="  ", description="d", resolution="r", status="resolved")
