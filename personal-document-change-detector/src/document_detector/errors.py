"""Errors raised by the detector. Messages are safe to show to users."""

from __future__ import annotations


class DetectorError(Exception):
    """Base error for expected failures."""


class InputError(DetectorError):
    """A document path or payload was missing or unusable."""


class ParseError(DetectorError):
    """A document file could not be read or extracted."""


class ConfigurationError(DetectorError):
    """Settings or the model provider are not usable."""


class ProviderError(DetectorError):
    """The model provider failed or returned unusable output."""
