from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader

LOGGER_NAME = "valutatrade_hub"
LOG_FORMAT = "%(levelname)s %(asctime)s %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 5


def setup_logging() -> None:
    """Configure the project logger: rotating file, level from settings."""
    settings = SettingsLoader()
    level = getattr(logging, str(settings.get("log_level", "INFO")).upper(), logging.INFO)
    # logging_config.py лежит на уровень выше core/infra, корень проекта — parents[1]
    log_path = Path(__file__).resolve().parents[1] / str(settings.get("log_file", "logs/app.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return
    logger.setLevel(level)
    logger.propagate = False
    handler = RotatingFileHandler(
        log_path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(handler)


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """Return the project logger (children inherit the configured handlers)."""
    return logging.getLogger(name)
