"""Typed domain errors. Services raise these; main.py turns each into an HTTP status.

Adding a new error: subclass FaqBuilderError AND add it to STATUS_BY_ERROR in main.py,
otherwise it reaches the client as a 500.
"""
from __future__ import annotations

from typing import Optional


class FaqBuilderError(Exception):
    """Base class for domain errors."""


class MalformedCsvError(FaqBuilderError):
    """The uploaded file is not a parseable CSV or lacks required columns."""


class EmptyDatasetError(FaqBuilderError):
    """No valid tickets were found."""


class InsufficientTicketsError(FaqBuilderError):
    """Too few tickets to cluster with the requested K values."""


class EmbeddingError(FaqBuilderError):
    """Embedding generation failed."""


class DuplicateUploadError(FaqBuilderError):
    """The same file was uploaded before."""


class FaqAlreadyExistsError(FaqBuilderError):
    """FAQ generation was requested for a cluster that already has an FAQ."""


class FaqRegenerationError(FaqBuilderError):
    """Regenerating an FAQ failed; the existing FAQ was kept. The message is user-facing."""


class NotFoundError(FaqBuilderError):
    """A requested cluster / FAQ does not exist."""


class LLMError(FaqBuilderError):
    """The LLM provider call failed (network, quota, auth, ...).

    `str(exc)` is a sanitized detail for logs only. `transient` marks failures that a
    later retry can plausibly fix (overload, rate limit, timeout).
    """

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        transient: bool = False,
        error_type: str = "UNKNOWN",
    ) -> None:
        super().__init__(message)
        self.status = status
        self.transient = transient
        self.error_type = error_type


class InvalidLLMOutputError(FaqBuilderError):
    """The LLM answered, but not with valid, grounded FAQ JSON."""
