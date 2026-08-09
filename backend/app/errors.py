from __future__ import annotations


class DomainError(Exception):
    """Base class for errors raised by the domain layers."""


class ValidationError(DomainError):
    """Malformed input — maps to HTTP 400."""


class NotFoundError(DomainError):
    """Unknown symbol, position, or resource — maps to HTTP 404."""


class BusinessRuleError(DomainError):
    """A domain rule was violated — maps to HTTP 409."""


class UpstreamUnavailableError(DomainError):
    """A required upstream (price, live data) is unavailable — maps to HTTP 503."""
