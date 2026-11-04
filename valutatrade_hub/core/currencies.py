from __future__ import annotations

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Abstract base currency with a human-readable name and a ticker code."""

    def __init__(self, name: str, code: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым.")
        if not isinstance(code, str):
            raise TypeError("Код валюты должен быть строкой.")
        if not 2 <= len(code) <= 5:
            raise ValueError("Код валюты должен содержать от 2 до 5 символов.")
        if code != code.upper():
            raise ValueError("Код валюты должен быть в верхнем регистре.")
        if " " in code:
            raise ValueError("Код валюты не должен содержать пробелов.")
        self.name = name.strip()
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Return a display string for UI and logs."""


class FiatCurrency(Currency):
    """Fiat currency issued by a country or a union."""

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name, code)
        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("Страна эмиссии не может быть пустой.")
        self.issuing_country = issuing_country.strip()

    def get_display_info(self) -> str:
        """Return the display string with the issuing country."""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Cryptocurrency with a consensus algorithm and a known market cap."""

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float) -> None:
        super().__init__(name, code)
        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("Алгоритм не может быть пустым.")
        if (
            isinstance(market_cap, bool)
            or not isinstance(market_cap, (int, float))
            or market_cap <= 0
        ):
            raise ValueError("Рыночная капитализация должна быть положительным числом.")
        self.algorithm = algorithm.strip()
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        """Return the display string with the algorithm and a short market cap."""
        mcap = f"{self.market_cap:.2e}".replace("e+", "e")
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {mcap})"


_CURRENCIES: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "GBP": FiatCurrency("British Pound", "GBP", "United Kingdom"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.3e11),
}


def get_currency(code: str) -> Currency:
    """Return the currency for the code (case-insensitive) or raise CurrencyNotFoundError."""
    if not isinstance(code, str) or not code.strip():
        raise CurrencyNotFoundError(f"Валюта '{code}' не найдена")
    key = code.strip().upper()
    try:
        return _CURRENCIES[key]
    except KeyError:
        raise CurrencyNotFoundError(f"Валюта '{code}' не найдена") from None
