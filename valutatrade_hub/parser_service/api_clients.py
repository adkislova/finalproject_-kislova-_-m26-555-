from __future__ import annotations

import time
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    """Abstract API client returning standardized {PAIR: rate} dicts."""

    source = "Base"

    def __init__(self, config: ParserConfig) -> None:
        self._config = config
        self.last_meta: dict[str, dict] = {}
        self._request_ms = 0
        self._status_code = 0
        self._etag = ""

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Fetch current rates as {FROM_TO: rate}."""

    def _request(self, url: str, params: dict | None = None) -> dict:
        """Send a GET request and return the parsed JSON body."""
        try:
            started = time.perf_counter()
            response = requests.get(url, params=params, timeout=self._config.REQUEST_TIMEOUT)
            self._request_ms = int((time.perf_counter() - started) * 1000)
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(f"сеть недоступна: {exc}") from None
        self._status_code = response.status_code
        self._etag = response.headers.get("ETag", "")
        if response.status_code == 401:
            raise ApiRequestError("неверный API-ключ (401)")
        if response.status_code == 429:
            raise ApiRequestError("превышен лимит запросов к источнику (429)")
        if response.status_code != 200:
            raise ApiRequestError(f"источник вернул статус {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise ApiRequestError(f"некорректный JSON от источника: {exc}") from None

    def _meta(self, raw_id: str) -> dict:
        """Build the history meta block for one pair."""
        return {
            "raw_id": raw_id,
            "request_ms": self._request_ms,
            "status_code": self._status_code,
            "etag": self._etag,
        }


class CoinGeckoClient(BaseApiClient):
    """Client of the public CoinGecko simple/price endpoint (crypto)."""

    source = "CoinGecko"

    def fetch_rates(self) -> dict[str, float]:
        """Fetch crypto prices against the base currency via coin IDs."""
        self.last_meta = {}
        ids = ",".join(self._config.CRYPTO_ID_MAP[code] for code in self._config.CRYPTO_CURRENCIES)
        params = {"ids": ids, "vs_currencies": self._config.BASE_CURRENCY.lower()}
        data = self._request(self._config.COINGECKO_URL, params=params)
        quote = self._config.BASE_CURRENCY.lower()
        rates: dict[str, float] = {}
        for code in self._config.CRYPTO_CURRENCIES:
            coin_id = self._config.CRYPTO_ID_MAP[code]
            price = data.get(coin_id, {}).get(quote)
            if isinstance(price, bool) or not isinstance(price, (int, float)):
                continue
            pair = f"{code}_{self._config.BASE_CURRENCY}"
            rates[pair] = float(price)
            self.last_meta[pair] = self._meta(coin_id)
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Client of the ExchangeRate-API latest endpoint (fiat)."""

    source = "ExchangeRate-API"

    def fetch_rates(self) -> dict[str, float]:
        """Fetch fiat rates against the base currency using the API key."""
        self.last_meta = {}
        if not self._config.EXCHANGERATE_API_KEY:
            raise ApiRequestError("не задан ключ EXCHANGERATE_API_KEY в .env")
        url = (
            f"{self._config.EXCHANGERATE_API_URL}/"
            f"{self._config.EXCHANGERATE_API_KEY}/latest/{self._config.BASE_CURRENCY}"
        )
        data = self._request(url)
        if data.get("result") != "success":
            raise ApiRequestError(f"ExchangeRate-API вернул result={data.get('result')}")
        section = data.get("conversion_rates") or data.get("rates", {})
        rates: dict[str, float] = {}
        for code in self._config.FIAT_CURRENCIES:
            value = section.get(code)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                continue
            pair = f"{code}_{self._config.BASE_CURRENCY}"
            rates[pair] = 1.0 / float(value)
            self.last_meta[pair] = self._meta(self._config.BASE_CURRENCY)
        return rates
