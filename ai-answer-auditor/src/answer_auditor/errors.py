"""Errors raised by the auditor. Messages are safe to show to users."""

from __future__ import annotations


class AuditorError(Exception):
    """Base error for expected failures."""


class InputError(AuditorError):
    """The answer or sources were missing or unusable."""


class ParseError(AuditorError):
    """A source file could not be read."""


class ConfigurationError(AuditorError):
    """Settings or the model provider are not usable."""


class ProviderError(AuditorError):
    """The model provider failed or returned output that could not be used."""
