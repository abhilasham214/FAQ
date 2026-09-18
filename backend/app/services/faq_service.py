from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import Faq, FaqStatus
from app.schemas.api import FaqUpdate


def get_faq(db: Session, faq_id: int) -> Faq:
    faq = db.get(Faq, faq_id)
    if faq is None:
        raise NotFoundError(f"FAQ {faq_id} not found")
    return faq


def update_faq(db: Session, faq_id: int, update: FaqUpdate) -> Faq:
    """Apply a partial edit; the FAQ goes back to REVIEW, even if it was APPROVED."""
    faq = get_faq(db, faq_id)
    changes = update.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(faq, field, value)
    if changes:
        faq.status = FaqStatus.REVIEW.value
    db.commit()
    return faq


def set_status(db: Session, faq_id: int, status: FaqStatus) -> Faq:
    faq = get_faq(db, faq_id)
    faq.status = status.value
    db.commit()
    return faq
