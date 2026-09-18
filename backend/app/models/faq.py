from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.cluster import Cluster


class FaqStatus(str, enum.Enum):
    GENERATED = "GENERATED"  # fresh from the LLM, nobody has looked at it
    REVIEW = "REVIEW"  # edited / being reviewed
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Faq(Base):
    __tablename__ = "faqs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"), unique=True)
    theme: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    resolution_steps: Mapped[list] = mapped_column(JSON, default=list)
    source_ticket_ids: Mapped[list] = mapped_column(JSON, default=list)
    insufficient_information: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default=FaqStatus.GENERATED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    cluster: Mapped[Cluster] = relationship(back_populates="faq")
