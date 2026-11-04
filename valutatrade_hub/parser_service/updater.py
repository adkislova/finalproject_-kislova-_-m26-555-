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


class RatesUpdater:
    """Coordinates fetching rates from all clients and saving them via storage."""

    def __init__(
        self,
        clients: list[BaseApiClient] | None = None,
        storage: RatesStorage | None = None,
    ) -> None:
        config = ParserConfig()
        self._clients = (
            clients
            if clients is not None
            else [CoinGeckoClient(config), ExchangeRateApiClient(config)]
        )
        self._storage = storage or RatesStorage()

    def run_update(self) -> dict[str, float]:
        """Fetch rates from every client, then save snapshot and history entries."""
        logger.info("UPDATE start: %d источников", len(self._clients))
        rates: dict[str, float] = {}
        sources: dict[str, str] = {}
        updated_at = utc_now()
        succeeded = 0
        for client in self._clients:
            try:
                client_rates = client.fetch_rates()
            except ApiRequestError as exc:
                logger.warning("UPDATE источник %s недоступен: %s", client.source, exc)
                continue
            logger.info("UPDATE источник %s вернул %d пар", client.source, len(client_rates))
            client_meta = dict(client.last_meta)
            for pair, rate in client_rates.items():
                rates[pair] = rate
                sources[pair] = client.source
                self._storage.append_history_entry(
                    pair, rate, client.source, client_meta.get(pair, {}), updated_at
                )
            succeeded += 1
        if succeeded == 0:
            raise ApiRequestError("все источники курсов недоступны")
        self._storage.save_snapshot(rates, sources, updated_at)
        logger.info("UPDATE завершён: %d пар от %d источников", len(rates), succeeded)
        return rates
