"""User-facing errors. Messages must stay free of secrets and document text."""

from __future__ import annotations


class EvidenceAgentError(Exception):
    """Base error for problems the CLI should print and exit on."""


class ConfigurationError(EvidenceAgentError):
    """Missing or invalid configuration."""


class IndexNotFoundError(EvidenceAgentError):
    """The persistent index has not been created yet."""


class CorruptIndexError(EvidenceAgentError):
    """The index exists but cannot be read safely."""


class EmptyCorpusError(EvidenceAgentError):
    """The supplied path contains no supported documents."""


class ProviderError(EvidenceAgentError):
    """The embedding or language-model provider failed."""


class GenerationError(EvidenceAgentError):
    """The model response could not be parsed into the answer schema."""
