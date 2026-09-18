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


class NotFoundError(FaqBuilderError):
    """A requested cluster / FAQ does not exist."""


class LLMError(FaqBuilderError):
    """The LLM provider call failed (network, quota, auth, ...)."""


class InvalidLLMOutputError(FaqBuilderError):
    """The LLM answered, but not with valid, grounded FAQ JSON."""
