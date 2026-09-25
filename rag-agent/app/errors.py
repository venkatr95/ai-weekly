"""Errors the API turns into HTTP responses. None of these fabricate an answer."""


class RAGError(Exception):
    """Base error for ingestion, retrieval, and generation failures."""


class UnsupportedDocument(RAGError):
    """The upload is not a PDF, TXT, or Markdown file."""


class InvalidDocument(RAGError):
    """The file could not be decoded or parsed."""


class EmptyDocument(RAGError):
    """The file had no extractable text to index."""


class DocumentNotFound(RAGError):
    """No document is stored under that id."""


class EmbeddingError(RAGError):
    """The embedding provider rejected or failed the request."""


class GenerationError(RAGError):
    """The language model request failed. The caller must not invent an answer."""
