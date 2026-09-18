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
