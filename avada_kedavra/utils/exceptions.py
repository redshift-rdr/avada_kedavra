# -*- coding: utf-8 -*-
"""Custom exceptions for avada_kedavra."""


class AvadaKedavraError(Exception):
    """Base exception for all avada_kedavra errors."""
    pass


class ConfigurationError(AvadaKedavraError):
    """Raised when there's an error in configuration files."""
    pass


class RequestParsingError(AvadaKedavraError):
    """Raised when request parsing fails."""
    pass


class PayloadLoadError(AvadaKedavraError):
    """Raised when payload loading fails."""
    pass


class FilterError(AvadaKedavraError):
    """Raised when filter application fails."""
    pass


class ModificationError(AvadaKedavraError):
    """Raised when request modification fails."""
    pass


class AuthenticationError(AvadaKedavraError):
    """Raised when authentication or re-authentication fails."""
    pass
