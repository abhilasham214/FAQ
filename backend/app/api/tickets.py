from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.api import UploadOut
from app.services.ticket_service import save_upload

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.post("/upload", response_model=UploadOut)
def upload_tickets(file: UploadFile = File(...), db: Session = Depends(get_db)) -> UploadOut:
    return save_upload(db, file.file.read(), file.filename or "upload.csv")
