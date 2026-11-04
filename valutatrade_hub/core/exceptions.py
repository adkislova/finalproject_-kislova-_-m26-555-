from __future__ import annotations


class ValutaTradeError(Exception):
    """Base class for all project errors."""


class CurrencyNotFoundError(ValutaTradeError):
    """Raised when a currency code is not found in the registry."""


class RateUnavailableError(ValutaTradeError):
    """Raised when a currency rate cannot be resolved from cache or the stub."""
