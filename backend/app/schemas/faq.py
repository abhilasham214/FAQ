from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class FaqDraft(BaseModel):
    """Structured output the LLM must produce for one cluster."""

    theme: str = Field(min_length=1)
    description: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    resolution_steps: List[str] = Field(default_factory=list)
    source_ticket_ids: List[str] = Field(min_length=1)
    # True when the tickets did not contain enough information for a reliable answer.
    insufficient_information: bool = False

    @field_validator("theme", "description", "question", "answer")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ClusterFaqResult(BaseModel):
    """Outcome of FAQ generation for one cluster; a failure never aborts the others."""

    cluster_id: int
    faq: Optional[FaqDraft] = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # QUOTA_EXHAUSTED | GENERATION_FAILED
    from_cache: bool = False
