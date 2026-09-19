"""Review actions on one FAQ: edit, approve, reject. Status rules live in services/faq_service.py."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import FaqStatus
from app.schemas.api import FaqOut, FaqUpdate
from app.services import faq_service

router = APIRouter(prefix="/api/faqs", tags=["faqs"])


@router.patch("/{faq_id}", response_model=FaqOut)
def edit_faq(faq_id: int, update: FaqUpdate, db: Session = Depends(get_db)) -> FaqOut:
    return FaqOut.model_validate(faq_service.update_faq(db, faq_id, update))


@router.post("/{faq_id}/approve", response_model=FaqOut)
def approve_faq(faq_id: int, db: Session = Depends(get_db)) -> FaqOut:
    return FaqOut.model_validate(faq_service.set_status(db, faq_id, FaqStatus.APPROVED))


@router.post("/{faq_id}/reject", response_model=FaqOut)
def reject_faq(faq_id: int, db: Session = Depends(get_db)) -> FaqOut:
    return FaqOut.model_validate(faq_service.set_status(db, faq_id, FaqStatus.REJECTED))
