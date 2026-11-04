from __future__ import annotations


class ValutaTradeError(Exception):
    """Base class for all project errors."""


class CurrencyNotFoundError(ValutaTradeError):
    """Raised when a currency code is unknown or not supported."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class InsufficientFundsError(ValutaTradeError):
    """Raised when a withdrawal or sale exceeds the available balance."""

    def __init__(self, available: float, required: float, code: str) -> None:
        self.available = available
        self.required = required
        self.code = code
        super().__init__(
            f"Недостаточно средств: доступно {available:.4f} {code}, "
            f"требуется {required:.4f} {code}"
        )


class ApiRequestError(ValutaTradeError):
    """Raised when an external API request fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")


class RateUnavailableError(ValutaTradeError):
    """Raised when a rate cannot be resolved from cache or the parser service."""
