from __future__ import annotations

import logging

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage, utc_now

logger = logging.getLogger("valutatrade_hub.parser")

if not logger.handlers:
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(console)

_SOURCE_CLIENTS = {"coingecko": CoinGeckoClient, "exchangerate": ExchangeRateApiClient}


class RatesUpdater:
    """Coordinates fetching rates from the selected clients and saving them."""

    def __init__(
        self,
        clients: list[BaseApiClient] | None = None,
        storage: RatesStorage | None = None,
        source_filter: str | None = None,
    ) -> None:
        config = ParserConfig()
        self._config = config
        self._storage = storage or RatesStorage()
        if clients is not None:
            self._clients = list(clients)
        elif source_filter:
            key = source_filter.strip().lower()
            if key not in _SOURCE_CLIENTS:
                raise ValueError(
                    f"Неизвестный источник '{source_filter}'. "
                    f"Доступны: {', '.join(_SOURCE_CLIENTS)}"
                )
            self._clients = [_SOURCE_CLIENTS[key](config)]
        else:
            self._clients = [factory(config) for factory in _SOURCE_CLIENTS.values()]

    def run_update(self) -> dict:
        """Fetch rates from every client, then save snapshot and history entries."""
        logger.info("Starting rates update...")
        rates: dict[str, float] = {}
        sources: dict[str, str] = {}
        ok_sources: list[str] = []
        failed_sources: list[str] = []
        updated_at = utc_now()
        for client in self._clients:
            try:
                client_rates = client.fetch_rates()
            except ApiRequestError as exc:
                logger.error("Failed to fetch from %s: %s", client.source, exc)
                failed_sources.append(client.source)
                continue
            logger.info("Fetching from %s... OK (%d rates)", client.source, len(client_rates))
            ok_sources.append(client.source)
            client_meta = dict(client.last_meta)
            for pair, rate in client_rates.items():
                rates[pair] = rate
                sources[pair] = client.source
                self._storage.append_history_entry(
                    pair, rate, client.source, client_meta.get(pair, {}), updated_at
                )
        if not ok_sources:
            raise ApiRequestError("все источники курсов недоступны")
        logger.info("Writing %d rates to %s...", len(rates), self._config.RATES_FILE_PATH)
        self._storage.save_snapshot(rates, sources, updated_at)
        logger.info("Update finished: %d rates from %d sources", len(rates), len(ok_sources))
        return {
            "rates": rates,
            "ok_sources": ok_sources,
            "failed_sources": failed_sources,
            "last_refresh": updated_at,
        }
