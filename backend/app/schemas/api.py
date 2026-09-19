"""Request/response shapes of the HTTP API.

Keep in sync with frontend/src/lib/types.ts: a field renamed here and not there shows up as
`undefined` in the UI, not as an error.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.clustering import KResult
from app.schemas.ticket import RowError, Ticket


class FaqOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cluster_id: int
    theme: str
    description: str
    question: str
    answer: str
    resolution_steps: List[str]
    source_ticket_ids: List[str]
    insufficient_information: bool
    status: str
    updated_at: Optional[datetime] = None


class FaqUpdate(BaseModel):
    """Partial edit. Any edit moves the FAQ back to REVIEW so it must be re-approved."""

    theme: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = Field(default=None, min_length=1)
    question: Optional[str] = Field(default=None, min_length=1)
    answer: Optional[str] = Field(default=None, min_length=1)
    resolution_steps: Optional[List[str]] = None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chosen_k: int
    silhouette: float
    k_results: List[KResult]
    total_tickets: int
    created_at: Optional[datetime] = None


class ClusterOut(BaseModel):
    id: int
    cluster_index: int
    name: str
    description: str
    ticket_count: int
    representative_tickets: List[Ticket]
    faq: Optional[FaqOut] = None
    faq_error: Optional[str] = None
    # the FAQ's status; GENERATION_FAILED / QUOTA_EXHAUSTED when generation failed; None if never tried
    faq_status: Optional[str] = None


class FaqBatchOut(BaseModel):
    """Result of generating / retrying FAQs for every cluster that has none."""

    attempted: int
    faqs_generated: int
    faqs_failed: int
    quota_exhausted: bool = False  # stopped early: the API reported project quota exhaustion
    clusters: List[ClusterOut]


class ClusterListOut(BaseModel):
    run: Optional[RunOut] = None
    clusters: List[ClusterOut]


class ClusterDetailOut(ClusterOut):
    run: RunOut


class UploadOut(BaseModel):
    tickets_added: int
    tickets_skipped_existing: int
    rejected_rows: List[RowError]


class StepOut(BaseModel):
    name: str
    status: str  # "done" | "failed"
    detail: Optional[str] = None


class GenerateOut(BaseModel):
    """Clustering only. FAQ generation is a separate, explicit step."""

    run: RunOut
    clusters: int
    steps: List[StepOut]


class StatsOut(BaseModel):
    total_tickets: int
    resolved_tickets: int
    clusters: int
    faqs: int
    faqs_by_status: dict
    cluster_distribution: List[dict]
