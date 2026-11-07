from __future__ import annotations

import logging
import time

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.updater import RatesUpdater

logger = logging.getLogger("valutatrade_hub.parser")


def run_scheduler(interval_seconds: int, source_filter: str | None = None) -> None:
    """Run rate updates in a loop with the given interval until interrupted."""
    logger.info("SCHEDULER start: интервал %d сек", interval_seconds)
    while True:
        try:
            RatesUpdater(source_filter=source_filter).run_update()
        except ApiRequestError as exc:
            logger.error("Scheduled update failed: %s", exc)
        time.sleep(interval_seconds)
